"use client";

/**
 * /marketplace/requests — Patient view of their drug synthesis requests.
 * Shows all requests, their bids, and lets the patient accept a bid.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  FlaskConical,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  Clock,
  DollarSign,
  X,
  Plus,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";

type Bid = {
  id: string;
  pharma_id: string;
  price_usd: number;
  estimated_weeks: string;
  notes: string | null;
  status: string;
  created_at: string;
};

type Request = {
  id: string;
  target_gene: string | null;
  drug_spec: string;
  max_budget_usd: number | null;
  bid_count: number;
  created_at: string;
};

function BidCard({
  bid,
  requestId,
  onAccepted,
}: {
  bid: Bid;
  requestId: string;
  onAccepted: () => void;
}) {
  const [accepting, setAccepting] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");

  const accept = async () => {
    setAccepting(true);
    setErr("");
    try {
      await api.acceptBid(requestId, bid.id);
      setDone(true);
      onAccepted();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to accept bid");
    } finally {
      setAccepting(false);
    }
  };

  const statusBg =
    bid.status === "accepted"
      ? "bg-green-50 border-green-200"
      : bid.status === "rejected"
      ? "bg-gray-50 border-gray-100 opacity-60"
      : "bg-white border-gray-100";

  return (
    <div className={`border rounded-xl p-4 ${statusBg}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <DollarSign size={15} className="text-green-600" />
            <span className="font-bold text-gray-900 text-lg">
              ${bid.price_usd.toLocaleString()}
            </span>
            <span className="text-gray-400 text-sm">·</span>
            <Clock size={13} className="text-gray-400" />
            <span className="text-gray-600 text-sm">{bid.estimated_weeks} weeks</span>
          </div>
          {bid.notes && (
            <p className="text-gray-600 text-sm leading-relaxed">{bid.notes}</p>
          )}
          <p className="text-gray-400 text-xs">
            Submitted {new Date(bid.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="shrink-0">
          {bid.status === "accepted" ? (
            <span className="inline-flex items-center gap-1 text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium">
              <CheckCircle size={12} /> Accepted
            </span>
          ) : bid.status === "rejected" ? (
            <span className="text-xs text-gray-400 px-2 py-1 rounded-full bg-gray-100">
              Rejected
            </span>
          ) : (
            !done && (
              <button
                onClick={accept}
                disabled={accepting}
                className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg font-semibold hover:bg-blue-700 transition-colors disabled:opacity-60"
              >
                {accepting ? "Accepting…" : "Accept Bid"}
              </button>
            )
          )}
          {done && (
            <span className="inline-flex items-center gap-1 text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium">
              <CheckCircle size={12} /> Accepted
            </span>
          )}
        </div>
      </div>
      {err && <p className="text-red-600 text-xs mt-2">{err}</p>}
    </div>
  );
}

function RequestRow({ req }: { req: Request }) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: bids, isLoading } = useQuery({
    queryKey: ["bids", req.id],
    queryFn: () => api.getBids(req.id),
    enabled: open,
  });

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-4 p-5 text-left hover:bg-gray-50 transition-colors"
      >
        <FlaskConical size={20} className="text-blue-500 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {req.target_gene && (
              <span className="font-mono font-bold text-blue-700 text-sm">
                {req.target_gene}
              </span>
            )}
            <span className="text-gray-400 text-xs">
              {new Date(req.created_at).toLocaleDateString()}
            </span>
            {req.max_budget_usd && (
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                Budget: ${req.max_budget_usd.toLocaleString()}
              </span>
            )}
          </div>
          <p className="text-gray-600 text-sm mt-1 line-clamp-2">{req.drug_spec}</p>
        </div>
        <div className="shrink-0 flex items-center gap-3">
          <span className="text-xs bg-blue-50 text-blue-600 px-2 py-1 rounded-full font-medium">
            {bids ? bids.length : req.bid_count} bid{(bids?.length ?? req.bid_count) !== 1 ? "s" : ""}
          </span>
          {open ? (
            <ChevronUp size={16} className="text-gray-400" />
          ) : (
            <ChevronDown size={16} className="text-gray-400" />
          )}
        </div>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-t border-gray-100 p-5 space-y-3 bg-gray-50">
              {isLoading && (
                <p className="text-gray-400 text-sm animate-pulse">Loading bids…</p>
              )}
              {bids && bids.length === 0 && (
                <p className="text-gray-400 text-sm">
                  No bids yet. Pharma companies will be notified of your request.
                </p>
              )}
              {bids && bids.map((bid) => (
                <BidCard
                  key={bid.id}
                  bid={bid}
                  requestId={req.id}
                  onAccepted={() =>
                    queryClient.invalidateQueries({ queryKey: ["bids", req.id] })
                  }
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function MyRequestsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["drug-requests"],
    queryFn: () => api.getDrugRequests(),
  });

  return (
    <main className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              My Drug Synthesis Requests
            </h1>
            <p className="text-gray-500 text-sm mt-1">
              Pharma companies can bid on your requests. Accept the best offer.
            </p>
          </div>
          <Link
            href="/marketplace/requests/new"
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2.5 rounded-xl text-sm font-semibold hover:bg-blue-700 transition-colors"
          >
            <Plus size={16} /> New Request
          </Link>
        </div>

        {isLoading && (
          <div className="text-center py-16 text-gray-400">Loading requests…</div>
        )}
        {error && (
          <div className="text-center py-16 text-red-400">
            Could not load requests.
          </div>
        )}
        {data && data.length === 0 && (
          <div className="bg-white rounded-2xl border border-dashed border-gray-200 p-12 text-center">
            <FlaskConical
              size={40}
              className="text-gray-300 mx-auto mb-4"
            />
            <p className="text-gray-500 font-medium">No requests yet</p>
            <p className="text-gray-400 text-sm mt-1">
              Create a request from your results page or click "New Request" above.
            </p>
          </div>
        )}
        {data && data.map((req) => <RequestRow key={req.id} req={req} />)}
      </div>
    </main>
  );
}
