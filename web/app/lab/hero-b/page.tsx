import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LenisScroll } from "@/components/marketing/lenis-scroll";
import { HeroLight } from "@/components/marketing/heroes/hero-light";
import { parseApproval } from "@/lib/approval";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { displayFont } from "@/lib/display-font";
import { displaySources } from "@/lib/evidence";
import { oncoKbLevel } from "@/lib/evidence-levels";
import { PROTEIN_REFERENCE, parseProteinChange } from "@/lib/protein";
import { tierInfo } from "@/lib/therapy-groups";

export const metadata: Metadata = { title: "Hero B (light) | OpenOncology", robots: { index: false, follow: false } };

export default function HeroBPage() {
  if (process.env.NODE_ENV === "production") notFound();

  const ranked = [...DEMO_REPURPOSING.candidates].sort((a, b) => (b.rank_score ?? 0) - (a.rank_score ?? 0));
  const candidates = ranked.map((c) => {
    const approval = parseApproval(c.approval_status);
    return {
      id: c.chembl_id,
      name: c.drug_name,
      score: c.rank_score ?? 0,
      approval: approval.differentIndication ? "Approved for a different indication" : approval.label,
      group: tierInfo(c.drug_tier).heading,
    };
  });

  const lead = DEMO_RESULTS.mutations.find((m) => m.is_targetable) ?? DEMO_RESULTS.mutations[0];
  const change = parseProteinChange(lead.hgvs);
  const ref = PROTEIN_REFERENCE[lead.gene];
  const level = oncoKbLevel(lead.oncokb_level);
  const domain = change ? (ref?.domains.find((d) => change.position >= d.start && change.position <= d.end) ?? null) : null;
  const variant = {
    gene: lead.gene,
    short: change?.short ?? lead.hgvs,
    hgvs: lead.hgvs,
    cancerType: "NSCLC",
    level: level?.short ?? "No OncoKB level",
    levelMeaning: level?.meaning ?? "",
    targetable: lead.is_targetable,
    position: change?.position ?? 1,
    length: ref?.length ?? 1,
    domain: domain ? { label: domain.short, start: domain.start, end: domain.end } : null,
  };

  const top = ranked[0];
  const evidence = {
    drug: top.drug_name,
    level: `${level?.label ?? "No OncoKB level"} · ${lead.gene} ${change?.short ?? ""}`.trim(),
    levelMeaning: level?.meaning ?? "",
    sources: displaySources(top),
  };

  return (
    <main className={displayFont.variable}>
      <LenisScroll />
      <HeroLight demoHref="/lab/results" candidates={candidates} variant={variant} evidence={evidence} />
    </main>
  );
}
