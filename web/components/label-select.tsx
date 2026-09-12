"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { setJobLabel } from "@/lib/actions";
import { VALIDATION_LABELS } from "@/lib/supabase/types";
import type { JobLabel } from "@/lib/types";
import { cn } from "@/lib/utils";

const LABELS: Record<JobLabel, string> = {
  strong: "Strong",
  acceptable: "OK",
  weak: "Weak",
  reject: "Reject",
};

const CLEAR = "__clear";

export interface LabelSelectProps {
  jobId: string;
  value: JobLabel | null;
  onChange?: (next: JobLabel | null) => void;
  className?: string;
}

export function LabelSelect({
  jobId,
  value,
  onChange,
  className,
}: LabelSelectProps) {
  const [current, setCurrent] = useState<JobLabel | null>(value);
  useEffect(() => setCurrent(value), [value]);

  async function handle(next: string) {
    const nextLabel = next === CLEAR ? null : (next as JobLabel);
    if (nextLabel === current) return;
    const prev = current;
    setCurrent(nextLabel);
    onChange?.(nextLabel);
    try {
      await setJobLabel(jobId, nextLabel);
    } catch {
      setCurrent(prev);
      onChange?.(prev);
      toast.error("Gagal simpan label");
    }
  }

  return (
    <Select value={current ?? ""} onValueChange={handle}>
      <SelectTrigger
        size="sm"
        aria-label="Label"
        className={cn(
          "h-7 w-full text-xs",
          current === null && "text-muted-foreground",
          className,
        )}
      >
        <SelectValue placeholder="–" />
      </SelectTrigger>
      <SelectContent position="popper">
        {VALIDATION_LABELS.map((l) => (
          <SelectItem key={l} value={l} className="text-xs">
            {LABELS[l]}
          </SelectItem>
        ))}
        {current ? (
          <>
            <SelectSeparator />
            <SelectItem value={CLEAR} className="text-xs text-muted-foreground">
              Buang label
            </SelectItem>
          </>
        ) : null}
      </SelectContent>
    </Select>
  );
}
