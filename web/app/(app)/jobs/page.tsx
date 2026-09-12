import { Briefcase } from "lucide-react";
import { Suspense } from "react";

import { EmptyState } from "@/components/empty-state";
import { FilterBar } from "@/components/filter-bar";
import { JobsAllTable } from "@/components/jobs-all-table";
import { Pager } from "@/components/pager";
import { RESUME_PREREQ_OK } from "@/lib/env";
import { getJobsMeta, getJobsPage } from "@/lib/queries";
import { JOB_STATUSES } from "@/lib/supabase/types";
import type { JobStatus, JobsFilters } from "@/lib/types";

export const dynamic = "force-dynamic";

type Search = Record<string, string | string[] | undefined>;
type Props = { searchParams: Promise<Search> };

function one(v: string | string[] | undefined): string | undefined {
  const s = Array.isArray(v) ? v[0] : v;
  return s ? s : undefined;
}

const DATE = /^\d{4}-\d{2}-\d{2}$/;

function parseFilters(sp: Search): JobsFilters {
  const status = one(sp.status);
  const from = one(sp.from);
  const to = one(sp.to);
  const page = Number.parseInt(one(sp.page) ?? "1", 10);
  return {
    q: one(sp.q)?.slice(0, 100),
    status:
      status && (JOB_STATUSES as readonly string[]).includes(status)
        ? (status as JobStatus)
        : undefined,
    family: one(sp.family),
    source: one(sp.source),
    from: from && DATE.test(from) ? from : undefined,
    to: to && DATE.test(to) ? to : undefined,
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

function hrefFor(filters: JobsFilters) {
  return (page: number) => {
    const params = new URLSearchParams();
    for (const k of ["q", "status", "family", "source", "from", "to"] as const) {
      const v = filters[k];
      if (v) params.set(k, v);
    }
    if (page > 1) params.set("page", String(page));
    const qs = params.toString();
    return qs ? `/jobs?${qs}` : "/jobs";
  };
}

export default async function JobsPage({ searchParams }: Props) {
  const filters = parseFilters(await searchParams);
  const [meta, page] = await Promise.all([getJobsMeta(), getJobsPage(filters)]);
  const prereq = { profileReady: RESUME_PREREQ_OK };
  const active = Boolean(
    filters.q || filters.status || filters.family || filters.source || filters.from || filters.to,
  );

  return (
    <>
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Semua Job</h1>
          <p className="text-sm text-muted-foreground">
            {meta.total} job · {meta.shortlisted} pernah disyorkan
          </p>
        </div>
      </div>

      {meta.total === 0 && !active ? (
        <EmptyState icon={Briefcase} title="Belum ada job" body="Jalankan scrape dulu." />
      ) : (
        <>
          <Suspense>
            <FilterBar value={filters} families={meta.families} sources={meta.sources} />
          </Suspense>
          <JobsAllTable
            rows={page.rows}
            resumePrereq={prereq}
            emptyMessage="Tiada job sepadan."
          />
          <Pager page={page.page} pageCount={page.pageCount} hrefFor={hrefFor(filters)} />
        </>
      )}
    </>
  );
}
