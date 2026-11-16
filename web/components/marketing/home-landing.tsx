import { LenisScroll } from "@/components/marketing/lenis-scroll";
import { SiteLanding } from "@/components/marketing/site-landing";
import { parseApproval } from "@/lib/approval";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { displayFont } from "@/lib/display-font";
import { displaySources } from "@/lib/evidence";
import { oncoKbLevel } from "@/lib/evidence-levels";
import { PROTEIN_REFERENCE, parseProteinChange } from "@/lib/protein";
import { tierInfo } from "@/lib/therapy-groups";

export const DEMO_CASE_HREF = "/results/demo-nsclc-kras-g12c?demo=true";

export function HomeLanding({ demoHref = DEMO_CASE_HREF }: { demoHref?: string }) {
  const ranked = [...DEMO_REPURPOSING.candidates].sort((a, b) => (b.rank_score ?? 0) - (a.rank_score ?? 0));
  const candidates = ranked.map((c) => ({ id: c.chembl_id, name: c.drug_name, score: c.rank_score ?? 0, group: tierInfo(c.drug_tier).heading }));
  const lead = DEMO_RESULTS.mutations.find((m) => m.is_targetable) ?? DEMO_RESULTS.mutations[0];
  const change = parseProteinChange(lead.hgvs);
  const ref = PROTEIN_REFERENCE[lead.gene];
  const level = oncoKbLevel(lead.oncokb_level);
  const top = ranked[0];

  return (
    <main className={displayFont.variable}>
      <LenisScroll />
      <SiteLanding
        demoHref={demoHref}
        candidates={candidates}
        variant={{
          gene: lead.gene,
          short: change?.short ?? lead.hgvs,
          hgvs: lead.hgvs,
          cancerType: "NSCLC",
          level: level?.short ?? "No OncoKB level",
          position: change?.position ?? 1,
          length: ref?.length ?? 1,
        }}
        topSources={displaySources(top)}
        topName={top.drug_name}
        topLevel={level?.label ?? "No OncoKB level"}
        topApproval={parseApproval(top.approval_status).label}
      />
    </main>
  );
}
