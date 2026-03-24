"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Building2,
  Globe,
  DollarSign,
  X,
  CheckCircle,
  FlaskConical,
  ChevronRight,
  Clock,
  Send,
} from "lucide-react";
import { api } from "@/lib/api";

const orderSchema = z.object({
  drug_spec: z.string().min(20, "Please provide a detailed drug specification").max(2000),
  amount_usd: z.coerce.number().min(100, "Minimum order is $100").max(1_000_000),
});

const bidSchema = z.object({
  price_usd: z.coerce.number().min(1, "Price is required"),
  estimated_weeks: z.coerce.number().min(1, "Estimated weeks required"),
  notes: z.string().max(1000).optional(),
});
type BidForm = z.infer<typeof bidSchema>;

type DrugRequest = {
  id: string;
  target_gene: string | null;
  drug_spec: string;
  max_budget_usd: number | null;
  bid_count: number;
  created_at: string;
};

function BidModal({
  request,
  onClose,
}: {
  request: DrugRequest;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [success, setSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<BidForm>({ resolver: zodResolver(bidSchema) });

  const submit = async (data: BidForm) => {
    await api.submitBid(request.id, {
      price_usd: data.price_usd,
      estimated_weeks: data.estimated_weeks,
      notes: data.notes ?? undefined,
    });
    queryClient.invalidateQueries({ queryKey: ["open-drug-requests"] });
    setSuccess(true);
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white rounded-2xl p-8 max-w-md w-full shadow-2xl"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-gray-900">Submit Bid</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <X size={20} />
          </button>
        </div>

        <div className="bg-gray-50 rounded-xl p-3 mb-5 text-sm text-gray-600">
          <span className="font-mono font-semibold text-blue-700">
            {request.target_gene ?? "Gene not specified"}
          </span>
          {request.max_budget_usd && (
            <span className="ml-2 text-gray-400">
              · Max budget ${request.max_budget_usd.toLocaleString()}
            </span>
          )}
          <p className="mt-1 text-gray-500 line-clamp-2">{request.drug_spec}</p>
        </div>

        {success ? (
          <div className="text-center py-6">
            <CheckCircle className="text-green-500 mx-auto mb-3" size={48} />
            <p className="font-semibold text-gray-900">Bid submitted!</p>
            <p className="text-gray-500 text-sm mt-1">
              The patient will be notified and can accept your bid.
            </p>
            <button onClick={onClose} className="mt-5 text-blue-600 text-sm hover:underline">
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit(submit)} className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">
                Your Price (USD) <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <DollarSign
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                />
                <input
                  {...register("price_usd")}
                  type="number"
                  min="1"
                  placeholder="25000"
                  className="w-full border border-gray-200 rounded-xl pl-8 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
              </div>
              {errors.price_usd && (
                <p className="text-red-500 text-xs mt-1">{errors.price_usd.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">
                Estimated Timeline (weeks) <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <Clock
                  size={14}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                />
                <input
                  {...register("estimated_weeks")}
                  type="number"
                  min="1"
                  placeholder="12"
                  className="w-full border border-gray-200 rounded-xl pl-8 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
              </div>
              {errors.estimated_weeks && (
                <p className="text-red-500 text-xs mt-1">{errors.estimated_weeks.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">
                Notes{" "}
                <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <textarea
                {...register("notes")}
                rows={3}
                placeholder="Describe your manufacturing capabilities, GMP certification, prior oncology experience..."
                className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
              {errors.notes && (
                <p className="text-red-500 text-xs mt-1">{errors.notes.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
            >
              <Send size={15} />
              {isSubmitting ? "Submitting…" : "Submit Bid"}
            </button>
          </form>
        )}
      </motion.div>
    </div>
  );
}
type OrderForm = z.infer<typeof orderSchema>;

function OrderModal({
  pharma,
  onClose,
}: {
  pharma: { id: string; name: string; min_order_usd: number | null };
  onClose: () => void;
}) {
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<OrderForm>({
    resolver: zodResolver(orderSchema),
    defaultValues: { amount_usd: pharma.min_order_usd ?? 500 },
  });

  const onSubmit = async (data: OrderForm) => {
    setStatus("submitting");
    try {
      const token = sessionStorage.getItem("kc_token");
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/marketplace/order`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ pharma_id: pharma.id, ...data }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail ?? "Order failed");
      }
      setStatus("success");
    } catch (err: unknown) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Order failed. Please try again.");
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white rounded-2xl p-8 max-w-md w-full shadow-2xl"
      >
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold text-gray-900">Order from {pharma.name}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <X size={20} />
          </button>
        </div>

        {status === "success" ? (
          <div className="text-center py-6">
            <CheckCircle className="text-green-500 mx-auto mb-3" size={48} />
            <p className="font-semibold text-gray-900">Order placed!</p>
            <p className="text-gray-500 text-sm mt-2">
              The pharma company will contact you to confirm details.
            </p>
            <button onClick={onClose} className="mt-6 text-blue-600 text-sm hover:underline">
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Drug specification
              </label>
              <textarea
                {...register("drug_spec")}
                rows={5}
                placeholder="Describe the drug, target mutation, dosage, formulation, and any special requirements..."
                className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
              {errors.drug_spec && (
                <p className="text-red-500 text-xs mt-1">{errors.drug_spec.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Budget (USD)
              </label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                <input
                  {...register("amount_usd")}
                  type="number"
                  className="w-full border border-gray-200 rounded-xl pl-9 pr-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              {errors.amount_usd && (
                <p className="text-red-500 text-xs mt-1">{errors.amount_usd.message}</p>
              )}
            </div>

            {status === "error" && (
              <p className="text-red-500 text-sm">{errorMsg}</p>
            )}

            <button
              type="submit"
              disabled={status === "submitting"}
              className="w-full bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {status === "submitting" ? "Placing order..." : "Submit Order Request"}
            </button>

            <p className="text-xs text-gray-400 text-center">
              A Stripe payment link will be generated after the pharma company confirms.
            </p>
          </form>
        )}
      </motion.div>
    </div>
  );
}

export default function MarketplacePage() {
  const [selectedPharma, setSelectedPharma] = useState<{
    id: string;
    name: string;
    min_order_usd: number | null;
  } | null>(null);
  const [selectedRequest, setSelectedRequest] = useState<DrugRequest | null>(null);

  const { data: companies, isLoading } = useQuery({
    queryKey: ["pharma-companies"],
    queryFn: api.getPharmaCompanies,
  });

  const { data: openRequests, isLoading: requestsLoading } = useQuery({
    queryKey: ["open-drug-requests"],
    queryFn: () => api.getDrugRequests(),
  });

  return (
    <main className="min-h-screen bg-gray-50 py-16 px-6">
      <div className="max-w-5xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Pharma Marketplace</h1>
          <p className="text-gray-500">
            Verified pharmaceutical manufacturers who can produce repurposed or custom drugs
            based on your mutation profile. All companies are manually verified by our team.
          </p>
        </motion.div>

        {isLoading ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="bg-white rounded-2xl h-48 animate-pulse" />
            ))}
          </div>
        ) : companies && companies.length > 0 ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {companies.map((c, i) => (
              <motion.div
                key={c.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                className="bg-white rounded-2xl border border-gray-100 p-6 hover:border-blue-200 hover:shadow-md transition-all flex flex-col"
              >
                <div className="flex items-start gap-3 mb-3">
                  <div className="bg-blue-50 rounded-xl p-2">
                    <Building2 className="text-blue-600" size={20} />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-900">{c.name}</h3>
                    <div className="flex items-center gap-1 text-gray-400 text-xs mt-0.5">
                      <Globe size={11} />
                      <span>{c.country}</span>
                    </div>
                  </div>
                </div>

                <p className="text-gray-500 text-sm flex-1 leading-relaxed">
                  {c.description ?? "Custom pharmaceutical manufacturing for oncology applications."}
                </p>

                {c.min_order_usd && (
                  <p className="text-xs text-gray-400 mt-3">
                    Min. order: <span className="font-semibold text-gray-600">${c.min_order_usd.toLocaleString()}</span>
                  </p>
                )}

                <button
                  onClick={() => setSelectedPharma(c)}
                  className="mt-4 w-full bg-blue-600 text-white py-2.5 rounded-xl text-sm font-semibold hover:bg-blue-700 transition-colors"
                >
                  Request Quote
                </button>
              </motion.div>
            ))}
          </div>
        ) : (
          <div className="text-center py-20 text-gray-400">
            <Building2 className="mx-auto mb-4" size={48} />
            <p>No verified pharma companies yet. Check back soon.</p>
          </div>
        )}
      </div>

      {/* ── Drug Synthesis Requests (for pharma to bid on) ── */}
      <div className="max-w-5xl mx-auto mt-16">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="mb-6"
        >
          <div className="flex items-center gap-3 mb-1">
            <FlaskConical size={22} className="text-blue-500" />
            <h2 className="text-2xl font-bold text-gray-900">
              Drug Synthesis Requests
            </h2>
          </div>
          <p className="text-gray-500 text-sm">
            Patients have posted these custom drug synthesis requests. Submit a
            competitive bid — patients will be notified and can accept the best offer.
          </p>
        </motion.div>

        {requestsLoading && (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="bg-white rounded-2xl h-20 animate-pulse border border-gray-100" />
            ))}
          </div>
        )}

        {openRequests && openRequests.length === 0 && (
          <div className="bg-white rounded-2xl border border-dashed border-gray-200 p-10 text-center text-gray-400">
            <FlaskConical size={36} className="mx-auto mb-3 opacity-40" />
            <p className="font-medium">No open requests at the moment</p>
            <p className="text-sm mt-1">Check back soon — new patient requests appear here.</p>
          </div>
        )}

        {openRequests && openRequests.length > 0 && (
          <div className="space-y-3">
            {openRequests.map((req, i) => (
              <motion.div
                key={req.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                className="bg-white rounded-2xl border border-gray-100 px-5 py-4 flex items-center gap-4 hover:border-blue-200 hover:shadow-sm transition-all"
              >
                <FlaskConical size={18} className="text-blue-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {req.target_gene && (
                      <span className="font-mono font-bold text-blue-700 text-sm">
                        {req.target_gene}
                      </span>
                    )}
                    {req.max_budget_usd && (
                      <span className="text-xs bg-green-50 text-green-700 border border-green-100 px-2 py-0.5 rounded-full">
                        Max ${req.max_budget_usd.toLocaleString()}
                      </span>
                    )}
                    <span className="text-gray-400 text-xs">
                      {new Date(req.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="text-gray-500 text-sm mt-0.5 line-clamp-1">
                    {req.drug_spec}
                  </p>
                </div>
                <div className="shrink-0 flex items-center gap-3">
                  <span className="text-xs text-gray-400">
                    {req.bid_count} bid{req.bid_count !== 1 ? "s" : ""}
                  </span>
                  <button
                    onClick={() => setSelectedRequest(req)}
                    className="flex items-center gap-1.5 bg-blue-600 text-white text-sm px-4 py-2 rounded-xl font-semibold hover:bg-blue-700 transition-colors"
                  >
                    Bid <ChevronRight size={14} />
                  </button>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {selectedPharma && (
        <OrderModal pharma={selectedPharma} onClose={() => setSelectedPharma(null)} />
      )}
      {selectedRequest && (
        <BidModal request={selectedRequest} onClose={() => setSelectedRequest(null)} />
      )}
    </main>
  );
}
