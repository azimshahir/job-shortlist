"use client";

import { TriangleAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export function ErrorAlert({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <Alert variant="destructive">
      <TriangleAlert />
      <AlertTitle>Tak dapat muat data</AlertTitle>
      <AlertDescription className="space-y-2">
        <p className="font-mono text-xs break-words">{error.message}</p>
        <Button variant="outline" size="sm" onClick={reset}>
          Cuba lagi
        </Button>
      </AlertDescription>
    </Alert>
  );
}
