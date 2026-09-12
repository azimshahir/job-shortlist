"use client";

import { ExternalLink, Link2Off, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface LinkButtonProps {
  jobUrl: string | null;
  jobUrlDirect: string | null;
  /** Drawer variant: outline button with the tooltip text as visible label. */
  showLabel?: boolean;
  className?: string;
}

export function LinkButton({
  jobUrl,
  jobUrlDirect,
  showLabel = false,
  className,
}: LinkButtonProps) {
  const href = jobUrlDirect || jobUrl || null;
  const direct = Boolean(jobUrlDirect);
  const label = !href ? "Tiada link" : direct ? "Apply terus" : "Lihat posting";
  const Icon = !href ? Link2Off : direct ? Send : ExternalLink;

  if (!href) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex" tabIndex={0}>
            <Button
              variant={showLabel ? "outline" : "ghost"}
              size={showLabel ? "sm" : "icon-sm"}
              disabled
              className={cn("text-muted-foreground", className)}
              aria-label={label}
            >
              <Icon />
              {showLabel ? label : null}
            </Button>
          </span>
        </TooltipTrigger>
        <TooltipContent>{label}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          asChild
          variant={showLabel ? "outline" : "ghost"}
          size={showLabel ? "sm" : "icon-sm"}
          className={className}
        >
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={label}
          >
            <Icon />
            {showLabel ? label : null}
          </a>
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
