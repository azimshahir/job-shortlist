"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { FamilyBadge } from "@/components/family-badge";
import { LabelSelect } from "@/components/label-select";
import { LinkButton } from "@/components/link-button";
import { ResumeButton, failureReason } from "@/components/resume-button";
import { SebabBadge } from "@/components/sebab-badge";
import { StatusSelect } from "@/components/status-select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { saveNotes } from "@/lib/actions";
import {
  cleanLocation,
  fmtDateMYT,
  fmtDateTimeMYT,
  fmtFinal,
  fmtKw,
  fmtSem,
} from "@/lib/format";
import type { JobRow, ResumePrereq, RunRef } from "@/lib/types";
import { cn } from "@/lib/utils";

export type RowPatch = Partial<
  Pick<JobRow, "status" | "label" | "notes" | "resumeStatus" | "resumeUrl">
>;

export function JobHeaderActions({
  row,
  prereq,
  onPatch,
}: {
  row: JobRow;
  prereq: ResumePrereq;
  onPatch?: (p: RowPatch) => void;
}) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <LinkButton jobUrl={row.jobUrl} jobUrlDirect={row.jobUrlDirect} showLabel />
      <ResumeButton
        jobId={row.jobId}
        resumeStatus={row.resumeStatus}
        resumeUrl={row.resumeUrl}
        failureReason={failureReason(row.notes)}
        prereq={prereq}
        title={row.title}
        company={row.company}
        compact={false}
        onChange={(p) => onPatch?.(p)}
      />
    </div>
  );
}

export function JobSubtitle({ row }: { row: JobRow }) {
  return (
    <>
      {row.company ?? "–"} · {cleanLocation(row.location)} · {row.source ?? "–"}
    </>
  );
}

function NotesField({
  jobId,
  value,
  onSaved,
}: {
  jobId: string;
  value: string | null;
  onSaved?: (notes: string | null) => void;
}) {
  const [text, setText] = useState(value ?? "");
  const [saved, setSaved] = useState(value ?? "");
  useEffect(() => {
    setText(value ?? "");
    setSaved(value ?? "");
  }, [value]);

  async function onBlur() {
    if (text === saved) return;
    try {
      await saveNotes(jobId, text);
      setSaved(text);
      onSaved?.(text.trim() ? text : null);
      toast.success("Nota disimpan");
    } catch {
      toast.error("Gagal simpan nota");
    }
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor={`notes-${jobId}`}>Nota</Label>
      <Textarea
        id={`notes-${jobId}`}
        rows={3}
        placeholder="Nota peribadi…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={onBlur}
      />
    </div>
  );
}

function Description({ text }: { text: string | null }) {
  const [expanded, setExpanded] = useState(false);
  if (!text) return <p className="text-sm text-muted-foreground">Tiada description.</p>;
  const long = text.length > 2000;
  return (
    <div>
      <p
        className={cn(
          "whitespace-pre-wrap text-sm leading-relaxed",
          long && !expanded && "line-clamp-[12]",
        )}
      >
        {text}
      </p>
      {long && !expanded ? (
        <Button
          variant="link"
          size="sm"
          className="h-7 px-0"
          onClick={() => setExpanded(true)}
        >
          Tunjuk semua
        </Button>
      ) : null}
    </div>
  );
}

