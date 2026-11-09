export const SOURCES_PENDING_REVIEW: ReadonlySet<string> = new Set(["DiffDock"]);

const SOURCE_LABEL: Record<string, string> = {
  ClinicalPhase: "Clinical phase",
};

export function displaySources(candidate: { evidence_sources: string[]; opentargets_score?: number | null }): string[] {
  return candidate.evidence_sources
    .filter((s) => !SOURCES_PENDING_REVIEW.has(s))
    .map((s) => {
      if (s === "OpenTargets" && candidate.opentargets_score != null) return `OpenTargets assoc. ${candidate.opentargets_score.toFixed(2)}`;
      return SOURCE_LABEL[s] ?? s;
    });
}
