# Daily Job Shortlist

A multi-stage job-hunting pipeline for Kuala Lumpur / Selangor finance
operations roles. Runs itself daily and emails a short, high-quality shortlist.

The whole design exists to keep expensive work rare:

```
JobSpy (~950 jobs)
   ↓  dedupe
   ↓  hard reject rules          ) deterministic Python
   ↓  keyword pre-filter         )  — free, instant
   ↓  local embeddings           ) one small model on CPU
   ↓  combined ranking           )  — free, ~5 seconds
   ↓  top 10
   ↓  strong LLM  ← at most 5 calls, ever
   ↓  tailored DOCX resume per role
   ↓  email
```

**Never** 950 LLM calls, and **never** an agent driving a browser through
snapshot → reason → click loops. That is the entire point.

## Measured funnel

From the real 952-job scrape:

| Stage | Count |
|---|---|
| Raw scraped | 952 |
| After dedupe | 461 |
| Hard rejected | 295 |
| Below keyword threshold | 124 |
| Passed keyword pre-filter | 42 |
| Semantically ranked | 42 |
| Selected for LLM analysis | 5 |

## Files

| File | Stage | What it does |
|---|---|---|
| `config.py` | — | **Every** tunable number. Nothing else hardcodes a threshold. |
| `candidate_profile.yaml` | — | Sectioned profile + accuracy constraints |
| `scraper.py` | 1 | JobSpy collection. **This is the stable, working scraper.** |
| `filters.py` | 2 | Hard rejects + keyword scoring |
| `candidate.py` | — | Loads and validates the profile |
| `semantic.py` | 3 | Local sentence-transformers ranking |
| `ranking.py` | 4 | Combined score + final selection |
| `enrich.py` | 10 | Playwright fallback seam (not implemented) |
| `llm.py` | 6 | The **only** module allowed to call a generative LLM |
| `resume.py` | 7 | Tailored ATS-friendly DOCX |
| `emailer.py` | 8 | HTML email + resume attachments |
| `pipeline.py` | — | Orchestrates everything. **Run this.** |
| `calibrate.py` | — | Retunes the similarity band against real data |

## Running it

```bash
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
python pipeline.py
```

| Flag | Effect |
|---|---|
| `--no-email` | Run everything, skip sending |
| `--from-raw` | Re-run analysis on the existing `raw_jobs.csv`, no scraping |

`--from-raw` is the one to use while tuning — it re-scores in seconds without
hitting LinkedIn or Indeed again.

## Traceability

Four CSVs are written, and no stage ever overwrites an earlier one:

| File | Contains |
|---|---|
| `raw_jobs.csv` | Everything scraped, untouched |
| `filtered_jobs.csv` | Every job with `filter_status` + `reject_reason` |
| `ranked_jobs.csv` | Survivors with `semantic_score`, `final_score`, components |
| `final_jobs.csv` | Top 10 with `selection_status` + `selection_reason` |

Every rejected job carries a reason. To see why something was dropped:

```bash
python -c "import pandas as pd; d=pd.read_csv('filtered_jobs.csv'); print(d[d.title.str.contains('Warehouse',case=False,na=False)][['title','filter_status','reject_reason']])"
```

## How the intelligence layer works

### Keyword pre-filter (Phase 2) — recall, not precision

`MIN_SCORE = 6` stays deliberately low. Its only job is removing obvious noise
before embedding. It is **not** the quality bar — raising it to fix false
positives would also drop good jobs whose wording differs from the keyword
list. Precision comes from the semantic layer instead.

Two deliberate exceptions preserved from the original rules:

- `transfer pricing` hard-rejects (tax), but `fund transfer pricing` does not
  (treasury/ALM) — negative lookbehind.
- Bare `mandarin` does **not** reject; only mandatory phrasings
  ("fluent in Mandarin", "Mandarin is a must") do.
- Alias groups (`uat` / `user acceptance testing`) score once, not twice.

### Semantic matching (Phase 3)

`intfloat/multilingual-e5-small` runs locally on CPU. Each **profile section**
is embedded separately and every job is scored against all of them, then the
best 3 are averaged. That is why `strongest_profile_match` is meaningful —
it names which part of your background the job actually resembles.

> **The match score is a ranking aid, not a hiring probability.** It says this
> posting resembles your profile more than that one does. Nothing more.

