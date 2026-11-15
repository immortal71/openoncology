export type TierKey =
  | "fda_approved"
  | "repurposed"
  | "investigational_late"
  | "investigational_early"
  | "preclinical"
  | "resistance_mechanism"
  | "unclassified";

export type TierInfo = { key: TierKey; badge: string; heading: string; note: string | null };

export const TIERS: Record<TierKey, TierInfo> = {
  fda_approved: { key: "fda_approved", badge: "FDA approved", heading: "OncoKB Level 1–2 (standard care)", note: "Approval status as reported on each row" },
  repurposed: {
    key: "repurposed",
    badge: "Repurposed",
    heading: "Approved drugs, weaker or off-label evidence",
    note: "Reported as approved, without Level 1–2 evidence for this variant",
  },
  investigational_late: { key: "investigational_late", badge: "Phase 3", heading: "Investigational, phase 3", note: null },
  investigational_early: { key: "investigational_early", badge: "Phase 1–2", heading: "Investigational, phase 1–2", note: null },
  preclinical: { key: "preclinical", badge: "Preclinical", heading: "Preclinical only", note: "No human trial data" },
  resistance_mechanism: {
    key: "resistance_mechanism",
    badge: "Resistance",
    heading: "Resistance (OncoKB R1–R2)",
    note: "Listed for awareness, not an actionable option",
  },
  unclassified: { key: "unclassified", badge: "Unclassified", heading: "Unclassified", note: null },
};

const ORDER: TierKey[] = ["fda_approved", "repurposed", "investigational_late", "investigational_early", "preclinical", "unclassified", "resistance_mechanism"];

export function tierInfo(tier: string | null | undefined): TierInfo {
  return tier && tier in TIERS ? TIERS[tier as TierKey] : TIERS.unclassified;
}

export type RankedItem = { tier: string | null | undefined; rank: number };
export type TherapyGroup<T> = TierInfo & { items: T[] };

export function groupByTier<T extends RankedItem>(items: T[]): TherapyGroup<T>[] {
  const buckets = new Map<TierKey, T[]>();
  for (const item of items) {
    const key = tierInfo(item.tier).key;
    const list = buckets.get(key) ?? [];
    list.push(item);
    buckets.set(key, list);
  }
  return ORDER.filter((key) => buckets.has(key)).map((key) => ({
    ...TIERS[key],
    items: [...(buckets.get(key) as T[])].sort((a, b) => a.rank - b.rank),
  }));
}
