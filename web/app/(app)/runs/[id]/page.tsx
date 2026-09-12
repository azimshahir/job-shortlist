import { redirect } from "next/navigation";

/** design.md §9 links to /runs/[id]; the run view lives at /today?run=<id>. */
export default async function RunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/today?run=${encodeURIComponent(id)}`);
}
