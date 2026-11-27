import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CardOptions } from "@/components/atlas/card-options-view";
import { atlasSans } from "@/lib/atlas-font";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { buildCase, GAP_LABELS, type GapState } from "@/lib/workspace";

export const metadata: Metadata = { title: "Card options | OpenOncology", robots: { index: false, follow: false } };

const SEQUENCING = new Set(["Allele fraction (VAF)", "Read depth"]);
const ORDER: GapState[] = ["not_supplied", "not_assessed", "not_recorded", "lookup_failed"];

export default function CardOptionsPage() {
  if (process.env.NODE_ENV === "production") notFound();
  const ws = buildCase(DEMO_RESULTS, DEMO_REPURPOSING.candidates, { demo: true });
  const clinicGaps = ws.gaps.filter((g) => !SEQUENCING.has(g.item));
  const data = {
    calls: ws.variants.map((v) => ({ gene: v.gene, protein: v.short, hgvs: v.hgvs })),
    lab: ws.gaps.filter((g) => SEQUENCING.has(g.item)).map((g) => ({ k: g.item, v: GAP_LABELS[g.state], note: g.note, state: g.state })),
    clinic: clinicGaps.slice(0, 4).map((g) => ({ k: g.scope ? `${g.item} · ${g.scope}` : g.item, v: GAP_LABELS[g.state], note: g.note, state: g.state })),
    clinicAll: clinicGaps.map((g) => ({ k: g.scope ? `${g.item} · ${g.scope}` : g.item, v: GAP_LABELS[g.state], note: g.note, state: g.state })),
    more: Math.max(0, clinicGaps.length - 4),
    total: clinicGaps.length,
    tally: ORDER.map((s) => [s, clinicGaps.filter((g) => g.state === s).length] as const)
      .filter(([, n]) => n > 0)
      .map(([s, n]) => `${n} ${GAP_LABELS[s].toLowerCase()}`)
      .join(" · "),
  };
  return (
    <main className={`${atlasSans.variable} min-h-screen bg-[#F7F5F0] font-[family-name:var(--font-atlas)] text-[#24212B] antialiased`}>
      <CardOptions data={data} />
    </main>
  );
}
