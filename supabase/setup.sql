-- ONE-SHOT SETUP: paste this whole file into Supabase > SQL Editor > Run.
-- Generated from migrations/0001_init.sql + 0002_views.sql. Safe to re-run.

-- 0001_init.sql -- Job Shortlist data contract (see CLAUDE.md "Data contract").
--
-- Two writers, one schema:
--   * The scraper (GitHub Actions) writes with the SERVICE ROLE key, which
--     bypasses RLS. It stamps every row with SUPABASE_USER_ID so the rows
--     belong to the single signed-in user.
--   * The web app (Vercel) reads and writes as the SIGNED-IN USER through the
--     anon key + session cookie. Every table has RLS with
--     `auth.uid() = user_id`, so a user only ever sees their own rows.
--
-- Run once in the Supabase SQL editor (or `supabase db push`). Idempotent
-- where Postgres allows it.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- runs: one row per pipeline execution (cron or manual)
-- ---------------------------------------------------------------------------
create table if not exists public.runs (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references auth.users (id) on delete cascade,
  started_at       timestamptz not null default now(),
  finished_at      timestamptz,
  trigger          text not null default 'manual'
                   check (trigger in ('cron', 'manual')),
  status           text not null default 'running'
                   check (status in ('running', 'ok', 'failed')),
  raw_count        integer not null default 0,
  deduped_count    integer not null default 0,
  hard_rejected    integer not null default 0,
  keyword_passed   integer not null default 0,
  ranked           integer not null default 0,
  career_rejected  integer not null default 0,
  history_excluded integer not null default 0,
  selected         integer not null default 0,
  error            text
);

create index if not exists runs_user_started_idx
  on public.runs (user_id, started_at desc);

-- ---------------------------------------------------------------------------
-- jobs: one row per unique job (identity from scraper/history.py)
-- The three shortlisted_* columns are denormalised from job_scores so the
-- scraper's SupabaseHistoryStore can load history in a single query.
-- ---------------------------------------------------------------------------
create table if not exists public.jobs (
  job_id              text primary key,
  user_id             uuid not null references auth.users (id) on delete cascade,
  content_key         text not null,
  url_key             text,
  source              text,
  title               text,
  company             text,
  location            text,
  job_url             text,
  job_url_direct      text,
  description         text,
  date_posted         date,
  first_seen          timestamptz not null default now(),
  last_seen           timestamptz not null default now(),
  seen_count          integer not null default 1,
  shortlisted_before  boolean not null default false,
  shortlist_count     integer not null default 0,
  last_shortlisted_at timestamptz
);

create index if not exists jobs_user_last_seen_idx
  on public.jobs (user_id, last_seen desc);
create index if not exists jobs_content_key_idx
  on public.jobs (user_id, content_key);

-- ---------------------------------------------------------------------------
-- job_scores: how one job scored in one run. Includes hard-rejected jobs
-- (filter_status / reject_reason) so the dashboard can explain every verdict.
-- ---------------------------------------------------------------------------
create table if not exists public.job_scores (
  run_id                  uuid not null references public.runs (id) on delete cascade,
  job_id                  text not null references public.jobs (job_id) on delete cascade,
  user_id                 uuid not null references auth.users (id) on delete cascade,
  filter_status           text,
  reject_reason           text,
  keyword_score           integer,
  semantic_raw            numeric,
  semantic_score          numeric,
  semantic_rank           integer,
  final_score             numeric,
  final_rank              integer,
  career_family           text,
  career_family_status    text,
  career_family_reason    text,
  selection_status        text,
  selection_reason        text,
  matched_keywords        text[] not null default '{}',
  strongest_profile_match text,
  history_status          text,
  history_reason          text,
  primary key (run_id, job_id)
);

create index if not exists job_scores_run_idx on public.job_scores (run_id);
create index if not exists job_scores_job_idx on public.job_scores (job_id);
create index if not exists job_scores_user_selected_idx
  on public.job_scores (user_id, selection_status);

-- ---------------------------------------------------------------------------
-- job_actions: the user's tracking state for a job (one row per job)
-- ---------------------------------------------------------------------------
create table if not exists public.job_actions (
  job_id        text primary key references public.jobs (job_id) on delete cascade,
  user_id       uuid not null references auth.users (id) on delete cascade,
  status        text not null default 'new'
                check (status in ('new', 'shortlisted', 'applied', 'interview',
                                  'offer', 'rejected', 'ignored')),
  applied_date  date,
  notes         text,
  resume_status text not null default 'none'
                check (resume_status in ('none', 'requested', 'pending', 'ready', 'failed')),
  resume_url    text,
  updated_at    timestamptz not null default now()
);

