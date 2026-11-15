import { describe, expect, it } from "vitest";
import { evidenceLookup, oncoKbLevel, predictionLabel } from "@/lib/evidence-levels";

describe("oncoKbLevel", () => {
  it("reads the API's LEVEL_ prefix and bare codes", () => {
    expect(oncoKbLevel("LEVEL_1")?.label).toBe("OncoKB Level 1");
    expect(oncoKbLevel("level_3b")?.code).toBe("3B");
    expect(oncoKbLevel("4")?.short).toBe("OncoKB 4");
  });

  it("marks resistance levels", () => {
    expect(oncoKbLevel("LEVEL_R1")?.resistance).toBe(true);
    expect(oncoKbLevel("LEVEL_1")?.resistance).toBe(false);
  });

  it("treats the backend's 'unknown' default and empty values as no level", () => {
    expect(oncoKbLevel("unknown")).toBeNull();
    expect(oncoKbLevel(null)).toBeNull();
    expect(oncoKbLevel("  ")).toBeNull();
  });

  it("keeps unrecognised codes visible instead of dropping them", () => {
    const level = oncoKbLevel("Dx1");
    expect(level?.label).toBe("OncoKB Level DX1");
    expect(level?.recognised).toBe(false);
  });
});

describe("evidenceLookup", () => {
  it("separates a failed lookup from a checked variant with no level", () => {
    expect(evidenceLookup("unknown", "unavailable").kind).toBe("unavailable");
    expect(evidenceLookup("unknown", "ok")).toEqual({ kind: "checked_none", source: "OncoKB" });
    expect(evidenceLookup("unknown", "not_attempted").kind).toBe("not_attempted");
    expect(evidenceLookup(null, null).kind).toBe("unrecorded");
  });

  it("names the curated table when no live token was used", () => {
    const state = evidenceLookup("LEVEL_1", "static_table");
    expect(state.kind).toBe("level");
    expect(state.kind === "level" && state.source).toContain("curated");
  });

  it("keeps the level when the status was never recorded", () => {
    const state = evidenceLookup("LEVEL_3B", null);
    expect(state.kind === "level" && state.level.code).toBe("3B");
    expect(state.kind === "level" && state.source).toBeNull();
  });
});

describe("predictionLabel", () => {
  it("uses AlphaMissense's own class names for the backend's stored values", () => {
    expect(predictionLabel("pathogenic", 0.98)).toBe("Likely pathogenic");
    expect(predictionLabel("uncertain", 0.5)).toBe("Ambiguous");
    expect(predictionLabel("likely_benign", 0.1)).toBe("Likely benign");
  });

  it("shows no class when nothing was scored, even if a default class is stored", () => {
    expect(predictionLabel("uncertain", null)).toBeNull();
    expect(predictionLabel("Pathogenic", undefined)).toBeNull();
    expect(predictionLabel(undefined, 0.9)).toBeNull();
  });
});
