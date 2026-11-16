import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LenisScroll } from "@/components/marketing/lenis-scroll";
import { HeroBold } from "@/components/marketing/heroes/hero-bold";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { displayFont } from "@/lib/display-font";
import { oncoKbLevel } from "@/lib/evidence-levels";
import { parseProteinChange } from "@/lib/protein";
import { tierInfo } from "@/lib/therapy-groups";

export const metadata: Metadata = { title: "Hero C (bold) | OpenOncology", robots: { index: false, follow: false } };

export default function HeroCPage() {
  if (process.env.NODE_ENV === "production") notFound();
  const variants = DEMO_RESULTS.mutations.map((m) => ({
    gene: m.gene,
    change: parseProteinChange(m.hgvs)?.short ?? m.hgvs,
    level: oncoKbLevel(m.oncokb_level)?.code ?? "none",
    actionable: m.is_targetable,
  }));
  const candidates = [...DEMO_REPURPOSING.candidates]
    .sort((a, b) => (b.rank_score ?? 0) - (a.rank_score ?? 0))
    .map((c) => ({ name: c.drug_name, score: c.rank_score ?? 0, tier: tierInfo(c.drug_tier).badge }));
  return (
    <main className={displayFont.variable}>
      <LenisScroll />
      <HeroBold demoHref="/lab/results" variants={variants} candidates={candidates} />
      <div className="h-[40vh] bg-oo-paper" />
    </main>
  );
}
