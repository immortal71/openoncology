import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LenisScroll } from "@/components/marketing/lenis-scroll";
import { AtlasHome } from "@/components/atlas/atlas-home";
import { atlasSans } from "@/lib/atlas-font";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { buildCase } from "@/lib/workspace";

export const metadata: Metadata = { title: "Evidence Atlas | OpenOncology", robots: { index: false, follow: false } };

const CASE_HREF = "/lab/results";

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

  return (
    <main className={atlasSans.variable}>
      <LenisScroll />
      <AtlasHome
        data={{
          demoHref: CASE_HREF,
          shot: { ws, list, caseHref: CASE_HREF },
          steps: {
            variant: ws.title,
            vcf: {
              title: "Variant calls (VCF) · demo case",
              columns: ["GENE", "HGVS_P", "PROTEIN"],
              rows: ws.variants.map((v) => [v.gene, v.hgvs, v.short]),
              highlight: Math.max(0, ws.variants.findIndex((v) => v.key === lead?.key)),
            },
            candidates: list,
            more,
            group: `${top?.approval.label ?? "Candidates"} · ${ws.title}`,
            evidence: `${levelLabel} · matched on ${top?.matched.join(", ") ?? ""}`,
            checks: [
              { k: "Context", v: `${ws.title} · ${ws.tumor}`, focus: true },
              { k: "Evidence level", v: levelLabel },
              { k: "Source record", v: "Not stored in this demo result", missing: true },
              { k: "Unresolved", v: unresolved.join(", "), missing: true },
              { k: "Co-mutations", v: others || "None in this result" },
            ],
          },
          heroNodes: [
            { label: "Variant", value: ws.title, href: "#product", view: "variants" },
            { label: "Evidence level", value: levelLabel, href: "#product", view: "sources" },
          ],
          compactNodes: [
            { label: "Variant", value: ws.title },
            { label: "Candidate · rank 1", value: top?.name ?? "No candidate", accent: true },
          ],
        }}
      />
    </main>
  );
}
