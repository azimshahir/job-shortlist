"use client";

import { Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { STATUS_LABELS, familyName } from "@/lib/format";
import { JOB_STATUSES } from "@/lib/supabase/types";
import type { JobsFilters } from "@/lib/types";

const ALL = "__all";

export interface FilterBarProps {
  value: JobsFilters;
  families: string[];
  sources: string[];
}

export function FilterBar({ value, families, sources }: FilterBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [q, setQ] = useState(value.q ?? "");
  const debounce = useRef<number | null>(null);

  useEffect(() => setQ(value.q ?? ""), [value.q]);

  function apply(patch: Partial<Record<keyof JobsFilters, string | undefined>>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [k, v] of Object.entries(patch)) {
      if (v) params.set(k, v);
      else params.delete(k);
    }
    params.delete("page");
    const qs = params.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname);
  }

  function onSearch(next: string) {
    setQ(next);
    if (debounce.current) window.clearTimeout(debounce.current);
    debounce.current = window.setTimeout(() => {
      apply({ q: next.trim() || undefined });
    }, 250);
  }

  const active = Boolean(
    value.q || value.status || value.family || value.source || value.from || value.to,
  );

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative w-full md:w-64">
        <Search
          className="pointer-events-none absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          type="search"
          value={q}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Cari title / company"
          aria-label="Cari title / company"
          className="pl-8"
        />
      </div>

      <Select
        value={value.status ?? ALL}
        onValueChange={(v) => apply({ status: v === ALL ? undefined : v })}
      >
        <SelectTrigger aria-label="Status" className="w-[150px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent position="popper">
          <SelectItem value={ALL}>Semua status</SelectItem>
          {JOB_STATUSES.map((s) => (
            <SelectItem key={s} value={s}>
              {STATUS_LABELS[s]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={value.family ?? ALL}
        onValueChange={(v) => apply({ family: v === ALL ? undefined : v })}
      >
        <SelectTrigger aria-label="Family" className="w-[190px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent position="popper">
          <SelectItem value={ALL}>Semua family</SelectItem>
          {families.map((f) => (
            <SelectItem key={f} value={f}>
              {familyName(f)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={value.source ?? ALL}
        onValueChange={(v) => apply({ source: v === ALL ? undefined : v })}
      >
        <SelectTrigger aria-label="Source" className="w-[150px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent position="popper">
          <SelectItem value={ALL}>Semua source</SelectItem>
          {sources.map((s) => (
            <SelectItem key={s} value={s}>
              {s}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <div className="flex items-center gap-2">
        <Label htmlFor="from" className="text-xs text-muted-foreground">
          Dari
        </Label>
        <Input
          id="from"
          type="date"
          className="w-36"
          value={value.from ?? ""}
          onChange={(e) => apply({ from: e.target.value || undefined })}
        />
        <Label htmlFor="to" className="text-xs text-muted-foreground">
          Hingga
        </Label>
        <Input
          id="to"
          type="date"
          className="w-36"
          value={value.to ?? ""}
          onChange={(e) => apply({ to: e.target.value || undefined })}
        />
      </div>

      {active ? (
        <Button variant="ghost" size="sm" onClick={() => router.push(pathname)}>
          Reset
        </Button>
      ) : null}
    </div>
  );
}
