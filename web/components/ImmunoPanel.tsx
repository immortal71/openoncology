"use client";

type ImmunotherapyCandidate = {
  drug_name: string;
  drug_class: string;
  oncokb_level: string;
  indication?: string;
  evidence_note?: string;
  rank_score_estimate?: number;
};

type ImmunotherapyProfile = {
  tmb_per_mb: number;
  tmb_high: boolean;
  msi_high: boolean;
  hrd: boolean;
  pole_mutation: boolean;
  mmr_gene_hits: string[];
  hrd_gene_hits: string[];
  candidates: ImmunotherapyCandidate[];
};

const LEVEL_COLOR: Record<string, string> = {
  LEVEL_1: "bg-green-100 text-green-800 border-green-200",
  LEVEL_2: "bg-blue-100 text-blue-800 border-blue-200",
  LEVEL_3A: "bg-yellow-100 text-yellow-800 border-yellow-200",
  LEVEL_3B: "bg-orange-100 text-orange-800 border-orange-200",
  LEVEL_4: "bg-slate-100 text-slate-700 border-slate-200",
};

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${color}`}>
      {label}
    </span>
  );
}

function TmbBar({ value, high }: { value: number; high: boolean }) {
  const pct = Math.min((value / 50) * 100, 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-600">
        <span>TMB</span>
        <span className={high ? "font-semibold text-green-700" : ""}>
          {value.toFixed(1)} mut/Mb {high ? "— HIGH" : ""}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-slate-200">
        <div
          className={`h-2 rounded-full transition-all duration-500 ${high ? "bg-green-500" : "bg-slate-400"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-[10px] text-slate-500">Cut-off ≥10 mut/Mb (FDA TMB-H)</p>
    </div>
  );
}

export default function ImmunoPanel({ profile }: { profile: ImmunotherapyProfile }) {
  const flags = [
    { key: "tmb_high", label: "TMB-High", active: profile.tmb_high, color: "bg-green-100 text-green-800 border-green-200" },
    { key: "msi_high", label: "MSI-High", active: profile.msi_high, color: "bg-teal-100 text-teal-800 border-teal-200" },
    { key: "hrd", label: "HRD", active: profile.hrd, color: "bg-purple-100 text-purple-800 border-purple-200" },
    { key: "pole_mutation", label: "POLE", active: profile.pole_mutation, color: "bg-indigo-100 text-indigo-800 border-indigo-200" },
  ];

  const activeFlags = flags.filter((f) => f.active);
  const hasSignal = activeFlags.length > 0;

  return (
    <section className="clinical-surface p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Immunotherapy Biomarkers</h2>
        {hasSignal ? (
          <Badge label="Actionable signal" color="bg-green-100 text-green-800 border-green-200" />
        ) : (
          <Badge label="No signal" color="bg-slate-100 text-slate-600 border-slate-200" />
        )}
      </div>

      {/* Status flags */}
      <div className="flex flex-wrap gap-2 mb-5">
        {flags.map((f) => (
          <span
            key={f.key}
            className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-semibold transition-opacity ${
              f.active ? f.color : "border-slate-200 bg-white text-slate-400 opacity-50"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${f.active ? "bg-current" : "bg-slate-300"}`} />
            {f.label}
          </span>
        ))}
      </div>

      {/* TMB bar */}
      <div className="mb-5">
        <TmbBar value={profile.tmb_per_mb} high={profile.tmb_high} />
      </div>

      {/* Gene hits */}
      {(profile.mmr_gene_hits.length > 0 || profile.hrd_gene_hits.length > 0) && (
        <div className="mb-5 flex flex-wrap gap-4 text-xs text-slate-600">
          {profile.mmr_gene_hits.length > 0 && (
            <div>
              <span className="font-medium text-teal-700">MMR genes affected: </span>
              {profile.mmr_gene_hits.join(", ")}
            </div>
          )}
          {profile.hrd_gene_hits.length > 0 && (
            <div>
              <span className="font-medium text-purple-700">HRD genes affected: </span>
              {profile.hrd_gene_hits.join(", ")}
            </div>
          )}
        </div>
      )}

      {/* Drug candidates */}
      {profile.candidates.length > 0 ? (
        <div>
          <p className="text-sm font-medium text-slate-700 mb-2">Recommended agents</p>
          <ul className="space-y-2">
            {profile.candidates.map((c, i) => (
              <li
                key={`${c.drug_name}-${i}`}
                className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"
              >
                <span className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-cyan-700 text-[11px] font-bold text-white">
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-gray-900">{c.drug_name}</p>
                    <Badge
                      label={c.oncokb_level.replace("LEVEL_", "L")}
                      color={LEVEL_COLOR[c.oncokb_level] ?? "bg-slate-100 text-slate-700 border-slate-200"}
                    />
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">{c.drug_class}</p>
                  {c.indication && <p className="text-xs text-slate-600 mt-1">{c.indication}</p>}
                  {c.evidence_note && (
                    <p className="text-[11px] text-slate-500 mt-1 italic">{c.evidence_note}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-sm text-slate-500">No immunotherapy candidates identified for this profile.</p>
      )}
    </section>
  );
}
