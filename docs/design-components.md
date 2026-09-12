# Components — install list + custom component contracts

Companion to `docs/design.md`. Section numbers (§) refer to that file.

## 1. shadcn/ui components to install

Run from `web/` after `npx shadcn@latest init` (style `new-york`, base colour
`neutral`, CSS variables on):

```
npx shadcn@latest add button badge table select tooltip sheet skeleton alert sonner input label textarea card dropdown-menu avatar separator
```

| component | used by |
|---|---|
| `button` | everything |
| `badge` | Sebab, Family status, Runs status, keyword chips |
| `table` | JobsTable, RunsTable |
| `select` | StatusSelect, LabelSelect, FilterBar |
| `tooltip` | LinkButton, ResumeButton, Sebab badge |
| `sheet` | JobDrawer |
| `skeleton` | loading states |
| `alert` | 0-scraped banner, error state |
| `sonner` | all toasts (`<Toaster />` in the app layout) |
| `input`, `label`, `textarea` | Login, FilterBar, drawer notes |
| `card` | Login, empty states, `/jobs/[id]` fallback |
| `dropdown-menu`, `avatar` | user menu |
| `separator` | drawer sections, user menu |

Also: `npm i @tanstack/react-table lucide-react next-themes sonner` (shadcn
`sonner` pulls `sonner`; `next-themes` is needed by the Toaster + theme).

Not installed on purpose: `calendar`, `popover`, `dialog`, `command`,
`data-table` scaffold, `pagination` (a two-button pager is enough).

## 2. Custom components (`web/components/`)

Types below assume Backend's generated `Database` type in
`web/lib/supabase/types.ts`. `Row<'jobs'>` etc. are the usual helpers.

```ts
// web/lib/types.ts — shared view models (Frontend owns this file)

export type JobStatus =
  | 'new' | 'shortlisted' | 'applied' | 'interview' | 'offer' | 'rejected' | 'ignored';
export type JobLabel = 'strong' | 'acceptable' | 'weak' | 'reject';
export type ResumeStatus = 'none' | 'pending' | 'ready' | 'failed';
export type SelectionStatus =
  | 'selected' | 'out_of_scope' | 'disqualified' | 'not_selected'
  | `history_${string}`;
export type FamilyStatus = 'CORE' | 'ADJACENT' | 'SECONDARY' | 'OUT_OF_SCOPE';

/** One table row: jobs ⨝ job_scores (one run) ⟕ job_actions ⟕ validation_labels */
export interface JobRow {
  jobId: string;
  runId: string;
  title: string;
  company: string | null;
  location: string | null;
  source: string | null;
  jobUrl: string | null;
  jobUrlDirect: string | null;
  description: string | null;
  datePosted: string | null;      // ISO date
  firstSeen: string;              // ISO timestamp
  lastSeen: string;
  seenCount: number;

  keywordScore: number | null;
  semanticRaw: number | null;
  semanticScore: number | null;
  semanticRank: number | null;
  finalScore: number | null;
  finalRank: number | null;
  careerFamily: string | null;
  careerFamilyStatus: FamilyStatus | null;
  careerFamilyReason: string | null;
  selectionStatus: SelectionStatus;
  selectionReason: string | null;
  matchedKeywords: string[];
  strongestProfileMatch: string | null;
  historyStatus: string | null;
  historyReason: string | null;

  status: JobStatus;              // default 'new'
  appliedDate: string | null;
  notes: string | null;
  resumeStatus: ResumeStatus;     // default 'none'
  resumeUrl: string | null;       // Storage path, not a signed URL
  label: JobLabel | null;
}

export interface RunRow {
  id: string;
  startedAt: string;
  finishedAt: string | null;
  trigger: 'cron' | 'manual' | string;
  status: 'running' | 'ok' | 'failed' | string;
  rawCount: number;
  dedupedCount: number;
  hardRejected: number;
  keywordPassed: number;
  ranked: number;
  careerRejected: number;
  historyExcluded: number;
  selected: number;
  error: string | null;
}

export interface ResumePrereq {
  profileReady: boolean;   // candidate_profile.yaml has no TODO_ placeholders
  llmKeyReady: boolean;    // ANTHROPIC_API_KEY or OPENAI_API_KEY present in GitHub Secrets
}

export interface JobsFilters {
  q?: string;
  status?: JobStatus;
  family?: string;
  source?: string;
  from?: string;   // yyyy-mm-dd, on jobs.last_seen
  to?: string;
  page?: number;   // 1-based
}
```

