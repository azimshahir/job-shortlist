import Link from "next/link";

import { Button } from "@/components/ui/button";

export function Pager({
  page,
  pageCount,
  hrefFor,
}: {
  page: number;
  pageCount: number;
  hrefFor: (page: number) => string;
}) {
  if (pageCount <= 1) return null;
  const hasPrev = page > 1;
  const hasNext = page < pageCount;
  return (
    <nav aria-label="Halaman" className="flex items-center justify-end gap-2">
      <span className="text-sm text-muted-foreground">
        Halaman {page} / {pageCount}
      </span>
      {hasPrev ? (
        <Button asChild variant="outline" size="sm">
          <Link href={hrefFor(page - 1)}>Sebelum</Link>
        </Button>
      ) : (
        <Button variant="outline" size="sm" disabled>
          Sebelum
        </Button>
      )}
      {hasNext ? (
        <Button asChild variant="outline" size="sm">
          <Link href={hrefFor(page + 1)}>Seterusnya</Link>
        </Button>
      ) : (
        <Button variant="outline" size="sm" disabled>
          Seterusnya
        </Button>
      )}
    </nav>
  );
}
