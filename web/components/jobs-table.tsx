"use client";

import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { FamilyBadge } from "@/components/family-badge";
import { JobDrawer } from "@/components/job-drawer";
import { LabelSelect } from "@/components/label-select";
import { LinkButton } from "@/components/link-button";
import { ResumeButton, failureReason } from "@/components/resume-button";
import { SebabBadge } from "@/components/sebab-badge";
import { StatusSelect } from "@/components/status-select";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  cleanLocation,
  fmtDayMonthMYT,
  fmtFinal,
  fmtKw,
  fmtSem,
} from "@/lib/format";
import type { JobRow, JobStatus, ResumePrereq } from "@/lib/types";
import { cn } from "@/lib/utils";

type Align = "left" | "right" | "center";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData, TValue> {
    headClass?: string;
    cellClass?: string;
    align?: Align;
    hideMd?: boolean;
    sortable?: boolean;
  }
}

export interface JobsTableProps {
  rows: JobRow[];
  /** 'today' = grouped with '#' rank col; 'all' = flat with 'Tarikh' col. */
  variant: "today" | "all";
  resumePrereq: ResumePrereq;
  caption: string;
  sorting?: SortingState;
  onSortingChange?: (s: SortingState) => void;
  /** Shown as one full-width row when there are no rows at all. */
  emptyMessage?: string;
  onOpen?: (row: JobRow) => void;
}

const ROW_TINT: Record<JobStatus, string> = {
  new: "",
  shortlisted: "",
  applied: "bg-green-50 hover:bg-green-100/60 dark:bg-green-950/40",
  interview: "bg-blue-50 hover:bg-blue-100/60 dark:bg-blue-950/40",
  offer: "bg-emerald-100 hover:bg-emerald-200/60 dark:bg-emerald-900/40",
  rejected: "bg-muted/40 text-muted-foreground",
  ignored: "bg-muted/40 text-muted-foreground",
};

const CELL = "px-2 py-1.5";
const HEAD = "h-9 px-2 text-xs font-medium text-muted-foreground";

function alignClass(a: Align | undefined) {
  return a === "right" ? "text-right" : a === "center" ? "text-center" : "text-left";
}

