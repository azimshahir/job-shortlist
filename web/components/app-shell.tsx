"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { UserMenu } from "@/components/user-menu";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/today", label: "Hari Ini" },
  { href: "/jobs", label: "Semua Job" },
  { href: "/runs", label: "Runs" },
] as const;

export function AppShell({
  email,
  children,
}: {
  email: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  return (
    <>
      <header className="sticky top-0 z-40 h-14 border-b bg-background">
        <div className="mx-auto flex h-14 max-w-screen-2xl items-center gap-3 px-4 md:gap-6 md:px-6">
          <Link href="/today" className="text-sm font-semibold whitespace-nowrap">
            Job Shortlist
          </Link>
          <nav aria-label="Utama" className="flex items-center gap-1">
            {NAV.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <Button
                  key={item.href}
                  asChild
                  variant="ghost"
                  size="sm"
                  className={cn("text-xs md:text-sm", active && "bg-muted")}
                >
                  <Link href={item.href} aria-current={active ? "page" : undefined}>
                    {item.label}
                  </Link>
                </Button>
              );
            })}
          </nav>
          <div className="ml-auto">
            <UserMenu email={email} />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-screen-2xl space-y-4 px-4 py-4 md:px-6 md:py-6">
        {children}
      </main>
    </>
  );
}
