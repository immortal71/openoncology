import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LenisScroll } from "@/components/marketing/lenis-scroll";
import { AtlasHome } from "@/components/atlas/atlas-home";
import { atlasSans } from "@/lib/atlas-font";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { buildCase, GAP_LABELS } from "@/lib/workspace";

export const metadata: Metadata = { title: "Evidence Atlas | OpenOncology", robots: { index: false, follow: false } };

const CASE_HREF = "/lab/results";
const SEQUENCING = new Set(["Allele fraction (VAF)", "Read depth"]);

export default function AtlasPage() {
  if (process.env.NODE_ENV === "production") notFound();

  const ws = buildCase(DEMO_RESULTS, DEMO_REPURPOSING.candidates, { demo: true });
  const list = ws.candidates.filter((c) => c.tier === "fda_approved");
  const top = list[0] ?? ws.candidates[0];
  const lead = ws.lead;
  const levelLabel = lead?.level?.label ?? "No OncoKB level";
  const rest = ws.candidates.length - list.length;
  const more = rest ? `${rest} more in a different indication` : "No other candidates";
  const others = ws.variants
    .filter((v) => v.key !== lead?.key)
    .map((v) => v.name)
    .join(", ");
  const unresolved = ws.gaps.filter((g) => g.state === "not_supplied").map((g) => g.item);
  const leadVariant = ws.variants.find((v) => v.key === lead?.key);
  const tie = ws.nearTies[0];
  const clinicGaps = ws.gaps.filter((g) => !SEQUENCING.has(g.item));

  return (
    <main id="main" className={atlasSans.variable}>
      <LenisScroll />
      <AtlasHome
        data={{
          demoHref: "/submit",
          shot: { ws, list, caseHref: CASE_HREF },
          steps: {
            variant: ws.title,
            vcf: {
              title: "Annotated variant calls · demo case",
              columns: ["GENE", "HGVS_P", "PROTEIN"],
              rows: ws.variants.map((v) => [v.gene, v.hgvs, v.short]),
              highlight: Math.max(0, ws.variants.findIndex((v) => v.key === lead?.key)),
            },
            candidates: list,
            more,
            group: `${top?.approval.label ?? "Candidates"} · ${ws.title}`,
            evidence: `${levelLabel} · matched on ${top?.matched.join(", ") ?? ""}`,
            checks: [
              { k: "Shortlist", v: list.map((c) => c.name).join(", "), focus: true },
              { k: "Gaps attached", v: `${ws.gaps.length} items this result doesn't contain`, missing: true },
              { k: "Oncologist sign-off", v: "Pending" },
            ],
          },
          heroNodes: [
            { step: 1, label: "Tumor variant", value: ws.title, sub: leadVariant?.hgvs, href: "#product", view: "variants" },
            { step: 2, label: "Evidence", value: levelLabel, href: "#product", view: "sources" },
            { step: 3, label: "Ranked drug", value: `${top?.name ?? "No candidate"} · rank 1`, sub: top?.matched.find((m) => /^[A-Z]+-\d+$/.test(m)), accent: true, href: "#product", view: "candidates" },
          ],
          labFacts: ws.gaps.filter((g) => SEQUENCING.has(g.item)).map((g) => ({ k: g.item, v: g.note, missing: true })),
          clinicFacts: clinicGaps.slice(0, 4).map((g) => ({ k: g.scope ? `${g.item} · ${g.scope}` : g.item, v: GAP_LABELS[g.state] })),
          clinicMore: Math.max(0, clinicGaps.length - 4),
          usedSources: [...new Set(DEMO_REPURPOSING.candidates.flatMap((c) => c.evidence_sources))],
          ladder: lead?.level ? { code: lead.level.code, names: list.map((c) => c.name).join(", ") } : null,
          compactNodes: [
            { step: 1, label: "Variant", value: ws.title },
            { step: 2, label: "Evidence", value: levelLabel },
            { step: 3, label: "Drug", value: top?.name ?? "No candidate", accent: true },
          ],
        }}
      />
    </main>
  );
}
