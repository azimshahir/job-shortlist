"use client";

import { useState } from "react";

import {
  JobDetailSections,
  JobHeaderActions,
  JobSubtitle,
  type RowPatch,
} from "@/components/job-detail";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { JobRow, ResumePrereq, RunRef } from "@/lib/types";

/** /jobs/[id]: the drawer's sections in a Card (design.md §8). */
export function JobPageCard({
  row: initial,
  runHistory,
  resumePrereq,
}: {
  row: JobRow;
  runHistory: RunRef[];
  resumePrereq: ResumePrereq;
}) {
  const [row, setRow] = useState(initial);
  const onPatch = (p: RowPatch) => setRow((r) => ({ ...r, ...p }));
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base leading-snug">{row.title}</CardTitle>
        <CardDescription>
          <JobSubtitle row={row} />
        </CardDescription>
        <JobHeaderActions row={row} prereq={resumePrereq} onPatch={onPatch} />
      </CardHeader>
      <CardContent>
        <JobDetailSections row={row} runHistory={runHistory} onPatch={onPatch} />
      </CardContent>
    </Card>
  );
}
