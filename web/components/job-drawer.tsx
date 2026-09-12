"use client";

import { useEffect, useState } from "react";

import {
  JobDetailSections,
  JobHeaderActions,
  JobSubtitle,
  type RowPatch,
} from "@/components/job-detail";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { createClient } from "@/lib/supabase/client";
import type { JobRow, ResumePrereq, RunRef } from "@/lib/types";

export interface JobDrawerProps {
  /** null = closed */
  row: JobRow | null;
  runHistory?: RunRef[];
  resumePrereq: ResumePrereq;
  onOpenChange: (open: boolean) => void;
  onRowChange?: (patch: RowPatch) => void;
}

export function JobDrawer({
  row,
  runHistory,
  resumePrereq,
  onOpenChange,
  onRowChange,
}: JobDrawerProps) {
  const [history, setHistory] = useState<RunRef[] | undefined>(runHistory);
  const jobId = row?.jobId ?? null;

  // Lazy-load the runs this job appeared in (browser client, RLS-scoped).
  useEffect(() => {
    if (runHistory) {
      setHistory(runHistory);
      return;
    }
    if (!jobId) return;
    let cancelled = false;
    setHistory(undefined);
    const supabase = createClient();
    supabase
      .from("job_scores")
      .select("run_id, runs(started_at)")
      .eq("job_id", jobId)
      .limit(50)
      .then(({ data }) => {
        if (cancelled) return;
        const refs = (data ?? [])
          .map((r) => {
            const run = r.runs as unknown as { started_at: string } | null;
            return run ? { runId: r.run_id, startedAt: run.started_at } : null;
          })
          .filter((r): r is RunRef => r !== null)
          .sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt))
          .slice(0, 10);
        setHistory(refs);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, runHistory]);

  return (
    <Sheet open={row !== null} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="overflow-y-auto data-[side=right]:w-full data-[side=right]:sm:max-w-xl">
        {row ? (
          <>
            <SheetHeader className="pr-10">
              <SheetTitle className="text-base leading-snug">{row.title}</SheetTitle>
              <SheetDescription>
                <JobSubtitle row={row} />
              </SheetDescription>
              <JobHeaderActions row={row} prereq={resumePrereq} onPatch={onRowChange} />
            </SheetHeader>
            <div className="px-4 pb-6">
              <JobDetailSections row={row} runHistory={history} onPatch={onRowChange} />
            </div>
          </>
        ) : (
          <SheetHeader>
            <SheetTitle className="sr-only">Job</SheetTitle>
            <SheetDescription className="sr-only">Butiran job</SheetDescription>
          </SheetHeader>
        )}
      </SheetContent>
    </Sheet>
  );
}
