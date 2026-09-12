"use client";

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { sebab, type SebabTone } from "@/lib/format";
import type { SelectionStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const TONE: Record<SebabTone, string> = {
  green:
    "border-green-300 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950/40 dark:text-green-300",
  red: "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300",
  amber:
    "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300",
  gray: "text-muted-foreground",
  slate:
    "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300",
  plain: "",
};

export function sebabToneClass(tone: SebabTone): string {
  return TONE[tone];
}

export function SebabBadge({
  status,
  reason,
  className,
}: {
  status: SelectionStatus | null;
  reason: string | null;
  className?: string;
}) {
  const { text, tone } = sebab(status, reason);
  const badge = (
    <Badge
      variant="outline"
      className={cn("rounded-md text-xs lowercase", TONE[tone], className)}
    >
      {text}
    </Badge>
  );
  if (!reason) return badge;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex" tabIndex={0}>
          {badge}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm whitespace-normal">
        {reason}
      </TooltipContent>
    </Tooltip>
  );
}
