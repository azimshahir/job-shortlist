# CLAUDE.md — Job Shortlist

Personal job-hunting system for one user (Azim, finance operations, KL). Read
`docs/PRD.md` first; it is the source of truth for scope. This file is the
working contract for anyone (human or agent) touching the repo.

## What this is

```
scraper/   Python. JobSpy → rules → local embeddings → career gating → history.
           WORKS. 81 tests. Runs on GitHub Actions (only place that can reach
           LinkedIn). Writes results to Supabase.
web/       Next.js 15 + TypeScript + Tailwind + shadcn/ui. Supabase Auth.
           One screen that matters: a table of today's jobs with Link and
           Tailored Resume buttons. Deployed on Vercel.
supabase/  Postgres schema + RLS migrations.
```

## Hard rules — do not break these

1. **The scraper's ranking logic is frozen.** `filters.py`, `semantic.py`,
   `careers.py`, `ranking.py`, `config.py` weights/thresholds: do not change
   behaviour without the user asking. Storage changes are fine.
2. **No paid LLM call anywhere except `scraper/llm.py`**, and only on the final
   ≤5 selected jobs or a single user-requested resume. `test_pipeline.py`
   asserts upstream modules never import it. Keep that test passing.
3. **Never fabricate candidate data.** `candidate_profile.yaml` has `TODO_`
   placeholders. Resume generation must stay blocked while they exist
   (`candidate.has_placeholders`). Do not fill them in — only the user can.
4. **Scraping runs on GitHub Actions only.** Vercel cannot (no torch, 10s
   limit). The Claude cloud sandbox cannot (403 on linkedin.com, verified
   2026-09-11). Do not move scraping anywhere else.
5. **Never lower `FINAL_SCORE_THRESHOLD` to fill the list.** User's principle.
6. **Secrets live in Vercel env and GitHub Secrets only.** Never in code, never
   in the repo, never in a committed `.env`.
7. **Every rejected or gated job keeps a reason.** `reject_reason`,
   `career_family_reason`, `selection_reason` must survive into Supabase and
   into the UI. Traceability is a feature, not a log.
8. **Reply to the user in Malay.** Short. They are not a developer; they say
   "tak faham" when we over-explain. Code, comments and commits stay English.

## Layout after Phase 0

```
scraper/
  pipeline.py        entry: python pipeline.py [--quiet] [--from-raw] [--sink supabase|csv]
  config.py          every tunable; SUPABASE_* read from env
  filters.py         hard rejects + keyword score        (frozen)
  semantic.py        e5-small local embeddings           (frozen)
  careers.py         career-family gate                  (frozen)
  ranking.py         combined score + selection          (frozen)
  history.py         HistoryStore interface; Sqlite, Memory, + Supabase backends
  sink.py            NEW: writes runs / jobs / job_scores to Supabase
  report.py          Markdown report (kept for /jobs in chat and Actions summary)
  llm.py, resume.py  inert until profile + key exist
  candidate.py, candidate_profile.yaml, enrich.py, calibrate.py
  test_*.py          run all four; must stay green
  requirements.txt   pinned
web/
  app/               Next.js App Router
    (auth)/login
    (app)/            today, jobs, runs, jobs/[id]
    api/scrape        POST → GitHub workflow_dispatch daily.yml
    api/resume        POST → GitHub workflow_dispatch resume.yml {job_id}
  components/        shadcn + JobsTable (TanStack)
  lib/supabase/      server + browser clients, typed
  lib/github.ts      dispatch helper (GITHUB_TOKEN, GITHUB_REPO env)
supabase/migrations/0001_init.sql
.github/workflows/daily.yml   scrape → Supabase; cron 40 23 * * * (07:40 MYT)
.github/workflows/resume.yml  workflow_dispatch {job_id} → docx → Supabase Storage
docs/PRD.md
```

## Data contract (Supabase) — Backend owns, Frontend consumes

All tables carry `user_id uuid not null` with RLS `auth.uid() = user_id`.
Scraper writes with the service-role key; web reads/writes as the signed-in user.

