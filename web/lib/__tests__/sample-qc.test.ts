import { describe, it, expect } from "vitest";
import {
  presentSampleQC,
  formatPct,
  formatNum,
  TONE_CLASSES,
  type SampleQC,
} from "@/lib/sample-qc";

describe("presentSampleQC", () => {
  it("maps each real verdict onto its own tone", () => {
    expect(presentSampleQC({ qc_verdict: "PASS", assessed: true }).tone).toBe("pass");
    expect(presentSampleQC({ qc_verdict: "WARN", assessed: true }).tone).toBe("warn");
    expect(presentSampleQC({ qc_verdict: "FAIL", assessed: true }).tone).toBe("fail");
  });

  it("accepts a lowercase verdict", () => {
    expect(presentSampleQC({ qc_verdict: "fail", assessed: true }).tone).toBe("fail");
  });

  // The safety property. Everything below is a way of not having run QC, and
  // none of them may look like a sample that passed.
  describe("an unchecked sample never reads as a clean one", () => {
    const unchecked: Array<[string, SampleQC | null | undefined]> = [
      ["missing payload", null],
      ["undefined payload", undefined],
      ["empty payload", {}],
      ["explicit NOT_ASSESSED", { qc_verdict: "NOT_ASSESSED", assessed: false }],
      ["UNKNOWN verdict", { qc_verdict: "UNKNOWN" }],
      ["unrecognised verdict", { qc_verdict: "SOMETHING_NEW", assessed: true }],
      ["verdict says PASS but assessed is false", { qc_verdict: "PASS", assessed: false }],
    ];

    it.each(unchecked)("%s is not assessed and not styled as a pass", (_name, qc) => {
      const p = presentSampleQC(qc);
      expect(p.assessed).toBe(false);
      expect(p.tone).not.toBe("pass");
      expect(p.label).toBe("Sample QC not assessed");
      expect(TONE_CLASSES[p.tone]).not.toContain("green");
    });
  });

  it("does not claim FFPE was ruled out when nothing was measured", () => {
    const qc: SampleQC = {};
    expect(qc.ffpe_suspected).toBeUndefined();
    expect(presentSampleQC(qc).warnings).toEqual([]);
  });

  it("carries warnings through unchanged", () => {
    const warnings = ["Coverage low: 40% of variants below 30x"];
    expect(presentSampleQC({ qc_verdict: "WARN", assessed: true, warnings }).warnings).toEqual(warnings);
  });

  it("gives a pass its green treatment only when QC actually ran", () => {
    const p = presentSampleQC({ qc_verdict: "PASS", assessed: true });
    expect(p.assessed).toBe(true);
    expect(TONE_CLASSES[p.tone]).toContain("green");
  });
});

describe("formatters keep unmeasured distinct from zero", () => {
  it("renders null and undefined as null, not as 0", () => {
    expect(formatPct(null)).toBeNull();
    expect(formatPct(undefined)).toBeNull();
    expect(formatNum(null)).toBeNull();
    expect(formatNum(undefined)).toBeNull();
  });

  it("renders a real zero as a measurement", () => {
    expect(formatPct(0)).toBe("0%");
    expect(formatNum(0)).toBe("0.0");
  });

  it("formats values at the requested precision", () => {
    expect(formatPct(0.4237, 1)).toBe("42.4%");
    expect(formatNum(2.345, 2)).toBe("2.35");
  });
});
