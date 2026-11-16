import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LenisScroll } from "@/components/marketing/lenis-scroll";
import { AtlasHome } from "@/components/atlas/atlas-home";
import { parseApproval } from "@/lib/approval";
import { atlasSans } from "@/lib/atlas-font";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { DERIVED_SIGNALS, SOURCES_PENDING_REVIEW, displaySources } from "@/lib/evidence";
import { oncoKbLevel } from "@/lib/evidence-levels";
import { parseProteinChange } from "@/lib/protein";

export const metadata: Metadata = { title: "Evidence Atlas | OpenOncology", robots: { index: false, follow: false } };

const NOT_IN_RESULT = ["Allele fraction (VAF)", "Read depth", "ClinVar review status", "COSMIC count"];

export default function AtlasPage() {
  if (process.env.NODE_ENV === "production") notFound();

  const ranked = [...DEMO_REPURPOSING.candidates].sort((a, b) => (b.rank_score ?? 0) - (a.rank_score ?? 0));
  const lead = DEMO_RESULTS.mutations.find((m) => m.is_targetable) ?? DEMO_RESULTS.mutations[0];
  const change = parseProteinChange(lead.hgvs);
  const short = change?.short ?? lead.hgvs;
  const level = oncoKbLevel(lead.oncokb_level);
  const top = ranked[0];
  const toShot = (c: (typeof ranked)[number]) => ({
    name: c.drug_name,
    approval: parseApproval(c.approval_status).label,
    mechanism: c.mechanism.split(" — ")[0],
    chembl: c.chembl_id,
    matched: c.matched_terms,
    signals: displaySources(c),
    hidden: c.evidence_sources
      .filter((src) => SOURCES_PENDING_REVIEW.has(src) || DERIVED_SIGNALS.has(src))
      .map((src) => ({ name: src, reason: SOURCES_PENDING_REVIEW.has(src) ? "pending review" : "derived signal" })),
    score: c.rank_score ?? 0,
  });
  const approved = ranked.filter((c) => c.drug_tier === "fda_approved").map(toShot);
  const rest = ranked.length - approved.length;
  const more = rest ? `${rest} more in a different indication` : "No other candidates";
  const others = DEMO_RESULTS.mutations
    .filter((m) => m !== lead)
    .map((m) => `${m.gene} ${m.hgvs}`)
    .join(", ");

  return (
    <main className={atlasSans.variable}>
      <LenisScroll />
      <AtlasHome
        data={{
          demoHref: "/lab/results",
          shot: {
            title: `${lead.gene} ${short}`,
            tumor: DEMO_RESULTS.cancer_type,
            tumorShort: "NSCLC",
            demoHref: "/lab/results",
            variants: DEMO_RESULTS.mutations.map((m) => ({
              gene: m.gene,
              hgvs: m.hgvs,
              short: parseProteinChange(m.hgvs)?.short ?? m.hgvs,
              level: oncoKbLevel(m.oncokb_level)?.label ?? "No OncoKB level",
              targetable: m.is_targetable,
            })),
            level: { label: level?.label ?? "No OncoKB level", meaning: level?.meaning ?? "" },
            candidates: approved,
            more: more,
            unknown: NOT_IN_RESULT,
          },
          steps: {
            vcf: {
              title: "Variant calls (VCF) · demo case",
              columns: ["GENE", "HGVS_P", "PROTEIN"],
              rows: DEMO_RESULTS.mutations.map((m) => [m.gene, m.hgvs, parseProteinChange(m.hgvs)?.short ?? ""]),
              highlight: DEMO_RESULTS.mutations.indexOf(lead),
            },
            candidates: approved,
            more: more,
            group: `${parseApproval(top.approval_status).label} · ${lead.gene} ${short}`,
            checks: [
              { k: "Evidence level read in tumor context", v: `${level?.label ?? "No OncoKB level"} · ${DEMO_RESULTS.cancer_type}` },
              { k: "Missing records noted", v: "Exact lookup record not stored in this demo result" },
              { k: "Co-mutations considered", v: others || "None in this result" },
            ],
          },
          heroNodes: [
            { label: "Variant", value: `${lead.gene} ${short}`, href: "#product", view: "variants" },
            { label: "Evidence level", value: level?.label ?? "No OncoKB level", href: "#product", view: "sources" },
            { label: "Candidate · rank 1", value: top.drug_name, accent: true, href: "#product", view: "candidates" },
          ],
          compactNodes: [
            { label: "Variant", value: `${lead.gene} ${short}` },
            { label: "Candidate · rank 1", value: top.drug_name, accent: true },
          ],
        }}
      />
    </main>
  );
}
