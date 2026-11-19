"use client";

import {
  presentSampleQC,
  formatPct,
  formatNum,
  type QCTone,
  type SampleQC,
} from "@/lib/sample-qc";
import { ink, line, muted, surface } from "@/components/workspace/parts";

export type { SampleQC };

/** `unassessed` is deliberately neutral, never green — matches lib/sample-qc.ts's own rule. */
const TONE_BADGE: Record<QCTone, string> = {
  pass: "border-[#C9D9C9] bg-[#EEF4EE] text-[#3E6B45]",
  warn: "border-[#E6D3AE] bg-[#FBF4E6] text-[#7A4F14]",
  fail: "border-[#D9B8AE] bg-[#FBF1EE] text-[#9E4A3A]",
  unassessed: `${line} bg-[#FAF9F7] ${muted}`,
};

/** "—" when the value was never measured. Zero is a measurement; null is not. */
function Metric({ label, value }: { label: string; value: string | null }) {
  return (
    <div className={`rounded-[8px] border ${line} bg-[#FAF9F7] px-3 py-2`}>
      <p className={`text-[11px] uppercase tracking-wide ${muted}`}>{label}</p>
      <p className={`text-[14px] font-semibold ${ink}`}>{value ?? "—"}</p>
    </div>
  );
}

export default function SampleQCCard({ qc }: { qc: SampleQC | null | undefined }) {
  const { tone, label, assessed, warnings } = presentSampleQC(qc);
  const meanDepth = formatNum(qc?.mean_depth);

  return (
    <section className={`rounded-[12px] border ${line} bg-white p-6 ${surface}`}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-[17px] font-semibold">Sample quality</h2>
        <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[12px] font-semibold ${TONE_BADGE[tone]}`}>
          {label}
        </span>
      </div>

      {!assessed ? (
        <p className={`text-[13.5px] leading-[20px] ${muted}`}>
          No quality check was recorded for this sample. This is <strong className={ink}>not</strong> a clean
          result — artefact, purity and coverage problems were never ruled out, so the findings
          below rest on an unverified specimen.
        </p>
      ) : (
        <>
          {qc?.ffpe_suspected && (
            <div className="mb-4 rounded-[10px] border border-[#D9B8AE] bg-[#FBF1EE] p-4">
              <p className="text-[13.5px] font-semibold text-[#7A3326]">FFPE artefact signal detected</p>
              <p className="mt-1 text-[12.5px] text-[#9E4A3A]">
                Fixation-induced cytosine deamination can imitate low-frequency somatic variants.
                Confirm any low-VAF finding on an orthogonal assay before acting on it.
                {qc.ffpe_confidence ? ` Detector confidence: ${qc.ffpe_confidence}.` : ""}
              </p>
            </div>
          )}

          <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Metric label="Tumour purity" value={formatPct(qc?.tumour_purity_estimate)} />
            <Metric label="Median VAF" value={formatPct(qc?.median_vaf, 1)} />
            <Metric label="Mean depth" value={meanDepth === null ? null : `${meanDepth}x`} />
            <Metric label="Ti/Tv ratio" value={formatNum(qc?.ti_tv_ratio, 2)} />
            <Metric label="C>T fraction" value={formatPct(qc?.ffpe_artefact_rate, 1)} />
            <Metric label="Coverage" value={qc?.coverage_adequacy ?? null} />
          </div>

          {qc?.pass_variants !== null && qc?.pass_variants !== undefined && (
            <p className={`mb-3 text-[12px] ${muted}`}>
              {qc.pass_variants} of {qc.total_variants ?? "?"} variants passed caller filters
              {qc.ffpe_score !== null && qc.ffpe_score !== undefined
                ? ` · FFPE score ${qc.ffpe_score.toFixed(2)}`
                : ""}
            </p>
          )}

          {warnings.length > 0 && (
            <div className="rounded-[10px] border border-[#E6D3AE] bg-[#FBF4E6] p-4">
              <p className="mb-1 text-[13.5px] font-semibold text-[#7A4F14]">Quality warnings</p>
              <ul className="list-inside list-disc space-y-1 text-[13.5px] text-[#7A4F14]">
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
