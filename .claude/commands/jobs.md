Run the job shortlist pipeline and show the results in chat. Reply in Malay.

Steps:
1. From the `job-scraper` folder run `python pipeline.py --quiet` (fresh scrape, a few minutes). If the user says "cepat" / "quick" / "from raw", run `python pipeline.py --from-raw --quiet` instead — it re-ranks the last scrape in seconds.
2. The script prints a Markdown report (also saved to `shortlist.md`). Paste that report to the user as-is — it already has the funnel line, the **Disyorkan** table, and the **Ranked, tak disyorkan** table with a `Source` column and the reason each job was gated.
3. Ignore progress noise (`it/s]`, Hugging Face warnings).
4. Add at most 2–3 sentences of your own: point out anything that looks misclassified (e.g. a banking-operations job tagged as retail), and note jobs that missed the threshold by only 1–2 points. Do NOT change `FINAL_SCORE_THRESHOLD` or any rule without asking first.
5. If the user says a job is wrongly placed, find the rule that fired (`career_family_reason`, `selection_reason`, or `reject_reason` in the stage CSVs) and propose the exact change in `config.py` or `filters.py`.

Never call a paid LLM. Never lower the standard just to fill the list.