### 2.1 `JobsTable` — `components/jobs-table.tsx` (client)

```ts
interface JobsTableProps {
  rows: JobRow[];
  variant: 'today' | 'all';          // 'today' = grouped, '#' rank col; 'all' = flat, 'Tarikh' col
  resumePrereq: ResumePrereq;
  caption: string;                    // sr-only <caption>
  onOpen?: (row: JobRow) => void;     // default: opens internal JobDrawer
  /** 'all' only */
  sorting?: SortingState;             // @tanstack/react-table
  onSortingChange?: (s: SortingState) => void;
  emptyMessage?: string;              // 'Tiada job sepadan.' etc.
}
```

Responsibilities: TanStack column defs (§3.1), group header rows for `today`
(§3.2), row tint (§3.6), row click/Enter → drawer, renders
`StatusSelect`/`LabelSelect`/`LinkButton`/`ResumeButton`/`SebabBadge`/
`FamilyBadge` per cell. Holds the "open row" state and mounts one `JobDrawer`.

Small presentational helpers in the same folder (no props beyond the value):
`SebabBadge({ status, reason })`, `FamilyBadge({ family, status })`,
`StatusDot({ status })`.

### 2.2 `StatusSelect` — `components/status-select.tsx` (client)

```ts
interface StatusSelectProps {
  jobId: string;
  value: JobStatus;
  onChange?: (next: JobStatus) => void;   // called after optimistic set, before server ack
  className?: string;
}
```

Internally: `useOptimistic`/`useState` + Supabase browser client upsert on
`job_actions` (§4.1). Reverts + toasts on error.

### 2.3 `LabelSelect` — `components/label-select.tsx` (client)

```ts
interface LabelSelectProps {
  jobId: string;
  value: JobLabel | null;
  onChange?: (next: JobLabel | null) => void;
  className?: string;
}
```

Upsert / delete on `validation_labels` (§4.2).

### 2.4 `LinkButton` — `components/link-button.tsx`

```ts
interface LinkButtonProps {
  jobUrl: string | null;
  jobUrlDirect: string | null;
  showLabel?: boolean;   // drawer variant: outline button with visible text
  className?: string;
}
```

Pure; picks icon/tooltip/href per §5. Server-renderable except for the Tooltip
(client boundary inside).

### 2.5 `ResumeButton` — `components/resume-button.tsx` (client)

```ts
interface ResumeButtonProps {
  jobId: string;
  resumeStatus: ResumeStatus;
  resumeUrl: string | null;           // Storage path
  failureReason?: string | null;      // from job_actions.notes for now
  prereq: ResumePrereq;
  title: string;                       // for the download filename
  company: string | null;
  compact?: boolean;                   // icon-only (< md); default from useMediaQuery
}
```

State machine per §6; owns its polling (`setInterval` 10 s, 5 min cap, cleared
on unmount). Signed URL via `supabase.storage.from('resumes').createSignedUrl(path, 3600, { download: filename })` on demand when entering `ready`.

### 2.6 `FunnelLine` — `components/funnel-line.tsx` (server)

```ts
interface FunnelLineProps {
  run: Pick<RunRow, 'rawCount' | 'hardRejected' | 'keywordPassed' | 'ranked'
                  | 'careerRejected' | 'historyExcluded' | 'selected'>;
  className?: string;   // e.g. 'text-xs' on Runs
}
```

