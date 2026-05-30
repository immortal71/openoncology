"use client";

type SignatureImplication = {
  signature_name: string;
  drug_class: string;
  drug_recommendations: string[];
  oncokb_level: string;
  evidence_note?: string;
};

type MutationalSignature = {
  dominant_signature: string | null;
  signature_fraction: number;
  confidence: string;
  mutation_count: number;
  all_fractions: Record<string, number>;
  implication: SignatureImplication | null;
};

const CONFIDENCE_COLOR: Record<string, string> = {
  HIGH: "bg-green-100 text-green-800 border-green-200",
  MEDIUM: "bg-yellow-100 text-yellow-800 border-yellow-200",
  LOW: "bg-orange-100 text-orange-800 border-orange-200",
  INSUFFICIENT: "bg-slate-100 text-slate-500 border-slate-200",
};

const FRACTION_COLORS: Record<string, string> = {
  "C>A": "bg-blue-500",
  "C>G": "bg-green-500",
  "C>T": "bg-red-500",
  "T>A": "bg-slate-400",
  "T>C": "bg-purple-500",
  "T>G": "bg-pink-500",
};

const LEVEL_COLOR: Record<string, string> = {
  LEVEL_1: "bg-green-100 text-green-800 border-green-200",
  LEVEL_2: "bg-blue-100 text-blue-800 border-blue-200",
  LEVEL_3A: "bg-yellow-100 text-yellow-800 border-yellow-200",
  LEVEL_3B: "bg-orange-100 text-orange-800 border-orange-200",
  LEVEL_4: "bg-slate-100 text-slate-700 border-slate-200",
};

function MutationSpectrum({ fractions }: { fractions: Record<string, number> }) {
  const channels = ["C>A", "C>G", "C>T", "T>A", "T>C", "T>G"];
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-slate-600 mb-2">Substitution spectrum</p>
      {channels.map((ch) => {
        const pct = ((fractions[ch] ?? 0) * 100).toFixed(1);
        return (
          <div key={ch} className="flex items-center gap-2">
            <span className="w-8 text-[11px] font-mono text-slate-500">{ch}</span>
            <div className="flex-1 h-2 rounded-full bg-slate-200">
              <div
                className={`h-2 rounded-full transition-all duration-500 ${FRACTION_COLORS[ch] ?? "bg-slate-400"}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="w-10 text-right text-[11px] text-slate-500">{pct}%</span>
          </div>
        );
      })}
    </div>
  );
}

export default function SignatureCard({ signature }: { signature: MutationalSignature }) {
  const noSignal = !signature.dominant_signature || signature.confidence === "INSUFFICIENT";

  return (
    <section className="clinical-surface p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Mutational Signature</h2>
        {signature.dominant_signature && (
          <span className="rounded-full bg-slate-800 px-3 py-1 text-xs font-bold text-white">
            {signature.dominant_signature}
          </span>
        )}
      </div>

      {noSignal ? (
        <p className="text-sm text-slate-500">
          Insufficient mutation count ({signature.mutation_count} SNVs) for reliable signature analysis.
          A minimum of 10 SNVs is required.
        </p>
      ) : (
        <>
          {/* Confidence + fraction */}
          <div className="flex flex-wrap gap-3 mb-5">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${
                CONFIDENCE_COLOR[signature.confidence] ?? CONFIDENCE_COLOR.LOW
              }`}
            >
              {signature.confidence} confidence
            </span>
            <span className="text-xs text-slate-500 self-center">
              {(signature.signature_fraction * 100).toFixed(0)}% of SNVs attributed
              · {signature.mutation_count} total SNVs
            </span>
          </div>

          {/* Substitution spectrum */}
          {Object.keys(signature.all_fractions).length > 0 && (
            <div className="mb-5">
              <MutationSpectrum fractions={signature.all_fractions} />
            </div>
          )}

          {/* Treatment implication */}
          {signature.implication && (
            <div className="rounded-xl border border-indigo-100 bg-indigo-50 p-4">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <p className="text-sm font-semibold text-indigo-900">
                  {signature.implication.signature_name}
                </p>
                <span
                  className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
                    LEVEL_COLOR[signature.implication.oncokb_level] ?? "bg-slate-100 text-slate-700 border-slate-200"
                  }`}
                >
                  {signature.implication.oncokb_level.replace("LEVEL_", "L")}
                </span>
              </div>
              <p className="text-xs text-indigo-700 mb-2">{signature.implication.drug_class}</p>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {signature.implication.drug_recommendations.map((d) => (
                  <span
                    key={d}
                    className="rounded-full bg-white border border-indigo-200 px-2 py-0.5 text-[11px] font-medium text-indigo-800"
                  >
                    {d}
                  </span>
                ))}
              </div>
              {signature.implication.evidence_note && (
                <p className="text-[11px] text-indigo-600 italic">{signature.implication.evidence_note}</p>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
