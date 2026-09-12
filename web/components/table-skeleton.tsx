import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const COLS: { label: string; head: string; w: string; hideMd?: boolean }[] = [
  { label: "#", head: "w-10 text-right", w: "w-6" },
  { label: "Job", head: "min-w-[240px]", w: "w-48" },
  { label: "Company", head: "min-w-[140px]", w: "w-28", hideMd: true },
  { label: "Lokasi", head: "min-w-[120px]", w: "w-24", hideMd: true },
  { label: "Source", head: "w-24", w: "w-16", hideMd: true },
  { label: "Family", head: "min-w-[170px]", w: "w-32", hideMd: true },
  { label: "KW", head: "w-12 text-right", w: "w-6", hideMd: true },
  { label: "Sem", head: "w-16 text-right", w: "w-10", hideMd: true },
  { label: "Final", head: "w-16 text-right", w: "w-10" },
  { label: "Sebab", head: "min-w-[120px]", w: "w-16" },
  { label: "Status", head: "w-[130px]", w: "w-24" },
  { label: "Label", head: "w-[110px]", w: "w-20", hideMd: true },
  { label: "Link", head: "w-12 text-center", w: "w-6" },
  { label: "Resume", head: "w-[160px]", w: "w-24" },
];

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="rounded-md border" aria-busy="true">
      <div className="overflow-x-auto">
        <Table className="min-w-[640px] md:min-w-[1180px]">
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {COLS.map((c) => (
                <TableHead
                  key={c.label}
                  scope="col"
                  className={`h-9 px-2 text-xs font-medium text-muted-foreground ${c.head} ${
                    c.hideMd ? "hidden md:table-cell" : ""
                  }`}
                >
                  {c.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {Array.from({ length: rows }).map((_, i) => (
              <TableRow key={i} className="hover:bg-transparent">
                {COLS.map((c) => (
                  <TableCell
                    key={c.label}
                    className={`px-2 py-1.5 ${c.hideMd ? "hidden md:table-cell" : ""}`}
                  >
                    <Skeleton className={`h-4 ${c.w}`} />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

export function PageSkeleton({ withFunnel = true }: { withFunnel?: boolean }) {
  return (
    <div className="space-y-4" aria-busy="true">
      <div className="flex items-center justify-between gap-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-8 w-36" />
      </div>
      {withFunnel ? <Skeleton className="h-4 w-full max-w-2xl" /> : null}
      <TableSkeleton />
    </div>
  );
}
