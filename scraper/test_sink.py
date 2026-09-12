"""
Supabase sink / history / resume-queue tests. Offline: a fake client that
mimics the small slice of supabase-py the code uses.

    python test_sink.py
"""

import os
import tempfile
import time
import uuid
from datetime import datetime, timezone

import config
import history
import render_resume
import resume_queue
import sink

_results = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    _results.append((status, name, detail))
    print(f"{status:<4} {name}" + (f"\n       {detail}" if detail else ""))
    return condition


# --------------------------------------------------------------------------
# Fake supabase-py client (only what sink / history / resume_queue call)
# --------------------------------------------------------------------------
PRIMARY_KEYS = {
    "runs": ("id",),
    "jobs": ("job_id",),
    "job_scores": ("run_id", "job_id"),
    "job_actions": ("job_id",),
    "validation_labels": ("job_id",),
}
CHECKS = {
    ("job_actions", "resume_status"): resume_queue.STATUSES,
    ("job_actions", "status"): ("new", "shortlisted", "applied", "interview",
                                "offer", "rejected", "ignored"),
    ("runs", "status"): ("running", "ok", "failed"),
    ("runs", "trigger"): ("cron", "manual"),
}
DEFAULTS = {
    "job_actions": {"status": "new", "resume_status": "none",
                    "resume_url": None, "notes": None, "applied_date": None},
    "runs": {"status": "running"},
}


class _Resp:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table):
        self.client, self.table = client, table
        self.rows = client.tables.setdefault(table, [])
        self.filters, self.op, self.payload = [], "select", None
        self.on_conflict, self._order, self._range, self._limit = None, None, None, None

    # builders
    def select(self, cols="*"):
        self.op = "select"
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def upsert(self, payload, on_conflict=None):
        self.op, self.payload, self.on_conflict = "upsert", payload, on_conflict
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def eq(self, key, value):
        self.filters.append(("eq", key, value))
        return self

    def in_(self, key, values):
        self.filters.append(("in", key, list(values)))
        return self

    def order(self, key, desc=False):
        self._order = (key, desc)
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def limit(self, n):
        self._limit = n
        return self

    # helpers
    def _match(self, row):
        for kind, key, value in self.filters:
            if kind == "eq" and row.get(key) != value:
                return False
            if kind == "in" and row.get(key) not in value:
                return False
        return True

    def _validate(self, row):
        for (table, col), allowed in CHECKS.items():
            if table == self.table and col in row and row[col] not in allowed:
                raise ValueError(f"check constraint: {table}.{col}={row[col]!r}")

    def _write_row(self, row, keys):
        row = dict(row)
        self._validate(row)
        for pk in keys:
            if pk == "id" and not row.get("id"):
                row["id"] = str(uuid.uuid4())
        for i, existing in enumerate(self.rows):
            if all(existing.get(k) == row.get(k) for k in keys):
                merged = {**existing, **row}
                self.rows[i] = merged
                return merged
        full = {**DEFAULTS.get(self.table, {}), **row}
        self.rows.append(full)
        return full

    def execute(self):
        self.client.calls.append((self.table, self.op, self.payload,
                                  self.on_conflict))
        if self.op == "select":
            data = [dict(r) for r in self.rows if self._match(r)]
            if self._order:
                key, desc = self._order
                data.sort(key=lambda r: str(r.get(key) or ""), reverse=desc)
            if self._range:
                data = data[self._range[0]:self._range[1] + 1]
            if self._limit is not None:
                data = data[:self._limit]
            return _Resp(data)
        if self.op in ("insert", "upsert"):
            keys = (tuple(self.on_conflict.split(",")) if self.on_conflict
                    else PRIMARY_KEYS[self.table])
            payload = self.payload if isinstance(self.payload, list) else [self.payload]
            if self.op == "upsert" and len(payload) > config.SUPABASE_BATCH_SIZE:
                raise ValueError(f"batch too large: {len(payload)}")
            return _Resp([self._write_row(r, keys) for r in payload])
        if self.op == "update":
            self._validate(self.payload)
            out = []
            for row in self.rows:
                if self._match(row):
                    row.update(self.payload)
                    out.append(dict(row))
            return _Resp(out)
        raise NotImplementedError(self.op)


