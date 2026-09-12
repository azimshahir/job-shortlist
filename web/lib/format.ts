/**
 * Pure formatting helpers (design.md §3.4, §3.7, §3.8). Mirrors
 * scraper/report.py where the UI must read the same as the chat report.
 */
import { FINAL_SCORE_THRESHOLD } from "@/lib/env";
import type { FamilyStatus, JobStatus, SelectionStatus } from "@/lib/types";

const MYT = "Asia/Kuala_Lumpur";

function isNum(n: unknown): n is number {
  return n != null && Number.isFinite(Number(n));
}

export function fmtFinal(n: number | null | undefined): string {
  return isNum(n) ? Number(n).toFixed(1) : "–";
}

export function fmtSem(n: number | null | undefined): string {
  return isNum(n) ? Number(n).toFixed(3) : "–";
}

export function fmtKw(n: number | null | undefined): string {
  return isNum(n) ? String(Math.round(Number(n))) : "–";
}

/** Mirror report.py::_loc without the 28-char slice. */
export function cleanLocation(loc: string | null | undefined): string {
  if (!loc) return "–";
  let out = loc;
  for (const noise of [", Malaysia", "Federal Territory of ", "WP. ", ", MY"]) {
    out = out.split(noise).join("");
  }
  out = out.replace(/^[,\s]+|[,\s]+$/g, "");
  return out || "–";
}

function fmt(iso: string, opts: Intl.DateTimeFormatOptions): string | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return new Intl.DateTimeFormat("en-GB", { timeZone: MYT, ...opts }).format(d);
}

/** '12 Sep 2026, 07:41' in MYT. */
export function fmtDateTimeMYT(iso: string | null | undefined): string {
  if (!iso) return "–";
  const date = fmt(iso, { day: "2-digit", month: "short", year: "numeric" });
  const time = fmt(iso, { hour: "2-digit", minute: "2-digit", hour12: false });
  return date && time ? `${date}, ${time}` : "–";
}

/** '12 Sep 2026' in MYT. */
export function fmtDateMYT(iso: string | null | undefined): string {
  if (!iso) return "–";
  return fmt(iso, { day: "2-digit", month: "short", year: "numeric" }) ?? "–";
}

/** '12 Sep' in MYT. */
export function fmtDayMonthMYT(iso: string | null | undefined): string {
  if (!iso) return "–";
  return fmt(iso, { day: "2-digit", month: "short" }) ?? "–";
}

/** 'yyyy-mm-dd' of an instant in MYT (for "today" comparisons). */
export function ymdMYT(date: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: MYT,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

/** '2m 41s' or '' when not finished. */
export function fmtDuration(
  startIso: string,
  endIso: string | null | undefined,
): string {
  if (!endIso) return "";
  const ms = Date.parse(endIso) - Date.parse(startIso);
  if (!Number.isFinite(ms) || ms < 0) return "";
  const total = Math.round(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export type SebabTone = "green" | "red" | "amber" | "gray" | "slate" | "plain";

/** Mirror report.py::_reason, plus a colour tone (design.md §3.7). */
export function sebab(
  status: SelectionStatus | null | undefined,
  reason: string | null | undefined,
): { text: string; tone: SebabTone } {
  const s = status ?? "";
  const r = reason ?? "";
  if (s === "selected") return { text: "dipilih", tone: "green" };
  if (s === "out_of_scope") return { text: "out of scope", tone: "red" };
  if (s === "disqualified") {
    const marker = "contains '";
    const idx = r.indexOf(marker);
    if (idx >= 0) {
      const rest = r.slice(idx + marker.length);
      const end = rest.indexOf("'");
      const term = end >= 0 ? rest.slice(0, end) : rest;
      return { text: term || "level mismatch", tone: "amber" };
    }
    return { text: "level mismatch", tone: "amber" };
  }
  if (s === "not_selected") {
    if (r.includes("below threshold")) {
      return {
        text: `bawah ${FINAL_SCORE_THRESHOLD.toFixed(0)}`,
        tone: "gray",
      };
    }
    return { text: "luar top 5", tone: "gray" };
  }
  if (s === "history_cooldown" || s === "history_repost_cooldown") {
    return { text: "cooldown", tone: "slate" };
  }
  if (s === "history_applied") return { text: "dah apply", tone: "slate" };
  if (s === "history_ignored") return { text: "diabaikan", tone: "slate" };
  if (s === "history_repost") return { text: "repost", tone: "slate" };
  if (s.startsWith("history_")) {
    return {
      text: s.replace("history_", "").replace(/_/g, " "),
      tone: "slate",
    };
  }
  return { text: s ? s.replace(/_/g, " ") : "–", tone: "plain" };
}

export function familyCode(
  status: FamilyStatus | null | undefined,
): "CORE" | "ADJ" | "SEC" | "OUT" {
  switch (status) {
    case "ADJACENT":
      return "ADJ";
    case "SECONDARY":
      return "SEC";
    case "OUT_OF_SCOPE":
      return "OUT";
    default:
      return "CORE";
  }
}

export function familyName(family: string | null | undefined): string {
  return family ? family.replace(/_/g, " ") : "–";
}

export const STATUS_LABELS: Record<JobStatus, string> = {
  new: "Baru",
  shortlisted: "Simpan",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  ignored: "Abaikan",
};

export function statusLabel(s: JobStatus): string {
  return STATUS_LABELS[s] ?? s;
}

/** Initials for the avatar fallback, e.g. 'azim.s@x.com' → 'AS'. */
export function initials(email: string | null | undefined): string {
  if (!email) return "?";
  const local = email.split("@")[0] ?? "";
  const bits = local.split(/[._\-+]/).filter(Boolean);
  const s =
    bits.length >= 2 ? bits[0][0] + bits[1][0] : local.slice(0, 2) || "?";
  return s.toUpperCase();
}

/** Safe filename for the resume download. */
export function resumeFilename(company: string | null, title: string): string {
  const clean = (s: string) =>
    s
      .replace(/[\\/:*?"<>|]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  const c = clean(company ?? "").slice(0, 40) || "Company";
  const t = clean(title).slice(0, 60) || "Job";
  return `Resume - ${c} - ${t}.docx`;
}
