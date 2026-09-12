import type { Metadata } from "next";

import "./globals.css";

// Placeholder root layout. The Frontend owns app/* screens; this only exists
// so the API routes and lib/ typecheck and `next build` passes.
export const metadata: Metadata = {
  title: "Job Shortlist",
  description: "Shortlist kerja harian",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ms">
      <body className="antialiased">{children}</body>
    </html>
  );
}
