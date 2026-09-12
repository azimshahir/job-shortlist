import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { getUser } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function AppLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const user = await getUser().catch(() => null);
  if (!user) redirect("/login");
  return <AppShell email={user.email ?? ""}>{children}</AppShell>;
}
