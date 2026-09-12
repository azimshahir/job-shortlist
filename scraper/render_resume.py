"""
Render one tailored resume from an analysis JSON, upload it, mark it ready.

    python render_resume.py <job_id> <analysis.json>

Used by the DEFAULT (no API key) path: Claude Code's `/resume` command writes
the analysis JSON itself (shape: llm.RESPONSE_SCHEMA), then calls this. Also
reused by make_resume.py for the optional API path.

Guardrails are enforced HERE, whichever path produced the JSON:
  * candidate.has_placeholders()  -> refuse, mark failed
  * must_not_claim phrases         -> refuse, mark failed (deterministic scan)
  * llm.RESPONSE_SCHEMA keys       -> refuse, mark failed if the resume
                                      sections are missing
  * resume.build_resume            -> the only renderer; framing rules such
                                      as the Copilot facilitator line live there
No network call other than Supabase. No LLM call.
"""

import json
import os
import re
import sys
import tempfile

import candidate as profile_mod
import config
import resume
import resume_queue
import sink

PLACEHOLDER_MSG = "CV induk belum diisi"

_REQUIRED_KEYS = ("tailored_summary", "tailored_bullets", "tailored_skills")
_STRIP_WORDS = ("ownership", "formal", "proficiency", "management",
                "experience", "of", "the")


class ResumeRefused(RuntimeError):
    """Raised when a guardrail blocks generation. Message is user-facing."""


def _flatten_text(node) -> str:
    if isinstance(node, dict):
        return " ".join(_flatten_text(v) for v in node.values())
    if isinstance(node, (list, tuple)):
        return " ".join(_flatten_text(v) for v in node)
    return str(node or "")


def banned_phrases(item: str) -> list:
    """'VOSTRO/NOSTRO management' -> ['vostro', 'nostro']; 'SQL proficiency' -> ['sql']."""
    out = []
    for part in re.split(r"[/,]", str(item).lower()):
        words = [w for w in re.findall(r"[a-z0-9&+.-]+", part)
                 if w not in _STRIP_WORDS]
        phrase = " ".join(words).strip()
        if phrase:
            out.append(phrase)
    return out


def check_must_not_claim(analysis: dict, profile: dict) -> list:
    """Return the banned phrases that appear in the analysis text."""
    text = " ".join(_flatten_text(analysis).lower().split())
    hits = []
    for item in profile_mod.must_not_claim(profile):
        for phrase in banned_phrases(item):
            if re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text):
                hits.append(item)
                break
    return hits


def validate_analysis(analysis: dict, profile: dict) -> None:
    if not isinstance(analysis, dict):
        raise ResumeRefused("analysis JSON must be an object")
    missing = [k for k in _REQUIRED_KEYS if not analysis.get(k)]
    if missing:
        raise ResumeRefused("analysis JSON missing: " + ", ".join(missing))
    hits = check_must_not_claim(analysis, profile)
    if hits:
        raise ResumeRefused("must_not_claim violated: " + "; ".join(hits))


def guard_profile(profile: dict) -> None:
    placeholders = profile_mod.has_placeholders(profile)
    if placeholders:
        raise ResumeRefused(
            f"{PLACEHOLDER_MSG} ({len(placeholders)} TODO_ placeholder(s) in "
            f"candidate_profile.yaml, e.g. {placeholders[0]})")


def render_and_publish(job: dict, analysis: dict, profile: dict,
                       client=None, user_id: str = None) -> str:
    """
    Validate, render to a temp file, upload, mark ready. Returns the storage
    path. Raises ResumeRefused (guardrail) or any renderer/upload exception;
    the caller decides how to record the failure.
    """
    guard_profile(profile)
    validate_analysis(analysis, profile)
    uid = user_id or sink.user_id()

    with tempfile.TemporaryDirectory() as tmp:
        local = os.path.join(
            tmp, resume.safe_filename(job.get("company"), job.get("title")))
        resume.build_resume(analysis, job, profile, local)
        path = resume_queue.upload_docx(uid, job["job_id"], local, client=client)
    resume_queue.mark_ready(job["job_id"], path, client=client, user_id=uid)
    return path


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if len(argv) != 2:
        print("usage: python render_resume.py <job_id> <analysis.json>")
        return 2
    job_id, json_path = argv

    sink.require_env()
    job = resume_queue.load_job(job_id)
    if job is None:
        print(f"REFUSED: job {job_id!r} not found in Supabase")
        return 1

    try:
        with open(json_path, encoding="utf-8") as fh:
            analysis = json.load(fh)
        profile = profile_mod.load_profile()
        path = render_and_publish(job, analysis, profile)
    except ResumeRefused as exc:
        resume_queue.mark_failed(job_id, str(exc))
        print(f"REFUSED: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        resume_queue.mark_failed(job_id, reason)
        print(f"FAILED: {reason}")
        return 1

    print(f"READY: {job.get('title')} - {job.get('company')} -> "
          f"{config.SUPABASE_RESUME_BUCKET}/{path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
