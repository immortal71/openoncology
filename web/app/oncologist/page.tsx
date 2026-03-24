"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ShieldCheck, AlertTriangle, Clock, CheckCircle, User } from "lucide-react";

interface PendingResult {
  submission_id: string;
  patient_email_hash: string;
  mutation_count: number;
  targetable_count: number;
  created_at: string;
}

interface ReviewPayload {
  submission_id: string;
  approved: boolean;
  notes: string;
}

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function authHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? sessionStorage.getItem("kc_token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchPending(): Promise<PendingResult[]> {
  const res = await fetch(`${API}/api/oncologist/pending`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Unauthorized or unavailable");
  return res.json();
}

async function submitReview(payload: ReviewPayload) {
  const res = await fetch(`${API}/api/oncologist/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Review submission failed");
  return res.json();
}

function ReviewCard({ item, onDone }: { item: PendingResult; onDone: () => void }) {
  const [notes, setNotes] = useState("");
  const [expanded, setExpanded] = useState(false);

  const mutation = useMutation({
    mutationFn: (approved: boolean) =>
      submitReview({ submission_id: item.submission_id, approved, notes }),
    onSuccess: onDone,
  });

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="font-mono text-sm text-gray-900">{item.submission_id}</p>
          <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
            <Clock size={12} />
            {new Date(item.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="text-right text-sm">
          <p className="text-gray-500">
            <span className="font-semibold text-gray-900">{item.mutation_count}</span> mutations
          </p>
          <p className="text-blue-600 font-medium">
            {item.targetable_count} targetable
          </p>
        </div>
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="text-sm text-blue-600 underline underline-offset-2"
      >
        {expanded ? "Hide" : "Add"} review notes
      </button>

      {expanded && (
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          placeholder="Optional clinical notes for the patient record…"
          className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      )}

      {mutation.isError && (
        <p className="text-red-500 text-xs">{(mutation.error as Error).message}</p>
      )}

      {mutation.isSuccess ? (
        <div className="flex items-center gap-2 text-green-700 text-sm">
          <CheckCircle size={16} /> Review submitted
        </div>
      ) : (
        <div className="flex gap-3">
          <button
            onClick={() => mutation.mutate(true)}
            disabled={mutation.isPending}
            className="flex-1 flex items-center justify-center gap-2 bg-green-600 text-white py-2.5 rounded-xl text-sm font-semibold hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            <ShieldCheck size={16} /> Approve
          </button>
          <button
            onClick={() => mutation.mutate(false)}
            disabled={mutation.isPending}
            className="flex-1 flex items-center justify-center gap-2 border border-red-200 text-red-600 py-2.5 rounded-xl text-sm font-semibold hover:bg-red-50 disabled:opacity-50 transition-colors"
          >
            <AlertTriangle size={16} /> Flag
          </button>
        </div>
      )}
    </div>
  );
}

export default function OncologistPage() {
  const queryClient = useQueryClient();
  const [reviewedIds, setReviewedIds] = useState<Set<string>>(new Set());

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["oncologist-pending"],
    queryFn: fetchPending,
    retry: false,
  });

  const handleDone = (id: string) => {
    setReviewedIds((prev) => new Set([...prev, id]));
    queryClient.invalidateQueries({ queryKey: ["oncologist-pending"] });
  };

  const pending = data?.filter((item) => !reviewedIds.has(item.submission_id)) ?? [];

  return (
    <main className="min-h-screen bg-gray-50 py-16 px-6">
      <div className="max-w-2xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
          {/* Header */}
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-xl">
              <User size={22} className="text-blue-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Oncologist Portal</h1>
              <p className="text-gray-500 text-sm">Review AI-analysed genomic results</p>
            </div>
          </div>

          {isLoading && (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto" />
            </div>
          )}

          {isError && (
            <div className="bg-red-50 border border-red-200 rounded-2xl p-5 text-red-700 text-sm">
              <p className="font-semibold mb-1">Access denied</p>
              <p>{(error as Error).message}</p>
              <p className="mt-2 text-xs text-red-500">
                Make sure you are signed in with an account that has the{" "}
                <code className="bg-red-100 px-1 rounded">oncologist</code> role in Keycloak.
              </p>
            </div>
          )}

          {!isLoading && !isError && pending.length === 0 && (
            <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center">
              <CheckCircle size={36} className="text-green-400 mx-auto mb-3" />
              <p className="font-semibold text-gray-800">All caught up!</p>
              <p className="text-gray-400 text-sm mt-1">No results are awaiting review.</p>
            </div>
          )}

          {pending.length > 0 && (
            <div className="space-y-4">
              <p className="text-sm text-gray-500">
                {pending.length} result{pending.length !== 1 ? "s" : ""} awaiting review
              </p>
              {pending.map((item) => (
                <ReviewCard key={item.submission_id} item={item} onDone={() => handleDone(item.submission_id)} />
              ))}
            </div>
          )}
        </motion.div>
      </div>
    </main>
  );
}
