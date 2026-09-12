"use client";

/**
 * Browser-side writes to job_actions / validation_labels. RLS enforces
 * ownership; we only need to stamp user_id so the insert half of an upsert
 * passes the NOT NULL + with-check constraints.
 */
import { createClient } from "@/lib/supabase/client";
import type { JobActionInsert } from "@/lib/supabase/types";
import type { JobLabel, JobStatus } from "@/lib/types";

async function userId(): Promise<string> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (session?.user?.id) return session.user.id;
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) throw new Error("Sila log masuk dulu.");
  return user.id;
}

export async function upsertJobAction(
  jobId: string,
  patch: Omit<Partial<JobActionInsert>, "job_id" | "user_id">,
): Promise<void> {
  const supabase = createClient();
  const uid = await userId();
  const { error } = await supabase
    .from("job_actions")
    .upsert({ job_id: jobId, user_id: uid, ...patch }, { onConflict: "job_id" });
  if (error) throw error;
}

export async function setJobStatus(
  jobId: string,
  status: JobStatus,
  appliedDate: string | null,
): Promise<void> {
  const patch: Omit<Partial<JobActionInsert>, "job_id" | "user_id"> = {
    status,
    updated_at: new Date().toISOString(),
  };
  if (status === "applied" && !appliedDate) {
    patch.applied_date = new Date().toISOString().slice(0, 10);
  }
  await upsertJobAction(jobId, patch);
}

export async function saveNotes(jobId: string, notes: string): Promise<void> {
  await upsertJobAction(jobId, {
    notes: notes.trim() ? notes : null,
    updated_at: new Date().toISOString(),
  });
}

export async function setJobLabel(
  jobId: string,
  label: JobLabel | null,
): Promise<void> {
  const supabase = createClient();
  if (label === null) {
    const { error } = await supabase
      .from("validation_labels")
      .delete()
      .eq("job_id", jobId);
    if (error) throw error;
    return;
  }
  const uid = await userId();
  const { error } = await supabase.from("validation_labels").upsert(
    {
      job_id: jobId,
      user_id: uid,
      label,
      labelled_at: new Date().toISOString(),
    },
    { onConflict: "job_id" },
  );
  if (error) throw error;
}

/** Fetch the current resume state of one job (used by polling). */
export async function fetchResumeState(jobId: string): Promise<{
  resumeStatus: string;
  resumeUrl: string | null;
  notes: string | null;
} | null> {
  const supabase = createClient();
  const { data } = await supabase
    .from("job_actions")
    .select("resume_status, resume_url, notes")
    .eq("job_id", jobId)
    .maybeSingle();
  if (!data) return null;
  return {
    resumeStatus: data.resume_status,
    resumeUrl: data.resume_url,
    notes: data.notes,
  };
}

/** Signed download URL (1 h) for a Storage path in the `resumes` bucket. */
export async function signResumeUrl(
  path: string,
  filename: string,
): Promise<string | null> {
  const supabase = createClient();
  const { data, error } = await supabase.storage
    .from("resumes")
    .createSignedUrl(path, 3600, { download: filename });
  if (error || !data?.signedUrl) return null;
  return data.signedUrl;
}
