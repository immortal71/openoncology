"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { Heart, Users, Target, Share2, CheckCircle } from "lucide-react";
import { loadStripe } from "@stripe/stripe-js";
import { Elements, PaymentElement, useStripe, useElements } from "@stripe/react-stripe-js";
import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { DEMO_CROWDFUND, DEMO_ID } from "@/lib/demo-data";

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ?? "");

function ProgressBar({ percent }: { percent: number }) {
  return (
    <div>
      <div className="relative w-full bg-slate-100 dark:bg-slate-800 rounded-full h-4 overflow-hidden">
        <motion.div
          className="bg-gradient-to-r from-cyan-600 to-cyan-400 h-4 rounded-full"
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(percent, 100)}%` }}
          transition={{ duration: 1.2, ease: "easeOut" }}
        />
        {[25, 50, 75].map((m) => (
          <div
            key={m}
            className="absolute top-0 bottom-0 w-px bg-slate-900/20 dark:bg-white/10"
            style={{ left: `${m}%` }}
          />
        ))}
      </div>
      <div className="relative mt-1 h-4">
        {[25, 50, 75, 100].map((m) => (
          <span
            key={m}
            className="absolute text-[10px] text-slate-400 -translate-x-1/2"
            style={{ left: `${m}%` }}
          >
            {m}%
          </span>
        ))}
      </div>
    </div>
  );
}

function DonateForm({
  slug,
  campaignTitle,
  onSuccess,
}: {
  slug: string;
  campaignTitle: string;
  onSuccess: () => void;
}) {
  const stripe = useStripe();
  const elements = useElements();
  const [amount, setAmount] = useState("25");
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [step, setStep] = useState<"amount" | "payment" | "done">("amount");
  const [error, setError] = useState("");
  const [processing, setProcessing] = useState(false);

  const handleAmountSubmit = async () => {
    setError("");
    const usd = parseFloat(amount);
    if (!usd || usd < 1) { setError("Enter a valid amount (min $1)"); return; }

    try {
      const token = getToken();
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/crowdfund/${slug}/donate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          body: JSON.stringify({ amount_usd: usd }),
        }
      );
      if (!res.ok) throw new Error("Could not create payment");
      const data = await res.json();
      setClientSecret(data.client_secret);
      setStep("payment");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Payment setup failed");
    }
  };

  const handlePaymentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements) return;
    setProcessing(true);

    const result = await stripe.confirmPayment({
      elements,
      confirmParams: { return_url: window.location.href },
      redirect: "if_required",
    });

    if (result.error) {
      setError(result.error.message ?? "Payment failed");
    } else {
      setStep("done");
      onSuccess();
    }
    setProcessing(false);
  };

  if (step === "done") {
    return (
      <div className="text-center py-6">
        <CheckCircle className="text-green-500 mx-auto mb-3" size={40} />
        <p className="font-semibold text-gray-900">Thank you for your donation!</p>
        <p className="text-gray-400 text-sm mt-1">You're helping make treatment possible.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {step === "amount" ? (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Donation amount (USD)</label>
            <div className="flex gap-2 mb-3">
              {["10", "25", "50", "100"].map((v) => (
                <button
                  key={v}
                  onClick={() => setAmount(v)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    amount === v
                      ? "bg-blue-600 text-white border-blue-600"
                      : "border-gray-200 text-gray-600 hover:border-blue-400"
                  }`}
                >
                  ${v}
                </button>
              ))}
            </div>
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              min="1"
              className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Custom amount"
            />
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <button
            onClick={handleAmountSubmit}
            className="w-full bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-colors"
          >
            Donate ${amount || "—"}
          </button>
        </>
      ) : clientSecret ? (
        <form onSubmit={handlePaymentSubmit} className="space-y-4">
          <Elements stripe={stripePromise} options={{ clientSecret }}>
            <PaymentElement />
          </Elements>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <button
            type="submit"
            disabled={processing}
            className="w-full bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {processing ? "Processing..." : `Complete $${amount} Donation`}
          </button>
        </form>
      ) : null}
    </div>
  );
}

