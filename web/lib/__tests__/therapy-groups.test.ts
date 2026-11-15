import { describe, expect, it } from "vitest";
import { groupByTier, tierInfo } from "@/lib/therapy-groups";

describe("groupByTier", () => {
  it("orders groups clinically and keeps the global rank inside each group", () => {
    const groups = groupByTier([
      { id: "a", tier: "repurposed", rank: 3 },
      { id: "b", tier: "fda_approved", rank: 2 },
      { id: "c", tier: "resistance_mechanism", rank: 1 },
      { id: "d", tier: "fda_approved", rank: 1 },
    ]);
    expect(groups.map((g) => g.key)).toEqual(["fda_approved", "repurposed", "resistance_mechanism"]);
    expect(groups[0].items.map((i) => i.id)).toEqual(["d", "b"]);
  });

  it("puts resistance last, after unclassified", () => {
    const groups = groupByTier([
      { id: "r", tier: "resistance_mechanism", rank: 1 },
      { id: "u", tier: null, rank: 2 },
    ]);
    expect(groups.map((g) => g.key)).toEqual(["unclassified", "resistance_mechanism"]);
  });

  it("treats unknown tiers as unclassified", () => {
    expect(tierInfo("something_new").key).toBe("unclassified");
    expect(tierInfo(undefined).badge).toBe("Unclassified");
  });

  it("keeps clinical group order even when a weaker tier outranks a stronger one", () => {
    const groups = groupByTier([
      { id: "rep", tier: "repurposed", rank: 1 },
      { id: "soc", tier: "fda_approved", rank: 2 },
    ]);
    expect(groups.map((g) => g.items[0].rank)).toEqual([2, 1]);
  });

  it("returns no groups for no items", () => {
    expect(groupByTier([])).toEqual([]);
  });
});