export function JobsTable({
  rows,
  variant,
  resumePrereq,
  caption,
  sorting: sortingProp,
  onSortingChange,
  emptyMessage = "Tiada job.",
  onOpen,
}: JobsTableProps) {
  const [data, setData] = useState<JobRow[]>(rows);
  useEffect(() => setData(rows), [rows]);

  const [openId, setOpenId] = useState<string | null>(null);
  const openRow = useMemo(
    () => data.find((r) => r.jobId === openId) ?? null,
    [data, openId],
  );

  const [internalSorting, setInternalSorting] = useState<SortingState>([]);
  const sorting = sortingProp ?? internalSorting;
  const setSorting = onSortingChange ?? setInternalSorting;

  const patchRow = useCallback((jobId: string, patch: Partial<JobRow>) => {
    setData((prev) =>
      prev.map((r) => (r.jobId === jobId ? { ...r, ...patch } : r)),
    );
  }, []);

  const columns = useMemo<ColumnDef<JobRow>[]>(() => {
    const first: ColumnDef<JobRow> =
      variant === "today"
        ? {
            id: "rank",
            accessorKey: "finalRank",
            header: "#",
            meta: { headClass: "w-10", align: "right" },
            cell: ({ row }) => (
              <span className="tabular-nums text-muted-foreground">
                {row.original.finalRank ?? "–"}
              </span>
            ),
          }
        : {
            id: "date",
            accessorKey: "lastSeen",
            header: "Tarikh",
            meta: { headClass: "w-16", sortable: true },
            sortingFn: (a, b) =>
              Date.parse(a.original.lastSeen) - Date.parse(b.original.lastSeen),
            cell: ({ row }) => (
              <span className="tabular-nums whitespace-nowrap">
                {fmtDayMonthMYT(row.original.lastSeen)}
              </span>
            ),
          };

    return [
      first,
      {
        id: "title",
        accessorKey: "title",
        header: "Job",
        meta: {
          headClass: "min-w-[240px]",
          cellClass: "max-w-[220px] md:max-w-[360px] whitespace-normal",
          sortable: variant === "all",
        },
        cell: ({ row }) => {
          const r = row.original;
          return (
            <div className="min-w-0">
              <div
                className={cn(
                  "truncate",
                  r.status === "offer" && "font-semibold",
                  r.status === "rejected" && "line-through",
                )}
                title={r.title}
              >
                {r.title}
              </div>
              <div className="truncate text-xs text-muted-foreground md:hidden">
                {r.company ?? "–"} · {cleanLocation(r.location)}
              </div>
            </div>
          );
        },
      },
      {
        id: "company",
        accessorKey: "company",
        header: "Company",
        meta: {
          headClass: "min-w-[140px]",
          cellClass: "max-w-[200px] truncate",
          hideMd: true,
          sortable: variant === "all",
        },
        cell: ({ row }) => (
          <span title={row.original.company ?? undefined}>
            {row.original.company ?? "–"}
          </span>
        ),
      },
      {
        id: "location",
        accessorKey: "location",
        header: "Lokasi",
        meta: {
          headClass: "min-w-[120px]",
          cellClass: "max-w-[160px] truncate",
          hideMd: true,
        },
        cell: ({ row }) => cleanLocation(row.original.location),
      },
      {
        id: "source",
        accessorKey: "source",
        header: "Source",
        meta: { headClass: "w-24", cellClass: "text-muted-foreground", hideMd: true },
        cell: ({ row }) => row.original.source ?? "–",
      },
      {
        id: "family",
        accessorKey: "careerFamily",
        header: "Family",
        meta: { headClass: "min-w-[170px]", hideMd: true },
        cell: ({ row }) => (
          <FamilyBadge
            family={row.original.careerFamily}
            status={row.original.careerFamilyStatus}
          />
        ),
      },
      {
        id: "kw",
        accessorKey: "keywordScore",
        header: "KW",
        meta: { headClass: "w-12", align: "right", hideMd: true },
        cell: ({ row }) => (
          <span className="tabular-nums">{fmtKw(row.original.keywordScore)}</span>
        ),
      },
      {
        id: "sem",
        accessorKey: "semanticRaw",
        header: "Sem",
        meta: { headClass: "w-16", align: "right", hideMd: true },
        cell: ({ row }) => (
          <span className="tabular-nums">{fmtSem(row.original.semanticRaw)}</span>
        ),
      },
      {
        id: "final",
        accessorKey: "finalScore",
        header: "Final",
        meta: { headClass: "w-16", align: "right", sortable: variant === "all" },
        sortingFn: (a, b) =>
          (a.original.finalScore ?? -1) - (b.original.finalScore ?? -1),
        cell: ({ row }) => (
          <span
            className={cn(
              "tabular-nums font-semibold",
              row.original.finalScore == null && "font-normal text-muted-foreground",
            )}
          >
            {fmtFinal(row.original.finalScore)}
          </span>
        ),
      },
      {
        id: "reason",
        accessorKey: "selectionStatus",
        header: "Sebab",
        meta: { headClass: "min-w-[120px]" },
        cell: ({ row }) => (
          <SebabBadge
            status={row.original.selectionStatus || null}
            reason={row.original.selectionReason}
          />
        ),
      },
      {
        id: "status",
        accessorKey: "status",
        header: "Status",
        meta: { headClass: "w-[130px]", sortable: variant === "all" },
        cell: ({ row }) => (
          <StatusSelect
            jobId={row.original.jobId}
            value={row.original.status}
            appliedDate={row.original.appliedDate}
            onChange={(status) => patchRow(row.original.jobId, { status })}
          />
        ),
      },
      {
        id: "label",
        accessorKey: "label",
        header: "Label",
        meta: { headClass: "w-[110px]", hideMd: true },
        cell: ({ row }) => (
          <LabelSelect
            jobId={row.original.jobId}
            value={row.original.label}
            onChange={(label) => patchRow(row.original.jobId, { label })}
          />
        ),
      },
      {
        id: "link",
        header: "Link",
        meta: { headClass: "w-12", align: "center" },
        cell: ({ row }) => (
          <LinkButton
            jobUrl={row.original.jobUrl}
            jobUrlDirect={row.original.jobUrlDirect}
          />
        ),
      },
      {
        id: "resume",
        header: () => (
          <>
            <span className="hidden md:inline">Tailored Resume</span>
            <span className="md:hidden">Resume</span>
          </>
        ),
        meta: { headClass: "w-[160px]" },
        cell: ({ row }) => (
          <ResumeButton
            jobId={row.original.jobId}
            resumeStatus={row.original.resumeStatus}
            resumeUrl={row.original.resumeUrl}
            failureReason={failureReason(row.original.notes)}
            prereq={resumePrereq}
            title={row.original.title}
            company={row.original.company}
            onChange={(patch) => patchRow(row.original.jobId, patch)}
          />
        ),
      },
    ];
  }, [variant, patchRow, resumePrereq]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: (updater) => {
      const next = typeof updater === "function" ? updater(sorting) : updater;
      setSorting(next);
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualSorting: variant === "today",
    getRowId: (r) => r.jobId,
  });

  const colCount = columns.length;
  const allRows = table.getRowModel().rows;
  const groupA = variant === "today" ? allRows.filter((r) => r.original.selectionStatus === "selected") : [];
  const groupB = variant === "today" ? allRows.filter((r) => r.original.selectionStatus !== "selected") : allRows;

  function open(row: JobRow) {
    if (onOpen) onOpen(row);
    else setOpenId(row.jobId);
  }

  function onRowClick(e: React.MouseEvent | React.KeyboardEvent, row: JobRow) {
    const target = e.target as HTMLElement;
    if (target.closest("button, a, [role=combobox], [role=listbox], input, textarea")) return;
    open(row);
  }

  const renderRow = (row: (typeof allRows)[number], highlight: boolean) => {
    const r = row.original;
    return (
      <TableRow
        key={row.id}
        tabIndex={0}
        className={cn(
          "cursor-pointer",
          highlight && ROW_TINT[r.status] === "" && "bg-primary/5 hover:bg-primary/10",
          ROW_TINT[r.status],
        )}
        onClick={(e) => onRowClick(e, r)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && e.target === e.currentTarget) onRowClick(e, r);
        }}
      >
        {row.getVisibleCells().map((cell) => {
          const meta = cell.column.columnDef.meta;
          return (
            <TableCell
              key={cell.id}
              className={cn(
                CELL,
                alignClass(meta?.align),
                meta?.hideMd && "hidden md:table-cell",
                meta?.cellClass,
              )}
            >
              {flexRender(cell.column.columnDef.cell, cell.getContext())}
            </TableCell>
          );
        })}
      </TableRow>
    );
  };

  const GroupHeader = ({ label }: { label: string }) => (
    <tr className="border-b bg-muted/50 hover:bg-muted/50">
      <th
        scope="rowgroup"
        colSpan={colCount}
        className="px-2 py-1.5 text-left text-xs font-medium text-muted-foreground"
      >
        {label}
      </th>
    </tr>
  );

  const FullRow = ({ children }: { children: React.ReactNode }) => (
    <TableRow className="hover:bg-transparent">
      <TableCell
        colSpan={colCount}
        className="whitespace-normal py-6 text-center text-muted-foreground"
      >
        {children}
      </TableCell>
    </TableRow>
  );

  return (
    <>
      <div className="rounded-md border">
        <div className="overflow-x-auto">
          <Table className="min-w-[640px] md:min-w-[1180px]">
            <TableCaption className="sr-only">{caption}</TableCaption>
            <TableHeader>
              {table.getHeaderGroups().map((hg) => (
                <TableRow key={hg.id} className="hover:bg-transparent">
                  {hg.headers.map((header) => {
                    const meta = header.column.columnDef.meta;
                    const sortable = Boolean(meta?.sortable);
                    const dir = header.column.getIsSorted();
                    return (
                      <TableHead
                        key={header.id}
                        scope="col"
                        aria-sort={
                          sortable
                            ? dir === "asc"
                              ? "ascending"
                              : dir === "desc"
                                ? "descending"
                                : "none"
                            : undefined
                        }
                        className={cn(
                          HEAD,
                          alignClass(meta?.align),
                          meta?.hideMd && "hidden md:table-cell",
                          meta?.headClass,
                        )}
                      >
                        {sortable ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="-ml-2 h-7 text-xs font-medium text-muted-foreground"
                            onClick={header.column.getToggleSortingHandler()}
                          >
                            {flexRender(header.column.columnDef.header, header.getContext())}
                            <ArrowUpDown className="ml-1 h-3 w-3 text-muted-foreground" />
                          </Button>
                        ) : (
                          flexRender(header.column.columnDef.header, header.getContext())
                        )}
                      </TableHead>
                    );
                  })}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {allRows.length === 0 ? (
                <FullRow>{emptyMessage}</FullRow>
              ) : variant === "today" ? (
                <>
                  <GroupHeader label={`Disyorkan (${groupA.length})`} />
                  {groupA.length === 0 ? (
                    <FullRow>
                      Tiada job cukup kuat hari ini. Standard tidak diturunkan
                      untuk penuhkan senarai.
                    </FullRow>
                  ) : (
                    groupA.map((row) => renderRow(row, true))
                  )}
                  {groupB.length > 0 ? (
                    <>
                      <GroupHeader label={`Ranked, tak disyorkan (${groupB.length})`} />
                      {groupB.map((row) => renderRow(row, false))}
                    </>
                  ) : null}
                </>
              ) : (
                groupB.map((row) => renderRow(row, false))
              )}
            </TableBody>
          </Table>
        </div>
      </div>
      {onOpen ? null : (
        <JobDrawer
          row={openRow}
          resumePrereq={resumePrereq}
          onOpenChange={(o) => {
            if (!o) setOpenId(null);
          }}
          onRowChange={(patch) => {
            if (openRow) patchRow(openRow.jobId, patch);
          }}
        />
      )}
    </>
  );
}
