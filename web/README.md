# web — Job Shortlist dashboard

Next.js 15 (App Router) + TypeScript + Tailwind v4 + shadcn/ui + Supabase Auth.
Screens: `/login`, `/today` (Hari Ini), `/jobs` (Semua Job), `/jobs/[id]`,
`/runs`. Root `/` redirects to `/today`.

## Run locally

```bash
cd web
npm i
cp .env.example .env.local   # then fill in the values
npm run dev                  # http://localhost:3000
```

`npm run lint` and `npm run build` must both pass before committing.

## Environment variables (`.env.local` / Vercel)

| Name | Purpose |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key (RLS protects rows) |
| `GITHUB_TOKEN` | fine-grained PAT, Actions read/write — "Scrape sekarang" |
| `GITHUB_REPO` | `owner/name` of this repo |
| `RESUME_MODE` | `queue` (default) or `api` |
| `NEXT_PUBLIC_RESUME_PREREQ_OK` | `true` once `candidate_profile.yaml` has no `TODO_`; enables "Minta resume" (default `false`) |
| `NEXT_PUBLIC_FINAL_SCORE_THRESHOLD` | threshold shown in the "bawah 60" badge (default `60`) |

The two `NEXT_PUBLIC_*` flags are read at build time — redeploy after changing them.

## Database

Run `supabase/migrations/0001_init.sql` then `0002_views.sql` in the Supabase
SQL editor. `0002` adds the `latest_job_scores` view (jobs joined to each job's
latest scores, action row and label) that `/jobs` and `/jobs/[id]` read from.

## Layout

```
app/(auth)/login        email + password sign-in
app/(app)/today         Hari Ini — latest run (or ?run=<id>)
app/(app)/jobs          Semua Job — filters in the URL, 50/page
app/(app)/jobs/[id]     plain-page fallback for the job drawer
app/(app)/runs          run history; row click -> /today?run=<id>
app/api/scrape          POST -> GitHub workflow_dispatch daily.yml
app/api/resume          POST -> job_actions.resume_status = requested
components/             JobsTable (TanStack), drawer, selects, buttons
lib/queries.ts          server loaders   lib/actions.ts  browser writes
lib/format.ts           formatting helpers mirroring scraper/report.py
```
