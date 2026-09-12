import { CalendarX } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { FunnelLine } from "@/components/funnel-line";
import { JobsTable } from "@/components/jobs-table";
import { ScrapeButton } from "@/components/scrape-button";
import { ScraperFailedAlert } from "@/components/scraper-failed-alert";
import { RESUME_PREREQ_OK } from "@/lib/env";
import { fmtDateTimeMYT } from "@/lib/format";
import {
  getLatestRun,
  getRunById,
  getRunJobs,
  getTodayRun,
} from "@/lib/queries";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ run?: string }> };

export default async function TodayPage({ searchParams }: Props) {
  const { run: runParam } = await searchParams;
  const latest = await getLatestRun();
  const run = runParam ? await getRunById(runParam) : await getTodayRun();
  const rows = run ? await getRunJobs(run.id) : [];
  const prereq = { profileReady: RESUME_PREREQ_OK };

  const title = runParam && run ? `Run ${fmtDateTimeMYT(run.startedAt)}` : "Hari Ini";
  const subtitle = run
    ? runParam
      ? `${run.trigger} · ${run.status}`
      : `Run terakhir: ${fmtDateTimeMYT(run.startedAt)} · ${run.trigger}`
    : latest
      ? `Run terakhir: ${fmtDateTimeMYT(latest.startedAt)} · ${latest.trigger}`
      : null;

  return (
    <>
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold">{title}</h1>
          {subtitle ? (
            <p className="text-sm text-muted-foreground">{subtitle}</p>
          ) : null}
        </div>
        <ScrapeButton latestRun={latest} />
      </div>

      {!run ? (
        runParam ? (
          <EmptyState
            icon={CalendarX}
            title="Run tidak dijumpai"
            body="Mungkin dah dipadam atau bukan milik anda."
          />
        ) : (
          <EmptyState
            icon={CalendarX}
            title="Belum ada run hari ini"
            body="Cron jalan 07:40 pagi. Atau tekan Scrape sekarang."
          />
        )
      ) : (
        <>
          <ScraperFailedAlert run={run} />
          <FunnelLine run={run} />
          <JobsTable
            rows={rows}
            variant="today"
            resumePrereq={prereq}
            caption={runParam ? `Run ${fmtDateTimeMYT(run.startedAt)}` : "Shortlist hari ini"}
            emptyMessage={
              run.status === "running"
                ? "Scrape sedang berjalan…"
                : "Tiada job lepas keyword hari ini."
            }
          />
          <p className="mt-2 text-xs text-muted-foreground">
            Sem = raw cosine ke profil; ranking aid, bukan kebarangkalian dapat
            kerja.
          </p>
        </>
      )}
    </>
  );
}
