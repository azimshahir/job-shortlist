import type { LucideIcon } from "lucide-react";

import { Card } from "@/components/ui/card";

export function EmptyState({
  icon: Icon,
  title,
  body,
}: {
  icon: LucideIcon;
  title: string;
  body?: string;
}) {
  return (
    <Card className="space-y-2 p-8 text-center">
      <Icon className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden />
      <p className="text-base font-medium">{title}</p>
      {body ? <p className="text-sm text-muted-foreground">{body}</p> : null}
    </Card>
  );
}
