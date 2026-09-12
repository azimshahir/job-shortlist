/**
 * Browser Supabase client ("use client" components). Shares the session
 * cookie with the server client, so a user signed in via a Server Action is
 * signed in here too.
 */
import { createBrowserClient } from "@supabase/ssr";

import type { Database } from "./types";

export function createClient() {
  return createBrowserClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
