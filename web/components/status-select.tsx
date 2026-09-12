"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { setJobStatus } from "@/lib/actions";
import { STATUS_LABELS } from "@/lib/format";
import { JOB_STATUSES } from "@/lib/supabase/types";
import type { JobStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const TRIGGER_TINT: Record<JobStatus, string> = {
  new: "",
  shortlisted: "",
  applied: "text-green-800 dark:text-green-300",
  interview: "text-blue-800 dark:text-blue-300",
  offer: "font-semibold text-emerald-800 dark:text-emerald-300",
  rejected: "text-muted-foreground",
  ignored: "text-muted-foreground",
};

const DOT: Record<JobStatus, string> = {
  new: "bg-muted-foreground/40",
  shortlisted: "bg-muted-foreground/40",
  applied: "bg-green-500",
  interview: "bg-blue-500",
  offer: "bg-emerald-500",
  rejected: "bg-muted-foreground/40",
  ignored: "bg-muted-foreground/40",
};

export function StatusDot({ status }: { status: JobStatus }) {
  return (
    <span
      aria-hidden
      className={cn("inline-block h-2 w-2 shrink-0 rounded-full", DOT[status])}
    />
  );
}

export interface StatusSelectProps {
  jobId: string;
  value: JobStatus;
  appliedDate?: string | null;
  /** Called after the optimistic set, before the server acks. */
  onChange?: (next: JobStatus) => void;
  className?: string;
}

export function StatusSelect({
  jobId,
  value,
  appliedDate = null,
  onChange,
  className,
}: StatusSelectProps) {
  const [current, setCurrent] = useState<JobStatus>(value);
  useEffect(() => setCurrent(value), [value]);

  async function handle(next: string) {
    const nextStatus = next as JobStatus;
    if (nextStatus === current) return;
    const prev = current;
    setCurrent(nextStatus);
    onChange?.(nextStatus);
    try {
      await setJobStatus(jobId, nextStatus, appliedDate);
    } catch {
      setCurrent(prev);
      onChange?.(prev);
      toast.error("Gagal simpan status — cuba lagi");
    }
  }

  return (
    <Select value={current} onValueChange={handle}>
      <SelectTrigger
        size="sm"
        aria-label="Status"
        className={cn("h-7 w-full text-xs", TRIGGER_TINT[current], className)}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent position="popper">
        {JOB_STATUSES.map((s) => (
          <SelectItem key={s} value={s} className="text-xs">
            <StatusDot status={s} />
            {STATUS_LABELS[s]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
