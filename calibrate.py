"""
Recalibrate SIMILARITY_FLOOR / SIMILARITY_CEILING against real data.

    python calibrate.py            # uses ranked_jobs.csv
    python calibrate.py --embed    # re-embeds from raw_jobs.csv

Why this exists: e5 cosine similarity sits in a narrow, corpus-dependent band.
If the configured band is too wide, every job squashes into the middle of the
0-100 scale and the ranking stops discriminating. If it is too narrow, scores
clamp at 0 and 100. Run this after any meaningful change to
candidate_profile.yaml.
"""

import sys

import pandas as pd

import config


def from_ranked(path=None):
    df = pd.read_csv(path or config.RANKED_CSV)
    if df.empty:
        raise SystemExit(f"{path or config.RANKED_CSV} is empty -- run the pipeline first")
    lo, hi = config.SIMILARITY_FLOOR, config.SIMILARITY_CEILING
    # Undo the current normalisation to recover raw cosine.
    return df["semantic_score"] / 100.0 * (hi - lo) + lo


def from_raw(path=None):
    import candidate as profile_mod
    import enrich
    import filters
    import pipeline
    import scraper
    import semantic
    import numpy as np

    df = pd.read_csv(path or config.RAW_CSV)
    records = pipeline.to_records(scraper.dedupe(df))
    records = enrich.enrich(records)
    passed = [r for r in records if filters.score_job(r)["keep"]]
    if not passed:
        raise SystemExit("no jobs cleared the keyword filter")

    prof = profile_mod.load_profile()
    model = semantic.get_model()
    names_texts = profile_mod.section_items(prof)
    sec = semantic._encode(model, [t for _, t in names_texts], config.E5_QUERY_PREFIX)
    job = semantic._encode(model, [semantic.job_text(j) for j in passed],
                           config.E5_PASSAGE_PREFIX)
    sim = job @ sec.T
    return pd.Series([semantic.aggregate(sim[i], config.SEMANTIC_TOP_K_SECTIONS)
                      for i in range(sim.shape[0])])


def main():
    raw = from_raw() if "--embed" in sys.argv[1:] else from_ranked()

    print(f"{len(raw)} jobs\n")
    print("raw cosine distribution:")
    for label, value in (("min", raw.min()), ("p05", raw.quantile(0.05)),
                         ("p25", raw.quantile(0.25)), ("median", raw.median()),
                         ("p75", raw.quantile(0.75)), ("p95", raw.quantile(0.95)),
                         ("max", raw.max())):
        print(f"  {label:>6}  {value:.4f}")

    lo, hi = config.SIMILARITY_FLOOR, config.SIMILARITY_CEILING
    used = (raw.max() - raw.min()) / (hi - lo) * 100 if hi > lo else 0
    print(f"\ncurrent band: {lo} - {hi}  ({used:.0f}% of it actually used)")

    # A little headroom either side so a future outstanding job still has room
    # to score near 100 without clamping the whole corpus.
    suggest_lo = round(float(raw.quantile(0.05)) - 0.005, 3)
    suggest_hi = round(float(raw.quantile(0.95)) + 0.005, 3)
    print(f"suggested   : {suggest_lo} - {suggest_hi}")
    if abs(suggest_lo - lo) < 0.006 and abs(suggest_hi - hi) < 0.006:
        print("\nCurrent band is fine; no change needed.")
    else:
        print(f"\nUpdate config.py:\n  SIMILARITY_FLOOR = {suggest_lo}"
              f"\n  SIMILARITY_CEILING = {suggest_hi}")


if __name__ == "__main__":
    main()
