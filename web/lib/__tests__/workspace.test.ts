import { describe, expect, it } from "vitest";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { buildCase, levelApplies, sourceRow } from "@/lib/workspace";

const demo = buildCase(DEMO_RESULTS, DEMO_REPURPOSING.candidates, { demo: true });

describe("buildCase", () => {
  it("keeps every candidate, ranked by score, grouped by tier", () => {
    expect(demo.candidates.map((c) => c.name)).toEqual(["Sotorasib", "Adagrasib", "Osimertinib"]);
    expect(demo.candidates.map((c) => c.rank)).toEqual([1, 2, 3]);
    expect(demo.groups.map((g) => g.key)).toEqual(["fda_approved", "repurposed"]);
  });

  it("uses the targetable variant as the lead", () => {
    expect(demo.lead?.name).toBe("KRAS G12C");
    expect(demo.title).toBe("KRAS G12C");
    expect(demo.tumorShort).toBe("NSCLC");
  });

  it("flags near-ties under 0.02", () => {
    expect(demo.nearTies).toEqual([{ name: "Adagrasib", above: "Sotorasib" }]);
  });

  it("hides pending-review and derived signals, and says which", () => {
    const top = demo.candidates[0];
    expect(top.sources).toEqual(["OncoKB", "OpenTargets assoc. 0.90"]);
    expect(top.hidden.map((h) => h.name)).toEqual(["DiffDock", "ClinicalPhase"]);
  });

  it("does not apply the lead's evidence level to a different-indication candidate", () => {
    const osimertinib = demo.candidates[2];
    expect(osimertinib.approval.differentIndication).toBe(true);
    expect(levelApplies(osimertinib, demo.lead)).toBe(false);
    expect(sourceRow("OncoKB", osimertinib, demo.lead).value).toBe("Listed");
    expect(sourceRow("OncoKB", demo.candidates[0], demo.lead).value).toBe("OncoKB Level 1 · KRAS G12C");
  });

  it("states gaps by kind without inventing values", () => {
    const states = new Set(demo.gaps.map((g) => g.state));
    expect(states.has("not_supplied")).toBe(true);
    expect(states.has("not_recorded")).toBe(true);
    expect(demo.gaps.some((g) => g.item === "AlphaMissense class" && g.scope === "KRAS G12C")).toBe(true);
    expect(demo.gaps.some((g) => g.state === "lookup_failed")).toBe(false);
  });

  it("reports a failed lookup as its own state", () => {
    const failed = buildCase({ ...DEMO_RESULTS, mutations: [{ gene: "KRAS", hgvs: "p.Gly12Cys", evidence_lookup_status: "unavailable" }] }, []);
    expect(failed.gaps.some((g) => g.state === "lookup_failed" && g.scope === "KRAS G12C")).toBe(true);
    expect(failed.candidates).toEqual([]);
  });
});
