"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { createClient } from "@/lib/supabase/client";
import type { RunRow } from "@/lib/types";

const POLL_MS = 10_000;
const POLL_CAP_MS = 20 * 60_000;

type Phase = "idle" | "dispatching" | "running";

export interface ScrapeButtonProps {
  latestRun: Pick<RunRow, "id" | "status" | "startedAt" | "selected" | "error"> | null;
}

export function ScrapeButton({ latestRun }: ScrapeButtonProps) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>(
    latestRun?.status === "running" ? "running" : "idle",
  );
  // Runs that started at or after this instant count as "the new run".
  const sinceRef = useRef<number>(
    latestRun?.status === "running"
      ? Date.parse(latestRun.startedAt) - 1
      : Date.now(),
  );

  useEffect(() => {
    if (phase !== "running") return;
    const supabase = createClient();
    const startedPolling = Date.now();
    let cancelled = false;

    const tick = async () => {
      if (cancelled) return;
      if (Date.now() - startedPolling > POLL_CAP_MS) {
        setPhase("idle");
        toast("Masih belum siap — semak Runs");
        return;
      }
      const { data } = await supabase
        .from("runs")
        .select("id, status, started_at, selected, error")
        .order("started_at", { ascending: false })
        .limit(1)
        .maybeSingle();
      if (cancelled || !data) return;
      const isNew = Date.parse(data.started_at) >= sinceRef.current;
      if (!isNew || data.status === "running") return;
      setPhase("idle");
      if (data.status === "ok") {
        toast.success(`Scrape siap — ${data.selected ?? 0} disyorkan`);
      } else {
        toast.error(`Scrape gagal: ${data.error || "tiada respons dari GitHub"}`);
      }
      router.refresh();
    };

    const id = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [phase, router]);

  async function onClick() {
    setPhase("dispatching");
    sinceRef.current = Date.now() - 60_000; // tolerate clock skew
    try {
      const res = await fetch("/api/scrape", { method: "POST" });
      if (res.ok) {
        setPhase("running");
        return;
      }
      const body = (await res.json().catch(() => ({}))) as { error?: string };
      if (res.status === 409) {
        // A run is already going; follow it instead of failing.
        setPhase("running");
        toast(body.error ?? "Scrape sedang berjalan.");
        return;
      }
      setPhase("idle");
      toast.error(`Scrape gagal: ${body.error ?? "tiada respons dari GitHub"}`);
    } catch {
      setPhase("idle");
      toast.error("Scrape gagal: tiada respons dari GitHub");
    }
  }

  const busy = phase !== "idle";
  return (
    <Button
      size="sm"
      onClick={onClick}
      disabled={busy}
      aria-busy={busy}
      className="shrink-0"
    >
      {busy ? (
        <Loader2 className="animate-spin motion-reduce:animate-none" />
      ) : (
        <RefreshCw />
      )}
      {phase === "dispatching"
        ? "Menghantar…"
        : phase === "running"
          ? "Sedang scrape…"
          : "Scrape sekarang"}
    </Button>
  );
}
