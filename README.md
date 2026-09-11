# Daily Job Shortlist

A multi-stage job-hunting pipeline for Kuala Lumpur / Selangor finance
operations roles. Run it from chat with `/jobs` and get a short, high-quality shortlist as a Markdown table.

The whole design exists to keep expensive work rare:

```
JobSpy (~950 jobs)
   ↓  in-scrape dedupe
   ↓  hard reject rules          ) deterministic Python
   ↓  keyword pre-filter         )  — free, instant
   ↓  local embeddings           ) one small model on CPU
   ↓  combined ranking           )  — free, ~5 seconds
   ↓  career-family gating       ) rules + the same local model
   ↓  cross-run history          ) SQLite; suppresses repeats & applied
   ↓  top 10 → final selection
   ↓  Markdown report in chat  ←── PRODUCTION STOPS HERE TODAY
   ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ inert until explicitly enabled ┄┄┄┄┄
   ↓  strong LLM  ← at most 5 calls, ever
   ↓  tailored DOCX resume per role
```

**No paid LLM call is made today.** `LLM_PROVIDER` defaults to `none`, and
resume generation is additionally blocked while `candidate_profile.yaml`
contains `TODO_` placeholders. The daily pipeline is a pure
scrape → rules → embeddings → gating → email loop, for human validation.

**Never** 950 LLM calls, and **never** an agent driving a browser through
snapshot → reason → click loops. That is the entire point.

## Measured funnel

From the real 952-job scrape:

| Stage | Count |
|---|---|
| Raw scraped | 952 |
| After in-scrape dedupe | 461 |
| Hard rejected | 295 |
| Below keyword threshold | 124 |
| Passed keyword pre-filter | 42 |
| Semantically ranked | 42 |
| Career family OUT_OF_SCOPE | 19 |
| Suppressed by history (run 1 / run 2) | 0 / 4 |
| **Final selected** | **4** |

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
| `careers.py` | — | Career-family gating (rules + local model) |
| `history.py` | — | Cross-run dedupe; storage abstraction + SQLite |
| `enrich.py` | 10 | Playwright fallback seam (not implemented) |
| `llm.py` | 6 | The **only** module allowed to call a generative LLM |
| `resume.py` | 7 | Tailored ATS-friendly DOCX |
| `report.py` | 8 | Markdown report for chat (email was removed) |
| `pipeline.py` | — | Orchestrates everything. **Run this.** |
| `calibrate.py` | — | Evaluates the frozen transform against a **labelled** set |

## Running it

```bash
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
python pipeline.py
```

| Flag | Effect |
|---|---|
| `--quiet` | Print only the report, no stage logs |
| `--from-raw` | Re-run analysis on the existing `raw_jobs.csv`, no scraping |

`--from-raw` is the one to use while tuning — it re-scores in seconds without
hitting LinkedIn or Indeed again.

## Traceability

Four CSVs are written, and no stage ever overwrites an earlier one:

| File | Contains |
|---|---|
| `raw_jobs.csv` | Everything scraped, untouched |
| `filtered_jobs.csv` | Every job with `filter_status` + `reject_reason` |
| `ranked_jobs.csv` | Survivors with `semantic_raw`, `semantic_score`, `career_family_*`, `history_*`, `final_score`, components, and the selection verdict |
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

Two values are recorded per job:

| Field | Meaning |
|---|---|
| `semantic_raw` | The raw cosine. Source of truth, stable across runs. |
| `semantic_score` | `semantic_raw` put through a **frozen** 0–100 transform. |
| `semantic_rank` | Position within this run. |

**The transform is frozen and must never be refit to a daily batch.** An
earlier version derived it from each morning's percentiles, which was
circular: the same job scored 68 on a weak day and 51 on a strong one purely
because of what else got scraped, so scores were not comparable across days
and no fixed threshold meant anything. Rescaling is monotonic, so freezing it
costs nothing in rank order.

Legitimate recalibration needs a **persistent labelled validation set**, built
independently of any single scrape:

```
validation_labels.csv
job_url,label          # label ∈ strong | acceptable | weak | reject
```

`calibrate.py` refuses to run without it, requires at least
`VALIDATION_MIN_LABELLED` (30) rows, and never writes to `config.py` —
it prints suggested constants for you to apply by hand.
`ENABLE_AUTO_CALIBRATION` is `False`.

### Career-family gating

Semantic similarity answers *"does this resemble the candidate's
background"*. It does **not** answer *"is this the candidate's career
family"*. Compliance, IT support and fund operations share heavy vocabulary —
controls, monitoring, operations, stakeholders — so the model rates them
alike. That is the model working correctly on a different question.

Families are declared in `config.CAREER_FAMILIES` with a status of `CORE`,
`SECONDARY`, `ADJACENT` or `OUT_OF_SCOPE`. Classification is:

