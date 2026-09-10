"""
Phase 6 -- the ONLY module allowed to call a generative LLM.

Design rules, enforced here rather than by convention:

  * Nothing upstream (scraping, filtering, embedding, ranking) imports this
    module. test_pipeline.py asserts that.
  * analyse_jobs() refuses to process more than LLM_MAX_CALLS_PER_RUN jobs,
    so a misconfiguration cannot fan out to hundreds of calls.
  * With no provider configured it returns a clear "not configured" result
    instead of failing the run or inventing credentials.

Switching provider is an env var (LLM_PROVIDER=anthropic|openai), never a code
change.
"""

import json
import os

import config
import candidate as profile_mod


class LLMNotConfigured(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Prompt construction
# --------------------------------------------------------------------------
SYSTEM_PROMPT = """You are assisting an experienced finance operations \
professional with job applications in Malaysia.

You will receive one job description and the candidate's factual profile.

ABSOLUTE ACCURACY RULES -- these override every other instruction:
- Never invent experience, employers, dates, metrics, or system proficiency.
- Never claim anything on the candidate's "must not claim" list.
- Follow every framing rule exactly.
- If the candidate lacks something the job wants, name it as a gap. Do not
  paper over it.
- When tailoring resume bullets, remove an entire irrelevant bullet rather
  than keeping it in weakened form. Any bullet you keep must retain its
  original quantified metrics unchanged.

Reply with valid JSON only, matching the requested schema."""

RESPONSE_SCHEMA = {
    "overall_suitability": "one of: strong | moderate | weak",
    "suitability_rationale": "2-3 sentences",
    "strongest_matching_experience": ["short strings"],
    "gaps": ["short strings"],
    "risks": ["short strings"],
    "interview_positioning": ["short strings"],
    "worth_applying": "boolean",
    "worth_applying_reason": "one sentence",
    "tailored_summary": "3-4 line professional summary for the resume",
    "tailored_bullets": [
        {"employer": "string", "title": "string", "dates": "string",
         "bullets": ["strings, metrics preserved verbatim"]}
    ],
    "tailored_skills": ["short strings"],
}


def build_prompt(job: dict, candidate_profile: dict) -> str:
    parts = [
        "## JOB",
        f"Title: {job.get('title')}",
        f"Company: {job.get('company')}",
        f"Location: {job.get('location')}",
        f"Source: {job.get('source') or job.get('site')}",
        f"URL: {job.get('job_url_direct') or job.get('job_url')}",
        "",
        "### Full job description",
        str(job.get("description") or "(no description available)"),
        "",
        "## CANDIDATE PROFILE",
        json.dumps(
            {
                "meta": candidate_profile.get("meta", {}),
                "sections": candidate_profile.get("sections", {}),
                "tools": candidate_profile.get("tools", {}),
                "experience": candidate_profile.get("experience", []),
                "education": candidate_profile.get("education", []),
                "certifications": candidate_profile.get("certifications", []),
            },
            indent=2, ensure_ascii=False,
        ),
        "",
        "## MUST NOT CLAIM (hard constraints)",
        "\n".join(f"- {x}" for x in profile_mod.must_not_claim(candidate_profile)),
        "",
        "## FRAMING RULES (hard constraints)",
        "\n".join(f"- {x}" for x in profile_mod.framing_rules(candidate_profile)),
        "",
        "## REQUIRED JSON SCHEMA",
        json.dumps(RESPONSE_SCHEMA, indent=2),
    ]
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Providers -- add a new one by writing a _call_x and registering it below.
# --------------------------------------------------------------------------
def _model_for(provider: str) -> str:
    return config.LLM_MODEL or config.LLM_DEFAULT_MODELS.get(provider, "")


def _call_anthropic(prompt: str) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise LLMNotConfigured(
            "LLM_PROVIDER=anthropic but the 'anthropic' package is not "
            "installed (pip install anthropic)"
        ) from exc
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise LLMNotConfigured("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(timeout=config.LLM_TIMEOUT_SECONDS)
    resp = client.messages.create(
        model=_model_for("anthropic"),
        max_tokens=config.LLM_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def _call_openai(prompt: str) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMNotConfigured(
            "LLM_PROVIDER=openai but the 'openai' package is not installed "
            "(pip install openai)"
        ) from exc
    if not os.environ.get("OPENAI_API_KEY"):
        raise LLMNotConfigured("LLM_PROVIDER=openai but OPENAI_API_KEY is not set")

    client = OpenAI(timeout=config.LLM_TIMEOUT_SECONDS)
    resp = client.chat.completions.create(
        model=_model_for("openai"),
        max_tokens=config.LLM_MAX_TOKENS,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or ""


PROVIDERS = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
}


def is_configured() -> bool:
    return config.LLM_PROVIDER in PROVIDERS


def _parse(raw: str) -> dict:
    """Tolerate a model that wraps its JSON in prose or a fenced block."""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in model response: {raw[:200]}")
    return json.loads(raw[start:end + 1])


def analyse_job(job: dict, candidate_profile: dict) -> dict:
    """Analyse ONE job. Raises LLMNotConfigured when no provider is set up."""
    if not is_configured():
        raise LLMNotConfigured(
            f"LLM_PROVIDER={config.LLM_PROVIDER!r}. Set LLM_PROVIDER to one of "
            f"{sorted(PROVIDERS)} and supply the matching API key."
        )
    raw = PROVIDERS[config.LLM_PROVIDER](build_prompt(job, candidate_profile))
    return _parse(raw)


def analyse_jobs(jobs: list, candidate_profile: dict) -> list:
    """
    Analyse the final shortlist ONLY.

    Never called for rejected or unranked jobs. Hard-capped at
    LLM_MAX_CALLS_PER_RUN. A failure on one job does not stop the others.
    """
    jobs = list(jobs)[:config.LLM_MAX_CALLS_PER_RUN]
    results = []

    if not is_configured():
        for job in jobs:
            results.append({
                "job": job,
                "status": "not_configured",
                "analysis": None,
                "error": (
                    "No strong LLM configured. Set LLM_PROVIDER and the API key "
                    "to enable JD analysis and tailored resumes."
                ),
            })
        return results

    for job in jobs:
        try:
            results.append({"job": job, "status": "ok",
                            "analysis": analyse_job(job, candidate_profile),
                            "error": None})
        except Exception as exc:  # noqa: BLE001 - one bad job must not kill the run
            results.append({"job": job, "status": "error", "analysis": None,
                            "error": f"{type(exc).__name__}: {exc}"})
    return results
