Run the daily job shortlist pipeline and show the results directly in chat.

Steps:
1. From the `job-scraper` folder, run `python pipeline.py --no-email` (fresh scrape; takes a few minutes). If the user says "cepat" / "quick" / "from raw", use `--from-raw` instead to re-rank the existing raw_jobs.csv without scraping.
2. Suppress progress noise (`it/s]`, HF warnings, per-search `ok`/`FAIL` lines).
3. Present, in Malay:
   - The funnel in one line: raw → hard-rejected → keyword passed → ranked → out-of-scope → history-excluded → selected
   - **Recommended** jobs as a table: rank, title (as a link to job_url_direct or job_url), company, career family + status, keyword score, semantic score (raw), final score, why selected
   - **Also ranked, not recommended**: the rest of the top 10 with the exact selection_reason, so the user can spot a wrong gate
4. If the user says a job is wrongly classified, find which rule fired (career_family_reason / selection_reason / reject_reason in the stage CSVs) and propose the specific config.py or filters.py change.

Never call a paid LLM. Never lower FINAL_SCORE_THRESHOLD just to fill the list.
