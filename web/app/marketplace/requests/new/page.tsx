"use client";

/**
 * /marketplace/requests/new — Patient creates a custom drug synthesis request.
 * Pre-fills target_gene and result_id from URL search params when arriving
 * from the results page "Request Custom Drug Synthesis" button.
 */

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { FlaskConical, ArrowLeft, Info } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function NewDrugRequestPage() {
  const params = useSearchParams();
  const router = useRouter();

  const prefillGene = params.get("gene") ?? "";
  const prefillResultId = params.get("result_id") ?? "";

  const [drugSpec, setDrugSpec] = useState("");
  const [targetGene, setTargetGene] = useState(prefillGene);
  const [maxBudget, setMaxBudget] = useState("");
  const [resultId, setResultId] = useState(prefillResultId);

  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [globalError, setGlobalError] = useState("");

  const validate = () => {
    const errs: Record<string, string> = {};
    if (drugSpec.trim().length < 20)
      errs.drugSpec = "Please describe the drug in at least 20 characters.";
    if (maxBudget && isNaN(Number(maxBudget)))
      errs.maxBudget = "Budget must be a number.";
    if (maxBudget && Number(maxBudget) <= 0)
      errs.maxBudget = "Budget must be greater than 0.";
    return errs;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate();
    setFieldErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setSubmitting(true);
    setGlobalError("");
    try {
      const body: Record<string, unknown> = {
        drug_spec: drugSpec.trim(),
      };
      if (targetGene.trim()) body.target_gene = targetGene.trim();
      if (resultId.trim()) body.result_id = resultId.trim();
      if (maxBudget.trim())
        body.max_budget_usd = Number(maxBudget.trim());

      const req = await api.createDrugRequest(body as Parameters<typeof api.createDrugRequest>[0]);
      router.push(`/marketplace/requests?highlight=${req.drug_request_id}`);
    } catch (e: unknown) {
      setGlobalError(
        e instanceof Error ? e.message : "Could not submit request. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 py-12 px-4">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="max-w-xl mx-auto"
      >
        <Link
          href="/marketplace/requests"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-6 transition-colors"
        >
          <ArrowLeft size={14} /> Back to my requests
        </Link>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-blue-50 p-2.5 rounded-xl">
              <FlaskConical size={22} className="text-blue-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">
                Request Custom Drug Synthesis
              </h1>
              <p className="text-gray-500 text-sm">
                Pharma companies will bid on your specification.
              </p>
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 flex gap-3 mb-6">
            <Info size={16} className="text-blue-500 mt-0.5 shrink-0" />
            <p className="text-blue-700 text-sm leading-relaxed">
              Your request is visible only to verified pharmaceutical companies
              on the platform. You control which bid, if any, you accept. No
              payment is collected until you explicitly accept a bid.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Drug specification */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                Drug Specification{" "}
                <span className="text-red-400">*</span>
              </label>
              <textarea
                rows={5}
                value={drugSpec}
                onChange={(e) => setDrugSpec(e.target.value)}
                placeholder="Describe the compound or drug class you need. Include mechanism of action, target pathway, preferred formulation, purity requirements, quantity, and any known scaffold references (e.g. erlotinib analogue targeting EGFR L858R with improved CNS penetration…)"
                className={`w-full rounded-xl border px-4 py-3 text-sm text-gray-900 placeholder-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 transition-shadow ${
                  fieldErrors.drugSpec
                    ? "border-red-300 bg-red-50"
                    : "border-gray-200"
                }`}
              />
              {fieldErrors.drugSpec && (
                <p className="text-red-500 text-xs mt-1">{fieldErrors.drugSpec}</p>
              )}
              <p className="text-gray-400 text-xs mt-1">
                Minimum 20 characters. The more detail, the better the bids.
              </p>
            </div>

            {/* Target gene — pre-filled from results page */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                Target Gene{" "}
                <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <input
                type="text"
                value={targetGene}
                onChange={(e) => setTargetGene(e.target.value)}
                placeholder="e.g. EGFR, KRAS, BRCA1"
                className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400 transition-shadow font-mono"
              />
            </div>

            {/* Max budget */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                Maximum Budget (USD){" "}
                <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 text-sm">
                  $
                </span>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={maxBudget}
                  onChange={(e) => setMaxBudget(e.target.value)}
                  placeholder="50000"
                  className={`w-full rounded-xl border pl-8 pr-4 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400 transition-shadow ${
                    fieldErrors.maxBudget
                      ? "border-red-300 bg-red-50"
                      : "border-gray-200"
                  }`}
                />
              </div>
              {fieldErrors.maxBudget && (
                <p className="text-red-500 text-xs mt-1">{fieldErrors.maxBudget}</p>
              )}
              <p className="text-gray-400 text-xs mt-1">
                Bids above this amount will still be shown — this is a guide for
                pharma companies, not a hard cap.
              </p>
            </div>

            {/* Hidden result linkage */}
            {resultId && (
              <p className="text-xs text-gray-400">
                Linked to genomic result{" "}
                <Link
                  href={`/results/${resultId}`}
                  className="underline hover:text-gray-600"
                >
                  {resultId.slice(0, 8)}…
                </Link>
              </p>
            )}

            {globalError && (
              <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-xl px-4 py-3">
                {globalError}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-60 text-sm"
            >
              {submitting ? "Submitting…" : "Post Request to Marketplace"}
            </button>
          </form>
        </div>
      </motion.div>
    </main>
  );
}
