"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

const STAGES = [
  { key: "queued", label: "Fetching protein structure", description: "Loading AlphaFold predicted structure for target gene." },
  { key: "running", label: "Building discovery brief", description: "Querying public target knowledge, ranked leads, and chemical components." },
  { key: "complete", label: "Generating drug brief", description: "Ranking leads by binding affinity, ADMET profile, and selectivity." },
];

function StatusTracker({ stage }: { stage: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6">
      {STAGES.map((s, i) => {
        const done = stage > i;
        const active = stage === i;
        return (
          <div
            key={s.key}
            className={`rounded-xl border p-4 ${done ? "border-green-300 bg-green-50" : active ? "border-blue-300 bg-blue-50" : "border-gray-200 bg-gray-50"}`}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className={`h-3 w-3 rounded-full ${done ? "bg-green-500" : active ? "bg-blue-500 animate-pulse" : "bg-gray-300"}`} />
              <p className="text-sm font-semibold text-gray-800">{s.label}</p>
            </div>
            <p className="text-xs text-gray-500">{s.description}</p>
          </div>
        );
      })}
    </div>
  );
}

type DrugRequestData = {
  drug_request_id?: string;
  result_id?: string;
  status?: string;
  target_gene?: string;
  cancer_type?: string;
  message?: string;
  stage?: number;
  mutation_profile?: string[];
  rationale?: string;
  live_data_used?: boolean;
  integration_issues?: string[];
  lead_compounds?: {
    name: string;
    smiles: string;
    binding_score: number | null;
    design_priority_score: number | null;
    oral_exposure_score: number | null;
    synthesis_feasibility_score: number | null;
    toxicity_risk: number | null;
    toxicity_flag: boolean;
    mechanism: string;
    phase: string;
    evidence_sources: string[];
    matched_terms: string[];
    ensemble_score?: number;
    ensemble_breakdown?: Record<string, number | null>;
  }[];
  de_novo_candidates?: {
    candidate_id: string;
    parent_lead: string;
    design_strategy: string;
    proposed_smiles: string | null;
    selected_scaffold: string | null;
    selected_fragment: string | null;
    docking_binding_score: number | null;
    target_fit_score: number;
    novelty_score: number;
    feasibility_score: number;
    overall_score: number;
    evidence_sources: string[];
    matched_terms: string[];
    ensemble_score?: number;
    ensemble_breakdown?: Record<string, number | null>;
    disclaimer: string;
  }[];
  docking_summary?: {
    runs_attempted: number;
    used_mutation_specific_structure: boolean;
    structure_path: string | null;
  };
  computational_synthesis_plan?: {
    mode?: string;
    status?: string;
    summary?: string;
    synthesis_readiness_score?: number;
    selected_candidates?: {
      candidate_id?: string;
      parent_lead?: string;
      proposed_smiles?: string | null;
      precursor_count_estimate?: number;
      route_confidence_score?: number;
      route_outline?: string[];
    }[];
    execution_stages?: {
      stage?: string;
      duration?: string;
      deliverable?: string;
    }[];
    constraints?: string[];
    disclaimer?: string;
  };
  scaffold_summary?: {
    core_scaffolds: string[];
    fragment_hits: string[];
    admet_notes: string;
  };
  timeline_weeks?: Record<string, string>;
  next_steps?: string[];
  attributions?: string[];
  scoring_engines_used?: string[];
};

