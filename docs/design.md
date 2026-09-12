# Design spec — Job Shortlist web

Scope: the four screens in PRD §7 (Login, Hari Ini, Semua Job, Runs) plus the
Job detail drawer. One user, laptop + phone. shadcn/ui defaults + Tailwind
utilities only. No bespoke CSS, no animation library, no custom design tokens.
Everything below is a decision, not a suggestion — implement as written; the
decisions the user may want to override are listed in §13.

UI copy is Malay (short, casual-professional). Code identifiers are English.

---

## 0. Ground rules

- **Tokens:** only shadcn CSS variables (`bg-background`, `text-foreground`,
  `text-muted-foreground`, `bg-muted`, `border`, `bg-primary`, `bg-destructive`,
  `ring`). The only raw Tailwind colours allowed are the status/badge tints
  listed in §3.5–§3.7, always with a `dark:` pair.
- **Theme:** shadcn default theme (`neutral` base colour, `next-themes` with
  `class` strategy, `defaultTheme="system"`). No theme toggle in MVP — follow OS.
- **Type:** default shadcn body (`text-sm`; Geist Sans via `next/font` or the
  Tailwind system stack — either). Numbers in tables use `tabular-nums`.
- **Spacing scale:** 1 · 2 · 3 · 4 · 6 · 8 (4/8/12/16/24/32 px). Nothing else.
  Table cell padding is `px-2 py-1.5` (a Tailwind class on `TableCell` /
  `TableHead` overriding shadcn's default `p-2`/`p-4`, for density).
- **Radius:** shadcn default (`--radius: 0.5rem`).
- **Icons:** `lucide-react` only, `h-4 w-4` unless stated.
- **Toasts:** shadcn `sonner`; `position="bottom-right"` on `md+`,
  `"top-center"` below. Duration 4 s.
- `animate-spin` / `motion-reduce:animate-none` are Tailwind core — allowed.
  Nothing else animates.

---

## 1. App shell

```
┌────────────────────────────────────────────────────────────────┐
│ Job Shortlist   Hari Ini   Semua Job   Runs            [AZ ▾]  │  h-14, border-b
├────────────────────────────────────────────────────────────────┤
│ <main class="mx-auto w-full max-w-screen-2xl px-4 md:px-6 py-4 md:py-6"> │
```

- **Top bar:** `header` `sticky top-0 z-40 h-14 border-b bg-background`.
  Inner: `mx-auto flex h-14 max-w-screen-2xl items-center gap-6 px-4 md:px-6`.
  - Brand: `Job Shortlist`, `text-sm font-semibold`, links to `/today`.
  - Nav: three `Link`s styled `Button variant="ghost" size="sm"`. Active
    route (`usePathname().startsWith`) gets `bg-muted`. Labels: **Hari Ini**
    (`/today`), **Semua Job** (`/jobs`), **Runs** (`/runs`).
  - Right (`ml-auto`): `DropdownMenu` on an `Avatar` (`h-8 w-8`, initials
    fallback from email, e.g. `AZ`). Items: email (disabled,
    `text-muted-foreground text-xs`), `DropdownMenuSeparator`, **Log keluar**
    with `LogOut` icon.
  - `< md`: brand stays, nav labels `text-xs`, `gap-3`. Fits 375 px. No hamburger.
- **Content:** `max-w-screen-2xl` (1536 px) — the Hari Ini table has 14 columns.
  Sections inside a page: `space-y-4`.
- **Page header** on every page: `flex items-center justify-between gap-4`;
  `h1` `text-lg font-semibold` left, page action right. Optional subtitle
  below: `text-sm text-muted-foreground`.
- Focus rings: shadcn defaults (`focus-visible:ring-2 ring-ring ring-offset-2`).
  Never removed.

---

## 2. Hari Ini (`/today`) — the screen that matters

Top to bottom:

1. Page header `Hari Ini` + subtitle `Run terakhir: 12 Sep 2026, 07:41 · cron`
   (`dd MMM yyyy, HH:mm` in `Asia/Kuala_Lumpur`; `trigger` verbatim). Right:
   **Scrape sekarang** (§2.3).
2. Warning banner when `raw_count = 0` or `status = 'failed'` (§2.5).
3. Funnel line (§2.2).
4. The table (§3).
5. Footer note `text-xs text-muted-foreground mt-2`:
   `Sem = raw cosine ke profil; ranking aid, bukan kebarangkalian dapat kerja.`

"Today's run" = latest `runs` row whose `started_at` falls on the current MYT
date. None → empty state (§2.4) replaces 2–5; the Scrape button stays.

### 2.1 Data

One query: `job_scores` where `run_id = today.id`, joined `jobs`, left-joined
`job_actions` and `validation_labels`. Client-side split:

- Group A **Disyorkan** = `selection_status = 'selected'`, by `final_rank`.
- Group B **Ranked, tak disyorkan** = the rest, by `final_rank`.

The pipeline writes ≤ `TOP_N_RANKED` (10) rows per run → no pagination.

### 2.2 Funnel line

One `p` `text-sm text-muted-foreground break-words`, wording identical to
`scraper/report.py::funnel_line`; last segment `font-semibold text-foreground`:

```
927 scraped → 812 hard-reject → 115 lepas keyword → 10 ranked → 3 out-of-scope → 2 pernah nampak → 2 disyorkan
```

Arrow = Unicode `→` with a space each side. Wraps on phone; never truncated.

### 2.3 Scrape sekarang

`Button variant="default" size="sm"`, `RefreshCw` icon left of label.

| State | Look | Copy |
|---|---|---|
| idle | default | `Scrape sekarang` |
| dispatching (POST in flight) | `disabled`, `Loader2 animate-spin` | `Menghantar…` |
| running (latest run `status='running'`, or dispatch OK and no row yet) | `disabled`, `Loader2 animate-spin` | `Sedang scrape…` |
| done | idle + `toast.success` | `Scrape siap — 2 disyorkan` |
| failed | idle + `toast.error` | `Scrape gagal: <runs.error \| "tiada respons dari GitHub">` |

Click → `POST /api/scrape` → 2xx → `running`. Poll latest `runs` row every
**10 s**; stop on a row newer than click time with `status in ('ok','failed')`
or after **20 min** (`toast` `Masih belum siap — semak Runs`, back to idle).
On done: `router.refresh()`. On first load, if the latest run is `running`,
start in the running state.

### 2.4 Empty state (no run today)

`Card` `p-8 text-center` with `space-y-2`:

```
[CalendarX  h-8 w-8 mx-auto text-muted-foreground]
Belum ada run hari ini                      ← text-base font-medium
Cron jalan 07:40 pagi. Atau tekan Scrape sekarang.   ← text-sm text-muted-foreground
```

The header's Scrape button is the CTA — don't duplicate it in the card.

Run exists but `ranked = 0` and `raw_count > 0`: render the table header plus
one full-width row `Tiada job lepas keyword hari ini.`
(`py-6 text-center text-muted-foreground`).

Group A empty, Group B not: Disyorkan group header still renders, followed by
one full-width row `Tiada job cukup kuat hari ini. Standard tidak diturunkan
untuk penuhkan senarai.` (wording from `report.py`).

### 2.5 "0 scraped" banner

Shown when today's run has `raw_count = 0` **or** `status = 'failed'`.
`Alert variant="destructive"` + `TriangleAlert`:

- `AlertTitle`: `Scraper gagal`
- `AlertDescription`: `0 job dijumpai — ini bukan market kosong, ini scraper tak
  jalan dengan betul. <runs.error jika ada> Cuba Scrape sekarang; kalau masih 0,
  semak GitHub Actions.`

The table still renders below (usually empty). `0 scraped` is never presented
as a quiet market.

### 2.6 Loading skeleton (`loading.tsx`)

- Header: `Skeleton h-6 w-32` + `Skeleton h-8 w-36`.
- Funnel: `Skeleton h-4 w-full max-w-2xl`.
- Table: real `Table` + real header row, 6 body rows, each cell `Skeleton h-4`
  with width matching the column (`w-6`, `w-48`, `w-28`, `w-24`, …).
- Container `aria-busy="true"`.

### 2.7 Error state (`error.tsx`)

`Alert variant="destructive"`: title `Tak dapat muat data`, description
`error.message` in `font-mono text-xs`, then `Button variant="outline"
size="sm"` `Cuba lagi` → `reset()`.

---

## 3. The table (`JobsTable`)

One shadcn `Table`. Wrapper `div.rounded-md.border > div.overflow-x-auto`.
The table scrolls horizontally; the page body never does. `<caption
class="sr-only">` = `Shortlist hari ini` / `Semua job` / `Run <date>`.

### 3.1 Columns (order fixed)

Widths are Tailwind classes on `TableHead`; body cells match. "hide-md" =
`hidden md:table-cell` on both `th` and `td`.

| # | id | Header | Align | Width | `< 768` | Cell |
|---|---|---|---|---|---|---|
| 1 | `rank` | `#` | right | `w-10` | show | `final_rank` `tabular-nums text-muted-foreground` |
| 2 | `title` | `Job` | left | `min-w-[240px] max-w-[360px]` (`max-w-[220px]` on `< md`) | show | title, truncated (§3.3). On `< md` a second line `company · location`, `text-xs text-muted-foreground truncate` |
| 3 | `company` | `Company` | left | `min-w-[140px] max-w-[200px]` | hide-md (folds under Job) | company, truncated |
| 4 | `location` | `Lokasi` | left | `min-w-[120px] max-w-[160px]` | hide-md → drawer | cleaned location (§3.4) |
| 5 | `source` | `Source` | left | `w-24` | hide-md → drawer | `source` verbatim (`linkedin`, `indeed`, `jobstreet`) |
| 6 | `family` | `Family` | left | `min-w-[170px]` | hide-md → drawer | `career_family` (`_`→space) + status `Badge` (§3.5) |
| 7 | `kw` | `KW` | right | `w-12` | hide-md → drawer | `keyword_score` integer |
| 8 | `sem` | `Sem` | right | `w-16` | hide-md → drawer | `semantic_raw` **3 dp** (`0.812`) |
| 9 | `final` | `Final` | right | `w-16` | show | `final_score` **1 dp, `font-semibold`** |
| 10 | `reason` | `Sebab` | left | `min-w-[120px]` | show | `Badge` (§3.7) |
| 11 | `status` | `Status` | left | `w-[130px]` | show | `StatusSelect` (§4.1) |
| 12 | `label` | `Label` | left | `w-[110px]` | hide-md → drawer | `LabelSelect` (§4.2) |
| 13 | `link` | `Link` | center | `w-12` | show | `LinkButton` (§5) |
| 14 | `resume` | `Tailored Resume` (`Resume` on `< md`) | left | `w-[160px]` | show | `ResumeButton` (§6) |

Header cells are real `<th scope="col">`. Numeric columns get `text-right` on
`th` and `td`.

Row click opens the drawer (§8). Row: `cursor-pointer tabIndex={0}`, `onClick`
+ Enter key, guarded by `e.target.closest('button, a, [role=combobox]')` so
controls don't open it.

### 3.2 Group header rows (not a second table)

Inside the same `TableBody`, one row before each group:

```html
<tr class="bg-muted/50 hover:bg-muted/50">
  <th scope="rowgroup" colspan="14"
      class="px-2 py-1.5 text-left text-xs font-medium text-muted-foreground">
    Disyorkan (2)
  </th>
</tr>
```

Second: `Ranked, tak disyorkan (4)`. Group A body rows get `bg-primary/5`
(subtle in both themes). Status tints (§3.6) override it — status wins.

### 3.3 Truncation

- `title`: single line, CSS `truncate` inside the `max-w`; full text in the
  `title=""` attribute and in the drawer. No JS character slicing.
- `company`: same, `max-w-[200px]`.

### 3.4 Location cleaning (`lib/format.ts::cleanLocation`)

Mirror `report.py::_loc`: strip `, Malaysia`, `Federal Territory of `, `WP. `,
`, MY`; trim `, `. No 28-char slice — `truncate` handles overflow.

### 3.5 Family status badge

`career_family_status` → code on `Badge variant="outline"` `text-[10px] px-1`:

| status | code | extra classes |
|---|---|---|
| `CORE` / null | `CORE` | — |
| `ADJACENT` | `ADJ` | — |
| `SECONDARY` | `SEC` | `text-muted-foreground` |
| `OUT_OF_SCOPE` | `OUT` | `border-red-300 text-red-700 dark:border-red-800 dark:text-red-400` |

Cell: `<span class="inline-flex items-center gap-1.5 whitespace-nowrap">reconciliation <Badge>CORE</Badge></span>`.

### 3.6 Row background by `job_actions.status`

On `TableRow className`, every table. Put after shadcn's `hover:bg-muted/50`.

| status | row classes | title |
|---|---|---|
| `new` | none (Group A keeps `bg-primary/5`) | — |
| `shortlisted` | none | — |
| `applied` | `bg-green-50 dark:bg-green-950/40` | — |
| `interview` | `bg-blue-50 dark:bg-blue-950/40` | — |
| `offer` | `bg-emerald-100 dark:bg-emerald-900/40` | `font-semibold` |
| `rejected` | `bg-muted/40 text-muted-foreground` | `line-through` |
| `ignored` | `bg-muted/40 text-muted-foreground` | — (dimmed only) |

Rejected = employer said no → crossed out. Ignored = user skipped → dimmed but
readable.

### 3.7 Sebab badge

From `selection_status` (+ `selection_reason` for the disqualifier term, same
parse as `report.py::_reason`). Always a `Badge variant="outline" text-xs`,
lowercase text, no icon. Full `selection_reason` in a `Tooltip` and in the drawer.

| `selection_status` | text | classes |
|---|---|---|
| `selected` | `dipilih` | `border-green-300 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950/40 dark:text-green-300` |
| `out_of_scope` | `out of scope` | `border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300` |
| `disqualified` | term inside `contains '…'` (e.g. `intern`), else `level mismatch` | `border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300` |
| `not_selected`, reason contains `below threshold` | `bawah 60` | `text-muted-foreground` (gray, outline) |
| `not_selected` otherwise | `luar top 5` | `text-muted-foreground` |
| `history_cooldown`, `history_repost_cooldown` | `cooldown` | `border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300` |
| `history_applied` | `dah apply` | slate (as above) |
| `history_ignored` | `diabaikan` | slate |
| `history_repost` | `repost` | slate |
| other | raw status, `_`→space | plain outline |

Contrast: only these pairs (`50/800` light, `950/300` dark) — all ≥ 4.5:1.

### 3.8 Numbers (`lib/format.ts`)

`fmtFinal = n.toFixed(1)` (bold) · `fmtSem = n.toFixed(3)` ·
`fmtKw = Math.round(n)`. Null → `–` in `text-muted-foreground`. All numeric
cells `tabular-nums text-right`.

---

## 4. Inline selects

shadcn `Select`; `SelectTrigger className="h-7 w-full text-xs"`. Must not open
the row drawer (§3.1 guard).

### 4.1 StatusSelect

| value | label | trigger text tint | dot (`span.h-2.w-2.rounded-full` before the label in items) |
|---|---|---|---|
| `new` | `Baru` | — | `bg-muted-foreground/40` |
| `shortlisted` | `Simpan` | — | `bg-muted-foreground/40` |
| `applied` | `Applied` | `text-green-800 dark:text-green-300` | `bg-green-500` |
| `interview` | `Interview` | `text-blue-800 dark:text-blue-300` | `bg-blue-500` |
| `offer` | `Offer` | `text-emerald-800 dark:text-emerald-300 font-semibold` | `bg-emerald-500` |
| `rejected` | `Rejected` | `text-muted-foreground` | `bg-muted-foreground/40` |
| `ignored` | `Abaikan` | `text-muted-foreground` | `bg-muted-foreground/40` |

**Optimistic.** On change: update local state (row tint changes at once),
upsert `job_actions` (`status`; `applied_date = today` when becoming `applied`
and `applied_date` is null; `updated_at = now()`). Error → revert + `toast.error`
`Gagal simpan status — cuba lagi`. Success → no toast (colour is the
confirmation). No `router.refresh()` on Hari Ini — the row stays until reload
(PRD: "hilang dari Disyorkan selepas refresh").

### 4.2 LabelSelect

Placeholder `–` (null, trigger `text-muted-foreground`). Items: `strong` →
`Strong`, `acceptable` → `OK`, `weak` → `Weak`, `reject` → `Reject`; plus
`__clear` → `Buang label` (only when a label exists; deletes the row).

Optimistic upsert to `validation_labels` (`label`, `labelled_at = now()`).
Error → revert + `toast.error` `Gagal simpan label`. No row colouring for
labels — they're calibration input, not pipeline state.

---

## 5. LinkButton

`Button variant="ghost" size="icon" className="h-7 w-7" asChild` →
`<a target="_blank" rel="noopener noreferrer">`, wrapped in `Tooltip`.
`aria-label` = tooltip text.

| condition | icon | tooltip | href |
|---|---|---|---|
| `job_url_direct` | `Send` | `Apply terus` | `job_url_direct` |
| only `job_url` | `ExternalLink` | `Lihat posting` | `job_url` |
| neither | `disabled`, `Link2Off`, `text-muted-foreground` | `Tiada link` | — |

In the drawer the same component renders with `showLabel` → `variant="outline"
size="sm"` with the tooltip text as visible label.

---

## 6. ResumeButton — exactly four states

Inputs per row: `job_actions.resume_status` (`none`/`pending`/`ready`/`failed`),
`resume_url`, `notes` (holds the failure reason, if Backend writes one); page-level
`resumePrereq: { profileReady: boolean; llmKeyReady: boolean }` from the
server (until Backend exposes it, both `false`).

Base: `size="sm" className="h-7 text-xs"`. Column is 160 px; state 4's two
controls must sit on one line.

| # | state | condition | render | copy |
|---|---|---|---|---|
| 1 | **Disabled** | `!profileReady \|\| !llmKeyReady` | `Button variant="outline" disabled`, icon `FileText`. Disabled buttons don't emit pointer events, so the `TooltipTrigger` is a wrapping `span tabIndex={0} className="inline-flex"`. | label `Generate`. Tooltip: `CV induk belum diisi` when `!profileReady`, otherwise `API key LLM belum ditetapkan`. Both missing → CV line only. |
| 2 | **Generate** | prereqs ok, `resume_status in ('none','failed')` | `Button variant="outline"`, icon `Sparkles`. For `failed`: an extra `TriangleAlert h-3.5 w-3.5 text-destructive` before the button, its own `Tooltip` = `Gagal: <notes \| "sebab tak diketahui">`. | `Generate` (retry is the same action) |
| 3 | **Pending** | `resume_status = 'pending'` | `Button variant="outline" disabled`, `Loader2 animate-spin`. | `Menjana… ~1 min` |
| 4 | **Ready** | `resume_status = 'ready' && resume_url` | `Button variant="default" asChild` → `<a href={signedUrl} download>`, icon `Download`; then `Button variant="link" size="sm" className="h-7 px-1 text-xs text-muted-foreground"`. | `Download` · `jana semula` |

Behaviour:

- Generate / jana semula → optimistic `pending` → `POST /api/resume { job_id }`.
  Non-2xx → revert + `toast.error` `Gagal hantar permintaan resume`.
- While any row is `pending`: poll its `job_actions` row every **10 s**; stop
  at `ready`/`failed` or **5 min** (then stay pending, `toast` `Resume masih
  dijana — refresh sekejap lagi`).
- `ready` → `toast.success` `Resume siap`; button becomes Download.
  `resume_url` is a Storage path → signed URL (1 h) resolved server-side at
  render, or `createSignedUrl` in the browser client on demand. Filename
  `Resume - <Company> - <Title>.docx` via the signed URL `download` option.
- `failed` → `toast.error` `Resume gagal: <reason>`; state 2 with the warning icon.

`< md`: states 1–3 are icon-only (`h-7 w-7`, `aria-label` = label + tooltip);
state 4 keeps `Download` text, `jana semula` becomes a `RotateCw` icon button.

---

## 7. Semua Job (`/jobs`)

Header `Semua Job`; subtitle `<n> job · <m> pernah disyorkan`. No Scrape button.

**FilterBar** (`flex flex-wrap items-center gap-2`), above the table:

1. `Input` search: `placeholder="Cari title / company"`, `w-full md:w-64`,
   `Search` icon in a relative wrapper (`pl-8`). Debounce 250 ms; server-side
   `or(title.ilike, company.ilike)`.
2. `Select` Status: `Semua status` + the 7 labels of §4.1.
3. `Select` Family: `Semua family` + distinct `career_family` (`_`→space).
4. `Select` Source: `Semua source` + distinct `source`.
5. Date range on `jobs.last_seen`: two native `Input type="date"` labelled
   `Dari` / `Hingga` (`w-36`). Native pickers work on phones.
6. `Button variant="ghost" size="sm"` `Reset` — only when a filter is active.

Filters live in the URL (`?q=&status=&family=&source=&from=&to=&page=`).
Filtering/pagination server-side; column sort client-side (TanStack) on the
loaded page.

**Table:** `JobsTable variant="all"`:

- No group rows, no `bg-primary/5`.
- Column 1 becomes **`Tarikh`** (`last_seen`, `dd MMM`, `w-16`) — rank is
  per-run and meaningless here. Scores come from the job's **latest**
  `job_scores` row.
- Sortable headers: Tarikh, Job, Company, Final, Status. Header is a
  `Button variant="ghost" size="sm" className="-ml-2 h-7"` with `ArrowUpDown
  h-3 w-3 ml-1 text-muted-foreground`; `aria-sort` set. Default: Tarikh desc,
  Final desc.
- Pagination: 50/page; below the table `flex items-center justify-end gap-2`:
  `Halaman 2 / 7` (`text-sm text-muted-foreground`), `Button variant="outline"
  size="sm"` `Sebelum` / `Seterusnya`.
- Empty with filters: one row `Tiada job sepadan.` Empty with no data at all:
  §2.4 card, `Belum ada job` / `Jalankan scrape dulu.`

---

## 8. Job detail drawer (`JobDrawer`)

shadcn `Sheet side="right"`, `SheetContent className="w-full sm:max-w-xl
overflow-y-auto"`. Full-width below `sm`. Opened by row click; URL unchanged.
`/jobs/[id]` also exists as a full page rendering the same sections in a `Card`
(fallback / deep link).

Sections in order, `Separator className="my-4"` between:

1. **Header** (`SheetHeader`): `SheetTitle` full title (`text-base`, wraps);
   `SheetDescription` `company · location · source`. Actions row `flex gap-2
   mt-2`: `LinkButton showLabel`, `ResumeButton`.
2. **Tindakan**: `grid grid-cols-2 gap-3` of `Label` `Status` → `StatusSelect`,
   `Label` `Label` → `LabelSelect`. Below: `Label` `Nota` + `Textarea rows={3}
   placeholder="Nota peribadi…"`, saved on blur to `job_actions.notes`
   (`toast.success` `Nota disimpan` — the one success toast, since nothing
   else visibly confirms it).
3. **Skor**: `dl` `grid grid-cols-3 gap-x-4 gap-y-1 text-sm` (`dt`
   `text-xs text-muted-foreground`): `Final` (bold, 1 dp) · `KW` · `Sem`
   (3 dp) · `Rank` (`#3 / 10`) · `Sem rank` · `Sem (scaled)` (`semantic_score`
   1 dp). Then `Strongest match: <strongest_profile_match>`.
4. **Sebab**: §3.7 `Badge` then `selection_reason` verbatim (`text-sm`).
   `Family:` name + §3.5 badge; `career_family_reason` in
   `text-sm text-muted-foreground`.
5. **Matched keywords**: `matched_keywords[]` as `Badge variant="secondary"`
   in `flex flex-wrap gap-1`. Empty → `Tiada.`
6. **Sejarah** (`text-sm space-y-1`): `Pertama nampak: 03 Sep 2026` ·
   `Terakhir: 12 Sep 2026` · `Muncul: 4 kali` · `History: <history_status> —
   <history_reason>` · `Run:` dates this job appeared in (from `job_scores`),
   each a `Link` to `/runs/[id]`, newest first, max 10.
7. **Description**: `whitespace-pre-wrap text-sm leading-relaxed`. Over 2000
   chars → clamp with `line-clamp-[12]` + `Button variant="link"` `Tunjuk semua`.

---

## 9. Runs (`/runs`)

Header `Runs` + the same Scrape sekarang button.

`RunsTable`: plain `Table`, newest first, 50/page (same pager as §7).

| header | content |
|---|---|
| `Masa` | `started_at` `dd MMM yyyy, HH:mm` MYT; second line `text-xs text-muted-foreground` duration `2m 41s` when finished |
| `Trigger` | `cron` / `manual`, `text-muted-foreground` |
| `Scraped` | `raw_count` |
| `Ranked` | `ranked` |
| `Disyorkan` | `selected`, `font-semibold` |
| `Status` | `Badge`: `ok` → green (§3.7 selected style); `running` → outline + `Loader2 animate-spin h-3 w-3`; `failed` → red (§3.7 out-of-scope style); **`0 scraped`** → amber (§3.7 disqualified style) when `status='ok' && raw_count=0` |
| `Funnel` | `hidden lg:table-cell`; §2.2 line for that run, `text-xs text-muted-foreground` |

Row click → `/runs/[id]`: header `Run 12 Sep 2026, 07:41`, §2.5 banner rule,
funnel line, then `JobsTable variant="today"` for that run. Failed run's
`error` shows in the banner.

Empty: §2.4 card, `Belum ada run.` / `Tekan Scrape sekarang.`

---

## 10. Login (`/login`)

`main` `flex min-h-svh items-center justify-center p-4`; one `Card`
`w-full max-w-sm`:

- `CardHeader`: `CardTitle` `Job Shortlist`; `CardDescription` `Log masuk untuk
  tengok shortlist hari ini.`
- `CardContent` `space-y-4`: `Label` `Email` + `Input type="email"
  autoComplete="email"`; `Label` `Kata laluan` + `Input type="password"
  autoComplete="current-password"`; error `p.text-sm.text-destructive` `Email
  atau kata laluan salah.`; `Button className="w-full"` `Log masuk` (`Loader2`
  + `Sedang log masuk…` while pending).
- No sign-up, no forgot-password, no logo.

Unauthenticated `(app)` routes → `/login?next=…`; after login → `next` or `/today`.

---

## 11. Responsive summary

| width | behaviour |
|---|---|
| `< 768` | Hidden: Company (folds under Job), Lokasi, Source, Family, KW, Sem, Label → all in the drawer. Remaining 7 columns ≈ 640 px; scrolls inside the wrapper. Resume icon-only. Drawer full-width. Toasts top-center. |
| `768–1279` | All columns; horizontal scroll inside the wrapper. |
| `≥ 1280` | Fits `max-w-screen-2xl` without scrolling. Runs shows Funnel at `lg`. |

Touch: every control in a row is `h-7` (28 px) with `py-1.5` cells → rows ≈
40 px. The whole row is also tappable (drawer), so precision isn't needed.

---

## 12. Accessibility basics

- Real `<table>`; `<th scope="col">` headers, `<th scope="rowgroup">` group
  rows, `sr-only` caption.
- Icon-only buttons carry `aria-label` = tooltip text.
- Selects are Radix (keyboard-navigable). Only the two date inputs are native.
- Focus rings untouched. Rows `tabIndex={0}` + Enter opens the drawer.
- Badge contrast: only the pairs in §3.5/§3.7; never `-100/-600` combos.
- Colour is never the only signal: status text is visible, rejected is struck
  through, offer is bold, Sebab is text.
- `aria-busy` on skeleton/polling containers; `motion-reduce:animate-none`
  on every spinner.

---

## 13. Decisions made here (override if you disagree)

1. **Label column is in the Hari Ini table** (between Status and Link) — PRD
   §7.2 lists it as a control even though the header row omits it. Hidden `< md`.
2. **`shortlisted` is a Status option** (`Simpan`) since the data enum has it;
   no row tint.
3. **`rejected` = strikethrough; `ignored` = dimmed only.**
4. **Disyorkan rows tinted `bg-primary/5`**; status tints win.
5. **No `router.refresh()` after a status change on Hari Ini** — applied rows
   stay until reload.
6. **Semua Job swaps `#` for `Tarikh`** and shows scores from the latest run.
7. **Native date inputs**; no Calendar/Popover.
8. **Drawer doesn't change the URL**; `/jobs/[id]` is a plain fallback page.
9. **Polling:** scrape 10 s / 20 min cap; resume 10 s / 5 min cap.
10. **Resume tooltip shows only the CV reason when both prereqs are missing.**
11. **No theme toggle**; follows OS.
12. **`bawah 60` hard-codes the threshold** for MVP (Settings is read-only v2).
13. **Resume failure reason is read from `job_actions.notes`** until Backend
    adds a dedicated column — flag to Backend.
