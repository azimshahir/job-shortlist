"""
Pipeline entry point.

    JobSpy -> dedupe -> hard reject -> keyword pre-filter
           -> local embeddings -> combined rank -> top N
           -> (optional) strong LLM on 3-5 jobs -> tailored DOCX -> email

Cost shape, by design:
    ~950 jobs -> deterministic Python -> local embeddings -> ~10 candidates
             -> at most 5 LLM calls.
Never ~950 LLM calls, and never an agent driving a browser.

    python pipeline.py                 full run
    python pipeline.py --no-email      run everything, skip sending
    python pipeline.py --from-raw      re-run analysis on the existing
                                       raw_jobs.csv (no scraping)
"""

import sys
import traceback
from datetime import datetime

import pandas as pd

import config
import emailer
import enrich
import filters
import candidate as profile_mod
import ranking
import scraper
import semantic


def _s(value, default=""):
    """CSV round-trips turn missing values into the string 'nan'."""
    if value is None:
        return default
    text = str(value)
    return default if text.strip().lower() in ("nan", "nat", "none", "") else text


def to_records(df: pd.DataFrame) -> list:
    return [] if df is None or df.empty else df.to_dict("records")


# --------------------------------------------------------------------------
# Phase 2 -- hard reject + keyword pre-filter
# --------------------------------------------------------------------------
def apply_filters(records: list) -> tuple:
    """
    Returns (passed, all_rows). `all_rows` keeps EVERY job with its verdict so
    filtered_jobs.csv explains each rejection.
    """
    passed, all_rows = [], []

    for job in records:
        verdict = filters.score_job(job)
        row = dict(job)
        row["source"] = _s(job.get("site"))
        row["keyword_score"] = verdict["score"]
        row["matched_keywords"] = verdict["matched"]
        row["description_status"] = enrich.description_status(job)

        if verdict["rejected_by"]:
            row["filter_status"] = "hard_rejected"
            row["reject_reason"] = "hard reject: " + ", ".join(verdict["rejected_by"])
        elif not verdict["keep"]:
            row["filter_status"] = "below_keyword_threshold"
            row["reject_reason"] = (
                f"keyword score {verdict['score']} < MIN_SCORE {filters.MIN_SCORE}"
            )
        else:
            row["filter_status"] = "passed"
            row["reject_reason"] = ""
            passed.append(row)

        all_rows.append(row)

    return passed, all_rows


# --------------------------------------------------------------------------
# Phase 3 -- local embeddings
# --------------------------------------------------------------------------
def apply_semantic(rows: list, candidate_profile: dict) -> list:
    if not rows:
        return rows
    scores = semantic.score_jobs(rows, candidate_profile)
    for row, result in zip(rows, scores):
        row.update(result)
    ordered = sorted(rows, key=lambda r: -float(r.get("semantic_score") or 0))
    for i, row in enumerate(ordered, start=1):
        row["semantic_rank"] = i
    return ordered


# --------------------------------------------------------------------------
# CSV writing
# --------------------------------------------------------------------------
def write_stage(rows: list, path: str, extra_cols=()) -> str:
    cols = list(config.TRACE_COLUMNS) + [
        "semantic_rank", "final_rank", "matched_keywords",
        "search_term", "enrichment_needed",
    ] + list(extra_cols)

    if not rows:
        pd.DataFrame(columns=cols).to_csv(path, index=False)
        return path

    out = []
    for row in rows:
        record = {}
        for col in cols:
            value = row.get(col)
            if col == "salary" and value is None:
                value = emailer._fmt_salary(row)
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            record[col] = value
        out.append(record)
    pd.DataFrame(out, columns=cols).to_csv(path, index=False, encoding="utf-8-sig")
    return path


