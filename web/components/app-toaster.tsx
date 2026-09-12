"use client";

import { Toaster } from "@/components/ui/sonner";
import { useMediaQuery } from "@/hooks/use-media-query";

/** bottom-right on md+, top-center on phones (design.md §0). */
export function AppToaster() {
  const isMd = useMediaQuery("(min-width: 768px)");
  return (
    <Toaster
      position={isMd ? "bottom-right" : "top-center"}
      duration={4000}
      closeButton
    />
  );
}