create index if not exists job_actions_user_status_idx
  on public.job_actions (user_id, status);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists job_actions_set_updated_at on public.job_actions;
create trigger job_actions_set_updated_at
  before update on public.job_actions
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- validation_labels: calibration input (calibrate.py)
-- ---------------------------------------------------------------------------
create table if not exists public.validation_labels (
  job_id      text primary key references public.jobs (job_id) on delete cascade,
  user_id     uuid not null references auth.users (id) on delete cascade,
  label       text not null
              check (label in ('strong', 'acceptable', 'weak', 'reject')),
  labelled_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Row Level Security: the signed-in user sees only their own rows.
-- The service role key bypasses RLS, which is how the scraper writes.
-- ---------------------------------------------------------------------------
alter table public.runs              enable row level security;
alter table public.jobs              enable row level security;
alter table public.job_scores        enable row level security;
alter table public.job_actions       enable row level security;
alter table public.validation_labels enable row level security;

do $$
declare
  t text;
begin
  foreach t in array array['runs', 'jobs', 'job_scores', 'job_actions',
                           'validation_labels']
  loop
    execute format('drop policy if exists %I on public.%I', t || '_select_own', t);
    execute format('drop policy if exists %I on public.%I', t || '_insert_own', t);
    execute format('drop policy if exists %I on public.%I', t || '_update_own', t);
    execute format('drop policy if exists %I on public.%I', t || '_delete_own', t);

    execute format(
      'create policy %I on public.%I for select to authenticated using (auth.uid() = user_id)',
      t || '_select_own', t);
    execute format(
      'create policy %I on public.%I for insert to authenticated with check (auth.uid() = user_id)',
      t || '_insert_own', t);
    execute format(
      'create policy %I on public.%I for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id)',
      t || '_update_own', t);
    execute format(
      'create policy %I on public.%I for delete to authenticated using (auth.uid() = user_id)',
      t || '_delete_own', t);
  end loop;
end;
$$;

-- ---------------------------------------------------------------------------
-- Storage: private bucket `resumes`. Objects live at <user_id>/<job_id>.docx
-- and only the owner (first path segment == auth.uid()) can read them.
-- The resume workflow uploads with the service role key.
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('resumes', 'resumes', false)
on conflict (id) do update set public = false;

drop policy if exists "resumes_owner_select" on storage.objects;
create policy "resumes_owner_select"
  on storage.objects for select to authenticated
  using (
    bucket_id = 'resumes'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists "resumes_owner_delete" on storage.objects;
create policy "resumes_owner_delete"
  on storage.objects for delete to authenticated
  using (
    bucket_id = 'resumes'
    and (storage.foldername(name))[1] = auth.uid()::text
  );


-- 0002_views.sql -- one flat row per job with its LATEST scores, the user's
-- action row and label. Used by /jobs (Semua Job) and /jobs/[id].
--
-- security_invoker = true: the view runs with the caller's privileges, so the
-- RLS policies on jobs / job_scores / runs / job_actions / validation_labels
-- still apply and a user only ever sees their own rows.
--
-- Run after 0001_init.sql in the Supabase SQL editor. Idempotent.

create or replace view public.latest_job_scores
with (security_invoker = true) as
select
  j.job_id,
  j.user_id,
  j.source,
  j.title,
  j.company,
  j.location,
  j.job_url,
  j.job_url_direct,
  j.description,
  j.date_posted,
  j.first_seen,
  j.last_seen,
  j.seen_count,
  j.shortlisted_before,
  j.shortlist_count,
  j.last_shortlisted_at,
  s.run_id,
  s.filter_status,
  s.reject_reason,
  s.keyword_score,
  s.semantic_raw,
  s.semantic_score,
  s.semantic_rank,
  s.final_score,
  s.final_rank,
  s.career_family,
  s.career_family_status,
  s.career_family_reason,
  s.selection_status,
  s.selection_reason,
  coalesce(s.matched_keywords, '{}'::text[]) as matched_keywords,
  s.strongest_profile_match,
  s.history_status,
  s.history_reason,
  coalesce(a.status, 'new')         as status,
  a.applied_date,
  a.notes,
  coalesce(a.resume_status, 'none') as resume_status,
  a.resume_url,
  l.label
from public.jobs j
left join lateral (
  select s.*
  from public.job_scores s
  join public.runs r on r.id = s.run_id
  where s.job_id = j.job_id
  order by r.started_at desc
  limit 1
) s on true
left join public.job_actions a on a.job_id = j.job_id
left join public.validation_labels l on l.job_id = j.job_id;

grant select on public.latest_job_scores to authenticated;
