export const SOURCES_PENDING_REVIEW: ReadonlySet<string> = new Set(["DiffDock"]);
export const DERIVED_SIGNALS: ReadonlySet<string> = new Set(["ClinicalPhase"]);

type Candidate = { evidence_sources: string[]; opentargets_score?: number | null };

export function displaySources(candidate: Candidate): string[] {
  return candidate.evidence_sources
    .filter((s) => !SOURCES_PENDING_REVIEW.has(s) && !DERIVED_SIGNALS.has(s))
    .map((s) => (s === "OpenTargets" && candidate.opentargets_score != null ? `OpenTargets assoc. ${candidate.opentargets_score.toFixed(2)}` : s));
}

export function usesClinicalPhaseSignal(candidate: Candidate): boolean {
  return candidate.evidence_sources.includes("ClinicalPhase");
}
