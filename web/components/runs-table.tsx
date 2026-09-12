"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

import { funnelText } from "@/components/funnel-line";
import { sebabToneClass } from "@/components/sebab-badge";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fmtDateTimeMYT, fmtDuration } from "@/lib/format";
import type { RunRow } from "@/lib/types";
import { cn } from "@/lib/utils";

export function RunStatusBadge({ run }: { run: RunRow }) {
  const base = "rounded-md text-xs";
  if (run.status === "running") {
    return (
      <Badge variant="outline" className={base}>
        <Loader2 className="h-3 w-3 animate-spin motion-reduce:animate-none" />
        running
      </Badge>
    );
  }
  if (run.status === "failed") {
    return (
      <Badge variant="outline" className={cn(base, sebabToneClass("red"))}>
        failed
      </Badge>
    );
  }
  if (run.rawCount === 0) {
    return (
      <Badge variant="outline" className={cn(base, sebabToneClass("amber"))}>
        0 scraped
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className={cn(base, sebabToneClass("green"))}>
      ok
    </Badge>
  );
}

const CELL = "px-2 py-1.5";
const HEAD = "h-9 px-2 text-xs font-medium text-muted-foreground";

export function RunsTable({ runs }: { runs: RunRow[] }) {
  const router = useRouter();
  const go = (id: string) => router.push(`/today?run=${id}`);
  return (
    <div className="rounded-md border">
      <div className="overflow-x-auto">
        <Table className="min-w-[560px]">
          <TableCaption className="sr-only">Senarai run</TableCaption>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead scope="col" className={cn(HEAD, "min-w-[160px]")}>Masa</TableHead>
              <TableHead scope="col" className={cn(HEAD, "w-20")}>Trigger</TableHead>
              <TableHead scope="col" className={cn(HEAD, "w-20 text-right")}>Scraped</TableHead>
              <TableHead scope="col" className={cn(HEAD, "w-20 text-right")}>Ranked</TableHead>
              <TableHead scope="col" className={cn(HEAD, "w-24 text-right")}>Disyorkan</TableHead>
              <TableHead scope="col" className={cn(HEAD, "w-28")}>Status</TableHead>
              <TableHead scope="col" className={cn(HEAD, "hidden lg:table-cell")}>Funnel</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.map((run) => (
              <TableRow
                key={run.id}
                tabIndex={0}
                className="cursor-pointer"
                onClick={() => go(run.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") go(run.id);
                }}
              >
                <TableCell className={CELL}>
                  <div className="tabular-nums">{fmtDateTimeMYT(run.startedAt)}</div>
                  {run.finishedAt ? (
                    <div className="text-xs text-muted-foreground">
                      {fmtDuration(run.startedAt, run.finishedAt)}
                    </div>
                  ) : null}
                </TableCell>
                <TableCell className={cn(CELL, "text-muted-foreground")}>{run.trigger}</TableCell>
                <TableCell className={cn(CELL, "text-right tabular-nums")}>{run.rawCount}</TableCell>
                <TableCell className={cn(CELL, "text-right tabular-nums")}>{run.ranked}</TableCell>
                <TableCell className={cn(CELL, "text-right font-semibold tabular-nums")}>
                  {run.selected}
                </TableCell>
                <TableCell className={CELL}>
                  <RunStatusBadge run={run} />
                </TableCell>
                <TableCell
                  className={cn(CELL, "hidden whitespace-normal text-xs text-muted-foreground lg:table-cell")}
                >
                  {funnelText(run)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
