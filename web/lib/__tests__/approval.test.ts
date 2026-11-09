import { describe, expect, it } from "vitest";
import { parseApproval } from "@/lib/approval";
import { displaySources } from "@/lib/evidence";

describe("parseApproval", () => {
  it("reads a bare approval", () => {
    expect(parseApproval("FDA Approved")).toEqual({ approved: true, label: "FDA approved", qualifier: null, differentIndication: false });
  });

  it("keeps the indication qualifier after an em dash", () => {
    const a = parseApproval("FDA Approved — NSCLC KRAS G12C");
    expect(a.approved).toBe(true);
    expect(a.qualifier).toBe("NSCLC KRAS G12C");
    expect(a.differentIndication).toBe(false);
  });

  it("flags approvals for a different indication", () => {
    const a = parseApproval("FDA Approved — different indication (EGFR)");
    expect(a.approved).toBe(true);
    expect(a.differentIndication).toBe(true);
    expect(a.qualifier).toBe("different indication (EGFR)");
  });

  it("does not treat unapproved or empty values as approved", () => {
    expect(parseApproval("Phase 2").approved).toBe(false);
    expect(parseApproval("Phase 2").label).toBe("Phase 2");
    expect(parseApproval(null).label).toBe("Approval status unknown");
    expect(parseApproval("   ").approved).toBe(false);
  });
});

describe("displaySources", () => {
  it("drops sources pending review and formats the rest", () => {
    expect(
      displaySources({ evidence_sources: ["OncoKB", "OpenTargets", "DiffDock", "ClinicalPhase"], opentargets_score: 0.9 })
    ).toEqual(["OncoKB", "OpenTargets assoc. 0.90", "Clinical phase"]);
  });

  it("leaves OpenTargets unscored when there is no score", () => {
    expect(displaySources({ evidence_sources: ["OpenTargets", "ClinVar"], opentargets_score: null })).toEqual(["OpenTargets", "ClinVar"]);
  });
});
