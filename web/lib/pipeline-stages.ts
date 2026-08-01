/**
 * The real sequential pipeline a case moves through, sourced directly from
 * the backend — not invented endpoint names. See file:line citations below
 * for where each stage actually lives in this codebase.
 */

export type StageStatus = "locked" | "ready" | "running" | "success";

export type PipelineStage = {
  id: string;
  label: string;
  endpoint: string;
  description: string;
  /** True if this stage only runs conditionally, not as a strict gate. */
  conditional?: boolean;
};

export const PIPELINE_STAGES: PipelineStage[] = [
  {
    id: "submission",
    label: "Sample submission",
    endpoint: "POST /api/submit/",
    description:
      "Accepts a biopsy report and a DNA/genomic file (VCF, FASTQ, BAM), uploads both encrypted, and queues the genomic pipeline.",
  },
  {
    id: "genomic-pipeline",
    label: "Genomic pipeline",
    endpoint: "nextflow run pipeline/main.nf",
    description:
      "Celery task workers.genomic_worker.run_genomic_pipeline shells out to Nextflow: FastQC → Trimmomatic → BWA-MEM2 → Mutect2/GATK → OpenCRAVAT annotation.",
  },
  {
    id: "ai-analysis",
    label: "AI analysis",
    endpoint: "workers.ai_worker.run_ai_analysis",
    description:
      "AlphaMissense pathogenicity scoring → OncoKB actionability query → COSMIC/cBioPortal enrichment → multi-source candidate gathering → rank_candidates().",
  },
  {
    id: "repurposing",
    label: "Ranked repurposing candidates",
    endpoint: "GET /api/repurposing/{result_id}",
    description:
      "Returns tiered, ranked drug candidates with a decision_path — tier1_found, tier2_only, tier3_escalation, or abstain.",
  },
  {
    id: "custom-brief",
    label: "Custom discovery brief",
    endpoint: "GET /api/marketplace/discovery-brief/{result_id}",
    description:
      "Only triggered when repurposing is insufficient or weak. Generates lead + de-novo candidates via AlphaFold/DiffDock, gated by a strict safety filter.",
    conditional: true,
  },
  {
    id: "manufacturing",
    label: "Manufacturing",
    endpoint: "POST /api/marketplace/order",
    description:
      "Patient-initiated. Creates a Stripe payment intent and an order against a verified pharma manufacturer for an FDA-approved drug.",
    conditional: true,
  },
  {
    id: "crowdfunding",
    label: "Crowdfunding",
    endpoint: "POST /api/crowdfund/",
    description:
      "A separate, independent patient action — launches a public campaign tied to a result or order, not dependent on manufacturing or the custom brief.",
    conditional: true,
  },
];

export const DRUG_TIER_LABELS: Record<string, string> = {
  fda_approved: "FDA-approved · OncoKB Level 1/2",
  repurposed: "Repurposed · approved, weaker evidence",
  investigational_late: "Investigational · Phase 3",
  investigational_early: "Investigational · Phase 1/2",
  preclinical: "Preclinical",
  resistance_mechanism: "Resistance mechanism · OncoKB R1/R2",
};

export type DrugCandidate = {
  drug: string;
  tier: string;
  rankScore: number;
  mechanism: string;
  evidence: string;
  trialPhase: string;
  isFdaApproved: boolean;
};

/**
 * Real backend candidate shape, per lib/api.ts's getRepurposing() return type
 * (api/routes/repurposing.py:90-112). drug_tier is computed server-side by
 * classify_drug_tier() (api/ai/ranking.py:161) — read it directly rather
 * than re-deriving tier from approval_status text on the client.
 */
export type RealRepurposingCandidate = {
  drug_name: string;
  chembl_id: string;
  approval_status: string;
  mechanism: string;
  binding_score: number | null;
  opentargets_score: number | null;
  rank_score: number | null;
  evidence_sources: string[];
  matched_terms: string[];
  drug_tier?: string;
  disclaimer?: string;
};

export function toDrugCandidate(c: RealRepurposingCandidate): DrugCandidate {
  const tier = c.drug_tier || "preclinical";
  return {
    drug: c.drug_name,
    tier,
    rankScore: c.rank_score ?? 0,
    mechanism: c.mechanism || "Not provided by the source database.",
    evidence: c.evidence_sources?.length ? `Evidence: ${c.evidence_sources.join(", ")}` : "No cited evidence source.",
    trialPhase: c.approval_status || "Unknown",
    isFdaApproved: tier === "fda_approved",
  };
}
