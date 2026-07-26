import { describe, it, expect } from "vitest";
import {
  toDrugCandidate,
  PIPELINE_STAGES,
  DRUG_TIER_LABELS,
  type RealRepurposingCandidate,
} from "@/lib/pipeline-stages";

// Minimal valid backend candidate; individual tests override fields.
function candidate(
  overrides: Partial<RealRepurposingCandidate> = {}
): RealRepurposingCandidate {
  return {
    drug_name: "Osimertinib",
    chembl_id: "CHEMBL3353410",
    approval_status: "FDA-approved",
    mechanism: "EGFR TKI",
    binding_score: 0.9,
    opentargets_score: 0.8,
    rank_score: 0.75,
    evidence_sources: ["OncoKB", "CIViC"],
    matched_terms: ["EGFR"],
    drug_tier: "fda_approved",
    ...overrides,
  };
}

describe("toDrugCandidate", () => {
  it("maps a full FDA-approved candidate correctly", () => {
    const out = toDrugCandidate(candidate());
    expect(out).toEqual({
      drug: "Osimertinib",
      tier: "fda_approved",
      rankScore: 0.75,
      mechanism: "EGFR TKI",
      evidence: "Evidence: OncoKB, CIViC",
      trialPhase: "FDA-approved",
      isFdaApproved: true,
    });
  });

  it("falls back to 'preclinical' tier when drug_tier is missing", () => {
    const out = toDrugCandidate(candidate({ drug_tier: undefined }));
    expect(out.tier).toBe("preclinical");
    expect(out.isFdaApproved).toBe(false);
  });

  it("coerces a null rank_score to 0", () => {
    expect(toDrugCandidate(candidate({ rank_score: null })).rankScore).toBe(0);
  });

  it("provides a fallback mechanism string when empty", () => {
    expect(toDrugCandidate(candidate({ mechanism: "" })).mechanism).toBe(
      "Not provided by the source database."
    );
  });

  it("provides a fallback evidence string when there are no sources", () => {
    expect(toDrugCandidate(candidate({ evidence_sources: [] })).evidence).toBe(
      "No cited evidence source."
    );
  });

  it("sets isFdaApproved only for the fda_approved tier", () => {
    expect(toDrugCandidate(candidate({ drug_tier: "repurposed" })).isFdaApproved).toBe(false);
    expect(toDrugCandidate(candidate({ drug_tier: "fda_approved" })).isFdaApproved).toBe(true);
  });

  it("uses 'Unknown' for missing approval_status (trialPhase)", () => {
    expect(toDrugCandidate(candidate({ approval_status: "" })).trialPhase).toBe("Unknown");
  });
});

describe("pipeline constants", () => {
  it("exposes stages with unique ids and required fields", () => {
    expect(PIPELINE_STAGES.length).toBeGreaterThan(0);
    const ids = PIPELINE_STAGES.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const stage of PIPELINE_STAGES) {
      expect(stage.id).toBeTruthy();
      expect(stage.label).toBeTruthy();
      expect(stage.endpoint).toBeTruthy();
      expect(stage.description).toBeTruthy();
    }
  });

  it("labels every drug tier that toDrugCandidate can emit", () => {
    // Every tier fallback/value used by the mapper should have a human label.
    expect(DRUG_TIER_LABELS.fda_approved).toBeTruthy();
    expect(DRUG_TIER_LABELS.preclinical).toBeTruthy();
  });
});
