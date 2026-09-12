"""
Tailored-resume queue on Supabase.

The dashboard's "Tailored Resume" button sets job_actions.resume_status to
'requested'. Something then has to pick that up and produce the .docx:

  * DEFAULT (no API key): the user runs `/resume` in Claude Code. Claude
    reads the queue with list_requested(), writes the tailored content itself
    (no paid API call -- it is the subscription), and runs
    `python scraper/render_resume.py <job_id> <json>` which renders, uploads
    and marks ready via this module.
  * OPTIONAL (LLM_PROVIDER + key set): resume.yml / make_resume.py does the
    same through scraper/llm.py.

Both paths go through resume.build_resume and candidate.has_placeholders:
this module only moves state, it never writes resume content.

Storage layout: bucket `resumes`, object `<user_id>/<safe job_id>.docx`.
`resume_url` stores that object path (not a signed URL); the web app signs it
on demand.
"""

import mimetypes
import os
import re
import sys

import config
import sink

DOCX_MIME = ("application/vnd.openxmlformats-officedocument."
             "wordprocessingml.document")

STATUSES = ("none", "requested", "pending", "ready", "failed")

_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_object_name(job_id: str) -> str:
    """job_ids look like 'ext:linkedin:123' or 'url:https://...'; flatten."""
    name = _SAFE_RE.sub("_", str(job_id or "")).strip("._")
    return (name or "job")[:180]


def storage_path(user_id: str, job_id: str) -> str:
    return f"{user_id}/{safe_object_name(job_id)}.docx"


def _client(client=None):
    return client or sink.get_client()


def _uid(user_id=None):
    return user_id or sink.user_id()


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------
def load_job(job_id: str, client=None, user_id=None) -> dict:
    """Full jobs row (with description) or None."""
    client, uid = _client(client), _uid(user_id)
    resp = (client.table("jobs").select("*")
            .eq("user_id", uid).eq("job_id", job_id).limit(1).execute())
    data = resp.data or []
    return dict(data[0]) if data else None


def list_requested(client=None, user_id=None) -> list:
    """
    Jobs whose job_actions.resume_status == 'requested', oldest request
    first. Each item is the full jobs row plus an `action` key with the
    job_actions row.
    """
    client, uid = _client(client), _uid(user_id)
    resp = (client.table("job_actions").select("*")
            .eq("user_id", uid).eq("resume_status", "requested")
            .order("updated_at").execute())
    actions = list(resp.data or [])
    if not actions:
        return []

    ids = [a["job_id"] for a in actions]
    jobs = {}
    for i in range(0, len(ids), config.SUPABASE_BATCH_SIZE):
        chunk = ids[i:i + config.SUPABASE_BATCH_SIZE]
        got = (client.table("jobs").select("*")
               .eq("user_id", uid).in_("job_id", chunk).execute())
        for row in got.data or []:
            jobs[row["job_id"]] = dict(row)

    out = []
    for action in actions:
        job = jobs.get(action["job_id"])
        if job is None:
            continue  # orphaned action; nothing to render
        job["action"] = dict(action)
        out.append(job)
    return out


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------
def _set_status(job_id: str, client=None, user_id=None, **fields) -> None:
    client, uid = _client(client), _uid(user_id)
    payload = {"job_id": job_id, "user_id": uid, **fields}
    client.table("job_actions").upsert(payload, on_conflict="job_id").execute()


def mark_pending(job_id: str, client=None, user_id=None) -> None:
    _set_status(job_id, client, user_id, resume_status="pending")


def mark_ready(job_id: str, storage_path: str, client=None, user_id=None) -> None:
    _set_status(job_id, client, user_id,
                resume_status="ready", resume_url=storage_path)


def mark_failed(job_id: str, reason: str, client=None, user_id=None) -> None:
    """Sets 'failed' and appends the reason to notes (never overwrites them)."""
    client, uid = _client(client), _uid(user_id)
    reason = (reason or "unknown error").strip()
    existing = (client.table("job_actions").select("notes")
                .eq("user_id", uid).eq("job_id", job_id).limit(1).execute())
    notes = ""
    if existing.data:
        notes = existing.data[0].get("notes") or ""
    line = f"[resume failed] {reason}"
    notes = f"{notes.rstrip()}\n{line}".strip() if notes else line
    _set_status(job_id, client, uid, resume_status="failed", notes=notes[:4000])


def upload_docx(user_id: str, job_id: str, local_path: str, client=None) -> str:
    """Upload a rendered .docx to the private bucket; returns the object path."""
    client = _client(client)
    path = storage_path(user_id, job_id)
    with open(local_path, "rb") as fh:
        data = fh.read()
    mime = mimetypes.guess_type(local_path)[0] or DOCX_MIME
    (client.storage.from_(config.SUPABASE_RESUME_BUCKET)
     .upload(path, data, {"content-type": mime, "upsert": "true"}))
    return path


# --------------------------------------------------------------------------
# CLI: `python resume_queue.py` lists the queue (used by /resume)
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    queue = list_requested()
    if not queue:
        print("Queue empty: no job with resume_status='requested'.")
        return 0
    print(f"{len(queue)} job(s) requested:")
    for job in queue:
        print(f"  {job['job_id']}\t{job.get('title')} - {job.get('company')} "
              f"({job.get('location')})")
    if "--json" in (argv or sys.argv[1:]):
        import json
        print(json.dumps(queue, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
