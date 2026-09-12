import type { RunRow } from "@/lib/types";
import { cn } from "@/lib/utils";

export type FunnelRun = Pick<
  RunRow,
  | "rawCount"
  | "hardRejected"
  | "keywordPassed"
  | "ranked"
  | "careerRejected"
  | "historyExcluded"
  | "selected"
>;

/** Same wording as scraper/report.py::funnel_line (design.md §2.2). */
export function funnelText(run: FunnelRun): string {
  return (
    `${run.rawCount} scraped → ${run.hardRejected} hard-reject → ` +
    `${run.keywordPassed} lepas keyword → ${run.ranked} ranked → ` +
    `${run.careerRejected} out-of-scope → ${run.historyExcluded} pernah nampak → ` +
    `${run.selected} disyorkan`
  );
}

export function FunnelLine({
  run,
  className,
}: {
  run: FunnelRun;
  className?: string;
}) {
  return (
    <p className={cn("break-words text-sm text-muted-foreground", className)}>
      {run.rawCount} scraped → {run.hardRejected} hard-reject →{" "}
      {run.keywordPassed} lepas keyword → {run.ranked} ranked →{" "}
      {run.careerRejected} out-of-scope → {run.historyExcluded} pernah nampak →{" "}
      <span className="font-semibold text-foreground">
        {run.selected} disyorkan
      </span>
    </p>
  );
}
