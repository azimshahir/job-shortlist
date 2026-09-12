"""
One-off: copy the old scraper/job_history.db (SQLite) into Supabase.

    python migrate_sqlite.py                 # migrates job_history.db
    python migrate_sqlite.py --dry-run       # shows what would be written
    python migrate_sqlite.py path/to/other.db

Needs SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_USER_ID in env.

Mapping (same as SupabaseHistoryStore):
    jobs row            -> public.jobs (first/last seen, seen_count,
                           shortlisted_before / shortlist_count /
                           last_shortlisted_at)
    applied=1           -> job_actions.status='applied' + applied_date
    ignored=1           -> job_actions.status='ignored' + notes
    resume_generated=1  -> job_actions.resume_status='ready' (no file; the
                           user can request a fresh one from the dashboard)

Safe to re-run: everything is an upsert on job_id, and it never LOWERS a
seen_count that is already higher in Supabase.
"""

import sqlite3
import sys

import config
import sink


def _iso(value):
    """SQLite stored ISO strings already; pass through, blank -> None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def rows_from_sqlite(path: str) -> list:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM jobs")]
    finally:
        conn.close()


def to_job(row: dict, uid: str) -> dict:
    return {
        "job_id": row["job_id"],
        "user_id": uid,
        "content_key": row.get("content_key") or "",
        "url_key": row.get("url_key") or None,
        "source": row.get("source"),
        "title": row.get("title"),
        "company": row.get("company"),
        "location": row.get("location"),
        "job_url": row.get("job_url"),
        "first_seen": _iso(row.get("first_seen")) or sink._now_iso(),
        "last_seen": _iso(row.get("last_seen")) or sink._now_iso(),
        "seen_count": int(row.get("seen_count") or 1),
        "shortlisted_before": bool(row.get("shortlisted_before")),
        "shortlist_count": int(row.get("shortlist_count") or 0),
        "last_shortlisted_at": _iso(row.get("last_shortlisted_at")),
    }


def to_action(row: dict, uid: str):
    action = {"job_id": row["job_id"], "user_id": uid}
    if row.get("applied"):
        action["status"] = "applied"
        applied = _iso(row.get("applied_date"))
        action["applied_date"] = applied[:10] if applied else None
    elif row.get("ignored"):
        action["status"] = "ignored"
        action["notes"] = row.get("ignore_reason") or None
    if row.get("resume_generated"):
        action["resume_status"] = "ready"
    return action if len(action) > 2 else None


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dry = "--dry-run" in argv
    paths = [a for a in argv if not a.startswith("--")]
    path = paths[0] if paths else config.HISTORY_DB_PATH

    rows = rows_from_sqlite(path)
    print(f"{len(rows)} history rows in {path}")
    if not rows:
        return 0

    sink.require_env()
    uid = sink.user_id()
    jobs = [to_job(r, uid) for r in rows]
    actions = [a for a in (to_action(r, uid) for r in rows) if a]
    print(f"-> {len(jobs)} jobs, {len(actions)} job_actions "
          f"({sum(1 for a in actions if a.get('status') == 'applied')} applied, "
          f"{sum(1 for a in actions if a.get('status') == 'ignored')} ignored)")

    if dry:
        for j in jobs[:5]:
            print("  ", j["job_id"], "|", j["title"], "|", j["company"],
                  "| seen", j["seen_count"])
        print("dry run: nothing written")
        return 0

    client = sink.get_client()
    size = config.SUPABASE_BATCH_SIZE
    for i in range(0, len(jobs), size):
        chunk = jobs[i:i + size]
        ids = [j["job_id"] for j in chunk]
        existing = {r["job_id"]: r for r in (
            client.table("jobs").select("job_id, seen_count, shortlist_count")
            .eq("user_id", uid).in_("job_id", ids).execute().data or [])}
        for j in chunk:
            prev = existing.get(j["job_id"])
            if prev:  # never go backwards
                j["seen_count"] = max(j["seen_count"], int(prev.get("seen_count") or 0))
                j["shortlist_count"] = max(j["shortlist_count"],
                                           int(prev.get("shortlist_count") or 0))
        client.table("jobs").upsert(chunk, on_conflict="job_id").execute()
        print(f"  jobs {i + len(chunk)}/{len(jobs)}")

    for i in range(0, len(actions), size):
        chunk = actions[i:i + size]
        client.table("job_actions").upsert(chunk, on_conflict="job_id").execute()
        print(f"  job_actions {i + len(chunk)}/{len(actions)}")

    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
