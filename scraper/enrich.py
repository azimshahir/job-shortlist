"""
Phase 10 -- Playwright fallback SEAM. Deliberately not implemented.

JobSpy is and remains the primary collector. This module exists so the
fallback has an obvious home later, and so the pipeline can already report
WHICH jobs would need it.

Current real numbers from the 952-row scrape:
    description missing:      0 of 952   -> fallback not needed for JDs
    job_url_direct missing: 720 of 952   -> all LinkedIn rows

So the only live gap is the direct apply URL on LinkedIn. The email already
falls back to job_url, which works, so implementing a browser fallback now
would add a heavy dependency for a cosmetic gain. Left as a TODO on purpose.

WHEN IT IS IMPLEMENTED, the constraints are:
  * Run ONLY over already-shortlisted jobs (PLAYWRIGHT_MAX_PAGES, i.e. <= 5),
    never the raw scrape.
  * Deterministic scripted navigation. An LLM must NOT drive the browser in a
    snapshot -> reason -> click loop; that is exactly the token cost this
    architecture exists to avoid.
  * Failure must stay non-fatal: return the job unchanged.
"""

import config

MISSING = "missing"
PRESENT = "present"


def description_status(job: dict) -> str:
    desc = job.get("description")
    if desc is None:
        return MISSING
    return PRESENT if str(desc).strip() and str(desc).strip().lower() != "nan" else MISSING


def needs_enrichment(job: dict) -> list:
    """Which fields a browser fallback would have to go and fetch."""
    gaps = []
    if description_status(job) == MISSING:
        gaps.append("description")
    direct = job.get("job_url_direct")
    if not direct or str(direct).strip().lower() in ("", "nan", "none"):
        gaps.append("job_url_direct")
    return gaps


def enrich(jobs: list) -> list:
    """
    No-op passthrough while ENABLE_PLAYWRIGHT_FALLBACK is False.

    Still stamps description_status on every job so the traceability CSVs
    record what was and wasn't available.
    """
    for job in jobs:
        job["description_status"] = description_status(job)
        job["enrichment_needed"] = ",".join(needs_enrichment(job))

    if not config.ENABLE_PLAYWRIGHT_FALLBACK:
        return jobs

    # TODO(playwright): fetch the gaps above for at most PLAYWRIGHT_MAX_PAGES
    # shortlisted jobs, with scripted navigation only.
    raise NotImplementedError(
        "ENABLE_PLAYWRIGHT_FALLBACK is True but the fallback is not "
        "implemented yet. Set it back to False in config.py."
    )
