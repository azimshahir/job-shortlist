"""
Supabase sink: writes one pipeline run (runs / jobs / job_scores).

The scraper runs on GitHub Actions with the SERVICE ROLE key, which bypasses
RLS, so every row is stamped with SUPABASE_USER_ID (the single user's auth
uuid) to keep it visible to the signed-in web user.

    run_id = sink.start_run("cron")
    sink.write_jobs(deduped_rows)          # ALL deduped jobs, incl. rejected
    sink.write_scores(run_id, rows)        # every job with a verdict
    sink.finish_run(run_id, stats, "ok")

Behaviour:
  * `is_selected()` is False unless --sink supabase / SINK=supabase, and every
    function above is a no-op that returns None / 0 in that case.
  * When selected, a missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY /
    SUPABASE_USER_ID raises SinkNotConfigured before any network call.
  * Upserts go in chunks of config.SUPABASE_BATCH_SIZE (200).

Nothing here ranks or filters; storage only.
"""

import math
from datetime import datetime, timezone

import config
import history

try:  # pandas Timestamp / NaT show up in rows read back from CSV
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None


class SinkNotConfigured(RuntimeError):
    pass


_REQUIRED_ENV = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_USER_ID")

_client = None
_selected = None  # None = follow config.SINK; True/False = explicit override
_run_started = None  # ISO timestamp captured by start_run(); see history.py


# --------------------------------------------------------------------------
# Selection + client
# --------------------------------------------------------------------------
def select(name: str) -> None:
    """Called by pipeline.py after parsing --sink. 'csv' disables the sink."""
    global _selected, _run_started
    _selected = (name or "").strip().lower() == "supabase"
    _run_started = None


def is_selected() -> bool:
    if _selected is None:
        return config.SINK == "supabase"
    return _selected


def run_started_at():
    """When start_run() ran in this process (None if the sink is off)."""
    return _run_started


def missing_env() -> list:
    return [name for name in _REQUIRED_ENV if not getattr(config, name, "")]


def require_env() -> None:
    missing = missing_env()
    if missing:
        raise SinkNotConfigured(
            "Supabase sink selected but env is missing: " + ", ".join(missing)
            + ". Set them in GitHub Secrets (never in the repo)."
        )


def user_id() -> str:
    require_env()
    return config.SUPABASE_USER_ID


def get_client():
    """Lazily build the supabase-py client. Tests replace this via monkeypatch."""
    global _client
    if _client is None:
        require_env()
        from supabase import create_client  # imported late: optional dep
        _client = create_client(config.SUPABASE_URL,
                                config.SUPABASE_SERVICE_ROLE_KEY)
    return _client


def set_client(client) -> None:
    """Inject a client (tests use a fake). None resets to lazy creation."""
    global _client
    _client = client


# --------------------------------------------------------------------------
# Value cleaning: CSV round-trips and pandas leave NaN / 'nan' everywhere
# --------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if pd is not None:
        try:
            if value is pd.NaT:
                return True
        except Exception:  # noqa: BLE001
            pass
    if isinstance(value, str) and value.strip().lower() in ("", "nan", "nat", "none"):
        return True
    return False


def _text(value):
    if _is_missing(value):
        return None
    return str(value)


def _int(value):
    if _is_missing(value):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _num(value):
    if _is_missing(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(out) else out


def _date(value):
    if _is_missing(value):
        return None
    text = str(value).strip()
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            return None
    # "2026-09-11", "2026-09-11 00:00:00", "2026-09-11T..." all start the same
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None


def _list(value) -> list:
    if _is_missing(value):
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if not _is_missing(v)]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _chunks(items: list, size: int = None):
    size = size or config.SUPABASE_BATCH_SIZE
    for i in range(0, len(items), size):
        yield items[i:i + size]


# --------------------------------------------------------------------------
# Row builders
# --------------------------------------------------------------------------
def job_row(job: dict, uid: str) -> dict:
    identity = history.job_identity(job)
    return {
        "job_id": identity["job_id"],
        "user_id": uid,
        "content_key": identity["content_key"],
        "url_key": identity["url_key"] or None,
        "source": _text(job.get("source")) or _text(job.get("site")),
        "title": _text(job.get("title")),
        "company": _text(job.get("company")),
        "location": _text(job.get("location")),
        "job_url": _text(job.get("job_url")),
        "job_url_direct": _text(job.get("job_url_direct")),
        "description": _text(job.get("description")),
        "date_posted": _date(job.get("date_posted")),
    }


