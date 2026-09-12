/**
 * Server-side data loaders. Every function tolerates zero rows and a missing
 * session (RLS returns nothing; we return empty values instead of throwing).
 * Import only from Server Components / Route Handlers.
 */
import "server-only";

import { PAGE_SIZE, TOP_N_RANKED } from "@/lib/env";
import { ymdMYT } from "@/lib/format";
import { createClient } from "@/lib/supabase/server";
import type {
  JobActionRow,
  JobRow as DbJobRow,
  JobScoreRow,
  LatestJobScoreRow,
  RunRow as DbRunRow,
  ValidationLabelRow,
} from "@/lib/supabase/types";
import type { JobRow, JobsFilters, RunRef, RunRow } from "@/lib/types";

// ---- mappers ---------------------------------------------------------------

export function mapRun(r: DbRunRow): RunRow {
  return {
    id: r.id,
    startedAt: r.started_at,
    finishedAt: r.finished_at,
    trigger: r.trigger,
    status: r.status,
    rawCount: r.raw_count ?? 0,
    dedupedCount: r.deduped_count ?? 0,
    hardRejected: r.hard_rejected ?? 0,
    keywordPassed: r.keyword_passed ?? 0,
    ranked: r.ranked ?? 0,
    careerRejected: r.career_rejected ?? 0,
    historyExcluded: r.history_excluded ?? 0,
    selected: r.selected ?? 0,
    error: r.error,
  };
}

const num = (v: number | string | null | undefined): number | null =>
  v == null || v === "" || !Number.isFinite(Number(v)) ? null : Number(v);

function mapJob(
  job: DbJobRow,
  score: JobScoreRow | null,
  action: JobActionRow | null,
  label: ValidationLabelRow | null,
): JobRow {
  return {
    jobId: job.job_id,
    runId: score?.run_id ?? null,
    title: job.title ?? "(tiada tajuk)",
    company: job.company,
    location: job.location,
    source: job.source,
    jobUrl: job.job_url,
    jobUrlDirect: job.job_url_direct,
    description: job.description,
    datePosted: job.date_posted,
    firstSeen: job.first_seen,
    lastSeen: job.last_seen,
    seenCount: job.seen_count ?? 1,

    keywordScore: num(score?.keyword_score),
    semanticRaw: num(score?.semantic_raw),
    semanticScore: num(score?.semantic_score),
    semanticRank: num(score?.semantic_rank),
    finalScore: num(score?.final_score),
    finalRank: num(score?.final_rank),
    careerFamily: score?.career_family ?? null,
    careerFamilyStatus: score?.career_family_status ?? null,
    careerFamilyReason: score?.career_family_reason ?? null,
    selectionStatus: score?.selection_status ?? "",
    selectionReason: score?.selection_reason ?? null,
    matchedKeywords: score?.matched_keywords ?? [],
    strongestProfileMatch: score?.strongest_profile_match ?? null,
    historyStatus: score?.history_status ?? null,
    historyReason: score?.history_reason ?? null,

    status: action?.status ?? "new",
    appliedDate: action?.applied_date ?? null,
    notes: action?.notes ?? null,
    resumeStatus: action?.resume_status ?? "none",
    resumeUrl: action?.resume_url ?? null,
    label: label?.label ?? null,
  };
}

export function mapViewRow(v: LatestJobScoreRow): JobRow {
  return {
    jobId: v.job_id,
    runId: v.run_id,
    title: v.title ?? "(tiada tajuk)",
    company: v.company,
    location: v.location,
    source: v.source,
    jobUrl: v.job_url,
    jobUrlDirect: v.job_url_direct,
    description: v.description,
    datePosted: v.date_posted,
    firstSeen: v.first_seen,
    lastSeen: v.last_seen,
    seenCount: v.seen_count ?? 1,

    keywordScore: num(v.keyword_score),
    semanticRaw: num(v.semantic_raw),
    semanticScore: num(v.semantic_score),
    semanticRank: num(v.semantic_rank),
    finalScore: num(v.final_score),
    finalRank: num(v.final_rank),
    careerFamily: v.career_family,
    careerFamilyStatus: v.career_family_status,
    careerFamilyReason: v.career_family_reason,
    selectionStatus: v.selection_status ?? "",
    selectionReason: v.selection_reason,
    matchedKeywords: v.matched_keywords ?? [],
    strongestProfileMatch: v.strongest_profile_match,
    historyStatus: v.history_status,
    historyReason: v.history_reason,

    status: v.status ?? "new",
    appliedDate: v.applied_date,
    notes: v.notes,
    resumeStatus: v.resume_status ?? "none",
    resumeUrl: v.resume_url,
    label: v.label,
  };
}

// ---- runs ------------------------------------------------------------------

export async function getLatestRun(): Promise<RunRow | null> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("runs")
    .select("*")
    .order("started_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  return data ? mapRun(data) : null;
}

export async function getRunById(id: string): Promise<RunRow | null> {
  if (!id) return null;
  const supabase = await createClient();
  const { data } = await supabase
    .from("runs")
    .select("*")
    .eq("id", id)
    .maybeSingle();
  return data ? mapRun(data) : null;
}

/** Latest run whose started_at falls on the current MYT date, or null. */
export async function getTodayRun(): Promise<RunRow | null> {
  const latest = await getLatestRun();
  if (!latest) return null;
  return ymdMYT(new Date(latest.startedAt)) === ymdMYT() ? latest : null;
}

