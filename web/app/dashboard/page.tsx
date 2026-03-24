"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import Link from "next/link";
import { Clock, CheckCircle, XCircle, Loader2, Dna, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";

const statusConfig: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  queued:       { icon: Clock,       color: "text-yellow-600 bg-yellow-50", label: "Queued" },
  processing:   { icon: Loader2,     color: "text-blue-600 bg-blue-50",    label: "Processing" },
  awaiting_ai:  { icon: Loader2,     color: "text-purple-600 bg-purple-50", label: "AI Analysis" },
  complete:     { icon: CheckCircle, color: "text-green-600 bg-green-50",  label: "Complete" },
  failed:       { icon: XCircle,     color: "text-red-600 bg-red-50",      label: "Failed" },
};

function StatusBadge({ status }: { status: string }) {
  const cfg = statusConfig[status] ?? { icon: Clock, color: "text-gray-600 bg-gray-50", label: status };
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.color}`}>
      <Icon size={12} className={status === "processing" || status === "awaiting_ai" ? "animate-spin" : ""} />
      {cfg.label}
    </span>
  );
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DashboardPage() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.getMe });
  const { data: submissions, isLoading } = useQuery({
    queryKey: ["submissions"],
    queryFn: api.getAllSubmissions,
    refetchInterval: (query) => {
      const submissions = (query as { state: { data?: { status: string }[] } }).state.data;
      return submissions?.some((s) => s.status !== "complete" && s.status !== "failed") ? 15000 : false;
    },
  });

  return (
    <main className="min-h-screen bg-gray-50 py-16 px-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
          <p className="text-sm text-gray-400 mb-1">Welcome back</p>
          <h1 className="text-3xl font-bold text-gray-900">
            {me?.name ?? "Your Dashboard"}
          </h1>
          <p className="text-gray-500 mt-1">
            All your sample submissions and analysis results.
          </p>
        </motion.div>

        {/* Quick actions */}
        <div className="flex gap-4 mb-8 flex-wrap">
          <Link
            href="/submit"
            className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-blue-700 transition-colors"
          >
            <Dna size={16} /> Submit New Sample
          </Link>
          <Link
            href="/marketplace"
            className="flex items-center gap-2 border border-gray-200 px-5 py-2.5 rounded-xl text-sm font-semibold text-gray-700 hover:border-gray-400 transition-colors"
          >
            Pharma Marketplace
          </Link>
        </div>

        {/* Submissions list */}
        {isLoading ? (
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="bg-white rounded-2xl h-24 animate-pulse" />
            ))}
          </div>
        ) : submissions && submissions.length > 0 ? (
          <div className="space-y-4">
            {submissions.map((s, i) => (
              <motion.div
                key={s.submission_id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Link
                  href={`/results/${s.submission_id}`}
                  className="block bg-white rounded-2xl border border-gray-100 p-6 hover:border-blue-200 hover:shadow-md transition-all"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-4 min-w-0">
                      <div className="bg-blue-50 rounded-xl p-2.5 shrink-0">
                        <Dna className="text-blue-600" size={20} />
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-semibold text-gray-900 truncate">{s.cancer_type}</h3>
                        <p className="text-gray-400 text-xs mt-0.5">
                          Submitted {formatDate(s.submitted_at)}
                          {s.completed_at && <> · Completed {formatDate(s.completed_at)}</>}
                        </p>
                        <p className="text-gray-300 font-mono text-xs mt-0.5">
                          {s.submission_id.slice(0, 16)}…
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <StatusBadge status={s.status} />
                      <ChevronRight className="text-gray-300" size={16} />
                    </div>
                  </div>
                </Link>
              </motion.div>
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-2xl border border-dashed border-gray-200 p-16 text-center">
            <Dna className="text-gray-200 mx-auto mb-4" size={48} />
            <p className="text-gray-500 font-medium">No submissions yet</p>
            <p className="text-gray-400 text-sm mt-1 mb-6">
              Upload your first DNA sample to get started.
            </p>
            <Link
              href="/submit"
              className="inline-flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-blue-700 transition-colors"
            >
              <Dna size={16} /> Submit Sample
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}
