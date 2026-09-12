"""
Semantic calibration -- from a LABELLED validation set only.

WHY THIS NO LONGER FITS THE DAILY BATCH
    An earlier version derived SIMILARITY_FLOOR / SIMILARITY_CEILING from the
    percentiles of whatever was scraped that morning. That is circular: it
    fits the scale to the very data being ranked, so the same job scores
    differently day to day depending on what else happened to be posted. A
    score of 70 stops meaning anything fixed, cross-day comparison becomes
    meaningless, and no threshold can be trusted.

    The transform is now FROZEN in config.SEMANTIC_TRANSFORM_*, and
    config.ENABLE_AUTO_CALIBRATION is False.

WHAT LEGITIMATE CALIBRATION NEEDS
    A persistent labelled validation set -- jobs the candidate has personally
    judged -- which is independent of any single day's scrape:

        validation_labels.csv
        job_url,label
        https://...,strong
        https://...,acceptable
        https://...,weak
        https://...,reject

    Build it by exporting rows from ranked_jobs.csv over a few weeks and
    labelling them by hand. At least VALIDATION_MIN_LABELLED rows are needed
    before any suggestion is offered; fitting to fewer overfits worse than not
    fitting at all.

USAGE
    python calibrate.py --report     evaluate the CURRENT frozen transform
                                     against the labelled set
    python calibrate.py --suggest    propose new constants from labels only
"""

import os
import sys

import pandas as pd

import config

LABELS = ("strong", "acceptable", "weak", "reject")
LABEL_RANK = {label: i for i, label in enumerate(reversed(LABELS))}


def load_labels(path: str = None) -> pd.DataFrame:
    path = path or config.VALIDATION_LABELS_CSV
    if not os.path.exists(path):
        raise SystemExit(
            f"No labelled validation set at {path}.\n\n"
            "Calibration deliberately refuses to fit against a daily batch --\n"
            "see the module docstring. Create the file with columns\n"
            "  job_url,label\n"
            f"where label is one of {', '.join(LABELS)}, and collect at least\n"
            f"{config.VALIDATION_MIN_LABELLED} rows by hand-labelling entries\n"
            "from ranked_jobs.csv over several runs.\n\n"
            "Until then the frozen transform in config.py stays as it is, "
            "which is the correct behaviour."
        )

    df = pd.read_csv(path)
    missing = {"job_url", "label"} - set(df.columns)
    if missing:
        raise SystemExit(f"{path} is missing column(s): {', '.join(sorted(missing))}")

    df["label"] = df["label"].astype(str).str.strip().str.lower()
    bad = sorted(set(df["label"]) - set(LABELS))
    if bad:
        raise SystemExit(f"{path} has unrecognised label(s): {bad}. "
                         f"Use one of {LABELS}.")
    return df


def join_scores(labels: pd.DataFrame, ranked_path: str = None) -> pd.DataFrame:
    """
    Attach semantic_raw to each labelled job.

    Uses ranked_jobs.csv only as a LOOKUP of already-computed scores for jobs
    the candidate labelled -- not as a distribution to fit against.
    """
    ranked_path = ranked_path or config.RANKED_CSV
    if not os.path.exists(ranked_path):
        raise SystemExit(f"{ranked_path} not found -- run the pipeline first "
                         f"so labelled jobs have scores to look up.")

    ranked = pd.read_csv(ranked_path)
    if "semantic_raw" not in ranked.columns:
        raise SystemExit(f"{ranked_path} has no semantic_raw column. "
                         f"Re-run the pipeline to regenerate it.")

    merged = labels.merge(ranked[["job_url", "semantic_raw", "title", "company"]],
                          on="job_url", how="inner")
    if merged.empty:
        raise SystemExit("No labelled job_url matched any row in "
                         f"{ranked_path}. Labels must reference jobs that "
                         "have actually been scored.")
    return merged


def report(merged: pd.DataFrame) -> None:
    lo, hi = config.SEMANTIC_TRANSFORM_FLOOR, config.SEMANTIC_TRANSFORM_CEILING
    print(f"{len(merged)} labelled jobs with scores\n")
    print("raw cosine by label:")
    for label in LABELS:
        subset = merged[merged["label"] == label]["semantic_raw"]
        if subset.empty:
            print(f"  {label:>11}  (none)")
            continue
        print(f"  {label:>11}  n={len(subset):>3}  "
              f"min {subset.min():.4f}  median {subset.median():.4f}  "
              f"max {subset.max():.4f}")

    # Separation: do 'strong' jobs actually score above 'reject' ones?
    strong = merged[merged["label"].isin(("strong", "acceptable"))]["semantic_raw"]
    weak = merged[merged["label"].isin(("weak", "reject"))]["semantic_raw"]
    if not strong.empty and not weak.empty:
        gap = strong.median() - weak.median()
        print(f"\nseparation (median good - median bad): {gap:+.4f}")
        if gap < 0.005:
            print("  WARNING: almost no separation. The profile sections, not "
                  "the transform, are what need work.")

    print(f"\ncurrent frozen transform: {lo} - {hi}")


def suggest(merged: pd.DataFrame) -> None:
    if len(merged) < config.VALIDATION_MIN_LABELLED:
        raise SystemExit(
            f"Only {len(merged)} labelled jobs; need at least "
            f"{config.VALIDATION_MIN_LABELLED}. Fitting to fewer overfits "
            f"worse than leaving the transform frozen."
        )

    weak = merged[merged["label"].isin(("weak", "reject"))]["semantic_raw"]
    strong = merged[merged["label"] == "strong"]["semantic_raw"]
    if weak.empty or strong.empty:
        raise SystemExit("Need labelled examples on both ends "
                         "(strong AND weak/reject) to fit a scale.")

    lo = round(float(weak.quantile(0.50)), 3)
    hi = round(float(strong.quantile(0.90)), 3)
    if hi <= lo:
        raise SystemExit(f"Labels do not separate (floor {lo} >= ceiling {hi}). "
                         "Improve candidate_profile.yaml before rescaling.")

    print(f"Suggested from {len(merged)} labelled jobs:")
    print(f"  SEMANTIC_TRANSFORM_FLOOR = {lo}")
    print(f"  SEMANTIC_TRANSFORM_CEILING = {hi}")
    print("\nApply by editing config.py by hand. This is deliberately not "
          "automatic -- see ENABLE_AUTO_CALIBRATION.")


def main():
    args = sys.argv[1:]
    if config.ENABLE_AUTO_CALIBRATION:
        print("WARNING: ENABLE_AUTO_CALIBRATION is True. Automatic "
              "recalibration against a daily batch is not supported and is "
              "not what this script does.\n")

    merged = join_scores(load_labels())
    report(merged)
    if "--suggest" in args:
        print()
        suggest(merged)
    else:
        print("\nRun with --suggest to propose new constants from these labels.")


if __name__ == "__main__":
    main()
