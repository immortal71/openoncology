import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LenisScroll } from "@/components/marketing/lenis-scroll";
import { AtlasHome } from "@/components/atlas/atlas-home";
import { atlasSans } from "@/lib/atlas-font";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { buildCase } from "@/lib/workspace";

export const metadata: Metadata = { title: "Evidence Atlas | OpenOncology", robots: { index: false, follow: false } };

const CASE_HREF = "/lab/results";
const KRAS_G12C_ROW: Record<string, { label: string; value: string }> = { "KRAS G12C": { label: "VCF row · GRCh38", value: "chr12 25245351 C>A" } };

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
            { step: 1, label: "Tumor variant", value: ws.title, sub: leadVariant?.hgvs, href: "#product", view: "variants", raw: KRAS_G12C_ROW[ws.title] },
            { step: 2, label: "Evidence", value: levelLabel, sub: top?.sources.length ? `Sources: ${top.sources.map((x) => x.split(" ")[0]).join(", ")}` : undefined, href: "#product", view: "sources" },
            { step: 3, label: "Ranked drug", value: `${top?.name ?? "No candidate"} · rank 1`, sub: top?.matched.find((m) => /^[A-Z]+-\d+$/.test(m)), accent: true, href: top ? `#shot-row-${top.id}` : "#product", view: "candidates", pick: top?.id },
          ],
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
