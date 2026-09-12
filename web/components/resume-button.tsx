"use client";

import {
  Download,
  FileText,
  Loader2,
  RotateCw,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useIsMobile } from "@/hooks/use-media-query";
import { fetchResumeState, signResumeUrl } from "@/lib/actions";
import { resumeFilename } from "@/lib/format";
import type { ResumePrereq, ResumeStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const POLL_MS = 10_000;
const POLL_CAP_MS = 5 * 60_000;

/** Last "[resume failed] …" line in job_actions.notes, else the raw notes. */
export function failureReason(notes: string | null | undefined): string | null {
  if (!notes) return null;
  const lines = notes
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.startsWith("[resume failed]"));
  if (lines.length === 0) return null;
  return lines[lines.length - 1].replace("[resume failed]", "").trim() || null;
}

export interface ResumeButtonProps {
  jobId: string;
  resumeStatus: ResumeStatus;
  /** Storage path, not a signed URL. */
  resumeUrl: string | null;
  failureReason?: string | null;
  prereq: ResumePrereq;
  title: string;
  company: string | null;
  /** Icon-only (< md). Defaults to a media query. */
  compact?: boolean;
  onChange?: (patch: { resumeStatus: ResumeStatus; resumeUrl: string | null }) => void;
  className?: string;
}

