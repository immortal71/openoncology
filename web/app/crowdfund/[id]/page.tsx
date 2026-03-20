"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Heart, Users, Target, Share2, CheckCircle } from "lucide-react";
import { loadStripe } from "@stripe/stripe-js";
import { Elements, PaymentElement, useStripe, useElements } from "@stripe/react-stripe-js";
import { api } from "@/lib/api";

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ?? "");

function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="w-full bg-gray-100 rounded-full h-3">
      <motion.div
        className="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full"
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(percent, 100)}%` }}
        transition={{ duration: 1, ease: "easeOut" }}
      />
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
      const token = sessionStorage.getItem("kc_token");
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
  const [donated, setDonated] = useState(false);
  const [showDonate, setShowDonate] = useState(false);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["campaign", params.id],
    queryFn: () => api.getCampaign(params.id),
  });

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
  };

  if (isLoading) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
      </main>
    );
  }

  if (!data) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Campaign not found.</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 py-16 px-6">
      <div className="max-w-2xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
          {/* Title */}
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{data.title}</h1>
          </div>

          {/* Progress */}
          <div className="bg-white rounded-2xl border border-gray-100 p-6">
            <div className="flex justify-between text-sm mb-3">
              <span className="text-gray-500">Raised</span>
              <span className="font-bold text-gray-900">
                ${data.raised_usd.toLocaleString()} of ${data.goal_usd.toLocaleString()}
              </span>
            </div>
            <ProgressBar percent={data.percent_complete} />
            <div className="flex items-center gap-4 mt-3 text-sm text-gray-500">
              <span className="font-semibold text-blue-600">{data.percent_complete}% funded</span>
            </div>
          </div>

          {/* Buttons */}
          <div className="flex gap-3">
            <button
              onClick={() => setShowDonate(true)}
              className="flex-1 flex items-center justify-center gap-2 bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-colors"
            >
              <Heart size={18} /> Donate
            </button>
            <button
              onClick={handleShare}
              className="flex items-center gap-2 border border-gray-200 px-5 py-3 rounded-xl font-semibold text-gray-700 hover:border-gray-400 transition-colors"
            >
              <Share2 size={16} /> Share
            </button>
          </div>

          {/* Donate panel */}
          {showDonate && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-white rounded-2xl border border-blue-200 p-6"
            >
              <h3 className="font-bold text-gray-900 mb-4">Make a donation</h3>
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
              className="bg-green-50 border border-green-200 rounded-2xl p-4 text-green-800 text-sm text-center"
            >
              Your donation has been received. Thank you for your support!
            </motion.div>
          )}

          {/* Story */}
          <div className="bg-white rounded-2xl border border-gray-100 p-6">
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Users size={18} className="text-blue-500" /> Their Story
            </h3>
            <p className="text-gray-600 text-sm leading-relaxed whitespace-pre-line">
              {data.patient_story}
            </p>
          </div>

          <p className="text-xs text-gray-400 text-center">
            Funds are held in escrow by Stripe and released directly to the verified
            pharmaceutical manufacturer when the goal is reached.
          </p>
        </motion.div>
      </div>
    </main>
  );
}
