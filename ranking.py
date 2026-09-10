"""
Phase 4 -- combine signals into one final score and choose what deserves
expensive analysis.

Every component is normalised to 0-100 first, then weighted per
config.WEIGHTS. Missing data scores NEUTRAL_COMPONENT_SCORE so an absent field
neither rewards nor punishes a job.
"""

from datetime import datetime, timezone

import config


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(v)))


def keyword_component(keyword_score) -> float:
    try:
        score = float(keyword_score)
    except (TypeError, ValueError):
        return config.NEUTRAL_COMPONENT_SCORE
    return _clamp(score / config.KEYWORD_SCORE_CEILING * 100.0)


def seniority_component(job: dict) -> float:
    """
    Soft preference around ~5 years of experience. Hard seniority rejects
    ("head of", "10+ years") already removed the worst cases in filters.py.
    """
    title = str(job.get("title") or "").lower()
    if not title:
        return config.NEUTRAL_COMPONENT_SCORE

    if any(t in title for t in config.SENIORITY_PREFERRED):
        base = 100.0
    elif any(t in title for t in config.SENIORITY_STRETCH):
        base = 70.0
    else:
        base = config.NEUTRAL_COMPONENT_SCORE

    # Internships and graduate schemes are a step backwards at 5 years in.
    if any(t in title for t in ("intern", "internship", "trainee",
                                "graduate programme", "graduate program",
                                "apprentice", "fresh graduate")):
        base = 10.0
    return _clamp(base)


def location_component(job: dict) -> float:
    loc = str(job.get("location") or "").lower()
    if not loc:
        return config.NEUTRAL_COMPONENT_SCORE
    if any(p in loc for p in config.PREFERRED_LOCATIONS):
        return 100.0
    if any(r in loc for r in config.REMOTE_TERMS):
        return 80.0
    if "malaysia" in loc:
        return 70.0
    return 30.0


def recency_component(job: dict, now=None) -> float:
    """
    Low weight by design: only Indeed supplies date_posted, so most rows land
    on the neutral score.
    """
    raw = job.get("date_posted")
    if raw is None or str(raw).strip() in ("", "nan", "NaT", "None"):
        return config.NEUTRAL_COMPONENT_SCORE
    try:
        posted = datetime.fromisoformat(str(raw)[:10]).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return config.NEUTRAL_COMPONENT_SCORE

    now = now or datetime.now(timezone.utc)
    days = (now - posted).days
    if days <= 1:
        return 100.0
    if days <= 3:
        return 85.0
    if days <= 7:
        return 65.0
    return 40.0


def salary_component(job: dict) -> float:
    """
    Implemented and ready, but JobSpy returned salary for 0 of 952 Malaysian
    rows, so config gives it weight 0.0. Raise the weight if that changes.
    """
    for key in ("min_amount", "max_amount"):
        val = job.get(key)
        try:
            if val is not None and float(val) > 0:
                return 100.0
        except (TypeError, ValueError):
            continue
    return config.NEUTRAL_COMPONENT_SCORE


def final_score(job: dict, semantic_score: float, keyword_score, now=None) -> dict:
    """Weighted combination. Returns the total plus every component, for tracing."""
    components = {
        "semantic": _clamp(semantic_score),
        "keyword": keyword_component(keyword_score),
        "seniority": seniority_component(job),
        "location": location_component(job),
        "recency": recency_component(job, now=now),
        "salary": salary_component(job),
    }
    total = sum(components[k] * config.WEIGHTS.get(k, 0.0) for k in components)
    weight_sum = sum(config.WEIGHTS.values()) or 1.0
    return {"final_score": round(total / weight_sum, 1), "components": components}


def select_final(ranked: list) -> list:
    """
    Choose which jobs get expensive LLM analysis.

    Rules, in order:
      - must clear FINAL_SCORE_THRESHOLD
      - cap at MAX_FINAL_SELECTION
      - never pad the list to hit a quota; two strong jobs beat five weak ones

    Mutates each row with selection_status / selection_reason and returns the
    selected subset.
    """
    import careers
    import history

    ordered = sorted(ranked, key=lambda r: -float(r.get("final_score") or 0))
    selected = []

    for row in ordered:
        score = float(row.get("final_score") or 0)
        title = str(row.get("title") or "").lower()
        disqualifier = next(
            (t for t in config.DISQUALIFYING_TITLE_TERMS if t in title), None
        )

        url = str(row.get("job_url") or "")
        overridden = url and url in config.CAREER_FAMILY_OVERRIDES

        family_status = row.get("career_family_status")
        history_status = row.get("history_status")

        # ---- Career-family gate --------------------------------------
        # A high semantic score must NOT override an out-of-scope family.
        # This is checked before the score threshold for exactly that reason.
        if (family_status and not overridden
                and not careers.is_actionable(family_status)):
            row["selection_status"] = "out_of_scope"
            row["selection_reason"] = (
                f"career family gate: {row.get('career_family_reason') or family_status}"
                f" (final score {score} ignored)"
            )

        # ---- Cross-run history gate ----------------------------------
        elif history_status and not history.is_actionable(history_status):
            row["selection_status"] = f"history_{history_status}"
            row["selection_reason"] = (
                f"history gate: {row.get('history_reason') or history_status}"
            )

        elif disqualifier:
            row["selection_status"] = "disqualified"
            row["selection_reason"] = (
                f"entry-level title ('{disqualifier}') is a step backwards at "
                f"{config.CANDIDATE_YEARS_EXPERIENCE} years' experience, "
                f"despite final score {score}"
            )
        elif score < config.FINAL_SCORE_THRESHOLD:
            row["selection_status"] = "not_selected"
            row["selection_reason"] = (
                f"final score {score} below threshold "
                f"{config.FINAL_SCORE_THRESHOLD}"
            )
        elif len(selected) >= config.MAX_FINAL_SELECTION:
            row["selection_status"] = "not_selected"
            row["selection_reason"] = (
                f"cleared threshold but outside the top "
                f"{config.MAX_FINAL_SELECTION}"
            )
        else:
            row["selection_status"] = "selected"
            row["selection_reason"] = (
                f"final score {score} >= threshold "
                f"{config.FINAL_SCORE_THRESHOLD}; career family "
                f"{row.get('career_family') or 'n/a'} "
                f"({family_status or 'ungated'}); strongest profile match: "
                f"{row.get('strongest_profile_match') or 'n/a'}"
            )
            selected.append(row)

    return selected


def apply_ranking(rows: list, now=None) -> list:
    """Score, sort, and stamp final_rank on every row. Returns them sorted."""
    for row in rows:
        result = final_score(
            row,
            semantic_score=row.get("semantic_score") or 0.0,
            keyword_score=row.get("keyword_score"),
            now=now,
        )
        row["final_score"] = result["final_score"]
        for name, value in result["components"].items():
            row[f"component_{name}"] = round(value, 1)

    rows.sort(key=lambda r: (-float(r.get("final_score") or 0),
                            str(r.get("title") or "")))
    for i, row in enumerate(rows, start=1):
        row["final_rank"] = i
    return rows