The 0–100 scale is a rescaling of raw cosine similarity, which for e5 sits in
a narrow, corpus-dependent band (measured: 0.806–0.850). `calibrate.py`
retunes `SIMILARITY_FLOOR` / `SIMILARITY_CEILING` — **run it after any
meaningful edit to `candidate_profile.yaml`**, or scores will bunch up and the
ranking will stop discriminating.

### Combined ranking (Phase 4)

Weights live in `config.WEIGHTS` and are set from the real data:

| Component | Weight | Why |
|---|---|---|
| semantic | 0.65 | Dominant, so one keyword can't float a warehouse role |
| keyword | 0.20 | Real but minority — encodes domain vocabulary |
| seniority | 0.08 | ~5 years; penalises entry-level and stretch titles |
| location | 0.05 | KL/Selangor preference |
| recency | 0.02 | Low: only Indeed supplies `date_posted` (232 of 952) |
| salary | 0.00 | JobSpy returned salary for **0 of 952** Malaysian rows |

The salary component is implemented and ready; raise its weight if that data
ever appears.

Entry-level titles (`intern`, `graduate programme`, …) are **disqualified from
selection regardless of score**. They score deceptively well because the JD
describes exactly the right work — two Principal Malaysia settlement
internships scored 82 and 80 semantically, the highest in the set. They still
appear in `ranked_jobs.csv` with a visible reason rather than vanishing.

### Strong LLM (Phase 6) — optional

Not configured by default. The pipeline runs fine without it and says so.

```bash
export LLM_PROVIDER=anthropic     # or: openai
export ANTHROPIC_API_KEY=...      # or: OPENAI_API_KEY
```

Switching provider is an env var, never a code change. `analyse_jobs()` is
hard-capped at `LLM_MAX_CALLS_PER_RUN` (5), so a misconfiguration cannot fan
out. `test_pipeline.py` asserts that no upstream stage imports `llm.py`.

### Resumes (Phase 7)

Generated only for jobs the LLM analysed, and only once
`candidate_profile.yaml` has no `TODO_` placeholders left — a resume built
from placeholder data would be worse than none.

ATS-friendly: single column, no tables, no text boxes, no headers/footers, no
images, black Calibri. Filenames are
`Azim_Shahir_<Company>_<Role>.docx`, sanitised against path traversal.

## ⚠️ Before generating any resume

`candidate_profile.yaml` currently has **10 `TODO_` placeholders** — employers,
dates, bullets, education. These were deliberately left empty rather than
invented. Semantic ranking works fine without them; resume generation is
blocked until they're filled in.

The accuracy contract in that file (`must_not_claim`, `framing_rules`) is
passed verbatim to the LLM and asserted by tests. It encodes: SS&C NAV work is
*contributing inputs to daily NAV production*, never owning the calculation;
the Agrobank ERM title is *Executive*; Microsoft Copilot Training Facilitator
always appears.

## Testing

```bash
python test_filters.py    # 12 original keyword cases
python test_pipeline.py   # 32 pipeline cases
```

Deterministic and offline. The embedding tests load the real local model and
skip loudly if it's unavailable rather than passing silently.

## Secrets

GitHub repo → Settings → Secrets and variables → Actions.

| Secret | Required | Value |
|---|---|---|
| `SMTP_USER` | yes | Gmail address |
| `SMTP_PASS` | yes | Gmail **app password**, 16 chars |
| `EMAIL_TO` | yes | Destination |
| `LLM_PROVIDER` | no | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | no | Matching key |

Never commit these.

## Schedule

Cron `11 0 * * *` = 00:11 UTC = **08:11 MYT**. Deliberately off the top of the
hour — GitHub's scheduler queues heavily at `:00` and delays those runs most.

## Not implemented on purpose

**Playwright fallback (Phase 10).** `enrich.py` holds the seam and reports
which jobs would need it. Current gaps: descriptions missing on **0 of 952**;
`job_url_direct` missing on 720 (all LinkedIn). The email already falls back to
`job_url`, so a browser dependency would buy a cosmetic gain. When implemented
it must run over shortlisted jobs only (≤5) with scripted navigation — never an
LLM driving the browser.

**LinkedIn recruiter posts (Phase 11).** Deliberately a separate future source.
Not mixed into the working job pipeline.