# --------------------------------------------------------------------------
def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    no_email = "--no-email" in argv
    from_raw = "--from-raw" in argv

    started = datetime.now(emailer.MYT)
    print(f"Run started {started.isoformat()} (MYT)", flush=True)

    # ---- Phase 1: collect -------------------------------------------------
    if from_raw:
        print(f"Reading existing {config.RAW_CSV} (no scraping)", flush=True)
        raw = pd.read_csv(config.RAW_CSV)
    else:
        raw = scraper.scrape_all()
        scraper.write_raw(raw)
        print(f"Wrote {config.RAW_CSV}", flush=True)

    n_raw = len(raw)
    print(f"\nScraped {n_raw} raw rows", flush=True)

    deduped = scraper.dedupe(raw)
    records = to_records(deduped)
    print(f"{len(records)} rows after dedupe", flush=True)

    # Stamps description_status / enrichment_needed. No browser is launched.
    records = enrich.enrich(records)

    # ---- Phase 2: hard reject + keyword pre-filter ------------------------
    passed, all_filtered = apply_filters(records)
    n_hard = sum(1 for r in all_filtered if r["filter_status"] == "hard_rejected")
    n_low = sum(1 for r in all_filtered
                if r["filter_status"] == "below_keyword_threshold")
    write_stage(all_filtered, config.FILTERED_CSV)
    print(f"Filter: {n_hard} hard-rejected, {n_low} below keyword threshold, "
          f"{len(passed)} passed -> {config.FILTERED_CSV}", flush=True)

    # ---- Phase 3+4: semantic ranking then combined ranking -----------------
    candidate_profile = profile_mod.load_profile()
    ranked = []
    if passed:
        print(f"Embedding {len(passed)} jobs locally with "
              f"{config.EMBEDDING_MODEL} ...", flush=True)
        ranked = apply_semantic(passed, candidate_profile)
        ranked = ranking.apply_ranking(ranked)
    write_stage(ranked, config.RANKED_CSV,
                extra_cols=[f"component_{k}" for k in config.WEIGHTS])
    print(f"Ranked {len(ranked)} jobs -> {config.RANKED_CSV}", flush=True)

    top = ranked[:config.TOP_N_RANKED]
    selected = ranking.select_final(top)
    for i, row in enumerate(selected, start=1):
        row["final_rank_display"] = i
    write_stage(top, config.FINAL_CSV,
                extra_cols=[f"component_{k}" for k in config.WEIGHTS])
    print(f"Selected {len(selected)} of the top {len(top)} for deep analysis "
          f"-> {config.FINAL_CSV}", flush=True)

    # ---- Phase 6: strong LLM, on the final few ONLY -----------------------
    attachments = []
    if selected:
        import llm  # imported here so no upstream stage can pull it in
        analysed = llm.analyse_jobs(selected, candidate_profile)
        for item in analysed:
            job = item["job"]
            if item["status"] == "ok":
                job["llm_analysis"] = item["analysis"]
            else:
                job["llm_note"] = item["error"]
        if llm.is_configured():
            print(f"Strong LLM: {sum(1 for a in analysed if a['status'] == 'ok')} "
                  f"of {len(analysed)} analysed", flush=True)
        else:
            print("Strong LLM: not configured -- skipping JD analysis and "
                  "resume generation (this is expected, not an error)", flush=True)

        # ---- Phase 7: tailored resumes ------------------------------------
        placeholders = profile_mod.has_placeholders(candidate_profile)
        if any(a["status"] == "ok" for a in analysed):
            if placeholders:
                print(f"Resumes skipped: candidate_profile.yaml still has "
                      f"{len(placeholders)} TODO_ placeholder(s)", flush=True)
            else:
                import resume
                for res in resume.generate_resumes(analysed, candidate_profile):
                    if res["status"] == "ok":
                        attachments.append(res["path"])
                        print(f"  resume: {res['path']}", flush=True)
                    else:
                        print(f"  resume skipped: {res['error']}", flush=True)

    # ---- Stats ------------------------------------------------------------
    stats = {
        "raw": n_raw,
        "deduped": len(records),
        "hard_rejected": n_hard,
        "keyword_passed": len(passed),
        "ranked": len(ranked),
        "selected": len(selected),
    }
    print(f"\nStats: {stats}", flush=True)
    for row in top:
        print(f"  [{row.get('final_rank')}] {row.get('final_score'):>5} "
              f"(kw {row.get('keyword_score')}, sem {row.get('semantic_score')}) "
              f"{str(row.get('title'))[:48]} - {str(row.get('company'))[:24]}",
              flush=True)

    # ---- Phase 8: email ---------------------------------------------------
    if no_email:
        print("\n--no-email: skipping send", flush=True)
        return 0

    html = emailer.build_html(selected, stats)
    try:
        emailer.send_email(html, emailer.subject_for(stats), attachments)
    except Exception as exc:  # noqa: BLE001
        print(f"\nEMAIL FAILED: {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
