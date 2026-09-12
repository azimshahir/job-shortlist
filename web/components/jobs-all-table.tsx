"use client";

import type { SortingState } from "@tanstack/react-table";
import { useState } from "react";

import { JobsTable } from "@/components/jobs-table";
import type { JobRow, ResumePrereq } from "@/lib/types";

/** Semua Job table: client-side sort state, default Tarikh desc, Final desc. */
export function JobsAllTable({
  rows,
  resumePrereq,
  emptyMessage,
}: {
  rows: JobRow[];
  resumePrereq: ResumePrereq;
  emptyMessage: string;
}) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "date", desc: true },
    { id: "final", desc: true },
  ]);
  return (
    <JobsTable
      rows={rows}
      variant="all"
      resumePrereq={resumePrereq}
      caption="Semua job"
      sorting={sorting}
      onSortingChange={setSorting}
      emptyMessage={emptyMessage}
    />
  );
}
