"""
Cross-run job history tests.

    python test_history.py

Uses a temporary SQLite file, so nothing touches the real job_history.db.
The persistence test spawns a genuinely separate Python process.
"""

import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import config
import history
import ranking

_results = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    _results.append((status, name, detail))
    print(f"{status:<4} {name}" + (f"\n       {detail}" if detail else ""))
    return condition


JOB = {
    "site": "linkedin", "title": "Reconciliation Analyst",
    "company": "Krypton Fund Services Sdn Bhd",
    "location": "Kuala Lumpur, Malaysia",
    "job_url": "https://linkedin.com/jobs/view/12345?refId=abc&trk=xyz",
    "job_url_direct": "",
}

# Same role, different URL, company written differently: a repost.
REPOST = {
    "site": "linkedin", "title": "Reconciliation Analyst (6 months contract)",
    "company": "Krypton Fund Services",
    "location": "Kuala Lumpur, Federal Territory of Kuala Lumpur, Malaysia",
    "job_url": "https://linkedin.com/jobs/view/99999",
    "job_url_direct": "",
}

OTHER = {
    "site": "indeed", "title": "Treasury Operations Executive",
    "company": "Maybank", "location": "Selangor, Malaysia",
    "job_url": "https://indeed.com/viewjob?jk=aaa",
}


def test_normalisation():
    check("Company suffixes are normalised away",
          history.normalise_company("Krypton Fund Services Sdn Bhd")
          == history.normalise_company("Krypton Fund Services"),
          f"-> '{history.normalise_company('Krypton Fund Services Sdn Bhd')}'")

    check("Title decoration is normalised away",
          history.normalise_title("Reconciliation Analyst (6 months contract)")
          == history.normalise_title("Reconciliation Analyst"),
          f"-> '{history.normalise_title('Reconciliation Analyst (6 months contract)')}'")

    check("URL tracking params are stripped",
          history.normalise_url("https://x.com/a/?refId=1&trk=2")
          == "https://x.com/a",
          history.normalise_url("https://x.com/a/?refId=1&trk=2"))

    check("Repost shares a content fingerprint with the original",
          history.content_fingerprint(JOB) == history.content_fingerprint(REPOST),
          history.content_fingerprint(JOB))

    check("A different job does NOT share the fingerprint",
          history.content_fingerprint(JOB) != history.content_fingerprint(OTHER))


def test_seen_tomorrow(store):
    first = store.upsert_seen(history.record_for(JOB))
    verdict = history.evaluate(JOB, first)
    check("First sighting is 'new'",
          verdict["history_status"] == "new" and history.is_actionable("new"),
          verdict["history_reason"])

    again = store.upsert_seen(history.record_for(JOB))
    verdict = history.evaluate(JOB, again)
    check("1. Same job tomorrow is recognised as previously seen",
          verdict["history_status"] == "seen_not_shortlisted"
          and again["seen_count"] == 2,
          f"seen_count={again['seen_count']}, status={verdict['history_status']}")


def test_repost(store):
    store.mark_shortlisted(history.job_identity(JOB)["job_id"])
    record = store.get(history.job_identity(REPOST)["job_id"],
                       history.content_fingerprint(REPOST))
    check("2. Same company/title under a new URL is matched as a repost",
          record is not None,
          f"repost resolved to existing job_id "
          f"{record['job_id'][:40] if record else 'NOT FOUND'}")

    verdict = history.evaluate(REPOST, record)
    check("2b. A repost inside the cooldown is suppressed",
          verdict["history_status"] in ("cooldown", "repost_cooldown")
          and not history.is_actionable(verdict["history_status"]),
          f"{verdict['history_status']}: {verdict['history_reason']}")


def test_applied(store):
    job_id = history.job_identity(OTHER)["job_id"]
    store.upsert_seen(history.record_for(OTHER))
    store.mark_applied(job_id)

    record = store.get(job_id, history.content_fingerprint(OTHER))
    verdict = history.evaluate(OTHER, record)
    check("3. An applied job is excluded from the actionable shortlist",
          verdict["history_status"] == "applied"
          and not history.is_actionable("applied"),
          verdict["history_reason"])

    check("3b. The applied job is retained for auditing, not deleted",
          record is not None and record["applied"] == 1
          and record["applied_date"],
          f"applied_date={record['applied_date'][:19]}")

    rows = [{"title": "Treasury Operations Executive", "final_score": 95.0,
             "career_family_status": "CORE", "history_status": "applied",
             "history_reason": verdict["history_reason"]}]
    selected = ranking.select_final(rows)
    check("3c. Even a 95-score applied job is not selected",
          selected == [] and rows[0]["selection_status"] == "history_applied",
          rows[0]["selection_reason"][:70])


