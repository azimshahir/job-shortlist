import { TriangleAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { RunRow } from "@/lib/types";

/** Renders only when the run scraped 0 jobs or failed (design.md §2.5). */
export function ScraperFailedAlert({ run }: { run: RunRow }) {
  if (run.status === "running") return null;
  if (run.rawCount !== 0 && run.status !== "failed") return null;
  return (
    <Alert variant="destructive">
      <TriangleAlert />
      <AlertTitle>Scraper gagal</AlertTitle>
      <AlertDescription>
        0 job dijumpai — ini bukan market kosong, ini scraper tak jalan dengan
        betul. {run.error ? `${run.error} ` : ""}Cuba Scrape sekarang; kalau
        masih 0, semak GitHub Actions.
      </AlertDescription>
    </Alert>
  );
}