1. Out-of-scope **title** pattern → `OUT_OF_SCOPE`, unless a
   `CAREER_RESCUE_TERM` shows it is genuinely in-domain
   ("Compliance Officer" is out; "Fund Services Compliance Officer" is not)
2. Confirming **title** pattern → that family
3. Otherwise, embedding similarity against the family descriptors, reusing the
   model already in memory. Below `CAREER_MIN_SIMILARITY` the result is
   `UNKNOWN`, which is not actionable by default.

**A high semantic score cannot override an `OUT_OF_SCOPE` family.** The gate is
checked before the score threshold, precisely so it cannot be outvoted.
Out-of-scope jobs stay visible in `ranked_jobs.csv` with a reason; they simply
never reach `final_jobs.csv`. `CAREER_FAMILY_OVERRIDES` accepts specific
`job_url`s as an escape hatch.

### Cross-run history

`scraper.dedupe()` only removes duplicates *within* one scrape. `history.py`
remembers jobs *between* runs.

Identity is layered so a repost under a fresh URL still collapses onto the
original:

| Key | Built from |
|---|---|
| `job_id` | strongest available: external id → URL → content hash |
| `content_key` | normalised company + title + location |

Normalisation strips company suffixes (`Sdn Bhd`, `Berhad`, …), title
decoration (`(6 months contract)`, `M/F`, …), URL tracking params, and
duplicated location tokens — so *"Krypton Fund Services Sdn Bhd"* and
*"Krypton Fund Services"* fingerprint identically.

Tracked per job: `first_seen`, `last_seen`, `seen_count`,
`shortlisted_before`, `shortlist_count`, `resume_generated`, `applied`,
`applied_date`, `ignored`, `ignore_reason`.

| Status | Actionable? |
|---|---|
| `new`, `seen_not_shortlisted`, `cooldown_expired` | yes |
| `cooldown`, `repost`, `repost_cooldown` | no — shown recently |
| `applied` | **never again** |
| `ignored` | no |

Nothing is ever deleted; suppressed jobs keep full history for auditing.
Cooldowns are `SHORTLIST_COOLDOWN_DAYS` / `REPOST_COOLDOWN_DAYS` (both 14).

Mark a job applied or ignored:

```bash
python -c "import history; s=history.get_store(); s.mark_applied('<job_id>'); s.close()"
```

#### Storage, and why GitHub Actions cannot persist it

`HistoryStore` is an interface; `SqliteHistoryStore` is production,
`MemoryHistoryStore` is for tests. Pipeline logic never touches a backend
directly, so moving to a VPS or Postgres changes nothing outside `history.py`.

**GitHub Actions runners are ephemeral** — the filesystem is destroyed after
every run. The Actions cache is *not* used as a database here: it is
best-effort, evictable at any moment, has no concurrency control, and silently
loses writes. Using it would produce a history that appears to work and quietly
forgets things.

So on Actions today, history starts empty every run: nothing breaks,
cross-run dedupe simply does not apply, and the run log says so. To activate
it, pick one:

1. **Run on the VPS** (cron + a local `job_history.db`) — the intended
   destination, needs no code change, only a durable `HISTORY_DB_PATH`.
2. Point `HISTORY_DB_PATH` at a mounted network volume.
3. Add a hosted-database backend behind the same interface.

`job_history.db` is gitignored and must never be committed.

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

### Strong LLM (Phase 6) — inert by default

**Not enabled, and not required.** The production pipeline stops at the email.
`LLM_PROVIDER` defaults to `none`; the run logs "not configured" and continues.
Enable it only when you deliberately want paid analysis:

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
python test_careers.py    # 19 career-family gating cases
python test_history.py    # 17 cross-run history cases
```

80 tests total.

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

## Remaining blockers to production

| Blocker | Impact | What unblocks it |
|---|---|---|
| Cross-run history inactive on Actions | Repeats suppressed only within a run | Move execution to the VPS |
| `candidate_profile.yaml` has 10 `TODO_`s | No resume generation | Supply the master CV |
| No labelled validation set | Transform stays frozen (correct, but unvalidated) | Label ~30 jobs from `ranked_jobs.csv` |
| Career families tuned on one 952-job scrape | Unseen titles may misclassify | Review `career_family_reason` over a few weeks |
| `job_url_direct` missing on LinkedIn rows | Email links to the posting, not the ATS | Playwright fallback (Phase 10) |

## Not implemented on purpose

**Playwright fallback (Phase 10).** `enrich.py` holds the seam and reports
which jobs would need it. Current gaps: descriptions missing on **0 of 952**;
`job_url_direct` missing on 720 (all LinkedIn). The email already falls back to
`job_url`, so a browser dependency would buy a cosmetic gain. When implemented
it must run over shortlisted jobs only (≤5) with scripted navigation — never an
LLM driving the browser.

**LinkedIn recruiter posts (Phase 11).** Deliberately a separate future source.
Not mixed into the working job pipeline.