def score_row(job: dict, run_id: str, uid: str) -> dict:
    job_id = _text(job.get("job_id")) or history.job_identity(job)["job_id"]
    return {
        "run_id": run_id,
        "job_id": job_id,
        "user_id": uid,
        "filter_status": _text(job.get("filter_status")),
        "reject_reason": _text(job.get("reject_reason")),
        "keyword_score": _int(job.get("keyword_score")),
        "semantic_raw": _num(job.get("semantic_raw")),
        "semantic_score": _num(job.get("semantic_score")),
        "semantic_rank": _int(job.get("semantic_rank")),
        "final_score": _num(job.get("final_score")),
        "final_rank": _int(job.get("final_rank")),
        "career_family": _text(job.get("career_family")),
        "career_family_status": _text(job.get("career_family_status")),
        "career_family_reason": _text(job.get("career_family_reason")),
        "selection_status": _text(job.get("selection_status")),
        "selection_reason": _text(job.get("selection_reason")),
        "matched_keywords": _list(job.get("matched_keywords")),
        "strongest_profile_match": _text(job.get("strongest_profile_match")),
        "history_status": _text(job.get("history_status")),
        "history_reason": _text(job.get("history_reason")),
    }


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def start_run(trigger: str = "manual"):
    """Insert a `running` row and return its id. None when the sink is off."""
    global _run_started
    if not is_selected():
        return None
    client = get_client()
    trigger = trigger if trigger in ("cron", "manual") else "manual"
    _run_started = _now_iso()
    resp = (client.table("runs")
            .insert({"user_id": user_id(), "trigger": trigger,
                     "status": "running", "started_at": _run_started})
            .execute())
    data = resp.data or []
    if not data or not data[0].get("id"):
        raise RuntimeError("Supabase did not return a run id")
    return data[0]["id"]


def write_jobs(rows: list) -> int:
    """
    Upsert every job on job_id. Existing rows get seen_count + 1 and a fresh
    last_seen; new rows start at seen_count 1. Returns rows written.
    """
    if not is_selected() or not rows:
        return 0
    client = get_client()
    uid = user_id()
    now = _now_iso()

    # Dedupe by job_id within the batch (two raw rows can share an identity).
    by_id = {}
    for job in rows:
        row = job_row(job, uid)
        by_id.setdefault(row["job_id"], row)

    written = 0
    for chunk in _chunks(list(by_id.values())):
        ids = [r["job_id"] for r in chunk]
        existing = {}
        resp = (client.table("jobs")
                .select("job_id, seen_count, first_seen")
                .eq("user_id", uid)
                .in_("job_id", ids)
                .execute())
        for rec in resp.data or []:
            existing[rec["job_id"]] = rec

        payload = []
        for row in chunk:
            prev = existing.get(row["job_id"])
            if prev:
                row["first_seen"] = prev.get("first_seen") or now
                row["seen_count"] = int(prev.get("seen_count") or 0) + 1
            else:
                row["first_seen"] = now
                row["seen_count"] = 1
            row["last_seen"] = now
            payload.append(row)

        client.table("jobs").upsert(payload, on_conflict="job_id").execute()
        written += len(payload)
    return written


def write_scores(run_id, rows: list) -> int:
    """Upsert one job_scores row per job for this run. Returns rows written."""
    if not is_selected() or not rows or not run_id:
        return 0
    client = get_client()
    uid = user_id()

    by_id = {}
    for job in rows:
        row = score_row(job, run_id, uid)
        by_id.setdefault(row["job_id"], row)

    written = 0
    for chunk in _chunks(list(by_id.values())):
        (client.table("job_scores")
         .upsert(chunk, on_conflict="run_id,job_id")
         .execute())
        written += len(chunk)
    return written


def finish_run(run_id, stats: dict, status: str = "ok", error: str = None) -> None:
    if not is_selected() or not run_id:
        return
    client = get_client()
    stats = stats or {}
    payload = {
        "finished_at": _now_iso(),
        "status": status if status in ("ok", "failed") else "failed",
        "raw_count": _int(stats.get("raw")) or 0,
        "deduped_count": _int(stats.get("deduped")) or 0,
        "hard_rejected": _int(stats.get("hard_rejected")) or 0,
        "keyword_passed": _int(stats.get("keyword_passed")) or 0,
        "ranked": _int(stats.get("ranked")) or 0,
        "career_rejected": _int(stats.get("career_rejected")) or 0,
        "history_excluded": _int(stats.get("history_excluded")) or 0,
        "selected": _int(stats.get("selected")) or 0,
        "error": (str(error)[:4000] if error else None),
    }
    client.table("runs").update(payload).eq("id", run_id).execute()