class FakeBucket:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def upload(self, path, data, opts=None):
        self.store.setdefault(self.name, {})[path] = (bytes(data), opts or {})
        return {"path": path}


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def from_(self, bucket):
        return FakeBucket(self.objects, bucket)


class FakeClient:
    def __init__(self):
        self.tables, self.calls = {}, []
        self.storage = FakeStorage()

    def table(self, name):
        return FakeQuery(self, name)

    def rows(self, table):
        return self.tables.get(table, [])


USER = "11111111-2222-3333-4444-555555555555"


def configure(fake):
    config.SUPABASE_URL = "https://fake.supabase.co"
    config.SUPABASE_SERVICE_ROLE_KEY = "service-role"
    config.SUPABASE_USER_ID = USER
    sink.set_client(fake)
    sink.select("supabase")


def new_run(trigger="cron"):
    """Simulate a fresh pipeline process: clock moves on, start_run marks it."""
    time.sleep(0.02)  # Windows clock ticks are coarse; make 'later' real
    return sink.start_run(trigger)


def unconfigure():
    config.SUPABASE_URL = ""
    config.SUPABASE_SERVICE_ROLE_KEY = ""
    config.SUPABASE_USER_ID = ""
    sink.set_client(None)
    sink.select("csv")


JOB = {
    "site": "linkedin", "title": "Reconciliation Analyst",
    "company": "Krypton Fund Services Sdn Bhd",
    "location": "Kuala Lumpur, Malaysia",
    "job_url": "https://linkedin.com/jobs/view/12345?refId=abc",
    "job_url_direct": float("nan"), "description": "Daily recs.",
    "date_posted": "2026-09-11", "id": "12345",
}
REPOST = {
    "site": "linkedin", "title": "Reconciliation Analyst (6 months contract)",
    "company": "Krypton Fund Services",
    "location": "Kuala Lumpur, Federal Territory of Kuala Lumpur, Malaysia",
    "job_url": "https://linkedin.com/jobs/view/99999", "job_url_direct": "",
    "id": "99999",
}


