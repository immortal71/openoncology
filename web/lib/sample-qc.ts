/**
 * Sample QC presentation rules.
 *
 * The logic lives here rather than in the component because one rule is a
 * safety property, not a styling choice: a sample nobody checked must never
 * render like a sample that passed. Keeping it in lib/ puts it inside the
 * Vitest boundary so that property is pinned by a test.
 */

export type SampleQC = {
  qc_verdict?: string;
  assessed?: boolean;
  tumour_purity_estimate?: number | null;
  ffpe_artefact_rate?: number | null;
  ffpe_suspected?: boolean | null;
  ti_tv_ratio?: number | null;
  median_vaf?: number | null;
  total_variants?: number | null;
  pass_variants?: number | null;
  mean_depth?: number | null;
  warnings?: string[];
  ffpe_score?: number | null;
  ffpe_confidence?: string | null;
  coverage_adequacy?: string | null;
};

export type QCTone = "pass" | "warn" | "fail" | "unassessed";

export type QCPresentation = {
  verdict: string;
  tone: QCTone;
  label: string;
  /** False whenever QC did not actually run, so the UI shows the caveat instead of metrics. */
  assessed: boolean;
  warnings: string[];
};

const TONE_BY_VERDICT: Record<string, QCTone> = {
  PASS: "pass",
  WARN: "warn",
  FAIL: "fail",
  NOT_ASSESSED: "unassessed",
  UNKNOWN: "unassessed",
};

const LABEL_BY_TONE: Record<QCTone, string> = {
  pass: "Sample QC passed",
  warn: "Sample QC warning",
  fail: "Sample QC failed",
  unassessed: "Sample QC not assessed",
};

/** Tailwind classes per tone. `unassessed` is deliberately neutral, never green. */
export const TONE_CLASSES: Record<QCTone, string> = {
  pass: "bg-green-100 text-green-800 border-green-200",
  warn: "bg-amber-100 text-amber-800 border-amber-200",
  fail: "bg-red-100 text-red-800 border-red-200",
  unassessed: "bg-slate-100 text-slate-600 border-slate-300",
};

/**
 * Resolve a stored QC payload into what the UI should say about it.
 *
 * An unrecognised verdict resolves to `unassessed`, not to `pass`: failing
 * towards "we do not know" is the safe direction when the sample's quality
 * qualifies every treatment recommendation shown beneath it.
 */
export function presentSampleQC(qc: SampleQC | null | undefined): QCPresentation {
  const verdict = (qc?.qc_verdict || "NOT_ASSESSED").toUpperCase();
  const verdictTone = TONE_BY_VERDICT[verdict] ?? "unassessed";
  // `assessed: false` from the API wins over the verdict string. A payload can
  // carry a stale or default "PASS" while saying QC never ran, and the tone has
  // to follow the weaker of the two claims, not the more reassuring one.
  const assessed = verdictTone !== "unassessed" && qc?.assessed !== false;
  const tone: QCTone = assessed ? verdictTone : "unassessed";

  return {
    verdict,
    tone,
    label: LABEL_BY_TONE[tone],
    assessed,
    warnings: qc?.warnings ?? [],
  };
}

/** Percentage, or null when the value was never measured. Zero is a measurement. */
export function formatPct(v?: number | null, digits = 0): string | null {
  return v === null || v === undefined ? null : `${(v * 100).toFixed(digits)}%`;
}

/** Fixed-point number, or null when never measured. */
export function formatNum(v?: number | null, digits = 1): string | null {
  return v === null || v === undefined ? null : v.toFixed(digits);
}
