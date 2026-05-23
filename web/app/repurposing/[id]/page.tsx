"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { FlaskConical, CheckCircle, AlertTriangle, ExternalLink, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { DEMO_REPURPOSING, DEMO_ID } from "@/lib/demo-data";

function ScoreBar({ value }: { value: number | null }) {
  if (value === null) return <span className="text-slate-300 text-xs">—</span>;
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-slate-100 dark:bg-slate-800 rounded-full h-2.5">
        <div
          className="bg-cyan-500 h-2.5 rounded-full"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-xs text-slate-500 w-8 text-right">{pct}%</span>
    </div>
  );
}

export default function RepurposingPage({ params }: { params: { id: string } }) {
  const searchParams = useSearchParams();
  const isDemo = searchParams.get("demo") === "true" || params.id === DEMO_ID;

  const { data, isLoading, error } = useQuery<any>({
    queryKey: ["repurposing", params.id],
    queryFn: () => isDemo ? Promise.resolve(DEMO_REPURPOSING) : api.getRepurposing(params.id),
  });

  if (isLoading) {
    return (
      <main className="min-h-screen bg-slate-50 dark:bg-slate-950 py-12 px-4">
        <div className="max-w-3xl mx-auto space-y-6 animate-pulse">
          <div className="h-8 w-72 bg-slate-200 dark:bg-slate-700 rounded-lg" />
          <div className="h-4 w-48 bg-slate-200 dark:bg-slate-700 rounded" />
          <div className="h-20 w-full bg-slate-100 dark:bg-slate-800 rounded-2xl" />
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 p-6 space-y-4">
              <div className="h-5 w-40 bg-slate-200 dark:bg-slate-700 rounded" />
              <div className="h-4 w-72 bg-slate-200 dark:bg-slate-700 rounded" />
              <div className="grid grid-cols-2 gap-4">
                <div className="h-3 w-full bg-slate-100 dark:bg-slate-800 rounded-full" />
                <div className="h-3 w-full bg-slate-100 dark:bg-slate-800 rounded-full" />
              </div>
            </div>
          ))}
        </div>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-6">
        <div className="text-center">
          <AlertTriangle className="text-red-400 mx-auto mb-3" size={40} />
          <p className="text-slate-700 dark:text-slate-300 font-semibold">Could not load repurposing data</p>
          <p className="text-slate-400 text-sm mt-1">Check that the submission ID is correct and the analysis has completed.</p>
        </div>
      </main>
    );
  }

  if (!data.has_targetable_mutation) {
    return (
      <main className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-6">
        <div className="bg-white dark:bg-slate-900 rounded-2xl p-10 max-w-md w-full text-center shadow-md border border-slate-100 dark:border-slate-800">
          <AlertTriangle className="text-orange-400 mx-auto mb-4" size={48} />
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">No targetable mutations</h2>
          <p className="text-slate-500 text-sm">{(data as Record<string, unknown>).message as string}</p>
          <Link
            href="/marketplace"
            className="mt-6 block text-cyan-600 text-sm hover:underline"
          >
            Browse our pharma marketplace →
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 dark:bg-slate-950 pb-16">
      <div className="sticky top-0 z-10 bg-slate-50/90 dark:bg-slate-950/90 backdrop-blur border-b border-slate-100 dark:border-slate-800 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-3">
            <FlaskConical className="text-cyan-600 shrink-0" size={24} />
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Drug Repurposing Candidates</h1>
          </div>
          <p className="text-sm text-slate-500">
            Target: <span className="font-mono font-semibold text-cyan-700 dark:text-cyan-400">{data.target_gene}</span>
            &nbsp;·&nbsp;{data.candidates.length} candidate{data.candidates.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>
      <div className="max-w-3xl mx-auto space-y-8 px-6 pt-8">

        {/* Explanation */}
        <div className="bg-cyan-50 dark:bg-cyan-950/40 border border-cyan-100 dark:border-cyan-800 rounded-2xl p-5 text-sm text-cyan-800 dark:text-cyan-300 leading-relaxed">
          <strong>How this works:</strong> These are existing approved drugs that our AI believes may
          bind to the mutated protein in your sample. They have not been tested specifically for
          your mutation. Always discuss these candidates with your oncologist before considering
          any treatment change.
        </div>

        {/* Candidates */}
        <div className="space-y-4">
          {data.candidates.map((c: any, i: number) => (
            <motion.div
              key={c.chembl_id ?? i}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.07 }}
              className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 p-6 hover:border-cyan-200 dark:hover:border-cyan-700 hover:shadow-md transition-all"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-cyan-700 text-white text-sm font-bold shrink-0">{i + 1}</span>
                    <h3 className="font-bold text-slate-900 dark:text-slate-100 text-lg">{c.drug_name}</h3>
                    {c.approval_status && (
                      <span className="bg-green-100 dark:bg-green-950/60 text-green-700 dark:text-green-300 text-xs px-2 py-0.5 rounded-full font-medium">
                        {c.approval_status}
                      </span>
                    )}
                  </div>
                  <p className="text-slate-500 text-sm ml-10">{c.mechanism ?? "Mechanism not available"}</p>
                </div>
                {c.chembl_id && (
                  <a
                    href={`https://www.ebi.ac.uk/chembl/compound_report_card/${c.chembl_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-slate-400 hover:text-cyan-600 transition-colors shrink-0"
                  >
                    <ExternalLink size={16} />
                  </a>
                )}
              </div>

              <div className="mt-4 ml-10 grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-slate-400 mb-1">OpenTargets association</p>
                  <ScoreBar value={c.opentargets_score} />
                </div>
                <div>
                  <p className="text-xs text-slate-400 mb-1">Overall rank score</p>
                  <ScoreBar value={c.rank_score} />
                </div>
              </div>

              <div className="mt-4 ml-10 space-y-2">
                <div>
                  <p className="text-xs text-slate-400 mb-2">Evidence sources</p>
                  <div className="flex flex-wrap gap-2">
                    {(c.evidence_sources?.length ? c.evidence_sources : ["Unspecified"]).map((source: string) => (
                      <span
                        key={`${c.chembl_id ?? c.drug_name}-${source}`}
                        className="rounded-full border border-cyan-100 dark:border-cyan-800 bg-cyan-50 dark:bg-cyan-950/50 px-2.5 py-1 text-xs font-medium text-cyan-700 dark:text-cyan-300"
                      >
                        {source}
                      </span>
                    ))}
                  </div>
                </div>

                {c.matched_terms?.length > 0 && (
                  <div>
                    <p className="text-xs text-slate-400 mb-1">Matched evidence terms</p>
                    <p className="text-sm text-slate-600 dark:text-slate-400">{c.matched_terms.join(", ")}</p>
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </div>

        {/* CTA */}
        <div className="flex gap-4 flex-wrap">
          <Link
            href="/marketplace"
            className="flex items-center gap-2 bg-cyan-700 text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-cyan-600 active:bg-cyan-800 transition-colors shadow-sm"
          >
            <ShoppingCart size={16} /> Find a Manufacturer
          </Link>
          <Link
            href="/dashboard"
            className="flex items-center gap-2 border border-slate-200 dark:border-slate-700 px-5 py-2.5 rounded-xl text-sm font-semibold text-slate-700 dark:text-slate-300 hover:border-slate-400 dark:hover:border-slate-500 transition-colors"
          >
            Back to Dashboard
          </Link>
        </div>

        <p className="text-xs text-slate-400 text-center">
          Repurposing candidates are generated by AI and are for informational purposes only.
          ChEMBL IDs link to the European Bioinformatics Institute drug database.
        </p>
      </div>
    </main>
  );
}
