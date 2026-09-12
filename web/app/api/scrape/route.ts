/**
 * POST /api/scrape -- "Scrape sekarang".
 * Requires a signed-in user (401 otherwise), then fires daily.yml via
 * workflow_dispatch. The scraper writes a `runs` row within ~1 min; the UI
 * polls that table to show progress.
 */
import { NextResponse } from "next/server";

import { dispatchWorkflow, GitHubDispatchError } from "@/lib/github";
import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Sila log masuk dulu." }, { status: 401 });
  }

  // Refuse to stack runs: one `running` row at a time. daily.yml also has a
  // concurrency group, so this is only a friendlier early exit.
  const { data: running } = await supabase
    .from("runs")
    .select("id, started_at")
    .eq("status", "running")
    .order("started_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (running) {
    const ageMin = (Date.now() - Date.parse(running.started_at)) / 60000;
    if (ageMin < 45) {
      return NextResponse.json(
        {
          ok: false,
          error: "Scrape sedang berjalan. Tunggu ia siap dulu.",
          run_id: running.id,
        },
        { status: 409 },
      );
    }
  }

  try {
    await dispatchWorkflow("daily.yml");
  } catch (err) {
    const status =
      err instanceof GitHubDispatchError
        ? err.status >= 500
          ? 502
          : err.status
        : 502;
    const message = err instanceof Error ? err.message : "dispatch failed";
    return NextResponse.json({ ok: false, error: message }, { status });
  }

  return NextResponse.json(
    { ok: true, dispatched: "daily.yml" },
    { status: 202 },
  );
}
