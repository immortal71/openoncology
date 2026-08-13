"use client";

import {
  presentSampleQC,
  formatPct,
  formatNum,
  TONE_CLASSES,
  type SampleQC,
} from "@/lib/sample-qc";

export type { SampleQC };

/** "—" when the value was never measured. Zero is a measurement; null is not. */
function Metric({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 dark:bg-slate-900/50">
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{value ?? "—"}</p>
    </div>
  );
}

export default function SampleQCCard({ qc }: { qc: SampleQC | null | undefined }) {
  const { tone, label, assessed, warnings } = presentSampleQC(qc);
  const meanDepth = formatNum(qc?.mean_depth);

  return (
    <section className="clinical-surface p-6">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Sample Quality</h2>
        <span
          className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TONE_CLASSES[tone]}`}
        >
          {label}
        </span>
      </div>

      {!assessed ? (
        <p className="text-sm text-slate-600 dark:text-slate-400">
          No quality check was recorded for this sample. This is <strong>not</strong> a clean
          result — artefact, purity and coverage problems were never ruled out, so the findings
          below rest on an unverified specimen.
        </p>
      ) : (
        <>
          {qc?.ffpe_suspected && (
            <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4">
              <p className="text-sm font-semibold text-red-900">FFPE artefact signal detected</p>
              <p className="text-xs text-red-700 mt-1">
                Fixation-induced cytosine deamination can imitate low-frequency somatic variants.
                Confirm any low-VAF finding on an orthogonal assay before acting on it.
                {qc.ffpe_confidence ? ` Detector confidence: ${qc.ffpe_confidence}.` : ""}
              </p>
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-4">
            <Metric label="Tumour purity" value={formatPct(qc?.tumour_purity_estimate)} />
            <Metric label="Median VAF" value={formatPct(qc?.median_vaf, 1)} />
            <Metric label="Mean depth" value={meanDepth === null ? null : `${meanDepth}x`} />
            <Metric label="Ti/Tv ratio" value={formatNum(qc?.ti_tv_ratio, 2)} />
            <Metric label="C>T fraction" value={formatPct(qc?.ffpe_artefact_rate, 1)} />
            <Metric label="Coverage" value={qc?.coverage_adequacy ?? null} />
          </div>

          {qc?.pass_variants !== null && qc?.pass_variants !== undefined && (
            <p className="text-xs text-slate-500 mb-3">
              {qc.pass_variants} of {qc.total_variants ?? "?"} variants passed caller filters
              {qc.ffpe_score !== null && qc.ffpe_score !== undefined
                ? ` · FFPE score ${qc.ffpe_score.toFixed(2)}`
                : ""}
            </p>
          )}

          {warnings.length > 0 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm font-semibold text-amber-900 mb-1">Quality warnings</p>
              <ul className="list-disc list-inside text-sm text-amber-800 space-y-1">
                {warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  );
}
