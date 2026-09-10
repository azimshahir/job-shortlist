"""
Career-family gating -- runs AFTER semantic ranking, BEFORE final selection.

Why this exists: semantic similarity measures "does this text resemble the
candidate's background". It does NOT measure "is this the candidate's career
family". A financial-crime compliance role and a fund reconciliation role
share a great deal of vocabulary -- controls, monitoring, operations,
stakeholders, regulatory reporting -- so the embedding model rates them
similarly. That is the model behaving correctly; it is simply answering a
different question than the one that should gate the shortlist.

Cost: deterministic rules plus the SAME local embedding model already loaded
for semantic ranking. No strong LLM, no extra model, no API call.

Precedence (first match wins):
  1. Disqualifying title pattern  -> OUT_OF_SCOPE, unless a rescue term shows
     the role is genuinely in the target domain
     ("Compliance" is out; "Fund Services Compliance" is not)
  2. Confirming title pattern     -> that family directly
  3. Embedding similarity against family descriptors
"""

import re

import numpy as np

import config

CORE = "CORE"
SECONDARY = "SECONDARY"
ADJACENT = "ADJACENT"
OUT_OF_SCOPE = "OUT_OF_SCOPE"
UNKNOWN = "UNKNOWN"

ACTIONABLE_STATUSES = (CORE, SECONDARY, ADJACENT)

_FAMILY_VECS = None
_FAMILY_ORDER = None


def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _has_any(text: str, terms) -> str:
    """Return the first matching term, or ''. Word-boundary aware."""
    for term in terms:
        pattern = r"(?<![a-z0-9])" + r"\s+".join(re.escape(w) for w in term.split()) \
                  + r"(?![a-z0-9])"
        if re.search(pattern, text):
            return term
    return ""


def classify_by_rules(job: dict) -> dict:
    """
    Deterministic pass over title + description.

    Returns a verdict dict, or None to defer to the embedding pass.
    """
    title = _norm(job.get("title"))
    desc = _norm(job.get("description"))
    blob = f"{title} {desc}"

    # --- 1. Disqualifiers, checked against the TITLE ---------------------
    # A title is the employer's own summary of the job; it is a far more
    # reliable disqualifier than description text, which often mentions
    # adjacent work in passing.
    for family, spec in config.CAREER_FAMILIES.items():
        if spec["status"] != OUT_OF_SCOPE:
            continue
        hit = _has_any(title, spec.get("title_terms", ()))
        if not hit:
            continue

        # Rescue: the role is nominally out of scope but explicitly sits in
        # the target domain, e.g. "Fund Services Compliance Officer".
        rescue = _has_any(blob, config.CAREER_RESCUE_TERMS)
        if rescue and _has_any(title, config.CAREER_RESCUE_TERMS):
            continue  # fall through to the CORE checks below

        return {
            "career_family": family,
            "career_family_status": OUT_OF_SCOPE,
            "career_family_score": 100.0,
            "career_family_reason": (
                f"title matches out-of-scope family '{family}' "
                f"(matched: '{hit}')"
            ),
            "career_family_method": "rule:title_disqualifier",
        }

    # --- 2. Confirmers, checked against the TITLE ------------------------
    for status in (CORE, SECONDARY, ADJACENT):
        for family, spec in config.CAREER_FAMILIES.items():
            if spec["status"] != status:
                continue
            hit = _has_any(title, spec.get("title_terms", ()))
            if hit:
                return {
                    "career_family": family,
                    "career_family_status": status,
                    "career_family_score": 100.0,
                    "career_family_reason": (
                        f"title matches {status} family '{family}' "
                        f"(matched: '{hit}')"
                    ),
                    "career_family_method": "rule:title_confirmer",
                }

    return None


def _family_vectors(model):
    """Embed each family descriptor once per process."""
    global _FAMILY_VECS, _FAMILY_ORDER
    if _FAMILY_VECS is None:
        import semantic
        _FAMILY_ORDER = sorted(config.CAREER_FAMILIES)
        descriptors = [config.CAREER_FAMILIES[f]["descriptor"]
                       for f in _FAMILY_ORDER]
        _FAMILY_VECS = semantic._encode(model, descriptors,
                                        config.E5_QUERY_PREFIX)
    return _FAMILY_ORDER, _FAMILY_VECS


def classify_by_embedding(jobs: list, model=None) -> list:
    """
    Assign each job to its nearest career family using the local model.

    Reuses the model already loaded for semantic ranking, so this costs one
    extra matrix multiply against ~12 short descriptors.
    """
    import semantic

    if not jobs:
        return []
    model = model or semantic.get_model()
    order, fam_vecs = _family_vectors(model)

    job_vecs = semantic._encode(model, [semantic.job_text(j) for j in jobs],
                                config.E5_PASSAGE_PREFIX)
    sim = job_vecs @ fam_vecs.T

    out = []
    for i in range(sim.shape[0]):
        row = sim[i]
        best = int(np.argmax(row))
        family = order[best]
        status = config.CAREER_FAMILIES[family]["status"]
        raw = float(row[best])
        margin = raw - float(np.sort(row)[-2]) if row.size > 1 else 0.0

        # A weak or ambiguous assignment is reported as UNKNOWN rather than
        # guessed. UNKNOWN is treated conservatively at selection time.
        if raw < config.CAREER_MIN_SIMILARITY:
            out.append({
                "career_family": family,
                "career_family_status": UNKNOWN,
                "career_family_score": round(raw * 100, 1),
                "career_family_reason": (
                    f"nearest family '{family}' but similarity {raw:.3f} is "
                    f"below {config.CAREER_MIN_SIMILARITY}"
                ),
                "career_family_method": "embedding:weak",
            })
            continue

        out.append({
            "career_family": family,
            "career_family_status": status,
            "career_family_score": round(raw * 100, 1),
            "career_family_reason": (
                f"closest family '{family}' ({status}) at similarity "
                f"{raw:.3f}, margin {margin:.3f} over next"
            ),
            "career_family_method": "embedding",
        })
    return out


def classify(jobs: list, model=None) -> list:
    """
    Classify every job. Rules first, embedding for whatever they don't settle.
    Returns a list aligned with `jobs`.
    """
    if not jobs:
        return []

    results = [None] * len(jobs)
    deferred_idx = []

    for i, job in enumerate(jobs):
        verdict = classify_by_rules(job)
        if verdict is None:
            deferred_idx.append(i)
        else:
            results[i] = verdict

    if deferred_idx:
        deferred = [jobs[i] for i in deferred_idx]
        for i, verdict in zip(deferred_idx,
                              classify_by_embedding(deferred, model=model)):
            results[i] = verdict

    return results


def is_actionable(status: str) -> bool:
    """
    Which statuses may reach final_jobs.csv.

    OUT_OF_SCOPE never can, regardless of semantic score -- that is the whole
    point of this stage. UNKNOWN is included only if configured.
    """
    if status in ACTIONABLE_STATUSES:
        return True
    if status == UNKNOWN:
        return config.CAREER_ALLOW_UNKNOWN
    return False


def apply(jobs: list, model=None) -> list:
    """Stamp career_family_* fields onto each job in place."""
    for job, verdict in zip(jobs, classify(jobs, model=model)):
        job.update(verdict)
    return jobs