function downloadBrief(data: DrugRequestData) {
  if (!data) return;
  const lines: string[] = [
    "OpenOncology Custom Drug Discovery Brief",
    "=========================================",
    `Request ID   : ${data.drug_request_id ?? ""}`,
    `Target Gene  : ${data.target_gene ?? ""}`,
    `Cancer Type  : ${data.cancer_type ?? ""}`,
    "",
    "Mutation Profile",
    "----------------",
    ...(data.mutation_profile ?? []).map((m: string) => `  • ${m}`),
    "",
    "Scientific Rationale",
    "--------------------",
    data.rationale ?? "",
    "",
    "Lead Compounds",
    "--------------",
    ...(data.lead_compounds ?? []).flatMap((c: {
      name: string; mechanism: string; binding_score: number | null;
      design_priority_score: number | null; oral_exposure_score: number | null;
      synthesis_feasibility_score: number | null; toxicity_risk: number | null;
      toxicity_flag: boolean; smiles: string; phase: string; evidence_sources: string[]; matched_terms: string[];
    }) => [
      `  ${c.name}`,
      `    Mechanism   : ${c.mechanism}`,
      `    Binding     : ${c.binding_score ?? "n/a"}`,
      `    Priority    : ${c.design_priority_score ?? "n/a"}`,
      `    Oral score  : ${c.oral_exposure_score ?? "n/a"}`,
      `    Synthesis   : ${c.synthesis_feasibility_score ?? "n/a"}`,
      `    Tox risk    : ${c.toxicity_risk ?? "n/a"}`,
      `    Evidence    : ${(c.evidence_sources ?? []).join(", ") || "n/a"}`,
      `    Matched     : ${(c.matched_terms ?? []).join(", ") || "n/a"}`,
      `    SMILES      : ${c.smiles}`,
      `    Phase       : ${c.phase}`,
      "",
    ]),
    "De Novo Candidates",
    "------------------",
    ...(data.de_novo_candidates ?? []).flatMap((cand: {
      candidate_id: string;
      parent_lead: string;
      design_strategy: string;
      proposed_smiles: string | null;
      selected_scaffold: string | null;
      selected_fragment: string | null;
      docking_binding_score: number | null;
      target_fit_score: number;
      novelty_score: number;
      feasibility_score: number;
      overall_score: number;
      evidence_sources: string[];
      matched_terms: string[];
      disclaimer: string;
    }) => [
      `  ${cand.candidate_id}`,
      `    Parent lead : ${cand.parent_lead ?? "n/a"}`,
      `    Strategy    : ${cand.design_strategy ?? "n/a"}`,
      `    Docking     : ${cand.docking_binding_score ?? "n/a"}`,
      `    Target fit  : ${cand.target_fit_score ?? "n/a"}`,
      `    Novelty     : ${cand.novelty_score ?? "n/a"}`,
      `    Feasibility : ${cand.feasibility_score ?? "n/a"}`,
      `    Overall     : ${cand.overall_score ?? "n/a"}`,
      `    Scaffold    : ${cand.selected_scaffold ?? "n/a"}`,
      `    Fragment    : ${cand.selected_fragment ?? "n/a"}`,
      `    Evidence    : ${(cand.evidence_sources ?? []).join(", ") || "n/a"}`,
      `    Matched     : ${(cand.matched_terms ?? []).join(", ") || "n/a"}`,
      `    SMILES      : ${cand.proposed_smiles ?? "n/a"}`,
      `    Note        : ${cand.disclaimer ?? "n/a"}`,
      "",
    ]),
    "Scaffold Summary",
    "----------------",
    `  Core scaffolds : ${(data.scaffold_summary?.core_scaffolds ?? []).join(", ")}`,
    `  Fragment hits  : ${(data.scaffold_summary?.fragment_hits ?? []).join(", ")}`,
    `  ADMET notes    : ${data.scaffold_summary?.admet_notes ?? ""}`,
    "",
    "Computational Synthesis Plan",
    "----------------------------",
    `  Mode                : ${data.computational_synthesis_plan?.mode ?? "n/a"}`,
    `  Status              : ${data.computational_synthesis_plan?.status ?? "n/a"}`,
    `  Readiness score     : ${data.computational_synthesis_plan?.synthesis_readiness_score ?? "n/a"}`,
    `  Summary             : ${data.computational_synthesis_plan?.summary ?? "n/a"}`,
    ...(data.computational_synthesis_plan?.selected_candidates ?? []).flatMap((cand) => [
      `  Candidate           : ${cand.candidate_id ?? "n/a"}`,
      `    Parent lead       : ${cand.parent_lead ?? "n/a"}`,
      `    Precursors est.   : ${cand.precursor_count_estimate ?? "n/a"}`,
      `    Route confidence  : ${cand.route_confidence_score ?? "n/a"}`,
      `    Route outline     : ${(cand.route_outline ?? []).join(" | ") || "n/a"}`,
      `    SMILES            : ${cand.proposed_smiles ?? "n/a"}`,
    ]),
    "",
    "Computation Timeline",
    "--------------------",
    ...Object.entries(data.timeline_weeks ?? {}).map(([k, v]) => `  ${k.replace(/_/g, " ")} : ${v}`),
    "",
    "Next Steps",
    "----------",
    ...(data.next_steps ?? []).map((s: string) => `  ${s}`),
    "",
    "Scientific Attributions",
    "-----------------------",
    ...(data.attributions ?? []).map((a: string) => `  ${a}`),
    "",
    `Generated by OpenOncology — ${new Date().toUTCString()}`,
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `custom_drug_brief_${(data.drug_request_id ?? "report").slice(0, 12)}.txt`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function CustomDrugPage() {
  const routeParams = useParams<{ id?: string | string[] }>();
  const requestId = Array.isArray(routeParams?.id) ? routeParams.id[0] : routeParams?.id;

  const { data, isLoading, isFetching, isError, error } = useQuery<DrugRequestData>({
    queryKey: ["drug-request", requestId],
    enabled: Boolean(requestId),
    queryFn: () => api.getDrugRequest(requestId as string),
    retry: false,
    refetchInterval: (query) => {
      const status = (query.state.data as { status?: string } | undefined)?.status;
      if (!status) return false;
      return status === "complete" ? false : 3000;
    },
  });

  if (isLoading || isFetching) {
    return (
      <main className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          <p className="text-gray-500 text-sm">Loading drug brief...</p>
        </div>
      </main>
    );
  }

  if (!requestId) {
    return (
      <main className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto rounded-2xl border border-red-200 bg-white p-6">
          <h1 className="text-xl font-bold text-red-700">Missing drug request ID</h1>
          <p className="text-sm text-gray-600 mt-2">This page requires a valid request ID in the URL.</p>
          <Link href="/orders" className="mt-4 inline-block text-sm text-blue-600 hover:underline">← Back to My Orders</Link>
        </div>
      </main>
    );
  }

  if (isError || !data) {
    return (
      <main className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto rounded-2xl border border-red-200 bg-white p-6">
          <h1 className="text-xl font-bold text-red-700">Could not load drug request</h1>
          <p className="text-sm text-gray-600 mt-2">{(error as Error | undefined)?.message ?? "Unknown error."}</p>
          <p className="text-sm text-gray-600 mt-2">This page only renders persisted request data from the live custom-discovery endpoint.</p>
          <Link href="/orders" className="mt-4 inline-block text-sm text-blue-600 hover:underline">← Back to My Orders</Link>
        </div>
      </main>
    );
  }

  const isComplete = data.status === "complete";
  const isFailed = data.status === "failed";
  const stageIndex = data.stage ?? (data.status === "running" ? 1 : data.status === "complete" ? 2 : 0);

  return (
    <main className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-5xl mx-auto space-y-8">

        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <Link href="/orders" className="text-xs text-blue-600 hover:underline">← My Orders</Link>
            <h1 className="text-3xl font-bold text-gray-900 mt-1">Custom Drug Discovery Brief</h1>
            <p className="text-sm text-gray-500 mt-1">
              Request <code className="bg-gray-100 px-1 rounded">{requestId}</code> · Target: <span className="font-semibold">{data.target_gene}</span> · {data.cancer_type}
            </p>
          </div>
          {isComplete && (
            <button
              onClick={() => downloadBrief(data)}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm px-5 py-2.5 rounded-xl shadow transition-colors"
            >
              ↓ Download Full Brief
            </button>
          )}
        </div>

        {/* Stage tracker — always shown */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6">
          <h2 className="text-base font-semibold text-gray-700 mb-1">Generation Progress</h2>
          <p className="text-sm text-gray-500">{data.message}</p>
          <StatusTracker stage={isComplete ? 3 : stageIndex} />
          {isFailed && (
            <p className="text-xs text-red-600 mt-4">Generation failed. Review the error above or restart the request from the result page.</p>
          )}
          {!isComplete && !isFailed && (
            <p className="text-xs text-gray-400 mt-4">This page auto-refreshes every few seconds. You can close it and come back — the job runs in the background.</p>
          )}
        </section>

        {/* Content only shows when complete */}
        {isComplete && (
          <>
            {((data.integration_issues?.length ?? 0) > 0 || data.live_data_used === false) && (
              <section className="bg-amber-50 rounded-2xl border border-amber-200 p-6">
                <h2 className="text-lg font-bold text-amber-900 mb-2">Live Integration Status</h2>
                <p className="text-sm text-amber-900">
                  {data.live_data_used === false
                    ? "This brief did not obtain usable live candidate data from the configured external sources."
                    : "Some configured external sources were unavailable or returned incomplete data during brief generation."}
                </p>
                {(data.integration_issues?.length ?? 0) > 0 && (
                  <ul className="mt-3 space-y-1 text-sm text-amber-900">
                    {(data.integration_issues ?? []).map((issue) => (
                      <li key={issue}>• {issue}</li>
                    ))}
                  </ul>
                )}
              </section>
            )}

            {/* Rationale */}
            <section className="bg-white rounded-2xl border border-gray-200 p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-2">Why a Custom Drug?</h2>
              <p className="text-sm text-gray-700 leading-relaxed">{data.rationale}</p>
              <div className="mt-4">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Mutation Profile</p>
                <ul className="space-y-1">
                  {(data.mutation_profile ?? []).map((m) => (
                    <li key={m} className="text-sm text-gray-700 flex items-start gap-2">
                      <span className="text-indigo-500 font-bold">•</span> {m}
                    </li>
                  ))}
                </ul>
              </div>
            </section>

            {/* Computational Synthesis Plan */}
            <section className="bg-white rounded-2xl border border-gray-200 p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-3">Computational Synthesis Plan</h2>
              <p className="text-sm text-gray-700">
                {data.computational_synthesis_plan?.summary ?? "Route planning data is not available for this request."}
              </p>
              <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <p className="text-slate-500 uppercase tracking-wide">Mode</p>
                  <p className="text-slate-800 font-semibold mt-1">{data.computational_synthesis_plan?.mode ?? "n/a"}</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <p className="text-slate-500 uppercase tracking-wide">Status</p>
                  <p className="text-slate-800 font-semibold mt-1">{data.computational_synthesis_plan?.status ?? "n/a"}</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <p className="text-slate-500 uppercase tracking-wide">Readiness Score</p>
                  <p className="text-slate-800 font-semibold mt-1">{data.computational_synthesis_plan?.synthesis_readiness_score ?? "n/a"}</p>
                </div>
              </div>

              {(data.computational_synthesis_plan?.selected_candidates?.length ?? 0) > 0 && (
                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  {(data.computational_synthesis_plan?.selected_candidates ?? []).map((cand) => (
                    <div key={cand.candidate_id} className="rounded-xl border border-cyan-100 bg-cyan-50 p-4 space-y-2">
                      <p className="font-semibold text-cyan-900">{cand.candidate_id ?? "Candidate"}</p>
                      <p className="text-xs text-cyan-800">Parent lead: {cand.parent_lead ?? "n/a"}</p>
                      <p className="text-xs text-cyan-800">Precursor estimate: {cand.precursor_count_estimate ?? "n/a"}</p>
                      <p className="text-xs text-cyan-800">Route confidence: {cand.route_confidence_score ?? "n/a"}</p>
                      <ul className="text-xs text-cyan-900 list-disc pl-5 space-y-1">
                        {(cand.route_outline ?? []).map((step) => (
                          <li key={step}>{step}</li>
                        ))}
                      </ul>
                      <p className="font-mono text-[11px] text-cyan-900 break-all bg-white rounded p-1">{cand.proposed_smiles ?? "n/a"}</p>
                    </div>
                  ))}
                </div>
              )}

              {(data.computational_synthesis_plan?.execution_stages?.length ?? 0) > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Execution Stages</p>
                  <div className="space-y-2">
                    {(data.computational_synthesis_plan?.execution_stages ?? []).map((stage) => (
                      <div key={stage.stage} className="rounded-lg border border-gray-200 p-3">
                        <p className="text-sm font-semibold text-gray-800">{stage.stage?.replace(/_/g, " ")}</p>
                        <p className="text-xs text-gray-600">Duration: {stage.duration ?? "n/a"}</p>
                        <p className="text-xs text-gray-600">Deliverable: {stage.deliverable ?? "n/a"}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(data.computational_synthesis_plan?.constraints?.length ?? 0) > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Constraints</p>
                  <ul className="space-y-1">
                    {(data.computational_synthesis_plan?.constraints ?? []).map((c) => (
                      <li key={c} className="text-xs text-gray-700">• {c}</li>
                    ))}
                  </ul>
                </div>
              )}

              {data.computational_synthesis_plan?.disclaimer && (
                <p className="mt-4 text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded p-2">
                  {data.computational_synthesis_plan.disclaimer}
                </p>
              )}
            </section>

            {/* Lead Compounds */}
            <section className="bg-white rounded-2xl border border-gray-200 p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4">Lead Compounds</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {(data.lead_compounds ?? []).map((c) => (
                  <div key={c.name} className="border border-gray-200 rounded-xl p-4 space-y-2 hover:border-indigo-300 transition-colors">
                    <div className="flex items-center justify-between">
                      <p className="font-bold text-gray-900">{c.name}</p>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${c.toxicity_flag ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"}`}>
                        {c.toxicity_flag ? "Tox flag" : "No tox flag"}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 italic">{c.phase}</p>
                    <p className="text-xs text-gray-700">{c.mechanism}</p>
                    <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-gray-600 mt-2">
                      <span>Binding score</span><span className="text-right font-medium text-indigo-700">{c.binding_score ?? "n/a"}</span>
                      <span>Ensemble score</span><span className="text-right font-medium text-cyan-700">{c.ensemble_score ?? "n/a"}</span>
                      <span>Priority score</span><span className="text-right font-medium">{c.design_priority_score ?? "n/a"}</span>
                      <span>Oral exposure</span><span className="text-right font-medium">{c.oral_exposure_score ?? "n/a"}</span>
                      <span>Synthesis</span><span className="text-right font-medium">{c.synthesis_feasibility_score ?? "n/a"}</span>
                      <span>Toxicity risk</span><span className="text-right font-medium">{c.toxicity_risk ?? "n/a"}</span>
                    </div>
                    <div className="mt-3 space-y-2">
                      <div className="flex flex-wrap gap-2">
                        {(c.evidence_sources?.length ? c.evidence_sources : ["Unspecified"]).map((source) => (
                          <span key={`${c.name}-${source}`} className="rounded-full border border-indigo-100 bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700">
                            {source}
                          </span>
                        ))}
                      </div>
                      {c.matched_terms?.length > 0 && (
                        <p className="text-xs text-gray-500">Matched evidence terms: {c.matched_terms.join(", ")}</p>
                      )}
                      {c.ensemble_breakdown && Object.keys(c.ensemble_breakdown).length > 0 && (
                        <p className="text-xs text-gray-500">
                          Ensemble inputs: {Object.entries(c.ensemble_breakdown).map(([k, v]) => `${k}=${v ?? "n/a"}`).join("; ")}
                        </p>
                      )}
                    </div>
                    <p className="font-mono text-xs text-gray-400 break-all mt-2 bg-gray-50 rounded p-1">{c.smiles}</p>
                  </div>
                ))}
              </div>
            </section>

            {/* De Novo Candidates */}
            <section className="bg-white rounded-2xl border border-gray-200 p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4">De Novo Candidate Proposals</h2>
              {data.docking_summary && (
                <div className="mb-4 rounded-xl border border-cyan-100 bg-cyan-50 p-3">
                  <p className="text-xs font-semibold text-cyan-800 uppercase tracking-wide">Docking Compute Summary</p>
                  <p className="text-sm text-cyan-900 mt-1">
                    Runs attempted: {data.docking_summary.runs_attempted ?? 0} · Mutation-specific structure: {data.docking_summary.used_mutation_specific_structure ? "yes" : "no"}
                  </p>
                  {data.docking_summary.structure_path && (
                    <p className="text-xs text-cyan-700 mt-1 break-all">Structure path: {data.docking_summary.structure_path}</p>
                  )}
                </div>
              )}
              {(data.de_novo_candidates?.length ?? 0) === 0 ? (
                <p className="text-sm text-gray-600">No de novo proposals were generated for this brief.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {(data.de_novo_candidates ?? []).map((cand) => (
                    <div key={cand.candidate_id} className="rounded-xl border border-gray-200 p-4 space-y-2 hover:border-cyan-300 transition-colors">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-bold text-gray-900">{cand.candidate_id}</p>
                        <span className="text-xs font-semibold text-cyan-700 bg-cyan-50 border border-cyan-100 rounded-full px-2 py-0.5">
                          Overall {cand.overall_score}
                        </span>
                      </div>
                      <p className="text-xs text-gray-600">Parent lead: {cand.parent_lead || "n/a"}</p>
                      <p className="text-xs text-gray-700">{cand.design_strategy}</p>
                      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-gray-600">
                        <span>Docking score</span><span className="text-right font-medium">{cand.docking_binding_score ?? "n/a"}</span>
                        <span>Ensemble</span><span className="text-right font-medium text-cyan-700">{cand.ensemble_score ?? "n/a"}</span>
                        <span>Target fit</span><span className="text-right font-medium">{cand.target_fit_score}</span>
                        <span>Novelty</span><span className="text-right font-medium">{cand.novelty_score}</span>
                        <span>Feasibility</span><span className="text-right font-medium">{cand.feasibility_score}</span>
                      </div>
                      <p className="text-xs text-gray-500">Scaffold: {cand.selected_scaffold || "n/a"}</p>
                      <p className="text-xs text-gray-500">Fragment: {cand.selected_fragment || "n/a"}</p>
                      <div className="flex flex-wrap gap-2">
                        {(cand.evidence_sources?.length ? cand.evidence_sources : ["Unspecified"]).map((source) => (
                          <span key={`${cand.candidate_id}-${source}`} className="rounded-full border border-indigo-100 bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700">
                            {source}
                          </span>
                        ))}
                      </div>
                      {cand.matched_terms?.length > 0 && (
                        <p className="text-xs text-gray-500">Matched terms: {cand.matched_terms.join(", ")}</p>
                      )}
                      {cand.ensemble_breakdown && Object.keys(cand.ensemble_breakdown).length > 0 && (
                        <p className="text-xs text-gray-500">
                          Ensemble inputs: {Object.entries(cand.ensemble_breakdown).map(([k, v]) => `${k}=${v ?? "n/a"}`).join("; ")}
                        </p>
                      )}
                      <p className="font-mono text-xs text-gray-400 break-all mt-1 bg-gray-50 rounded p-1">{cand.proposed_smiles || "n/a"}</p>
                      <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-100 rounded p-2">{cand.disclaimer}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Scaffold & ADMET */}
            <section className="bg-white rounded-2xl border border-gray-200 p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-3">Scaffold & ADMET Summary</h2>
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Core Scaffolds</p>
                  <ul className="space-y-1">
                    {(data.scaffold_summary?.core_scaffolds ?? []).map((s) => (
                      <li key={s} className="text-sm text-gray-700 flex gap-2"><span className="text-indigo-500">▸</span>{s}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Fragment Hits</p>
                  <ul className="space-y-1">
                    {(data.scaffold_summary?.fragment_hits ?? []).map((f) => (
                      <li key={f} className="text-sm text-gray-700 flex gap-2"><span className="text-indigo-500">▸</span>{f}</li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="mt-4 bg-amber-50 border border-amber-200 rounded-xl p-3">
                <p className="text-xs font-semibold text-amber-800 mb-1">ADMET Notes</p>
                <p className="text-sm text-amber-900">{data.scaffold_summary?.admet_notes}</p>
              </div>
            </section>

            {/* Timeline */}
            <section className="bg-white rounded-2xl border border-gray-200 p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4">Computation Timeline</h2>
              <div className="relative">
                <div className="absolute left-3 top-0 bottom-0 w-0.5 bg-indigo-200" />
                <ol className="space-y-4 ml-8">
                  {Object.entries(data.timeline_weeks ?? {}).map(([phase, duration], i) => (
                    <li key={phase} className="relative">
                      <div className="absolute -left-5 top-1 h-3 w-3 rounded-full bg-indigo-500 border-2 border-white" />
                      <p className="text-sm font-semibold text-gray-800 capitalize">{phase.replace(/_/g, " ")}</p>
                      <p className="text-xs text-gray-500">{duration}</p>
                    </li>
                  ))}
                </ol>
              </div>
            </section>

            {/* Next Steps */}
            <section className="bg-white rounded-2xl border border-gray-200 p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-3">Recommended Next Steps</h2>
              <ol className="space-y-3">
                {(data.next_steps ?? []).map((step, i) => (
                  <li key={i} className="flex gap-3 text-sm text-gray-700">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center">
                      {i + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            </section>

            {/* Attributions */}
            <section className="bg-white rounded-2xl border border-gray-200 p-6">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Scientific Attributions</h2>
              <ul className="space-y-1">
                {(data.attributions ?? []).map((a) => (
                  <li key={a} className="text-xs text-gray-500">{a}</li>
                ))}
              </ul>
              {(data.scoring_engines_used?.length ?? 0) > 0 && (
                <>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mt-4 mb-2">Scoring Engines Used</h3>
                  <ul className="space-y-1">
                    {(data.scoring_engines_used ?? []).map((engine) => (
                      <li key={engine} className="text-xs text-gray-500">{engine}</li>
                    ))}
                  </ul>
                </>
              )}
            </section>

            {/* CTA bar */}
            <div className="bg-indigo-900 rounded-2xl p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
              <div>
                <p className="text-white font-bold text-lg">Ready to proceed to synthesis?</p>
                <p className="text-indigo-200 text-sm mt-1">Download the full brief and place a compounding order with a verified pharma partner.</p>
              </div>
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => downloadBrief(data)}
                  className="bg-white text-indigo-900 font-bold text-sm px-6 py-3 rounded-xl shadow-lg hover:bg-indigo-50 transition-colors"
                >
                  ↓ Download Full Brief
                </button>
                <Link
                  href={`/marketplace/requests?highlight=${requestId}`}
                  className="bg-indigo-500 hover:bg-indigo-400 text-white font-bold text-sm px-6 py-3 rounded-xl shadow-lg transition-colors"
                >
                  Place Order with Pharma →
                </Link>
              </div>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
