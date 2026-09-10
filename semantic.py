"""
Phase 3 -- local semantic matching.

A sentence-transformers model runs ON THIS MACHINE. There is no hosted
inference call and no generative LLM anywhere in this module; encoding a few
hundred short texts with a small model is cheap and deterministic.

Each profile section is embedded separately and every job is scored against
all of them, so we learn not just "how relevant" but "relevant to WHICH part
of the profile" -- that becomes strongest_profile_match.
"""

import re

import numpy as np

import config
import candidate as profile_mod

_MODEL = None

_WS_RE = re.compile(r"\s+")
_HTML_RE = re.compile(r"<[^>]+>")


def get_model(name: str = None):
    """Load the embedding model once and reuse it."""
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer  # heavy; import late
        _MODEL = SentenceTransformer(name or config.EMBEDDING_MODEL)
    return _MODEL


def clean_text(text) -> str:
    if text is None:
        return ""
    text = _HTML_RE.sub(" ", str(text))
    return _WS_RE.sub(" ", text).strip()


def job_text(job: dict) -> str:
    """
    What we embed for a job. Title and company lead because they carry the
    most signal per token; the description is truncated so encoding stays fast.
    """
    title = clean_text(job.get("title"))
    company = clean_text(job.get("company"))
    desc = clean_text(job.get("description"))[:config.MAX_JD_CHARS]
    parts = [p for p in (title, company, desc) if p]
    return ". ".join(parts)


def normalise(similarity: float) -> float:
    """
    Rescale raw cosine similarity onto a readable 0-100 range.

    The transform is FIXED (config.SEMANTIC_TRANSFORM_*) and must never be
    refit to the batch being ranked -- otherwise a job's score would change
    meaning day to day depending on what else was scraped. semantic_raw
    carries the untransformed cosine and is the source of truth.

    IMPORTANT: this is a RANKING score. It says this job looks more like the
    profile than that one does. It is NOT a probability of being hired or an
    objective measure of employment fit.
    """
    lo, hi = config.SEMANTIC_TRANSFORM_FLOOR, config.SEMANTIC_TRANSFORM_CEILING
    if hi <= lo:
        return 0.0
    scaled = (float(similarity) - lo) / (hi - lo)
    return round(max(0.0, min(1.0, scaled)) * 100.0, 1)


def _encode(model, texts, prefix):
    vecs = model.encode(
        [prefix + t for t in texts],
        batch_size=config.EMBED_BATCH_SIZE,
        normalize_embeddings=True,   # so a dot product IS cosine similarity
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return np.asarray(vecs, dtype=np.float32)


def aggregate(sims: np.ndarray, top_k: int) -> float:
    """
    Combine one job's similarity to every profile section.

    Mean over the best `top_k` sections: a job that matches fund ops,
    reconciliation and settlement strongly should win, without being punished
    for not also matching Islamic finance or Copilot training.
    """
    if sims.size == 0:
        return 0.0
    k = max(1, min(int(top_k), sims.size))
    return float(np.sort(sims)[::-1][:k].mean())


def score_jobs(jobs: list, profile: dict, model=None) -> list:
    """
    Score every job against the profile sections.

    Returns a list aligned with `jobs`, each entry:
        {semantic_score, strongest_profile_match, strongest_section_score}

    An empty input returns an empty list without loading the model at all.
    """
    if not jobs:
        return []

    names_and_texts = profile_mod.section_items(profile)
    names = [n for n, _ in names_and_texts]
    section_texts = [t for _, t in names_and_texts]

    texts = [job_text(j) for j in jobs]

    model = model or get_model()
    # e5 expects asymmetric prefixes: profile = query, job = passage.
    sec_vecs = _encode(model, section_texts, config.E5_QUERY_PREFIX)
    job_vecs = _encode(model, texts, config.E5_PASSAGE_PREFIX)

    sim = job_vecs @ sec_vecs.T          # (n_jobs, n_sections), already cosine

    results = []
    for i in range(sim.shape[0]):
        row = sim[i]
        if not texts[i]:
            # Nothing to embed (no title and no description) -- neutral, not a crash.
            results.append({
                "semantic_raw": 0.0,
                "semantic_score": 0.0,
                "strongest_profile_match": "",
                "strongest_section_score": 0.0,
            })
            continue
        best = int(np.argmax(row))
        raw = aggregate(row, config.SEMANTIC_TOP_K_SECTIONS)
        results.append({
            # semantic_raw is the untransformed cosine: stable across runs,
            # independent of the display transform, and the value any future
            # labelled calibration should be fitted against.
            "semantic_raw": round(float(raw), 4),
            "semantic_score": normalise(raw),
            "strongest_profile_match": profile_mod.pretty_section(names[best]),
            "strongest_section_score": normalise(float(row[best])),
        })
    return results