export default function CrowdfundPage({ params }: { params: { id: string } }) {
  const searchParams = useSearchParams();
  const isDemo = searchParams.get("demo") === "true" || params.id === DEMO_ID;
  const [donated, setDonated] = useState(false);
  const [showDonate, setShowDonate] = useState(false);

  const { data, isLoading, refetch } = useQuery<any>({
    queryKey: ["campaign", params.id],
    queryFn: () => isDemo ? Promise.resolve(DEMO_CROWDFUND) : api.getCampaign(params.id),
  });

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
  };

  if (isLoading) {
    return (
      <main className="min-h-screen bg-slate-50 dark:bg-slate-950 py-16 px-6">
        <div className="max-w-2xl mx-auto space-y-6 animate-pulse">
          <div className="h-9 w-3/4 bg-slate-200 dark:bg-slate-700 rounded-lg" />
          <div className="h-5 w-1/3 bg-slate-200 dark:bg-slate-700 rounded" />
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 p-6 space-y-4">
            <div className="flex justify-between">
              <div className="h-4 w-24 bg-slate-200 dark:bg-slate-700 rounded" />
              <div className="h-4 w-36 bg-slate-200 dark:bg-slate-700 rounded" />
            </div>
            <div className="h-4 w-full bg-slate-100 dark:bg-slate-800 rounded-full" />
          </div>
          <div className="flex gap-3">
            <div className="flex-1 h-12 bg-slate-200 dark:bg-slate-700 rounded-xl" />
            <div className="w-28 h-12 bg-slate-200 dark:bg-slate-700 rounded-xl" />
          </div>
        </div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
        <p className="text-slate-500">Campaign not found.</p>
      </main>
    );
  }

  const percentComplete = data?.raised_usd && data?.goal_usd
    ? Math.round((data.raised_usd / data.goal_usd) * 100)
    : 0;

  return (
    <main className="min-h-screen bg-slate-50 dark:bg-slate-950 py-16 px-6">
      <div className="max-w-2xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
          {/* Title + meta */}
          <div>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 leading-snug">{data.title}</h1>
            {(data.cancer_type || data.target_gene) && (
              <div className="flex flex-wrap gap-2 mt-3">
                {data.cancer_type && (
                  <span className="text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-2.5 py-1 rounded-full">{data.cancer_type}</span>
                )}
                {data.target_gene && (
                  <span className="text-xs font-mono font-bold bg-cyan-50 dark:bg-cyan-950/50 text-cyan-700 dark:text-cyan-400 border border-cyan-100 dark:border-cyan-800 px-2.5 py-1 rounded-full">{data.target_gene}</span>
                )}
              </div>
            )}
          </div>

          {/* Progress */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 p-6">
            <div className="flex items-end justify-between mb-4">
              <div>
                <p className="text-3xl font-extrabold text-slate-900 dark:text-slate-100">
                  ${data.raised_usd.toLocaleString()}
                </p>
                <p className="text-sm text-slate-500 mt-0.5">raised of <span className="font-semibold text-slate-700 dark:text-slate-300">${data.goal_usd.toLocaleString()}</span> goal</p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-extrabold text-cyan-600">{percentComplete}%</p>
                <p className="text-xs text-slate-400">funded</p>
              </div>
            </div>
            <ProgressBar percent={percentComplete} />
            <div className="flex items-center gap-6 mt-4 text-sm text-slate-500">
              {data.backer_count != null && (
                <span className="flex items-center gap-1.5">
                  <Users size={14} className="text-slate-400" />
                  <span className="font-semibold text-slate-700 dark:text-slate-300">{data.backer_count.toLocaleString()}</span> backers
                </span>
              )}
              {data.end_date && (
                <span className="flex items-center gap-1.5">
                  <Target size={14} className="text-slate-400" />
                  Ends {new Date(data.end_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                </span>
              )}
            </div>
          </div>

          {/* Buttons */}
          <div className="flex gap-3">
            <button
              onClick={() => setShowDonate(true)}
              className="flex-1 flex items-center justify-center gap-2 bg-cyan-700 text-white py-3 rounded-xl font-semibold hover:bg-cyan-600 active:bg-cyan-800 transition-colors shadow-sm"
            >
              <Heart size={18} /> Donate
            </button>
            <button
              onClick={handleShare}
              className="flex items-center gap-2 border border-slate-200 dark:border-slate-700 px-5 py-3 rounded-xl font-semibold text-slate-700 dark:text-slate-300 hover:border-slate-400 dark:hover:border-slate-500 transition-colors"
            >
              <Share2 size={16} /> Share
            </button>
          </div>

          {/* Donate panel */}
          {showDonate && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-white dark:bg-slate-900 rounded-2xl border border-cyan-200 dark:border-cyan-800 p-6"
            >
              <h3 className="font-bold text-slate-900 dark:text-slate-100 mb-4">Make a donation</h3>
              <DonateForm
                slug={params.id}
                campaignTitle={data.title}
                onSuccess={() => { setDonated(true); refetch(); setShowDonate(false); }}
              />
            </motion.div>
          )}

          {donated && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="bg-green-50 dark:bg-green-950/50 border border-green-200 dark:border-green-800 rounded-2xl p-4 text-green-800 dark:text-green-300 text-sm text-center"
            >
              Your donation has been received. Thank you for your support!
            </motion.div>
          )}

          {/* Story */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 p-6">
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 mb-3 flex items-center gap-2">
              <Users size={18} className="text-cyan-500" /> Their Story
            </h3>
            <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed whitespace-pre-line">
              {(data as Record<string, unknown>).patient_story as string ?? data.description}
            </p>
          </div>

          <p className="text-xs text-slate-400 text-center">
            Funds are held in escrow by Stripe and released directly to the verified
            pharmaceutical manufacturer when the goal is reached.
          </p>
        </motion.div>
      </div>
    </main>
  );
}
