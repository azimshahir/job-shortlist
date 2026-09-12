import { FileQuestion } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { JobPageCard } from "@/components/job-page-card";
import { Button } from "@/components/ui/button";
import { RESUME_PREREQ_OK } from "@/lib/env";
import { getJobById, getJobRunHistory } from "@/lib/queries";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ id: string }> };

export default async function JobPage({ params }: Props) {
  const { id } = await params;
  const jobId = decodeURIComponent(id);
  const [row, history] = await Promise.all([
    getJobById(jobId),
    getJobRunHistory(jobId),
  ]);

  return (
    <>
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-lg font-semibold">Job</h1>
        <Button asChild variant="outline" size="sm">
          <Link href="/jobs">Semua Job</Link>
        </Button>
      </div>
      {row ? (
        <JobPageCard
          row={row}
          runHistory={history}
          resumePrereq={{ profileReady: RESUME_PREREQ_OK }}
        />
      ) : (
        <EmptyState
          icon={FileQuestion}
          title="Job tidak dijumpai"
          body="Mungkin dah dipadam atau bukan milik anda."
        />
      )}
    </>
  );
}
