import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CaseWorkspace } from "@/components/workspace/case-workspace";
import { atlasSans } from "@/lib/atlas-font";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { buildCase } from "@/lib/workspace";

export const metadata: Metadata = {
  title: "KRAS G12C evidence review | OpenOncology",
  robots: { index: false, follow: false },
};

export default async function ResultsLabPage({ searchParams }: { searchParams: Promise<{ view?: string; candidate?: string }> }) {
  if (process.env.NODE_ENV === "production") notFound();
  const { view, candidate } = await searchParams;
  const ws = buildCase(DEMO_RESULTS, DEMO_REPURPOSING.candidates, { demo: true });
  return (
    <div className={atlasSans.variable}>
      <CaseWorkspace ws={ws} backHref="/lab/atlas" backLabel="Home" initialView={view} initialCandidate={candidate} />
    </div>
  );
}
