"""
Cross-run job history: persistent deduplication ACROSS DAYS.

The in-scrape dedupe in scraper.py only removes duplicates within a single
run. This module remembers jobs between runs so the same posting does not
reappear every morning, and so a job marked applied never comes back into the
actionable shortlist.

STORAGE ABSTRACTION
    HistoryStore is the interface. SqliteHistoryStore is the production
    implementation; MemoryHistoryStore is for tests. Pipeline logic talks only
    to the interface, so moving execution from GitHub Actions to a VPS -- or
    swapping SQLite for Postgres -- touches nothing outside this file.

A NOTE ON GITHUB ACTIONS
    Actions runners are ephemeral: the filesystem is destroyed after every
    run. There is no safe mutable persistence available to it out of the box.
    The GitHub Actions cache is explicitly NOT used as a database here -- it
    is best-effort, evictable at any time, has no concurrency control, and
    silently loses writes. Using it as a datastore would produce a history
    that appears to work and quietly forgets things.

    To get real persistence, pick one:
      1. Run the pipeline on the VPS (cron + a local job_history.db). This is
         the intended destination and needs no code change -- only
         HISTORY_DB_PATH pointing at a durable path.
      2. Point HISTORY_DB_PATH at a mounted network volume.
      3. Add a hosted-database backend behind this same interface.

    Until then, a GitHub Actions run starts with an empty history: nothing
    breaks, cross-run dedupe simply does not apply. The pipeline reports which
    mode it is in on every run.
"""

import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone

import config

SCHEMA_VERSION = 1

_PUNCT_RE = re.compile(r"[^a-z0-9\s]+")
_WS_RE = re.compile(r"\s+")

# Dropped when normalising a company name so "CACEIS Malaysia Sdn Bhd" and
# "CACEIS" fingerprint alike.
_COMPANY_SUFFIXES = (
    "sdn bhd", "sdn", "bhd", "berhad", "pte ltd", "pte", "ltd", "limited",
    "llc", "inc", "incorporated", "plc", "group", "holdings", "malaysia",
    "asia", "asia pacific", "apac", "services", "sea",
)

# Dropped from titles: employer decoration that varies between reposts.
_TITLE_NOISE = (
    r"\(.*?\)", r"\[.*?\]",
    r"\b\d+\s*months?\s*contract\b", r"\bcontract\b", r"\bpermanent\b",
    r"\bfull[\s-]?time\b", r"\bpart[\s-]?time\b", r"\bm/f\b", r"\bm\|f\b",
    r"\burgent\b", r"\bhiring\b", r"\bnew\b", r"\bopen\b",
    r"\bkuala lumpur\b", r"\bselangor\b", r"\bmalaysia\b",
)


def _now():
    return datetime.now(timezone.utc)


def normalise_company(value) -> str:
    text = _PUNCT_RE.sub(" ", str(value or "").lower())
    text = _WS_RE.sub(" ", text).strip()
    changed = True
    while changed:  # strip stacked suffixes: "... Sdn Bhd Malaysia"
        changed = False
        for suffix in _COMPANY_SUFFIXES:
            if text.endswith(" " + suffix) or text == suffix:
                text = text[: -len(suffix)].strip()
                changed = True
    return text


def normalise_title(value) -> str:
    text = str(value or "").lower()
    for pattern in _TITLE_NOISE:
        text = re.sub(pattern, " ", text)
    text = _PUNCT_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def normalise_location(value) -> str:
    """
    Collapse the many ways sources spell the same place.

    "Kuala Lumpur, Malaysia" and
    "Kuala Lumpur, Federal Territory of Kuala Lumpur, Malaysia" must produce
    the same key, so administrative wrappers are stripped AND repeated tokens
    are de-duplicated -- otherwise the second form leaves "kuala lumpur kuala
    lumpur" and the two never match.
    """
    text = _PUNCT_RE.sub(" ", str(value or "").lower())
    text = _WS_RE.sub(" ", text).strip()
    for noise in ("federal territory of", "wilayah persekutuan", "wp",
                  "malaysia", "greater", "area"):
        text = re.sub(rf"(?<![a-z]){re.escape(noise)}(?![a-z])", " ", text)

    seen, words = set(), []
    for word in text.split():
        if word not in seen:
            seen.add(word)
            words.append(word)
    return " ".join(words)