def test_cooldown_expiry(store):
    job_id = history.job_identity(JOB)["job_id"]
    record = store.get(job_id, history.content_fingerprint(JOB))

    # Inside the cooldown.
    verdict = history.evaluate(JOB, record)
    inside = not history.is_actionable(verdict["history_status"])

    # Now look at the same record from far enough in the future.
    future = datetime.now(timezone.utc) + timedelta(
        days=config.SHORTLIST_COOLDOWN_DAYS + 1)
    verdict_future = history.evaluate(JOB, record, now=future)
    check("4. A job outside the cooldown becomes eligible again",
          inside and verdict_future["history_status"] == "cooldown_expired"
          and history.is_actionable(verdict_future["history_status"]),
          f"inside: suppressed; "
          f"+{config.SHORTLIST_COOLDOWN_DAYS + 1}d: "
          f"{verdict_future['history_reason']}")


def test_persistence_across_processes(db_path):
    """The real test: a brand-new interpreter must see the same history."""
    script = (
        "import sys; sys.path.insert(0, r'%s')\n"
        "import history\n"
        "store = history.SqliteHistoryStore(r'%s')\n"
        "rows = store.all_records()\n"
        "applied = [r for r in rows if r['applied']]\n"
        "print(len(rows), len(applied))\n"
    ) % (os.path.dirname(os.path.abspath(__file__)), db_path)

    result = subprocess.run([sys.executable, "-c", script],
                            capture_output=True, text=True, timeout=120)
    ok = result.returncode == 0 and result.stdout.strip()
    counts = result.stdout.strip().split() if ok else []
    check("5. History survives a new Python process",
          ok and len(counts) == 2 and int(counts[0]) >= 2 and int(counts[1]) == 1,
          f"fresh process saw {counts[0] if counts else '?'} jobs, "
          f"{counts[1] if len(counts) > 1 else '?'} applied"
          + (f" | stderr: {result.stderr[:120]}" if result.returncode else ""))


def test_ignored(store):
    store.upsert_seen(history.record_for(JOB))
    job_id = history.job_identity(JOB)["job_id"]
    store.mark_ignored(job_id, "wrong shift pattern")
    record = store.get(job_id, history.content_fingerprint(JOB))
    verdict = history.evaluate(JOB, record)
    check("Ignored jobs are suppressed with their reason preserved",
          verdict["history_status"] == "ignored"
          and "wrong shift pattern" in verdict["history_reason"],
          verdict["history_reason"])


def test_backend_swap():
    mem = history.get_store("memory")
    check("Storage backend is swappable behind one interface",
          isinstance(mem, history.HistoryStore)
          and not isinstance(mem, history.SqliteHistoryStore),
          f"{type(mem).__name__} implements the same interface")

    rec = mem.upsert_seen(history.record_for(JOB))
    mem.mark_applied(rec["job_id"])
    verdict = history.evaluate(JOB, mem.get(rec["job_id"], rec["content_key"]))
    check("Memory backend honours the same policy",
          verdict["history_status"] == "applied")


def main():
    print("=" * 70)
    print("CROSS-RUN HISTORY TESTS")
    print("=" * 70)

    test_normalisation()
    print()

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test_history.db")
        store = history.SqliteHistoryStore(db_path)
        try:
            test_seen_tomorrow(store)
            test_repost(store)
            test_applied(store)
            test_cooldown_expiry(store)
        finally:
            store.close()

        test_persistence_across_processes(db_path)

        store = history.SqliteHistoryStore(db_path)
        try:
            test_ignored(store)
        finally:
            store.close()

    print()
    test_backend_swap()

    print("\n" + "=" * 70)
    failed = [r for r in _results if r[0] == "FAIL"]
    print(f"{len(_results) - len(failed)} passed, {len(failed)} failed")
    for _, name, detail in failed:
        print(f"  FAILED: {name} -- {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
