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
