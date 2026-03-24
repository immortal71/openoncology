"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { FlaskConical, CheckCircle, AlertTriangle, ExternalLink, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";

function ScoreBar({ value }: { value: number | null }) {
  if (value === null) return <span className="text-gray-300 text-xs">—</span>;
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-100 rounded-full h-1.5">
        <div
          className="bg-blue-500 h-1.5 rounded-full"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-xs text-gray-500 w-8 text-right">{pct}%</span>
    </div>
  );
}

export default function RepurposingPage({ params }: { params: { id: string } }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["repurposing", params.id],
    queryFn: () => api.getRepurposing(params.id),
  });

  if (isLoading) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="text-red-400 mx-auto mb-3" size={40} />
          <p className="text-gray-700 font-semibold">Could not load repurposing data</p>
        </div>
      </main>
    );
  }

  if (!data.has_targetable_mutation) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="bg-white rounded-2xl p-10 max-w-md w-full text-center shadow-md">
          <AlertTriangle className="text-orange-400 mx-auto mb-4" size={48} />
          <h2 className="text-xl font-bold text-gray-900 mb-2">No targetable mutations</h2>
          <p className="text-gray-500 text-sm">{(data as Record<string, unknown>).message as string}</p>
          <Link
            href="/marketplace"
            className="mt-6 block text-blue-600 text-sm hover:underline"
          >
            Browse our pharma marketplace →
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 py-16 px-6">
      <div className="max-w-3xl mx-auto space-y-8">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex items-center gap-3 mb-2">
            <FlaskConical className="text-blue-600" size={28} />
            <h1 className="text-3xl font-bold text-gray-900">Drug Repurposing Candidates</h1>
          </div>
          <p className="text-gray-500 text-sm">
            Target gene: <span className="font-mono font-semibold text-blue-700">{data.target_gene}</span>
            &nbsp;·&nbsp; {data.candidates.length} candidate{data.candidates.length !== 1 ? "s" : ""} found
          </p>
        </motion.div>

        {/* Explanation */}
        <div className="bg-blue-50 border border-blue-100 rounded-2xl p-5 text-sm text-blue-800 leading-relaxed">
          <strong>How this works:</strong> These are existing approved drugs that our AI believes may
          bind to the mutated protein in your sample. They have not been tested specifically for
          your mutation. Always discuss these candidates with your oncologist before considering
          any treatment change.
        </div>

        {/* Candidates */}
        <div className="space-y-4">
          {data.candidates.map((c, i) => (
            <motion.div
              key={c.chembl_id ?? i}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.07 }}
              className="bg-white rounded-2xl border border-gray-100 p-6 hover:border-blue-200 hover:shadow-md transition-all"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-2xl font-bold text-gray-300 w-7">#{i + 1}</span>
                    <h3 className="font-bold text-gray-900 text-lg">{c.drug_name}</h3>
                    {c.approval_status && (
                      <span className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full font-medium">
                        {c.approval_status}
                      </span>
                    )}
                  </div>
                  <p className="text-gray-500 text-sm ml-9">{c.mechanism ?? "Mechanism not available"}</p>
                </div>
                {c.chembl_id && (
                  <a
                    href={`https://www.ebi.ac.uk/chembl/compound_report_card/${c.chembl_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-400 hover:text-blue-600 transition-colors shrink-0"
                  >
                    <ExternalLink size={16} />
                  </a>
                )}
              </div>

              <div className="mt-4 ml-9 grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-400 mb-1">OpenTargets association</p>
                  <ScoreBar value={c.opentargets_score} />
                </div>
                <div>
                  <p className="text-xs text-gray-400 mb-1">Overall rank score</p>
                  <ScoreBar value={c.rank_score} />
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* CTA */}
        <div className="flex gap-4 flex-wrap">
          <Link
            href="/marketplace"
            className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-blue-700 transition-colors"
          >
            <ShoppingCart size={16} /> Find a Manufacturer
          </Link>
          <Link
            href="/dashboard"
            className="flex items-center gap-2 border border-gray-200 px-5 py-2.5 rounded-xl text-sm font-semibold text-gray-700 hover:border-gray-400 transition-colors"
          >
            Back to Dashboard
          </Link>
        </div>

        <p className="text-xs text-gray-400 text-center">
          Repurposing candidates are generated by AI and are for informational purposes only.
          ChEMBL IDs link to the European Bioinformatics Institute drug database.
        </p>
      </div>
    </main>
  );
}
