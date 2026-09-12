import { CalendarX } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { Pager } from "@/components/pager";
import { RunsTable } from "@/components/runs-table";
import { ScrapeButton } from "@/components/scrape-button";
import { getLatestRun, getRunsPage } from "@/lib/queries";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ page?: string }> };

export default async function RunsPage({ searchParams }: Props) {
  const { page: pageParam } = await searchParams;
  const parsed = Number.parseInt(pageParam ?? "1", 10);
  const page = Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  const [latest, data] = await Promise.all([getLatestRun(), getRunsPage(page)]);

  return (
    <>
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-lg font-semibold">Runs</h1>
        <ScrapeButton latestRun={latest} />
      </div>
      {data.total === 0 ? (
        <EmptyState icon={CalendarX} title="Belum ada run." body="Tekan Scrape sekarang." />
      ) : (
        <>
          <RunsTable runs={data.runs} />
          <Pager
            page={page}
            pageCount={data.pageCount}
            hrefFor={(p) => (p > 1 ? `/runs?page=${p}` : "/runs")}
          />
        </>
      )}
    </>
  );
}