Pure text per §2.2. Also export `funnelText(run): string` for reuse in the Runs table.

### 2.7 `ScrapeButton` — `components/scrape-button.tsx` (client)

```ts
interface ScrapeButtonProps {
  latestRun: Pick<RunRow, 'id' | 'status' | 'startedAt' | 'selected' | 'error'> | null;
}
```

States per §2.3. `POST /api/scrape`, polls `runs` (10 s, 20 min cap),
`router.refresh()` on completion, toasts.

### 2.8 `JobDrawer` — `components/job-drawer.tsx` (client)

```ts
interface JobDrawerProps {
  row: JobRow | null;                 // null = closed
  runHistory?: { runId: string; startedAt: string }[];   // for Sejarah → Run list; lazy-loaded if undefined
  resumePrereq: ResumePrereq;
  onOpenChange: (open: boolean) => void;
  onRowChange?: (patch: Partial<Pick<JobRow, 'status' | 'label' | 'notes' | 'resumeStatus' | 'resumeUrl'>>) => void;
}
```

Sections per §8. Shares `StatusSelect`/`LabelSelect`/`LinkButton`/`ResumeButton`.
Notes textarea saves on blur.

### 2.9 `RunsTable` — `components/runs-table.tsx` (server-renderable; rows are `Link`s)

```ts
interface RunsTableProps {
  runs: RunRow[];
  page: number;
  pageCount: number;
}
```

Columns per §9; `RunStatusBadge({ run })` helper (handles `0 scraped`).

### 2.10 `FilterBar` — `components/filter-bar.tsx` (client)

```ts
interface FilterBarProps {
  value: JobsFilters;
  families: string[];   // distinct career_family values
  sources: string[];    // distinct source values
  // writes to the URL via useRouter/useSearchParams; no onChange needed
}
```

Debounced search (250 ms), resets `page` on any change, shows `Reset` when
any key is set.

### 2.11 Shell + states (no props worth typing)

- `components/app-shell.tsx` — header, nav, user menu (`email: string`).
- `components/empty-state.tsx` — `{ icon: LucideIcon; title: string; body?: string }`.
- `app/(app)/today/loading.tsx`, `error.tsx` — per §2.6 / §2.7.
- `components/scraper-failed-alert.tsx` — `{ run: RunRow }`, renders only when
  `run.rawCount === 0 || run.status === 'failed'`.

## 3. `lib/format.ts` (pure helpers, unit-testable)

```ts
export function fmtFinal(n: number | null): string;      // '76.1' | '–'
export function fmtSem(n: number | null): string;        // '0.812' | '–'
export function fmtKw(n: number | null): string;         // '42' | '–'
export function cleanLocation(loc: string | null): string;
export function fmtDateTimeMYT(iso: string): string;     // '12 Sep 2026, 07:41'
export function fmtDateMYT(iso: string): string;         // '12 Sep 2026'
export function fmtDuration(startIso: string, endIso: string | null): string; // '2m 41s' | ''
export function sebab(status: SelectionStatus, reason: string | null): { text: string; tone: 'green'|'red'|'amber'|'gray'|'slate'|'plain' };
export function familyCode(status: FamilyStatus | null): 'CORE'|'ADJ'|'SEC'|'OUT';
export function statusLabel(s: JobStatus): string;       // 'Baru', 'Applied', …
```

## 4. Open items for Backend

- `ResumePrereq` source: cheapest is a `settings` view or a single row the
  scraper upserts on each run (`profile_ready`, `llm_key_ready`). Until then
  Frontend hard-codes `{ profileReady: false, llmKeyReady: false }`.
- Resume failure reason: `job_actions.notes` is user-owned; a
  `resume_error text` column would be cleaner.
- Signed-URL `download` filename needs Storage v2 `createSignedUrl` options —
  confirm the bucket is private and RLS lets the user read their own path.