export function ResumeButton({
  jobId,
  resumeStatus,
  resumeUrl,
  failureReason: reason,
  prereq,
  title,
  company,
  compact,
  onChange,
  className,
}: ResumeButtonProps) {
  const isMobile = useIsMobile();
  const iconOnly = compact ?? isMobile;
  const [status, setStatus] = useState<ResumeStatus>(resumeStatus);
  const [path, setPath] = useState<string | null>(resumeUrl);
  const [failReason, setFailReason] = useState<string | null>(reason ?? null);
  const [busy, setBusy] = useState(false);
  const pollStart = useRef<number | null>(null);

  useEffect(() => setStatus(resumeStatus), [resumeStatus]);
  useEffect(() => setPath(resumeUrl), [resumeUrl]);
  useEffect(() => setFailReason(reason ?? null), [reason]);

  // Poll job_actions while queued/generating (10 s, 5 min cap).
  useEffect(() => {
    if (status !== "requested" && status !== "pending") {
      pollStart.current = null;
      return;
    }
    if (pollStart.current === null) pollStart.current = Date.now();
    let cancelled = false;
    const id = window.setInterval(async () => {
      if (cancelled) return;
      if (Date.now() - (pollStart.current ?? Date.now()) > POLL_CAP_MS) {
        window.clearInterval(id);
        toast("Resume masih dijana — refresh sekejap lagi");
        return;
      }
      const next = await fetchResumeState(jobId).catch(() => null);
      if (!next || cancelled) return;
      if (next.resumeStatus === "ready") {
        setStatus("ready");
        setPath(next.resumeUrl);
        onChange?.({ resumeStatus: "ready", resumeUrl: next.resumeUrl });
        toast.success("Resume siap");
      } else if (next.resumeStatus === "failed") {
        const why = failureReason(next.notes) ?? "sebab tak diketahui";
        setStatus("failed");
        setFailReason(why);
        onChange?.({ resumeStatus: "failed", resumeUrl: null });
        toast.error(`Resume gagal: ${why}`);
      } else if (next.resumeStatus === "pending" && status !== "pending") {
        setStatus("pending");
        onChange?.({ resumeStatus: "pending", resumeUrl: null });
      }
    }, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, jobId]);

  async function request() {
    const prev = status;
    const prevPath = path;
    setStatus("requested");
    setPath(null);
    setBusy(true);
    onChange?.({ resumeStatus: "requested", resumeUrl: null });
    try {
      const res = await fetch("/api/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId }),
      });
      if (!res.ok) throw new Error(String(res.status));
      const body = (await res.json().catch(() => ({}))) as {
        resume_status?: ResumeStatus;
      };
      if (body.resume_status === "pending") {
        setStatus("pending");
        onChange?.({ resumeStatus: "pending", resumeUrl: null });
      }
    } catch {
      setStatus(prev);
      setPath(prevPath);
      onChange?.({ resumeStatus: prev, resumeUrl: prevPath });
      toast.error("Gagal hantar permintaan resume");
    } finally {
      setBusy(false);
    }
  }

  async function download() {
    if (!path) return;
    setBusy(true);
    try {
      const url = await signResumeUrl(path, resumeFilename(company, title));
      if (!url) throw new Error("no url");
      window.location.assign(url);
    } catch {
      toast.error("Gagal buka fail resume");
    } finally {
      setBusy(false);
    }
  }

  const base = cn("h-7 text-xs", className);

  // 1. Disabled: master CV not filled in.
  if (!prereq.profileReady) {
    const label = "Minta resume";
    const why = "CV induk belum diisi";
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex" tabIndex={0}>
            <Button
              variant="outline"
              size={iconOnly ? "icon-sm" : "sm"}
              disabled
              className={base}
              aria-label={`${label} — ${why}`}
            >
              <FileText />
              {iconOnly ? null : label}
            </Button>
          </span>
        </TooltipTrigger>
        <TooltipContent>{why}</TooltipContent>
      </Tooltip>
    );
  }

  // 3. Queued for /resume in Claude Code.
  if (status === "requested") {
    const text = "Dalam senarai — jana dengan /resume di Claude Code";
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className="inline-flex max-w-[160px] items-center gap-1 text-xs leading-tight text-muted-foreground"
            tabIndex={0}
          >
            <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden />
            <span className={cn(iconOnly ? "sr-only" : "line-clamp-2")}>
              {text}
            </span>
            {iconOnly ? <span aria-hidden>Dalam senarai</span> : null}
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs whitespace-normal">{text}</TooltipContent>
      </Tooltip>
    );
  }

  // 4. Generating via the optional API path.
  if (status === "pending") {
    const label = "Menjana…";
    return (
      <Button
        variant="outline"
        size={iconOnly ? "icon-sm" : "sm"}
        disabled
        className={base}
        aria-label={label}
        aria-busy="true"
      >
        <Loader2 className="animate-spin motion-reduce:animate-none" />
        {iconOnly ? null : label}
      </Button>
    );
  }

  // 5. Ready: Download + jana semula.
  if (status === "ready" && path) {
    return (
      <span className="inline-flex items-center whitespace-nowrap">
        <Button
          variant="default"
          size="sm"
          className={base}
          onClick={download}
          disabled={busy}
        >
          <Download />
          Download
        </Button>
        {iconOnly ? (
          <Button
            variant="ghost"
            size="icon-sm"
            className="h-7 w-7 text-muted-foreground"
            onClick={request}
            disabled={busy}
            aria-label="Jana semula"
          >
            <RotateCw />
          </Button>
        ) : (
          <Button
            variant="link"
            size="sm"
            className="h-7 px-1 text-xs text-muted-foreground"
            onClick={request}
            disabled={busy}
          >
            jana semula
          </Button>
        )}
      </span>
    );
  }

  // 2. Minta resume (none / failed / ready-without-path).
  const label = "Minta resume";
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap">
      {status === "failed" ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-flex" tabIndex={0}>
              <TriangleAlert
                className="h-3.5 w-3.5 text-destructive"
                aria-label={`Gagal: ${failReason ?? "sebab tak diketahui"}`}
              />
            </span>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs whitespace-normal">
            Gagal: {failReason ?? "sebab tak diketahui"}
          </TooltipContent>
        </Tooltip>
      ) : null}
      <Button
        variant="outline"
        size={iconOnly ? "icon-sm" : "sm"}
        className={base}
        onClick={request}
        disabled={busy}
        aria-label={label}
      >
        <Sparkles />
        {iconOnly ? null : label}
      </Button>
    </span>
  );
}