# --------------------------------------------------------------------------
def test_noop_and_env():
    unconfigure()
    check("Sink is a no-op when csv is selected",
          sink.start_run("cron") is None and sink.write_jobs([JOB]) == 0
          and sink.write_scores("x", [JOB]) == 0
          and sink.finish_run("x", {}, "ok") is None)

    sink.select("supabase")
    try:
        sink.start_run("cron")
        loud = False
    except sink.SinkNotConfigured as exc:
        loud = all(n in str(exc) for n in
                   ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_USER_ID"))
    check("Sink fails loudly when selected but env is missing", loud)
    unconfigure()


def test_runs_and_jobs():
    fake = FakeClient()
    configure(fake)

    run_id = sink.start_run("cron")
    row = fake.rows("runs")[0]
    check("start_run inserts a running row stamped with user_id",
          bool(run_id) and row["status"] == "running"
          and row["trigger"] == "cron" and row["user_id"] == USER)

    many = [{**JOB, "id": str(i), "title": f"Job {i}"} for i in range(450)]
    n = sink.write_jobs(many)
    batches = [c for c in fake.calls if c[0] == "jobs" and c[1] == "upsert"]
    check("write_jobs upserts every deduped job in chunks of <= 200",
          n == 450 and len(batches) == 3
          and all(len(b[2]) <= 200 for b in batches)
          and len(fake.rows("jobs")) == 450,
          f"{n} rows, {len(batches)} batches of {[len(b[2]) for b in batches]}")

    job = next(r for r in fake.rows("jobs") if r["job_id"] == "ext:linkedin:0")
    check("write_jobs cleans NaN and derives identity keys",
          job["job_url_direct"] is None and job["source"] == "linkedin"
          and job["content_key"].startswith("content:")
          and job["date_posted"] == "2026-09-11" and job["seen_count"] == 1
          and job["user_id"] == USER)

    first_seen = job["first_seen"]
    sink.write_jobs(many[:1])
    job = next(r for r in fake.rows("jobs") if r["job_id"] == "ext:linkedin:0")
    check("Re-seeing a job bumps seen_count and keeps first_seen",
          job["seen_count"] == 2 and job["first_seen"] == first_seen
          and job["last_seen"] >= first_seen)

    scored = [
        {**many[0], "job_id": "ext:linkedin:0", "filter_status": "passed",
         "reject_reason": "", "keyword_score": 7, "semantic_raw": 0.81,
         "semantic_score": 61.2, "final_score": 66.0, "final_rank": 1,
         "matched_keywords": ["reconciliation", "fund"],
         "career_family": "reconciliation", "career_family_status": "CORE",
         "selection_status": "selected", "selection_reason": "top",
         "history_status": "new", "history_reason": "not seen before"},
        {**many[1], "filter_status": "hard_rejected",
         "reject_reason": "hard reject: mandarin", "keyword_score": 0,
         "matched_keywords": float("nan"), "semantic_score": float("nan")},
    ]
    n = sink.write_scores(run_id, scored)
    rows = fake.rows("job_scores")
    sel = next(r for r in rows if r["job_id"] == "ext:linkedin:0")
    rej = next(r for r in rows if r["job_id"] == "ext:linkedin:1")
    check("write_scores keeps every verdict, incl. hard rejects with reasons",
          n == 2 and sel["selection_status"] == "selected"
          and sel["matched_keywords"] == ["reconciliation", "fund"]
          and sel["run_id"] == run_id and sel["user_id"] == USER
          and rej["filter_status"] == "hard_rejected"
          and rej["reject_reason"].startswith("hard reject")
          and rej["matched_keywords"] == [] and rej["semantic_score"] is None
          and rej["reject_reason"] is not None,
          f"upsert on_conflict={[c[3] for c in fake.calls if c[0]=='job_scores'][0]}")

    stats = {"raw": 900, "deduped": 450, "hard_rejected": 300,
             "keyword_passed": 40, "ranked": 40, "career_rejected": 10,
             "history_excluded": 3, "selected": 2}
    sink.finish_run(run_id, stats, "ok")
    row = fake.rows("runs")[0]
    check("finish_run maps stats onto the runs row",
          row["status"] == "ok" and row["finished_at"]
          and row["raw_count"] == 900 and row["deduped_count"] == 450
          and row["hard_rejected"] == 300 and row["selected"] == 2
          and row["error"] is None)

    run2 = sink.start_run("manual")
    sink.finish_run(run2, {}, "failed", error="RuntimeError: boom")
    row = next(r for r in fake.rows("runs") if r["id"] == run2)
    check("finish_run records failures with the error text",
          row["status"] == "failed" and row["error"] == "RuntimeError: boom"
          and row["raw_count"] == 0)
    unconfigure()


def test_history_store():
    fake = FakeClient()
    configure(fake)

    # Run 1: sink writes the job, then history sees it -> new, counted once.
    new_run()
    sink.write_jobs([JOB])
    store = history.SupabaseHistoryStore(fake, USER)
    rec = store.upsert_seen(history.record_for(JOB))
    verdict = history.evaluate(JOB, rec)
    check("Supabase history: first sighting is 'new' and not double-counted",
          verdict["history_status"] == "new" and rec["seen_count"] == 1
          and fake.rows("jobs")[0]["seen_count"] == 1,
          f"seen_count={rec['seen_count']}")

    check("get_store('supabase') returns the Supabase backend",
          isinstance(history.get_store("supabase"), history.SupabaseHistoryStore))

    # Run 2 (a new process): seen again, not shortlisted.
    new_run()
    sink.write_jobs([JOB])
    store = history.SupabaseHistoryStore(fake, USER)
    rec = store.upsert_seen(history.record_for(JOB))
    verdict = history.evaluate(JOB, rec)
    check("Second run: seen_not_shortlisted with seen_count 2",
          verdict["history_status"] == "seen_not_shortlisted"
          and rec["seen_count"] == 2, verdict["history_reason"])

    # History alone (csv sink, HISTORY_BACKEND=supabase) bumps the counter itself.
    sink.select("csv")
    time.sleep(0.02)
    store = history.SupabaseHistoryStore(fake, USER)
    rec = store.upsert_seen(history.record_for(JOB))
    check("Without the sink, upsert_seen bumps seen_count itself",
          rec["seen_count"] == 3 and fake.rows("jobs")[0]["seen_count"] == 3,
          f"seen_count={rec['seen_count']}")
    sink.select("supabase")

    store.mark_shortlisted(rec["job_id"])
    jrow = fake.rows("jobs")[0]
    check("mark_shortlisted denormalises onto jobs",
          jrow["shortlisted_before"] is True and jrow["shortlist_count"] == 1
          and jrow["last_shortlisted_at"])

    # Run 3: cooldown applies.
    new_run()
    sink.write_jobs([JOB])
    store = history.SupabaseHistoryStore(fake, USER)
    rec = store.upsert_seen(history.record_for(JOB))
    verdict = history.evaluate(JOB, rec)
    check("Shortlisted job enters cooldown next run",
          verdict["history_status"] == "cooldown", verdict["history_reason"])

    # Repost under a new URL: sink creates its own row (FK for job_scores),
    # history still matches the older row by content_key.
    new_run()
    sink.write_jobs([REPOST])
    store = history.SupabaseHistoryStore(fake, USER)
    rec = store.upsert_seen(history.record_for(REPOST))
    verdict = history.evaluate(REPOST, rec)
    check("Repost is matched to the original via content_key",
          rec["job_id"] == "ext:linkedin:12345" and rec["seen_count"] == 5
          and verdict["history_status"] == "repost_cooldown"
          and len(fake.rows("jobs")) == 2,
          f"{verdict['history_status']}: {verdict['history_reason']}")

    # Tomorrow the repost row has its own history, but the original still wins.
    new_run()
    sink.write_jobs([REPOST])
    store = history.SupabaseHistoryStore(fake, USER)
    rec = store.upsert_seen(history.record_for(REPOST))
    check("Repost keeps resolving to the original on later runs",
          rec["job_id"] == "ext:linkedin:12345" and rec["seen_count"] == 6)

    # Web marks applied through job_actions -> scraper sees applied.
    fake.table("job_actions").upsert(
        {"job_id": "ext:linkedin:12345", "user_id": USER, "status": "applied",
         "applied_date": "2026-09-12"}, on_conflict="job_id").execute()
    store = history.SupabaseHistoryStore(fake, USER)
    verdict = history.evaluate(JOB, store.get("ext:linkedin:12345", ""))
    check("job_actions.status='applied' suppresses the job",
          verdict["history_status"] == "applied"
          and "2026-09-12" in verdict["history_reason"], verdict["history_reason"])

    store.mark_ignored("ext:linkedin:12345", "wrong shift")
    store2 = history.SupabaseHistoryStore(fake, USER)
    verdict = history.evaluate(JOB, store2.get("ext:linkedin:12345", ""))
    check("mark_ignored writes job_actions and reads back with the reason",
          verdict["history_status"] == "ignored"
          and "wrong shift" in verdict["history_reason"], verdict["history_reason"])

    store2.mark_resume_generated("ext:linkedin:12345")
    act = next(a for a in fake.rows("job_actions") if a["job_id"] == "ext:linkedin:12345")
    check("mark_resume_generated maps to resume_status='ready'",
          act["resume_status"] == "ready"
          and store2.get("ext:linkedin:12345", "")["resume_generated"] == 1)

    check("all_records returns every job for the user",
          len(store2.all_records()) == 2)

    # Paging: more than one page of jobs loads completely.
    history.SupabaseHistoryStore.PAGE = 3
    try:
        sink.write_jobs([{**JOB, "id": str(i), "title": f"T{i}"} for i in range(10)])
        store3 = history.SupabaseHistoryStore(fake, USER)
        check("History loads past the first page", len(store3.all_records()) == 12)
    finally:
        history.SupabaseHistoryStore.PAGE = 1000
    unconfigure()


def test_resume_queue():
    fake = FakeClient()
    configure(fake)
    sink.write_jobs([JOB, REPOST])
    jid = "ext:linkedin:12345"

    check("Empty queue lists nothing", resume_queue.list_requested(fake, USER) == [])

    fake.table("job_actions").upsert(
        {"job_id": jid, "user_id": USER, "resume_status": "requested",
         "notes": "user note"}, on_conflict="job_id").execute()
    queue = resume_queue.list_requested(fake, USER)
    check("list_requested returns the full job with description + action",
          len(queue) == 1 and queue[0]["job_id"] == jid
          and queue[0]["description"] == "Daily recs."
          and queue[0]["action"]["resume_status"] == "requested")

    resume_queue.mark_failed(jid, "CV induk belum diisi", fake, USER)
    act = fake.rows("job_actions")[0]
    check("mark_failed sets failed and appends the reason to notes",
          act["resume_status"] == "failed"
          and act["notes"].startswith("user note")
          and "CV induk belum diisi" in act["notes"], act["notes"])

    with tempfile.TemporaryDirectory() as tmp:
        local = os.path.join(tmp, "x.docx")
        with open(local, "wb") as fh:
            fh.write(b"PK-docx")
        path = resume_queue.upload_docx(USER, jid, local, fake)
    obj = fake.storage.objects["resumes"][path]
    check("upload_docx lands in resumes/<user_id>/<job_id>.docx",
          path == f"{USER}/ext_linkedin_12345.docx" and obj[0] == b"PK-docx"
          and obj[1].get("upsert") == "true", path)

    resume_queue.mark_ready(jid, path, fake, USER)
    act = fake.rows("job_actions")[0]
    check("mark_ready stores the storage path, not a signed URL",
          act["resume_status"] == "ready" and act["resume_url"] == path)

    # Guardrails in render_resume
    todo_profile = {"meta": {"name": "TODO_NAME"}, "sections": {},
                    "must_not_claim": ["SQL proficiency"]}
    try:
        render_resume.guard_profile(todo_profile)
        blocked = False
    except render_resume.ResumeRefused as exc:
        blocked = "CV induk belum diisi" in str(exc)
    check("Placeholders block rendering with the Malay reason", blocked)

    profile = {
        "meta": {"name": "Azim Shahir", "email": "a@b.c"},
        "sections": {"a": "b"},
        "experience": [{"employer": "X", "title": "Executive", "dates": "2022",
                        "bullets": ["Did 5 things"]}],
        "education": [], "certifications": [],
        "must_not_claim": ["SQL proficiency", "VOSTRO/NOSTRO management",
                           "NAV calculation ownership"],
        "framing_rules": [],
    }
    bad = {"tailored_summary": "Owns NAV calculation and SQL reporting.",
           "tailored_bullets": [{"employer": "X", "title": "Executive",
                                 "dates": "2022", "bullets": ["Did 5 things"]}],
           "tailored_skills": ["Excel"]}
    hits = render_resume.check_must_not_claim(bad, profile)
    check("must_not_claim phrases are caught in Claude/LLM output",
          set(hits) == {"SQL proficiency", "NAV calculation ownership"}, str(hits))

    good = {**bad, "tailored_summary": "Contributes inputs to daily NAV production."}
    job = resume_queue.load_job(jid, fake, USER)
    path = render_resume.render_and_publish(job, good, profile, client=fake, user_id=USER)
    act = fake.rows("job_actions")[0]
    docx = fake.storage.objects["resumes"][path][0]
    check("render_and_publish builds a real docx, uploads it and marks ready",
          docx[:2] == b"PK" and act["resume_status"] == "ready"
          and act["resume_url"] == path, f"{len(docx)} bytes")

    try:
        render_resume.render_and_publish(job, {"tailored_summary": "x"}, profile,
                                         client=fake, user_id=USER)
        refused = False
    except render_resume.ResumeRefused as exc:
        refused = "missing" in str(exc)
    check("Incomplete analysis JSON is refused", refused)
    unconfigure()


def main():
    print("=" * 70)
    print("SUPABASE SINK / HISTORY / RESUME QUEUE TESTS (offline, fake client)")
    print("=" * 70)
    test_noop_and_env()
    print()
    test_runs_and_jobs()
    print()
    test_history_store()
    print()
    test_resume_queue()

    print("\n" + "=" * 70)
    failed = [r for r in _results if r[0] == "FAIL"]
    print(f"{len(_results) - len(failed)} passed, {len(failed)} failed")
    for _, name, detail in failed:
        print(f"  FAILED: {name} -- {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
