/**
 * Hand-written Database types matching supabase/migrations/0001_init.sql
 * EXACTLY. If the migration changes, change this file in the same commit.
 *
 * Usage:
 *   const supabase = await createClient();          // lib/supabase/server
 *   const { data } = await supabase.from("jobs").select("*");  // typed Row[]
 */

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

// ---- enums (check constraints in the migration) ---------------------------
export type RunTrigger = "cron" | "manual";
export type RunStatus = "running" | "ok" | "failed";

export const JOB_STATUSES = [
  "new",
  "shortlisted",
  "applied",
  "interview",
  "offer",
  "rejected",
  "ignored",
] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

export const RESUME_STATUSES = [
  "none",
  "requested",
  "pending",
  "ready",
  "failed",
] as const;
export type ResumeStatus = (typeof RESUME_STATUSES)[number];

export const VALIDATION_LABELS = [
  "strong",
  "acceptable",
  "weak",
  "reject",
] as const;
export type ValidationLabel = (typeof VALIDATION_LABELS)[number];

/** Values the scraper writes; kept as string unions for autocomplete only. */
export type FilterStatus =
  | "passed"
  | "hard_rejected"
  | "below_keyword_threshold";
export type CareerFamilyStatus =
  | "CORE"
  | "SECONDARY"
  | "ADJACENT"
  | "OUT_OF_SCOPE"
  | "UNKNOWN";
export type SelectionStatus =
  | "selected"
  | "not_selected"
  | "disqualified"
  | "out_of_scope"
  | `history_${string}`;
export type HistoryStatus =
  | "new"
  | "seen_not_shortlisted"
  | "cooldown_expired"
  | "cooldown"
  | "repost_cooldown"
  | "repost"
  | "applied"
  | "ignored";

// ---- rows ------------------------------------------------------------------
export type RunRow = {
  id: string;
  user_id: string;
  started_at: string;
  finished_at: string | null;
  trigger: RunTrigger;
  status: RunStatus;
  raw_count: number;
  deduped_count: number;
  hard_rejected: number;
  keyword_passed: number;
  ranked: number;
  career_rejected: number;
  history_excluded: number;
  selected: number;
  error: string | null;
};

export type JobRow = {
  job_id: string;
  user_id: string;
  content_key: string;
  url_key: string | null;
  source: string | null;
  title: string | null;
  company: string | null;
  location: string | null;
  job_url: string | null;
  job_url_direct: string | null;
  description: string | null;
  date_posted: string | null; // YYYY-MM-DD
  first_seen: string;
  last_seen: string;
  seen_count: number;
  shortlisted_before: boolean;
  shortlist_count: number;
  last_shortlisted_at: string | null;
};

export type JobScoreRow = {
  run_id: string;
  job_id: string;
  user_id: string;
  filter_status: FilterStatus | string | null;
  reject_reason: string | null;
  keyword_score: number | null;
  semantic_raw: number | null;
  semantic_score: number | null;
  semantic_rank: number | null;
  final_score: number | null;
  final_rank: number | null;
  career_family: string | null;
  career_family_status: CareerFamilyStatus | string | null;
  career_family_reason: string | null;
  selection_status: SelectionStatus | string | null;
  selection_reason: string | null;
  matched_keywords: string[];
  strongest_profile_match: string | null;
  history_status: HistoryStatus | string | null;
  history_reason: string | null;
};

export type JobActionRow = {
  job_id: string;
  user_id: string;
  status: JobStatus;
  applied_date: string | null; // YYYY-MM-DD
  notes: string | null;
  resume_status: ResumeStatus;
  /** Storage object path inside bucket `resumes` (NOT a signed URL). */
  resume_url: string | null;
  updated_at: string;
};

export type ValidationLabelRow = {
  job_id: string;
  user_id: string;
  label: ValidationLabel;
  labelled_at: string;
};

// ---- Insert / Update shapes (defaults and generated columns optional) ------
type Optional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

export type RunInsert = Optional<
  RunRow,
  | "id"
  | "started_at"
  | "finished_at"
  | "trigger"
  | "status"
  | "raw_count"
  | "deduped_count"
  | "hard_rejected"
  | "keyword_passed"
  | "ranked"
  | "career_rejected"
  | "history_excluded"
  | "selected"
  | "error"
>;
export type JobInsert = Optional<
  JobRow,
  | "url_key"
  | "source"
  | "title"
  | "company"
  | "location"
  | "job_url"
  | "job_url_direct"
  | "description"
  | "date_posted"
  | "first_seen"
  | "last_seen"
  | "seen_count"
  | "shortlisted_before"
  | "shortlist_count"
  | "last_shortlisted_at"
>;
export type JobScoreInsert = Optional<
  JobScoreRow,
  Exclude<keyof JobScoreRow, "run_id" | "job_id" | "user_id">
>;
export type JobActionInsert = Optional<
  JobActionRow,
  "status" | "applied_date" | "notes" | "resume_status" | "resume_url" | "updated_at"
>;
export type ValidationLabelInsert = Optional<ValidationLabelRow, "labelled_at">;

// ---- supabase-js Database shape ------------------------------------------
export type Database = {
  public: {
    Tables: {
      runs: {
        Row: RunRow;
        Insert: RunInsert;
        Update: Partial<RunRow>;
        Relationships: [];
      };
      jobs: {
        Row: JobRow;
        Insert: JobInsert;
        Update: Partial<JobRow>;
        Relationships: [];
      };
      job_scores: {
        Row: JobScoreRow;
        Insert: JobScoreInsert;
        Update: Partial<JobScoreRow>;
        Relationships: [
          {
            foreignKeyName: "job_scores_run_id_fkey";
            columns: ["run_id"];
            isOneToOne: false;
            referencedRelation: "runs";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "job_scores_job_id_fkey";
            columns: ["job_id"];
            isOneToOne: false;
            referencedRelation: "jobs";
            referencedColumns: ["job_id"];
          },
        ];
      };
      job_actions: {
        Row: JobActionRow;
        Insert: JobActionInsert;
        Update: Partial<JobActionRow>;
        Relationships: [
          {
            foreignKeyName: "job_actions_job_id_fkey";
            columns: ["job_id"];
            isOneToOne: true;
            referencedRelation: "jobs";
            referencedColumns: ["job_id"];
          },
        ];
      };
      validation_labels: {
        Row: ValidationLabelRow;
        Insert: ValidationLabelInsert;
        Update: Partial<ValidationLabelRow>;
        Relationships: [
          {
            foreignKeyName: "validation_labels_job_id_fkey";
            columns: ["job_id"];
            isOneToOne: true;
            referencedRelation: "jobs";
            referencedColumns: ["job_id"];
          },
        ];
      };
    };
    Views: { [_ in never]: never };
    Functions: { [_ in never]: never };
    Enums: { [_ in never]: never };
    CompositeTypes: { [_ in never]: never };
  };
};

/** Private Storage bucket holding `<user_id>/<safe job_id>.docx`. */
export const RESUMES_BUCKET = "resumes";

export type Tables<T extends keyof Database["public"]["Tables"]> =
  Database["public"]["Tables"][T]["Row"];