- `runs(id, user_id, started_at, finished_at, trigger text, status text,
  raw_count, deduped_count, hard_rejected, keyword_passed, ranked,
  career_rejected, history_excluded, selected, error text)`
- `jobs(job_id text pk, user_id, content_key, url_key, source, title, company,
  location, job_url, job_url_direct, description, date_posted, first_seen,
  last_seen, seen_count)`
- `job_scores(run_id fk, job_id fk, keyword_score int, semantic_raw numeric,
  semantic_score numeric, semantic_rank int, final_score numeric, final_rank int,
  career_family text, career_family_status text, career_family_reason text,
  selection_status text, selection_reason text, matched_keywords text[],
  strongest_profile_match text, history_status text, history_reason text,
  pk(run_id, job_id))`
- `job_actions(job_id pk fk, user_id, status text default 'new', applied_date,
  notes, resume_status text default 'none', resume_url text, updated_at)`
  status ∈ new·shortlisted·applied·interview·offer·rejected·ignored
  resume_status ∈ none·pending·ready·failed
- `validation_labels(job_id pk fk, user_id, label text, labelled_at)`
  label ∈ strong·acceptable·weak·reject
- Storage bucket `resumes` (private; signed URLs).

The scraper's `SupabaseHistoryStore` maps: `jobs` ↔ history record,
`job_actions.status='applied'` ↔ applied, `='ignored'` ↔ ignored, and
"shortlisted_before / last_shortlisted_at" from the latest `job_scores` row with
`selection_status='selected'`. Cooldown logic in `history.evaluate()` is unchanged.

## Environment variables

| Where | Name | Purpose |
|---|---|---|
| GitHub Secrets | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | scraper writes |
| GitHub Secrets | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, `LLM_PROVIDER` | resume only, optional |
| Vercel | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | web reads |
| Vercel | `GITHUB_TOKEN` (fine-grained, actions:write on this repo), `GITHUB_REPO=azimshahir/job-shortlist` | scrape/resume buttons |

## Working conventions

- Commit messages: what changed and why, English, ends with the Co-Authored-By trailer.
- Run `cd scraper && python test_filters.py && python test_pipeline.py &&
  python test_careers.py && python test_history.py` before any commit touching
  `scraper/`. All must pass.
- `web/`: `npm run build` must pass before commit. `npm run lint` too.
- Prefer boring choices. shadcn defaults, no custom design system, no animation
  library. Tables scroll horizontally on mobile; nothing else clever.
- Do not push. The user pushes. (`git pull --rebase` first — the Actions bot
  commits `shortlist.md` daily.)
- Nothing in `web/` may import from `scraper/` or vice versa. Supabase is the
  only interface between them.

## Roles (orchestrated build)

- **Orchestrator** — Phase 0 (move Python into `scraper/`, keep tests green),
  sequencing, integration, deploy checklist. Owns this file and the PRD.
- **Backend** — `supabase/migrations`, `scraper/sink.py`,
  `SupabaseHistoryStore`, `daily.yml` + `resume.yml`, `web/app/api/*`,
  `web/lib/supabase`, `web/lib/github.ts`. Delivers typed `Database` types.
- **Designer** — visual spec for the 4 screens: spacing, table density, status
  colours, the three states of the Resume button, empty/loading/error states,
  mobile behaviour. Delivers `docs/design.md` + component list. Uses shadcn
  tokens; no bespoke CSS.
- **Frontend** — `web/app/*`, `web/components/*`. Implements the Designer's spec
  against the Backend's types. Auth flow, the table, status/label dropdowns,
  Link + Resume buttons with polling, Runs page, Job detail drawer.

Backend and Designer run in parallel after Phase 0. Frontend starts once
`0001_init.sql` and `Database` types exist; may consume `design.md` incrementally.

## Definition of done (from the PRD)

User logs in from their phone, sees today's shortlist in one table, taps Link
to open a posting, taps Scrape sekarang and sees a new run complete, marks a job
Applied and it leaves Disyorkan on refresh. The Tailored Resume button exists on
every row — greyed with a clear reason until the master CV and an API key exist,
and produces a downloadable `.docx` once they do. No GitHub, Gmail or Claude Code
involved.
