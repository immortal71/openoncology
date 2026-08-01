import { DRUG_TIER_LABELS, toDrugCandidate, type RealRepurposingCandidate } from "@/lib/pipeline-stages";

const INK = "#16181D";
const MUTED = "#8A8D86";
const BODY = "#5B5E64";
const BORDER = "#E4E2DB";
const BG = "#FAFAF8";

export type MutationRow = {
  gene?: string;
  hgvs?: string;
  classification?: string;
  oncokb_level?: string;
  is_targetable?: boolean;
};

export function VariantCallOutput({
  runStatus,
  mutations,
}: {
  runStatus: string;
  mutations: MutationRow[];
}) {
  return (
    <div className="border overflow-x-auto" style={{ borderColor: BORDER, backgroundColor: BG }}>
      <div className="px-4 py-2 border-b" style={{ borderColor: BORDER }}>
        <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: MUTED }}>
          status:{" "}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: INK }}>
          {runStatus}
        </span>
      </div>
      {mutations.length === 0 ? (
        <p className="text-sm px-4 py-3" style={{ color: MUTED }}>No mutations returned.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b" style={{ borderColor: BORDER }}>
              {["gene", "protein change", "classification", "OncoKB level", "targetable"].map((h) => (
                <th
                  key={h}
                  className="text-left font-mono text-[10px] uppercase tracking-widest px-4 py-2 font-normal"
                  style={{ color: MUTED }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: BORDER }}>
            {mutations.map((m, i) => (
              <tr key={i}>
                <td className="px-4 py-2 font-mono text-xs" style={{ color: INK }}>{m.gene ?? "—"}</td>
                <td className="px-4 py-2 font-mono text-xs" style={{ color: BODY }}>{m.hgvs ?? "—"}</td>
                <td className="px-4 py-2 font-mono text-xs" style={{ color: BODY }}>{m.classification ?? "—"}</td>
                <td className="px-4 py-2 font-mono text-xs" style={{ color: BODY }}>{m.oncokb_level ?? "—"}</td>
                <td className="px-4 py-2 font-mono text-xs" style={{ color: m.is_targetable ? INK : MUTED }}>
                  {m.is_targetable ? "yes" : "no"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function RepurposingOutput({
  resultId,
  targetGene,
  candidates,
}: {
  resultId: string;
  targetGene: string | null;
  candidates: RealRepurposingCandidate[];
}) {
  const rows = candidates.map(toDrugCandidate);
  return (
    <div className="border" style={{ borderColor: BORDER, backgroundColor: BG }}>
      <div className="px-4 py-3 border-b grid grid-cols-2 sm:grid-cols-3 gap-3" style={{ borderColor: BORDER }}>
        <div>
          <p className="font-mono text-[9px] uppercase tracking-widest" style={{ color: MUTED }}>Result ID</p>
          <p className="font-mono text-xs mt-0.5 truncate" style={{ color: INK }}>{resultId}</p>
        </div>
        <div>
          <p className="font-mono text-[9px] uppercase tracking-widest" style={{ color: MUTED }}>Target gene</p>
          <p className="font-mono text-xs mt-0.5" style={{ color: INK }}>{targetGene ?? "—"}</p>
        </div>
        <div>
          <p className="font-mono text-[9px] uppercase tracking-widest" style={{ color: MUTED }}>Candidates returned</p>
          <p className="font-mono text-xs mt-0.5" style={{ color: INK }}>{candidates.length}</p>
        </div>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm px-4 py-3" style={{ color: MUTED }}>No candidates returned for this result.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b" style={{ borderColor: BORDER }}>
                {["drug", "tier", "rank_score"].map((h) => (
                  <th
                    key={h}
                    className="text-left font-mono text-[10px] uppercase tracking-widest px-4 py-2 font-normal"
                    style={{ color: MUTED }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: BORDER }}>
              {rows.map((c) => (
                <tr key={c.drug}>
                  <td className="px-4 py-2 text-xs" style={{ color: INK }}>{c.drug}</td>
                  <td className="px-4 py-2 font-mono text-xs" style={{ color: BODY }}>
                    {DRUG_TIER_LABELS[c.tier] ?? c.tier}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs" style={{ color: INK }}>
                    {c.rankScore.toFixed(3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function CustomBriefOutput({
  reason,
  leadCandidates,
  componentLibrary,
}: {
  reason: string;
  leadCandidates: number;
  componentLibrary: { scaffolds: string[]; fragments: string[] };
}) {
  return (
    <div className="border p-4 flex flex-col gap-3" style={{ borderColor: BORDER, backgroundColor: BG }}>
      <div>
        <p className="font-mono text-[9px] uppercase tracking-widest" style={{ color: MUTED }}>reason</p>
        <p className="font-mono text-xs mt-0.5" style={{ color: INK }}>{reason}</p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="font-mono text-[9px] uppercase tracking-widest" style={{ color: MUTED }}>Lead candidates</p>
          <p className="text-sm mt-0.5" style={{ color: INK }}>{leadCandidates}</p>
        </div>
        <div>
          <p className="font-mono text-[9px] uppercase tracking-widest" style={{ color: MUTED }}>Scaffolds / fragments</p>
          <p className="text-sm mt-0.5" style={{ color: INK }}>
            {componentLibrary.scaffolds.length} / {componentLibrary.fragments.length}
          </p>
        </div>
      </div>
      <div
        className="border px-3 py-2 text-xs"
        style={{ borderColor: "#D9C08A", backgroundColor: "#FAF6EA", color: "#6B4A1E" }}
      >
        Computational planning only — does not represent physical synthesis.
      </div>
    </div>
  );
}
