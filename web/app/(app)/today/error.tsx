"use client";

import { ErrorAlert } from "@/components/error-alert";

export default function Error(props: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <ErrorAlert {...props} />;
}
