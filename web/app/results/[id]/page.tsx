"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  CheckCircle,
  Clock,
  AlertTriangle,
  Dna,
  FlaskConical,
  BookOpen,
  BarChart2,
  Users,
  ShieldCheck,
  Award,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";

const statusColors: Record<string, string> = {
  queued: "text-yellow-600 bg-yellow-50",
  processing: "text-blue-600 bg-blue-50",
  awaiting_ai: "text-purple-600 bg-purple-50",
  complete: "text-green-600 bg-green-50",
  failed: "text-red-600 bg-red-50",
};

/** AlphaMissense score badge: red = pathogenic, amber = uncertain, green = benign */
function ScoreBadge({ score }: { score: number | null | undefined }) {
  if (score == null) return <span className="text-gray-300 text-xs">â€”</span>;
  const pct = Math.round(score * 100);
  const color =
    score >= 0.564
      ? "bg-red-100 text-red-700"
      : score <= 0.34
      ? "bg-green-100 text-green-700"
      : "bg-yellow-100 text-yellow-700";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {pct}%
    </span>
  );
}

/** Classification string badge */
function ClassBadge({ cls }: { cls: string | null | undefined }) {
  const map: Record<string, string> = {
    pathogenic: "bg-red-100 text-red-700",
    likely_pathogenic: "bg-orange-100 text-orange-700",
    benign: "bg-green-100 text-green-700",
    likely_benign: "bg-green-50 text-green-600",
    uncertain: "bg-gray-100 text-gray-600",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[cls as string] ?? "bg-gray-100 text-gray-500"}`}>
      {cls ?? "unknown"}
    </span>
  );
}

/** Approval status badge */
function ApprovalBadge({ status }: { status: string }) {
  const isApproved = status?.toLowerCase().includes("approved");
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
        isApproved
          ? "bg-green-100 text-green-700"
          : "bg-gray-100 text-gray-500"
      }`}
    >
      {status ?? "Unknown"}
    </span>
  );
}

/** Progress bar for binding score (0â€“1 scale) */
function BindingBar({ score }: { score: number | null | undefined }) {
  if (score == null) return <span className="text-gray-300 text-xs">â€”</span>;
  const pct = Math.max(0, Math.min(100, Math.round(score * 100)));
  const color = pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-yellow-400" : "bg-gray-300";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500 w-8 text-right">{pct}%</span>
    </div>
  );
}