export async function getRunsPage(
  page: number,
): Promise<{ runs: RunRow[]; total: number; pageCount: number }> {
  const supabase = await createClient();
  const safePage = Math.max(1, page || 1);
  const from = (safePage - 1) * PAGE_SIZE;
  const { data, count } = await supabase
    .from("runs")
    .select("*", { count: "exact" })
    .order("started_at", { ascending: false })
    .range(from, from + PAGE_SIZE - 1);
  const total = count ?? 0;
  return {
    runs: (data ?? []).map(mapRun),
    total,
    pageCount: Math.max(1, Math.ceil(total / PAGE_SIZE)),
  };
}

// ---- Hari Ini ---------------------------------------------------------------

/**
 * Ranked rows of one run (selected ∪ top-N by final_rank), joined to jobs,
 * job_actions and validation_labels. Sorted by final_rank.
 */
export async function getRunJobs(runId: string): Promise<JobRow[]> {
  if (!runId) return [];
  const supabase = await createClient();
  const { data: scores } = await supabase
    .from("job_scores")
    .select("*")
    .eq("run_id", runId)
    .not("final_rank", "is", null)
    .order("final_rank", { ascending: true })
    .limit(200);

  const kept = (scores ?? []).filter(
    (s) =>
      s.selection_status === "selected" ||
      (s.final_rank != null && s.final_rank <= TOP_N_RANKED),
  );
  if (kept.length === 0) return [];

  const ids = kept.map((s) => s.job_id);
  const [jobsRes, actionsRes, labelsRes] = await Promise.all([
    supabase.from("jobs").select("*").in("job_id", ids),
    supabase.from("job_actions").select("*").in("job_id", ids),
    supabase.from("validation_labels").select("*").in("job_id", ids),
  ]);
  const jobs = new Map((jobsRes.data ?? []).map((j) => [j.job_id, j]));
  const actions = new Map((actionsRes.data ?? []).map((a) => [a.job_id, a]));
  const labels = new Map((labelsRes.data ?? []).map((l) => [l.job_id, l]));

  const rows: JobRow[] = [];
  for (const s of kept) {
    const job = jobs.get(s.job_id);
    if (!job) continue;
    rows.push(
      mapJob(job, s, actions.get(s.job_id) ?? null, labels.get(s.job_id) ?? null),
    );
  }
  rows.sort((a, b) => (a.finalRank ?? 1e9) - (b.finalRank ?? 1e9));
  return rows;
}

// ---- Semua Job -------------------------------------------------------------

export async function getJobsPage(filters: JobsFilters): Promise<{
  rows: JobRow[];
  total: number;
  pageCount: number;
  page: number;
}> {
  const supabase = await createClient();
  const page = Math.max(1, filters.page || 1);
  const from = (page - 1) * PAGE_SIZE;

  let q = supabase
    .from("latest_job_scores")
    .select("*", { count: "exact" })
    .order("last_seen", { ascending: false })
    .order("final_score", { ascending: false, nullsFirst: false });

  if (filters.q) {
    const term = filters.q.replace(/[%,()]/g, " ").trim();
    if (term) q = q.or(`title.ilike.%${term}%,company.ilike.%${term}%`);
  }
  if (filters.status) q = q.eq("status", filters.status);
  if (filters.family) q = q.eq("career_family", filters.family);
  if (filters.source) q = q.eq("source", filters.source);
  if (filters.from) q = q.gte("last_seen", `${filters.from}T00:00:00+08:00`);
  if (filters.to) q = q.lte("last_seen", `${filters.to}T23:59:59+08:00`);

  const { data, count } = await q.range(from, from + PAGE_SIZE - 1);
  const total = count ?? 0;
  return {
    rows: (data ?? []).map(mapViewRow),
    total,
    pageCount: Math.max(1, Math.ceil(total / PAGE_SIZE)),
    page,
  };
}

/** Distinct filter options + header counts for Semua Job. */
export async function getJobsMeta(): Promise<{
  families: string[];
  sources: string[];
  total: number;
  shortlisted: number;
}> {
  const supabase = await createClient();
  const [famRes, srcRes, totalRes, shortRes] = await Promise.all([
    supabase
      .from("job_scores")
      .select("career_family")
      .not("career_family", "is", null)
      .limit(2000),
    supabase.from("jobs").select("source").not("source", "is", null).limit(2000),
    supabase.from("jobs").select("job_id", { count: "exact", head: true }),
    supabase
      .from("jobs")
      .select("job_id", { count: "exact", head: true })
      .eq("shortlisted_before", true),
  ]);
  const families = Array.from(
    new Set((famRes.data ?? []).map((r) => r.career_family).filter(Boolean)),
  ).sort() as string[];
  const sources = Array.from(
    new Set((srcRes.data ?? []).map((r) => r.source).filter(Boolean)),
  ).sort() as string[];
  return {
    families,
    sources,
    total: totalRes.count ?? 0,
    shortlisted: shortRes.count ?? 0,
  };
}

// ---- Job detail ------------------------------------------------------------

export async function getJobById(jobId: string): Promise<JobRow | null> {
  if (!jobId) return null;
  const supabase = await createClient();
  const { data } = await supabase
    .from("latest_job_scores")
    .select("*")
    .eq("job_id", jobId)
    .maybeSingle();
  return data ? mapViewRow(data) : null;
}

/** Runs this job appeared in, newest first (max 10). */
export async function getJobRunHistory(jobId: string): Promise<RunRef[]> {
  if (!jobId) return [];
  const supabase = await createClient();
  const { data } = await supabase
    .from("job_scores")
    .select("run_id, runs(started_at)")
    .eq("job_id", jobId)
    .limit(50);
  const refs: RunRef[] = (data ?? [])
    .map((r) => {
      const run = r.runs as unknown as { started_at: string } | null;
      return run ? { runId: r.run_id, startedAt: run.started_at } : null;
    })
    .filter((r): r is RunRef => r !== null)
    .sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt));
  return refs.slice(0, 10);
}
