import { redirect } from "next/navigation";

import { LoginForm } from "@/components/login-form";
import { getUser } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ next?: string }> };

function safeNext(next: string | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) return "/today";
  if (next.startsWith("/login")) return "/today";
  return next;
}

export default async function LoginPage({ searchParams }: Props) {
  const { next } = await searchParams;
  const target = safeNext(next);
  const user = await getUser().catch(() => null);
  if (user) redirect(target);

  return (
    <main className="flex min-h-svh items-center justify-center p-4">
      <LoginForm next={target} />
    </main>
  );
}