/** Sections 2–7 of design.md §8 (header is rendered by the caller). */
export function JobDetailSections({
  row,
  runHistory,
  onPatch,
}: {
  row: JobRow;
  runHistory: RunRef[] | undefined;
  onPatch?: (p: RowPatch) => void;
}) {
  return (
    <div className="text-sm">
      <section aria-labelledby={`tindakan-${row.jobId}`} className="space-y-3">
        <h3 id={`tindakan-${row.jobId}`} className="text-sm font-semibold">
          Tindakan
        </h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor={`status-${row.jobId}`}>Status</Label>
            <StatusSelect
              jobId={row.jobId}
              value={row.status}
              appliedDate={row.appliedDate}
              onChange={(status) => onPatch?.({ status })}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`label-${row.jobId}`}>Label</Label>
            <LabelSelect
              jobId={row.jobId}
              value={row.label}
              onChange={(label) => onPatch?.({ label })}
            />
          </div>
        </div>
        <NotesField
          jobId={row.jobId}
          value={row.notes}
          onSaved={(notes) => onPatch?.({ notes })}
        />
      </section>

      <Separator className="my-4" />

      <section aria-labelledby={`skor-${row.jobId}`} className="space-y-2">
        <h3 id={`skor-${row.jobId}`} className="text-sm font-semibold">
          Skor
        </h3>
        <dl className="grid grid-cols-3 gap-x-4 gap-y-1 text-sm tabular-nums">
          <div>
            <dt className="text-xs text-muted-foreground">Final</dt>
            <dd className="font-semibold">{fmtFinal(row.finalScore)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">KW</dt>
            <dd>{fmtKw(row.keywordScore)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Sem</dt>
            <dd>{fmtSem(row.semanticRaw)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Rank</dt>
            <dd>{row.finalRank != null ? `#${row.finalRank}` : "–"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Sem rank</dt>
            <dd>{row.semanticRank != null ? `#${row.semanticRank}` : "–"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Sem (scaled)</dt>
            <dd>{fmtFinal(row.semanticScore)}</dd>
          </div>
        </dl>
        <p className="text-sm">
          <span className="text-muted-foreground">Strongest match:</span>{" "}
          {row.strongestProfileMatch ?? "–"}
        </p>
      </section>

      <Separator className="my-4" />

      <section aria-labelledby={`sebab-${row.jobId}`} className="space-y-2">
        <h3 id={`sebab-${row.jobId}`} className="text-sm font-semibold">
          Sebab
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <SebabBadge status={row.selectionStatus || null} reason={null} />
          <span className="text-sm">{row.selectionReason ?? "–"}</span>
        </div>
        <p className="text-sm">
          <span className="text-muted-foreground">Family:</span>{" "}
          <FamilyBadge family={row.careerFamily} status={row.careerFamilyStatus} />
        </p>
        {row.careerFamilyReason ? (
          <p className="text-sm text-muted-foreground">{row.careerFamilyReason}</p>
        ) : null}
      </section>

      <Separator className="my-4" />

      <section aria-labelledby={`kw-${row.jobId}`} className="space-y-2">
        <h3 id={`kw-${row.jobId}`} className="text-sm font-semibold">
          Matched keywords
        </h3>
        {row.matchedKeywords.length === 0 ? (
          <p className="text-sm text-muted-foreground">Tiada.</p>
        ) : (
          <div className="flex flex-wrap gap-1">
            {row.matchedKeywords.map((k) => (
              <Badge key={k} variant="secondary" className="rounded-md">
                {k}
              </Badge>
            ))}
          </div>
        )}
      </section>

      <Separator className="my-4" />

      <section aria-labelledby={`sejarah-${row.jobId}`} className="space-y-1 text-sm">
        <h3 id={`sejarah-${row.jobId}`} className="text-sm font-semibold">
          Sejarah
        </h3>
        <p>Pertama nampak: {fmtDateMYT(row.firstSeen)}</p>
        <p>Terakhir: {fmtDateMYT(row.lastSeen)}</p>
        <p>Muncul: {row.seenCount} kali</p>
        <p>
          History: {row.historyStatus ?? "–"}
          {row.historyReason ? ` — ${row.historyReason}` : ""}
        </p>
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span>Run:</span>
          {runHistory === undefined ? (
            <span className="text-muted-foreground">memuat…</span>
          ) : runHistory.length === 0 ? (
            <span className="text-muted-foreground">–</span>
          ) : (
            runHistory.map((r) => (
              <Link
                key={r.runId}
                href={`/today?run=${r.runId}`}
                className="underline underline-offset-4 hover:text-foreground"
              >
                {fmtDateTimeMYT(r.startedAt)}
              </Link>
            ))
          )}
        </p>
      </section>

      <Separator className="my-4" />

      <section aria-labelledby={`desc-${row.jobId}`} className="space-y-2">
        <h3 id={`desc-${row.jobId}`} className="text-sm font-semibold">
          Description
        </h3>
        <Description text={row.description} />
      </section>
    </div>
  );
}
