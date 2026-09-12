"""
OPTIONAL API path: generate one tailored resume through scraper/llm.py.

    python make_resume.py <job_id>

Run by .github/workflows/resume.yml (workflow_dispatch {job_id}) when the
web app is in RESUME_MODE=api. Requires LLM_PROVIDER + the matching API key;
otherwise it refuses and records the reason on job_actions.

The default, no-API-key path is Claude Code's `/resume` command plus
render_resume.py -- see docs/backend.md. Both paths share render_and_publish,
so the guardrails (placeholders, must_not_claim, framing rules, DOCX
renderer) are identical.

This is one of only two callers of llm.py (the other is pipeline.py's final
selection) and it makes exactly ONE call.
"""

import sys

import candidate as profile_mod
import config
import render_resume
import resume_queue
import sink


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if len(argv) != 1:
        print("usage: python make_resume.py <job_id>")
        return 2
    job_id = argv[0]

    sink.require_env()
    job = resume_queue.load_job(job_id)
    if job is None:
        print(f"REFUSED: job {job_id!r} not found in Supabase")
        return 1

    resume_queue.mark_pending(job_id)

    try:
        profile = profile_mod.load_profile()
        render_resume.guard_profile(profile)

        import llm  # imported here: nothing upstream may pull it in
        if not llm.is_configured():
            raise render_resume.ResumeRefused(
                f"LLM tidak dikonfigurasi (LLM_PROVIDER={config.LLM_PROVIDER!r}). "
                f"Guna /resume dalam Claude Code, atau set LLM_PROVIDER + API key "
                f"di GitHub Secrets.")

        analysis = llm.analyse_job(job, profile)
        path = render_resume.render_and_publish(job, analysis, profile)
    except render_resume.ResumeRefused as exc:
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
