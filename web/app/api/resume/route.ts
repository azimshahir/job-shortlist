/**
 * POST /api/resume  body: { job_id: string }
 *
 * Queue-based by default (RESUME_MODE unset or "queue"): validates the job
 * belongs to the signed-in user and sets job_actions.resume_status =
 * 'requested'. The user then runs `/resume` in Claude Code, which renders
 * and uploads the .docx and flips the status to 'ready'. No API key needed.
 *
 * RESUME_MODE=api (Vercel env): additionally fires resume.yml via
 * workflow_dispatch and sets 'pending'. Requires LLM_PROVIDER + key in
 * GitHub Secrets; the workflow marks 'failed' with a reason otherwise.
 */
import { NextResponse } from "next/server";

import { dispatchWorkflow, GitHubDispatchError } from "@/lib/github";
import { createClient } from "@/lib/supabase/server";
import type { ResumeStatus } from "@/lib/supabase/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Body = { job_id?: unknown };

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Sila log masuk dulu." }, { status: 401 });
  }

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json(
      { error: "Body mesti JSON { job_id }." },
      { status: 400 },
    );
  }
  const jobId = typeof body.job_id === "string" ? body.job_id.trim() : "";
  if (!jobId || jobId.length > 500) {
    return NextResponse.json({ error: "job_id diperlukan." }, { status: 400 });
  }

  // RLS already scopes to auth.uid(); the explicit filter keeps intent clear.
  const { data: job, error: jobErr } = await supabase
    .from("jobs")
    .select("job_id, title, company")
    .eq("user_id", user.id)
    .eq("job_id", jobId)
    .maybeSingle();
  if (jobErr) {
    return NextResponse.json({ error: jobErr.message }, { status: 500 });
  }
  if (!job) {
    return NextResponse.json({ error: "Job tidak dijumpai." }, { status: 404 });
  }

  const apiMode = (process.env.RESUME_MODE ?? "queue").toLowerCase() === "api";
  const status: ResumeStatus = apiMode ? "pending" : "requested";

  const { error: upsertErr } = await supabase.from("job_actions").upsert(
    {
      job_id: jobId,
      user_id: user.id,
      resume_status: status,
      resume_url: null,
    },
    { onConflict: "job_id" },
  );
  if (upsertErr) {
    return NextResponse.json({ error: upsertErr.message }, { status: 500 });
  }

  if (!apiMode) {
    return NextResponse.json(
      {
        ok: true,
        mode: "queue",
        resume_status: status,
        message:
          "Permintaan disimpan. Jalankan /resume dalam Claude Code untuk jana .docx.",
      },
      { status: 202 },
    );
  }

  try {
    await dispatchWorkflow("resume.yml", { job_id: jobId });
  } catch (err) {
    // Roll back to 'requested' so the queue path can still pick it up.
    await supabase
      .from("job_actions")
      .update({ resume_status: "requested" })
      .eq("job_id", jobId);
    const httpStatus =
      err instanceof GitHubDispatchError
        ? err.status >= 500
          ? 502
          : err.status
        : 502;
    const message = err instanceof Error ? err.message : "dispatch failed";
    return NextResponse.json(
      { ok: false, error: message },
      { status: httpStatus },
    );
  }

  return NextResponse.json(
    { ok: true, mode: "api", resume_status: status, dispatched: "resume.yml" },
    { status: 202 },
  );
}
