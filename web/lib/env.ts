/**
 * Build-time public config. Both are optional; the defaults keep the app
 * safe: the resume button stays disabled until the user flips the flag.
 */
export const RESUME_PREREQ_OK =
  (process.env.NEXT_PUBLIC_RESUME_PREREQ_OK ?? "false").toLowerCase() ===
  "true";

const parsed = Number.parseFloat(
  process.env.NEXT_PUBLIC_FINAL_SCORE_THRESHOLD ?? "60",
);
export const FINAL_SCORE_THRESHOLD = Number.isFinite(parsed) ? parsed : 60;

/** Rows shown in Hari Ini (mirrors scraper/config.py TOP_N_RANKED). */
export const TOP_N_RANKED = 10;

/** Semua Job / Runs page size. */
export const PAGE_SIZE = 50;
