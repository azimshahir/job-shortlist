/**
 * Server-side Supabase client for Next.js 15 App Router (Server Components,
 * Route Handlers, Server Actions). Cookie-based session via @supabase/ssr.
 *
 * Reads NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY. The anon key
 * is safe in the browser: RLS (auth.uid() = user_id) is what protects rows.
 */
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import type { Database } from "./types";

function env(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing env ${name} (set it in Vercel project settings)`);
  }
  return value;
}

export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient<Database>(
    env("NEXT_PUBLIC_SUPABASE_URL"),
    env("NEXT_PUBLIC_SUPABASE_ANON_KEY"),
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // Called from a Server Component: cookies are read-only there.
            // The middleware refreshes the session instead.
          }
        },
      },
    },
  );
}

/** Convenience: the signed-in user, or null. */
export async function getUser() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return user;
}
