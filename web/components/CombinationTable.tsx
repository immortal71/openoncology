"use client";

type CombinationSuggestion = {
  drugs: string[];
  synergy_type: string;
  rationale: string;
  combination_score: number;
  evidence_level: string;
  evidence_note: string;
  cancer_type_context?: string | null;
  trial_ids: string[];
};

const SYNERGY_LABELS: Record<string, { label: string; color: string }> = {
  pathway_vertical: { label: "Pathway synergy", color: "bg-blue-100 text-blue-800 border-blue-200" },
  bypass_resistance: { label: "Resistance bypass", color: "bg-orange-100 text-orange-800 border-orange-200" },
  approved_regimen: { label: "Approved regimen", color: "bg-green-100 text-green-800 border-green-200" },
};

const LEVEL_COLOR: Record<string, string> = {
  LEVEL_1: "bg-green-100 text-green-800 border-green-200",
  LEVEL_2: "bg-blue-100 text-blue-800 border-blue-200",
  LEVEL_3A: "bg-yellow-100 text-yellow-800 border-yellow-200",
};

function ScoreDots({ score }: { score: number }) {
  const filled = Math.round(score * 5);
  return (
    <div className="flex gap-0.5" title={`Score: ${(score * 100).toFixed(0)}%`}>
      {Array.from({ length: 5 }).map((_, i) => (
        <span
          key={i}
          className={`h-2 w-2 rounded-full ${i < filled ? "bg-cyan-600" : "bg-slate-200"}`}
        />
      ))}
    </div>
  );
}

export default function CombinationTable({ combinations }: { combinations: CombinationSuggestion[] }) {
  if (!combinations.length) return null;

  return (
    <section className="clinical-surface p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Combination Therapy</h2>
        <span className="rounded-full bg-cyan-50 border border-cyan-200 px-2.5 py-0.5 text-xs font-semibold text-cyan-800">
          {combinations.length} suggestion{combinations.length !== 1 ? "s" : ""}
        </span>
      </div>

      <p className="text-xs text-slate-500 mb-4">
        These are evidence-based combination regimens where two or more agents target complementary
        vulnerabilities in this mutation profile. All are FDA-approved or supported by Phase 3 data
        unless otherwise noted. Discuss with your oncologist before considering any combination.
      </p>

      <ul className="space-y-4">
        {combinations.map((combo, i) => {
          const synergyMeta = SYNERGY_LABELS[combo.synergy_type] ?? {
            label: combo.synergy_type,
            color: "bg-slate-100 text-slate-700 border-slate-200",
          };
          return (
            <li
              key={combo.drugs.join("+")}
              className="rounded-xl border border-slate-200 bg-slate-50 p-4"
            >
              {/* Drug names */}
              <div className="flex flex-wrap items-center gap-2 mb-2">
                {combo.drugs.map((d, di) => (
                  <span key={d}>
                    <span className="font-semibold text-gray-900 text-sm">{d}</span>
                    {di < combo.drugs.length - 1 && (
                      <span className="mx-1 text-slate-400 text-sm">+</span>
                    )}
                  </span>
                ))}
              </div>

              {/* Badges row */}
              <div className="flex flex-wrap gap-2 mb-3">
                <span
                  className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${synergyMeta.color}`}
                >
                  {synergyMeta.label}
                </span>
                <span
                  className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
                    LEVEL_COLOR[combo.evidence_level] ?? "bg-slate-100 text-slate-700 border-slate-200"
                  }`}
                >
                  {combo.evidence_level.replace("LEVEL_", "L")}
                </span>
                {combo.cancer_type_context && (
                  <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600">
                    {combo.cancer_type_context}
                  </span>
                )}
                <ScoreDots score={combo.combination_score} />
              </div>

              {/* Rationale */}
              <p className="text-xs text-slate-600 mb-2">{combo.rationale}</p>

              {/* Evidence note */}
              <p className="text-[11px] text-slate-500 italic mb-2">{combo.evidence_note}</p>

              {/* Trial links */}
              {combo.trial_ids.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {combo.trial_ids.map((id) => (
                    <a
                      key={id}
                      href={`https://clinicaltrials.gov/study/${id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] font-medium text-blue-700 hover:underline"
                    >
                      {id}
                    </a>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
