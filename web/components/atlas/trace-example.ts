export type Effect =
  | { kind: "na"; reason: string }
  | { kind: "depends"; text: string }
  | { kind: "small" }
  | { kind: "applies" }
  | { kind: "num"; text: string };

type Rule = { verb: string; rule: string; l1: Effect; r1: Effect };

export const RULES: Rule[] = [
  {
    verb: "Cap",
    rule: "R1/R2 hard-capped at 0.08",
    l1: { kind: "na", reason: "Level 1" },
    r1: { kind: "num", text: "0.209 → 0.08" },
  },
  {
    verb: "Penalise",
    rule: "Safety, up to −0.50",
    l1: { kind: "depends", text: "Depends on the drug" },
    r1: { kind: "depends", text: "Depends on the drug" },
  },
  {
    verb: "Discount",
    rule: "Single-source ×0.78",
    l1: { kind: "na", reason: "two sources" },
    r1: { kind: "na", reason: "two sources" },
  },
  {
    verb: "Attenuate",
    rule: "Co-mutation, low VAF",
    l1: { kind: "depends", text: "Depends on the case" },
    r1: { kind: "depends", text: "Depends on the case" },
  },
  {
    verb: "Shape",
    rule: "Conflict −0.12 · translational +0.08 · multi-source +0.04",
    l1: { kind: "small" },
    r1: { kind: "small" },
  },
  {
    verb: "Floor",
    rule: "Level 1/2 floors re-applied",
    l1: { kind: "applies" },
    r1: { kind: "na", reason: "Level R1" },
  },
];

export const STATE = {
  l1: {
    level: "Level 1",
    score: "1.00",
    sum: "0.727 × 1.00 + 0.273 × 0.50 = 0.8635 → 0.864",
    base: "0.864",
    pos: 1,
  },
  r1: {
    level: "Level R1",
    score: "0.10",
    sum: "0.727 × 0.10 + 0.273 × 0.50 = 0.2092 → 0.209",
    base: "0.209",
    pos: 0.1,
  },
};

export function effectLabel(e: Effect) {
  if (e.kind === "na") return `Not applied · ${e.reason}`;
  if (e.kind === "applies") return "Applies";
  if (e.kind === "num") return e.text;
  if (e.kind === "small") return "Small terms";
  return e.text;
}