export default function ResultsPage({ params }: { params: { id: string } }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["results", params.id],
    queryFn: () => api.getResults(params.id),
    refetchInterval: (query) => {
      const d = (query as { state: { data?: { status?: string } } }).state.data;
      return d?.status !== "complete" && d?.status !== "failed" ? 10000 : false;
    },
  });

  // Fetch repurposing candidates once results are complete and a result_id exists
  const { data: repurposing } = useQuery({
    queryKey: ["repurposing", data?.result_id],
    queryFn: () => api.getRepurposing(data!.result_id!),
    enabled: data?.status === "complete" && !!data?.result_id,
  });

  if (isLoading) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-500">Loading your results...</p>
        </div>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="text-center">
          <AlertTriangle className="text-red-400 mx-auto mb-4" size={48} />
          <p className="text-gray-700 font-semibold">Could not load results</p>
          <p className="text-gray-400 text-sm mt-2">Submission not found or access denied.</p>
        </div>
      </main>
    );
  }

  if (data.status !== "complete") {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-white rounded-2xl p-10 max-w-md w-full text-center shadow-md"
        >
          <Clock className="text-blue-500 mx-auto mb-4 animate-pulse" size={48} />
          <h2 className="text-xl font-bold text-gray-900 mb-2">Analysis in progress</h2>
          <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${statusColors[data.status] ?? ""}`}>
            {data.status}
          </span>
          <p className="text-gray-500 text-sm mt-4">{data.message}</p>
          <p className="text-gray-400 text-xs mt-2">This page refreshes automatically.</p>
        </motion.div>
      </main>
    );
  }

  const topMutation = data.mutations?.[0] as Record<string, unknown> | undefined;
  const level1 = topMutation?.oncokb_level === "1";
  const candidates = repurposing?.candidates ?? [];

  return (
    <main className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-4xl mx-auto space-y-8">

        {/* â”€â”€ HEADER â”€â”€ */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-3xl font-bold text-gray-900 mb-1">Your Results</h1>
          <p className="text-gray-500 text-sm flex flex-wrap items-center gap-2">
            <span>{data.cancer_type} Â· Submission {params.id.slice(0, 8)}</span>
            {data.oncologist_reviewed && (
              <span className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full flex items-center gap-1">
                <ShieldCheck size={12} /> Oncologist reviewed
              </span>
            )}
          </p>
        </motion.div>

        {/* â•â• SECTION 1: Plain-language summary â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
        {data.plain_language_summary && (
          <motion.div
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
            className="bg-blue-50 border border-blue-100 rounded-2xl p-6"
          >
            <div className="flex items-center gap-2 mb-3">
              <BookOpen className="text-blue-600" size={20} />
              <h2 className="font-bold text-blue-900 text-lg">What this means for you</h2>
              <span className="ml-auto text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full shrink-0">
                AI-generated Â· plain language
              </span>
            </div>
            <p className="text-gray-800 text-base leading-relaxed whitespace-pre-line">
              {data.plain_language_summary}
            </p>
          </motion.div>
        )}

        {/* â•â• SECTION 2: Mutation details â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="space-y-3"
        >
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <Dna size={20} className="text-blue-500" />
            Mutation Details
          </h2>

          {/* Level 1 FDA banner */}
          {level1 && (
            <div className="bg-green-50 border border-green-300 rounded-xl px-5 py-4 flex items-start gap-3">
              <Award size={20} className="text-green-600 mt-0.5 shrink-0" />
              <div>
                <p className="font-bold text-green-800 text-sm">OncoKB Level 1 â€” FDA-approved drug exists for this exact mutation</p>
                <p className="text-green-700 text-xs mt-0.5">
                  Your oncologist can prescribe an approved therapy targeting this specific mutation. Ask about it at your next appointment.
                </p>
              </div>
            </div>
          )}

          <div className="bg-white rounded-2xl border border-gray-100 overflow-x-auto shadow-sm">
            <table className="w-full text-sm min-w-[640px]">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-left p-4 font-semibold text-gray-600">Gene</th>
                  <th className="text-left p-4 font-semibold text-gray-600">Mutation (HGVS)</th>
                  <th className="text-left p-4 font-semibold text-gray-600">Type</th>
                  <th className="text-left p-4 font-semibold text-gray-600">AlphaMissense</th>
                  <th className="text-left p-4 font-semibold text-gray-600">Classification</th>
                  <th className="text-left p-4 font-semibold text-gray-600">OncoKB Level</th>
                  <th className="text-left p-4 font-semibold text-gray-600">Targetable</th>
                </tr>
              </thead>
              <tbody>
                {(data.mutations ?? []).map((m: Record<string, unknown>, i: number) => (
                  <tr key={i} className="border-b border-gray-50 last:border-0 hover:bg-gray-50 transition-colors">
                    <td className="p-4 font-mono font-bold text-blue-700">{m.gene as string}</td>
                    <td className="p-4 font-mono text-xs text-gray-500 max-w-[180px] truncate">{(m.hgvs as string) ?? "â€”"}</td>
                    <td className="p-4 text-gray-500 text-xs capitalize">{(m.mutation_type as string) ?? "â€”"}</td>
                    <td className="p-4"><ScoreBadge score={m.alphamissense_score as number | null} /></td>
                    <td className="p-4"><ClassBadge cls={m.classification as string} /></td>
                    <td className="p-4">
                      {m.oncokb_level && m.oncokb_level !== "unknown" ? (
                        <span className={`font-mono text-xs px-2 py-0.5 rounded-full font-semibold ${
                          m.oncokb_level === "1" ? "bg-green-100 text-green-700" :
                          m.oncokb_level === "2" ? "bg-blue-100 text-blue-700" :
                          "bg-gray-100 text-gray-500"
                        }`}>
                          Level {m.oncokb_level as string}
                        </span>
                      ) : <span className="text-gray-300 text-xs">â€”</span>}
                    </td>
                    <td className="p-4">
                      {m.is_targetable
                        ? <CheckCircle className="text-green-500" size={16} />
                        : <span className="text-gray-300">â€”</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>

        {/* â•â• SECTION 3: COSMIC + cBioPortal frequency â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
        {((data.cbioportal_data?.length ?? 0) > 0 || data.cosmic_sample_count) && (
          <motion.div
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
            className="space-y-3"
          >
            <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <BarChart2 size={20} className="text-purple-500" />
              Population Frequency
            </h2>

            {data.cosmic_sample_count && parseInt(data.cosmic_sample_count) > 0 && (
              <div className="bg-purple-50 border border-purple-100 rounded-xl px-5 py-4 text-sm text-purple-900">
                <span className="font-bold text-purple-800 text-base">
                  {parseInt(data.cosmic_sample_count).toLocaleString()}
                </span>{" "}tumour samples in COSMIC carry this {data.target_gene ?? ""} mutation â€” showing how commonly it appears in cancer genomes worldwide.
              </div>
            )}

            {(data.cbioportal_data?.length ?? 0) > 0 && (
              <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden shadow-sm">
                <div className="px-4 py-3 border-b border-gray-50 text-xs text-gray-400">
                  cBioPortal Â· mutation frequency across cancer studies
                </div>
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-100">
                    <tr>
                      <th className="text-left p-4 font-semibold text-gray-600">Study</th>
                      <th className="text-left p-4 font-semibold text-gray-600">Cancer Type</th>
                      <th className="text-right p-4 font-semibold text-gray-600">Samples with Mutation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.cbioportal_data!.slice(0, 6).map((row, i) => (
                      <tr key={i} className="border-b border-gray-50 last:border-0 hover:bg-gray-50">
                        <td className="p-4 font-mono text-xs text-blue-600">{row.study_id}</td>
                        <td className="p-4 text-gray-600 capitalize text-sm">{row.cancer_type}</td>
                        <td className="p-4 text-right">
                          <span className="inline-flex items-center gap-1 justify-end">
                            <Users size={13} className="text-gray-400" />
                            <span className="font-semibold text-gray-900">{row.mutation_count}</span>
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(data.cbioportal_data!.length) > 6 && (
                  <p className="text-center text-xs text-gray-400 py-3">
                    Showing 6 of {data.cbioportal_data!.length} studies
                  </p>
                )}
              </div>
            )}
          </motion.div>
        )}

        {/* â•â• SECTION 4: Drug repurposing candidates â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
        {candidates.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
            className="space-y-3"
          >
            <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <FlaskConical size={20} className="text-blue-500" />
              Drug Repurposing Candidates
              <span className="text-xs font-normal text-gray-400">Top {candidates.slice(0, 5).length} ranked by AI</span>
            </h2>
            <div className="space-y-3">
              {candidates.slice(0, 5).map((c, i) => (
                <div key={i} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div>
                      <span className="font-bold text-gray-900 text-base">{c.drug_name}</span>
                      <span className="ml-2 text-xs text-gray-400 font-mono">{c.chembl_id}</span>
                    </div>
                    <ApprovalBadge status={c.approval_status} />
                  </div>
                  {c.mechanism && (
                    <p className="text-gray-600 text-sm leading-relaxed mb-3">{c.mechanism}</p>
                  )}
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-xs text-gray-400">
                      <span className="w-28 shrink-0">Binding score</span>
                      <div className="flex-1">
                        <BindingBar score={c.binding_score} />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-3 flex-wrap pt-1">
              {data.result_id && (
                <Link
                  href={`/repurposing/${data.result_id}`}
                  className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-blue-700 transition-colors"
                >
                  <FlaskConical size={16} /> View All Candidates
                </Link>
              )}
              <Link
                href={`/marketplace/requests/new?result_id=${data.result_id}&gene=${data.target_gene ?? ""}`}
                className="flex items-center gap-2 border border-blue-200 text-blue-700 px-5 py-2.5 rounded-xl text-sm font-semibold hover:border-blue-400 transition-colors"
              >
                Request Custom Drug Synthesis
              </Link>
            </div>
          </motion.div>
        )}

        {/* â•â• SECTION 5: Oncologist validation â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
        <motion.div
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
        >
          {data.oncologist_reviewed ? (
            <div className="bg-white border border-green-200 rounded-2xl p-6 space-y-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="text-green-600" size={20} />
                <h3 className="font-bold text-gray-900">Oncologist Review</h3>
              </div>
              {Boolean((data as Record<string, unknown>).oncologist_name) && (
                <div className="text-sm text-gray-600">
                  <span className="font-semibold text-gray-800">
                    {(data as Record<string, unknown>).oncologist_name as string}
                  </span>
                  {Boolean((data as Record<string, unknown>).oncologist_institution) && (
                    <span className="text-gray-400"> Â· {(data as Record<string, unknown>).oncologist_institution as string}</span>
                  )}
                </div>
              )}
              {data.oncologist_notes && (
                <p className="text-gray-700 text-sm leading-relaxed border-l-4 border-green-200 pl-4">
                  {data.oncologist_notes}
                </p>
              )}
            </div>
          ) : (
            <div className="bg-gray-50 border border-dashed border-gray-200 rounded-2xl p-6 flex items-start gap-3">
              <Clock className="text-gray-300 shrink-0 mt-0.5" size={20} />
              <div>
                <p className="font-semibold text-gray-500 text-sm">Pending oncologist review</p>
                <p className="text-gray-400 text-xs mt-1">
                  A qualified oncologist will review your results within 3â€“5 business days and add clinical context. You will be notified by email.
                </p>
              </div>
            </div>
          )}
        </motion.div>

        <p className="text-xs text-gray-400 text-center pb-8">
          This analysis is for informational purposes only and does not constitute medical advice.
          Always consult a qualified oncologist before making any treatment decisions.
        </p>
      </div>
    </main>
  );
}
