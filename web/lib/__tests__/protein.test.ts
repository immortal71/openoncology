import { describe, expect, it } from "vitest";
import { domainAt, parseProteinChange } from "@/lib/protein";

describe("parseProteinChange", () => {
  it("converts three-letter HGVS to the short form", () => {
    expect(parseProteinChange("p.Gly12Cys")).toEqual({ ref: "G", position: 12, alt: "C", short: "G12C" });
    expect(parseProteinChange("p.Arg175His")?.short).toBe("R175H");
  });

  it("accepts one-letter codes, a missing p. prefix, stops and synonymous changes", () => {
    expect(parseProteinChange("V600E")?.position).toBe(600);
    expect(parseProteinChange("p.Arg213Ter")?.short).toBe("R213*");
    expect(parseProteinChange("p.Leu858=")?.short).toBe("L858L");
  });

  it("returns null for anything it cannot place", () => {
    expect(parseProteinChange(null)).toBeNull();
    expect(parseProteinChange("c.34G>T")).toBeNull();
    expect(parseProteinChange("p.Glu746_Ala750del")).toBeNull();
    expect(parseProteinChange("p.Xyz12Cys")).toBeNull();
  });
});

describe("domainAt", () => {
  it("finds the KRAS P-loop and the TP53 DNA-binding domain", () => {
    expect(domainAt("KRAS", 12)).toBe("P-loop");
    expect(domainAt("tp53", 175)).toBe("DNA-binding domain");
  });

  it("returns null outside known domains or for unknown genes", () => {
    expect(domainAt("KRAS", 61)).toBeNull();
    expect(domainAt("EGFR", 858)).toBeNull();
  });
});
