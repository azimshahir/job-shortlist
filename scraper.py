"""
Phase 1 -- collection. THIS IS THE WORKING SCRAPER; treat it as stable.

JobSpy is the primary and only collector. Playwright is not used here and is
not a fallback for bulk scraping (see enrich.py).

The scrape/dedupe logic below is unchanged in behaviour from the version that
successfully pulled 952 jobs; it now reads its settings from config.py instead
of module-level constants.

Run the whole pipeline with:  python pipeline.py
"""

import pandas as pd
from jobspy import scrape_jobs

import config


def scrape_all() -> pd.DataFrame:
    """
    Run every (search term x location) combination.

    One failing combination must not kill the run, so each is wrapped in its
    own try/except and we just carry on with the rest.
    """
    frames = []
    failures = []

    for term in config.SEARCH_TERMS:
        for loc in config.LOCATIONS:
            label = f"'{term}' @ {loc}"
            try:
                df = scrape_jobs(
                    site_name=config.SITES,
                    search_term=term,
                    location=loc,
                    results_wanted=config.RESULTS_WANTED,
                    hours_old=config.HOURS_OLD,
                    country_indeed=config.COUNTRY_INDEED,
                    linkedin_fetch_description=True,
                    verbose=0,
                )
                n = 0 if df is None else len(df)
                print(f"  ok   {label}: {n} rows", flush=True)
                if n:
                    df = df.copy()
                    df["search_term"] = term
                    df["search_location"] = loc
                    frames.append(df)
            except Exception as exc:  # noqa: BLE001 - keep going no matter what
                failures.append(f"{label}: {type(exc).__name__}: {exc}")
                print(f"  FAIL {label}: {exc}", flush=True)

    if failures:
        print(f"\n{len(failures)} search(es) failed:", flush=True)
        for f in failures:
            print(f"  - {f}", flush=True)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """Dedupe on job URL first, then on title+company as a fallback."""
    if df.empty:
        return df
    df = df.copy()
    if "job_url" in df.columns:
        df = df.drop_duplicates(subset=["job_url"], keep="first")
    key_cols = [c for c in ("title", "company") if c in df.columns]
    if key_cols:
        df["_k"] = (
            df[key_cols].fillna("").astype(str)
            .apply(lambda r: "|".join(v.strip().lower() for v in r), axis=1)
        )
        df = df.drop_duplicates(subset=["_k"], keep="first").drop(columns=["_k"])
    return df.reset_index(drop=True)


def write_raw(df: pd.DataFrame, path: str = None) -> str:
    """
    Persist the raw scrape BEFORE any filtering. Never overwritten by a later
    stage -- every downstream stage writes its own file.
    """
    path = path or config.RAW_CSV
    if df.empty:
        pd.DataFrame(columns=["site", "title", "company", "location",
                              "job_url", "job_url_direct", "date_posted",
                              "description"]).to_csv(path, index=False)
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


if __name__ == "__main__":
    # Kept so `python scraper.py` still works; the pipeline is the real entry.
    import pipeline
    raise SystemExit(pipeline.main())