def normalise_url(value) -> str:
    """Strip tracking params and trailing slashes so reposts collapse."""
    url = str(value or "").strip().lower()
    if not url or url in ("nan", "none"):
        return ""
    url = url.split("?")[0].split("#")[0]
    return url.rstrip("/")


def external_id(job: dict) -> str:
    """JobSpy's own id, when the source provided one."""
    value = str(job.get("id") or "").strip().lower()
    return "" if value in ("", "nan", "none") else value


def content_fingerprint(job: dict) -> str:
    """
    Identity that survives a repost.

    Company + title + location, all normalised. Deliberately excludes the URL:
    a repost of the same role under a new URL must collapse onto this key.
    """
    parts = (normalise_company(job.get("company")),
             normalise_title(job.get("title")),
             normalise_location(job.get("location")))
    return "content:" + "|".join(parts)


def url_fingerprint(job: dict) -> str:
    url = normalise_url(job.get("job_url_direct")) or normalise_url(job.get("job_url"))
    return f"url:{url}" if url else ""


def job_identity(job: dict) -> dict:
    """
    All identity keys for a job.

    `job_id` is the strongest available: external id > url > content hash.
    `content_key` is always present and is what repost detection matches on.
    """
    ext = external_id(job)
    url_fp = url_fingerprint(job)
    content = content_fingerprint(job)

    if ext:
        job_id = f"ext:{job.get('site') or 'unknown'}:{ext}"
    elif url_fp:
        job_id = url_fp
    else:
        job_id = content

    return {"job_id": job_id, "url_key": url_fp, "content_key": content}


# --------------------------------------------------------------------------
# Storage interface
# --------------------------------------------------------------------------
class HistoryStore:
    """Interface. Any backend implementing this works with the pipeline."""

    def get(self, job_id: str, content_key: str) -> dict:
        raise NotImplementedError

    def upsert_seen(self, record: dict) -> dict:
        raise NotImplementedError

    def mark_shortlisted(self, job_id: str) -> None:
        raise NotImplementedError

    def mark_applied(self, job_id: str, when=None) -> None:
        raise NotImplementedError

    def mark_ignored(self, job_id: str, reason: str = "") -> None:
        raise NotImplementedError

    def mark_resume_generated(self, job_id: str) -> None:
        raise NotImplementedError

    def all_records(self) -> list:
        raise NotImplementedError

    def close(self) -> None:
        pass


FIELDS = ("job_id", "content_key", "url_key", "source", "company", "title",
          "location", "job_url", "first_seen", "last_seen", "seen_count",
          "shortlisted_before", "shortlist_count", "last_shortlisted_at",
          "resume_generated", "applied", "applied_date", "ignored",
          "ignore_reason")


