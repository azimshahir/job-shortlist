import { Badge } from "@/components/ui/badge";
import { familyCode, familyName } from "@/lib/format";
import type { FamilyStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const CODE_CLASS: Record<ReturnType<typeof familyCode>, string> = {
  CORE: "",
  ADJ: "",
  SEC: "text-muted-foreground",
  OUT: "border-red-300 text-red-700 dark:border-red-800 dark:text-red-400",
};

export function FamilyBadge({
  family,
  status,
}: {
  family: string | null;
  status: FamilyStatus | null;
}) {
  const code = familyCode(status);
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      {familyName(family)}
      <Badge
        variant="outline"
        className={cn("h-4 rounded-md px-1 text-[10px]", CODE_CLASS[code])}
      >
        {code}
      </Badge>
    </span>
  );
}
