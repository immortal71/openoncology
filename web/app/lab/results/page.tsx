import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ResultsView } from "@/components/results/results-view";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";

export const metadata: Metadata = {
  title: "Results (redesign) | OpenOncology",
  robots: { index: false, follow: false },
};

export default function ResultsLabPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <ResultsView results={DEMO_RESULTS} candidates={DEMO_REPURPOSING.candidates} demo />;
}