class SqliteHistoryStore(HistoryStore):
    """Production backend. A single file; safe to back up by copying."""

    def __init__(self, path: str = None):
        self.path = path or config.HISTORY_DB_PATH
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id              TEXT PRIMARY KEY,
                content_key         TEXT NOT NULL,
                url_key             TEXT,
                source              TEXT,
                company             TEXT,
                title               TEXT,
                location            TEXT,
                job_url             TEXT,
                first_seen          TEXT NOT NULL,
                last_seen           TEXT NOT NULL,
                seen_count          INTEGER NOT NULL DEFAULT 1,
                shortlisted_before  INTEGER NOT NULL DEFAULT 0,
                shortlist_count     INTEGER NOT NULL DEFAULT 0,
                last_shortlisted_at TEXT,
                resume_generated    INTEGER NOT NULL DEFAULT 0,
                applied             INTEGER NOT NULL DEFAULT 0,
                applied_date        TEXT,
                ignored             INTEGER NOT NULL DEFAULT 0,
                ignore_reason       TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_content ON jobs(content_key);
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            """
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.conn.commit()

    def get(self, job_id: str, content_key: str) -> dict:
        cur = self.conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        if row is None and content_key:
            # Repost: same role, different URL.
            cur = self.conn.execute(
                "SELECT * FROM jobs WHERE content_key = ? "
                "ORDER BY last_seen DESC LIMIT 1", (content_key,))
            row = cur.fetchone()
        return dict(row) if row else None

    def upsert_seen(self, record: dict) -> dict:
        now = _now().isoformat()
        existing = self.get(record["job_id"], record.get("content_key", ""))

        if existing is None:
            payload = {k: record.get(k) for k in FIELDS}
            payload.update(first_seen=now, last_seen=now, seen_count=1,
                           shortlisted_before=0, shortlist_count=0,
                           resume_generated=0, applied=0, ignored=0)
            self.conn.execute(
                f"INSERT INTO jobs ({','.join(FIELDS)}) "
                f"VALUES ({','.join('?' for _ in FIELDS)})",
                [payload.get(k) for k in FIELDS])
            self.conn.commit()
            return self.get(record["job_id"], record.get("content_key", ""))

        self.conn.execute(
            "UPDATE jobs SET last_seen = ?, seen_count = seen_count + 1 "
            "WHERE job_id = ?", (now, existing["job_id"]))
        self.conn.commit()
        return self.get(existing["job_id"], existing["content_key"])

    def _set(self, job_id: str, **fields):
        assignments = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(f"UPDATE jobs SET {assignments} WHERE job_id = ?",
                          [*fields.values(), job_id])
        self.conn.commit()

    def mark_shortlisted(self, job_id: str) -> None:
        self.conn.execute(
            "UPDATE jobs SET shortlisted_before = 1, "
            "shortlist_count = shortlist_count + 1, last_shortlisted_at = ? "
            "WHERE job_id = ?", (_now().isoformat(), job_id))
        self.conn.commit()

    def mark_applied(self, job_id: str, when=None) -> None:
        self._set(job_id, applied=1,
                  applied_date=(when or _now()).isoformat()
                  if not isinstance(when, str) else when)

    def mark_ignored(self, job_id: str, reason: str = "") -> None:
        self._set(job_id, ignored=1, ignore_reason=reason)

    def mark_resume_generated(self, job_id: str) -> None:
        self._set(job_id, resume_generated=1)

    def all_records(self) -> list:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM jobs ORDER BY last_seen DESC")]

    def close(self) -> None:
        self.conn.close()


class MemoryHistoryStore(HistoryStore):
    """Non-persistent backend for tests and for runs with no durable storage."""

    def __init__(self):
        self._rows = {}

    def get(self, job_id, content_key):
        if job_id in self._rows:
            return dict(self._rows[job_id])
        if content_key:
            for row in self._rows.values():
                if row["content_key"] == content_key:
                    return dict(row)
        return None

    def upsert_seen(self, record):
        now = _now().isoformat()
        existing = self.get(record["job_id"], record.get("content_key", ""))
        if existing is None:
            row = {k: record.get(k) for k in FIELDS}
            row.update(first_seen=now, last_seen=now, seen_count=1,
                       shortlisted_before=0, shortlist_count=0,
                       last_shortlisted_at=None, resume_generated=0,
                       applied=0, applied_date=None, ignored=0,
                       ignore_reason=None)
            self._rows[record["job_id"]] = row
            return dict(row)
        row = self._rows[existing["job_id"]]
        row["last_seen"] = now
        row["seen_count"] += 1
        return dict(row)

    def mark_shortlisted(self, job_id):
        row = self._rows[job_id]
        row["shortlisted_before"] = 1
        row["shortlist_count"] += 1
        row["last_shortlisted_at"] = _now().isoformat()

    def mark_applied(self, job_id, when=None):
        self._rows[job_id]["applied"] = 1
        self._rows[job_id]["applied_date"] = (when or _now()).isoformat() \
            if not isinstance(when, str) else when

    def mark_ignored(self, job_id, reason=""):
        self._rows[job_id]["ignored"] = 1
        self._rows[job_id]["ignore_reason"] = reason

    def mark_resume_generated(self, job_id):
        self._rows[job_id]["resume_generated"] = 1

    def all_records(self):
        return [dict(r) for r in self._rows.values()]


def get_store(backend: str = None, path: str = None) -> HistoryStore:
    backend = (backend or config.HISTORY_BACKEND).lower()
    if backend == "sqlite":
        return SqliteHistoryStore(path)
    if backend == "memory":
        return MemoryHistoryStore()
    raise ValueError(f"unknown HISTORY_BACKEND: {backend!r}")


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------
def _age_days(timestamp, now=None) -> float:
    if not timestamp:
        return float("inf")
    try:
        then = datetime.fromisoformat(str(timestamp))
    except (ValueError, TypeError):
        return float("inf")
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return ((now or _now()) - then).total_seconds() / 86400.0


def evaluate(job: dict, record: dict, now=None) -> dict:
    """
    Decide whether a job is actionable today, given its history.

    Returns history_status / history_reason plus the tracked counters. Nothing
    is ever deleted -- a suppressed job stays in ranked_jobs.csv with a reason.
    """
    identity = job_identity(job)
    base = {
        "job_id": identity["job_id"],
        "content_key": identity["content_key"],
        "first_seen": record.get("first_seen") if record else None,
        "last_seen": record.get("last_seen") if record else None,
        "seen_count": record.get("seen_count", 0) if record else 0,
        "shortlisted_before": bool(record.get("shortlisted_before")) if record else False,
        "shortlist_count": record.get("shortlist_count", 0) if record else 0,
        "resume_generated": bool(record.get("resume_generated")) if record else False,
        "applied": bool(record.get("applied")) if record else False,
        "applied_date": record.get("applied_date") if record else None,
        "ignored": bool(record.get("ignored")) if record else False,
        "ignore_reason": record.get("ignore_reason") if record else None,
    }

    if record is None:
        base.update(history_status="new", history_reason="not seen before")
        return base

    # applied / ignored are TERMINAL states and are checked before anything
    # else -- a job marked applied must stay suppressed even if it was only
    # seen once, or if it reappears under a fresh URL.
    if config.EXCLUDE_APPLIED and record.get("applied"):
        base.update(history_status="applied",
                    history_reason=f"already applied on "
                                   f"{record.get('applied_date') or 'unknown date'}")
        return base

    if config.EXCLUDE_IGNORED and record.get("ignored"):
        base.update(history_status="ignored",
                    history_reason=f"manually ignored"
                                   + (f": {record['ignore_reason']}"
                                      if record.get("ignore_reason") else ""))
        return base

    # seen_count == 1 means this run's upsert_seen created the row, so the job
    # is genuinely new. apply_history necessarily records a job before
    # evaluating it, so `record is None` is never true on that path.
    if int(record.get("seen_count") or 0) <= 1:
        base.update(history_status="new", history_reason="not seen before")
        return base

    # Repost: same content key, different URL, seen before.
    is_repost = (identity["url_key"] and record.get("url_key")
                 and identity["url_key"] != record["url_key"])

    if record.get("shortlisted_before"):
        age = _age_days(record.get("last_shortlisted_at"), now=now)
        if age < config.SHORTLIST_COOLDOWN_DAYS:
            base.update(
                history_status="repost_cooldown" if is_repost else "cooldown",
                history_reason=(
                    f"shortlisted {age:.0f}d ago "
                    f"(cooldown {config.SHORTLIST_COOLDOWN_DAYS}d, "
                    f"shown {record.get('shortlist_count', 0)}x)"
                    + (" -- repost under a new URL" if is_repost else "")))
            return base
        base.update(history_status="cooldown_expired",
                    history_reason=(f"shortlisted {age:.0f}d ago, past the "
                                    f"{config.SHORTLIST_COOLDOWN_DAYS}d cooldown"))
        return base

    if is_repost:
        age = _age_days(record.get("last_seen"), now=now)
        if age < config.REPOST_COOLDOWN_DAYS:
            base.update(history_status="repost",
                        history_reason=(f"same company/title/location seen "
                                        f"{age:.0f}d ago under a different URL"))
            return base

    base.update(history_status="seen_not_shortlisted",
                history_reason=(f"seen {base['seen_count']}x before but never "
                                f"shortlisted"))
    return base


ACTIONABLE_HISTORY = ("new", "seen_not_shortlisted", "cooldown_expired")


def is_actionable(history_status: str) -> bool:
    return history_status in ACTIONABLE_HISTORY


def record_for(job: dict) -> dict:
    identity = job_identity(job)
    return {
        "job_id": identity["job_id"],
        "content_key": identity["content_key"],
        "url_key": identity["url_key"],
        "source": job.get("source") or job.get("site"),
        "company": job.get("company"),
        "title": job.get("title"),
        "location": job.get("location"),
        "job_url": job.get("job_url_direct") or job.get("job_url"),
    }


def apply_history(jobs: list, store: HistoryStore, now=None) -> list:
    """Stamp history_* fields on every job, recording each as seen."""
    for job in jobs:
        record = store.upsert_seen(record_for(job))
        job.update(evaluate(job, record, now=now))
    return jobs
