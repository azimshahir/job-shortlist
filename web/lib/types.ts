/**
 * View models shared by the screens. Frontend owns this file; the raw DB
 * shapes live in lib/supabase/types.ts (Backend).
 */
import type {
  JobStatus as DbJobStatus,
  ResumeStatus as DbResumeStatus,
  ValidationLabel,
} from "@/lib/supabase/types";

export type JobStatus = DbJobStatus;
export type JobLabel = ValidationLabel;
export type ResumeStatus = DbResumeStatus;
export type SelectionStatus =
  | "selected"
  | "out_of_scope"
  | "disqualified"
  | "not_selected"
  | `history_${string}`
  | (string & {});
export type FamilyStatus =
  | "CORE"
  | "ADJACENT"
  | "SECONDARY"
  | "OUT_OF_SCOPE"
  | "UNKNOWN"
  | (string & {});

/** One table row: jobs ⨝ job_scores (one run) ⟕ job_actions ⟕ validation_labels */
export interface JobRow {
  jobId: string;
  runId: string | null;
  title: string;
  company: string | null;
  location: string | null;
  source: string | null;
  jobUrl: string | null;
  jobUrlDirect: string | null;
  description: string | null;
  datePosted: string | null;
  firstSeen: string;
  lastSeen: string;
  seenCount: number;

  keywordScore: number | null;
  semanticRaw: number | null;
  semanticScore: number | null;
  semanticRank: number | null;
  finalScore: number | null;
  finalRank: number | null;
  careerFamily: string | null;
  careerFamilyStatus: FamilyStatus | null;
  careerFamilyReason: string | null;
  selectionStatus: SelectionStatus;
  selectionReason: string | null;
  matchedKeywords: string[];
  strongestProfileMatch: string | null;
  historyStatus: string | null;
  historyReason: string | null;

  status: JobStatus;
  appliedDate: string | null;
  notes: string | null;
  resumeStatus: ResumeStatus;
  /** Storage path inside bucket `resumes`, not a signed URL. */
  resumeUrl: string | null;
  label: JobLabel | null;
}

export interface RunRow {
  id: string;
  startedAt: string;
  finishedAt: string | null;
  trigger: string;
  status: string;
  rawCount: number;
  dedupedCount: number;
  hardRejected: number;
  keywordPassed: number;
  ranked: number;
  careerRejected: number;
  historyExcluded: number;
  selected: number;
  error: string | null;
}

/** Only one prerequisite exists in the queue-based flow: the master CV. */
export interface ResumePrereq {
  profileReady: boolean;
}

export interface JobsFilters {
  q?: string;
  status?: JobStatus;
  family?: string;
  source?: string;
  from?: string;
  to?: string;
  page?: number;
}

export interface RunRef {
  runId: string;
  startedAt: string;
}
