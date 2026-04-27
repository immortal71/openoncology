"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getOrdersFromLocalStorage } from "@/lib/orders";

const LS_KEY = "oo_drug_request_ids";

type LocalOrder = {
  drug_request_id: string;
  target_gene: string;
  cancer_type: string;
  result_id: string;
  saved_at: string;
  status?: string;
};

function StatusBadge({ status }: { status?: string }) {
  const map: Record<string, string> = {
    complete: "bg-green-100 text-green-700",
    running: "bg-blue-100 text-blue-700",
    queued: "bg-amber-100 text-amber-700",
    failed: "bg-red-100 text-red-700",
  };
  const cls = map[status ?? ""] ?? "bg-gray-100 text-gray-500";
  return <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${cls}`}>{status ?? "unknown"}</span>;
}

export default function OrdersPage() {
  const [localOrders, setLocalOrders] = useState<LocalOrder[]>([]);

  useEffect(() => {
    const raw = getOrdersFromLocalStorage();
    setLocalOrders(
      Object.entries(raw).map(([id, meta]) => ({ drug_request_id: id, ...meta }))
    );
  }, []);

  const serverQuery = useQuery({
    queryKey: ["drug-requests-list"],
    queryFn: () => api.listDrugRequests(),
    refetchInterval: 10_000,
  });

  // Merge: prefer server status over local
  const serverMap = Object.fromEntries(
    (serverQuery.data?.requests ?? []).map((r) => [r.drug_request_id, r])
  );

  const merged: LocalOrder[] = localOrders.map((lo) => ({
    ...lo,
    status: serverMap[lo.drug_request_id]?.status ?? lo.status,
  }));

  // Also show server-side requests not yet in localStorage
  for (const sr of serverQuery.data?.requests ?? []) {
    if (!merged.find((m) => m.drug_request_id === sr.drug_request_id)) {
      merged.push({
        drug_request_id: sr.drug_request_id,
        target_gene: sr.target_gene,
        cancer_type: sr.cancer_type,
        result_id: sr.result_id,
        saved_at: "",
        status: sr.status,
      });
    }
  }

  return (
    <main className="min-h-screen py-10 px-4">
      <div className="max-w-4xl mx-auto clinical-surface p-5 md:p-7">
        <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-[var(--font-manrope)] font-extrabold text-slate-900">My Custom Drug Orders</h1>
            <p className="text-sm text-slate-500 mt-1">
              Jobs run in the background. Come back anytime — results are saved here automatically.
            </p>
          </div>
          <Link href="/submit" className="bg-cyan-700 hover:bg-cyan-600 text-white text-sm font-semibold px-4 py-2 rounded-xl transition-colors shadow">
            + Submit New Sample
          </Link>
        </div>

        {merged.length === 0 ? (
          <div className="bg-slate-50 rounded-2xl border border-dashed border-slate-300 p-10 text-center">
            <p className="text-slate-600 text-sm">No custom drug orders yet.</p>
            <p className="text-slate-400 text-xs mt-1">
              Submit a genomic sample and generate a custom drug brief from the results page.
            </p>
            <Link href="/submit" className="mt-4 inline-block text-sm text-cyan-700 hover:underline">Submit a sample -&gt;</Link>
          </div>
        ) : (
          <div className="space-y-4">
            {merged.sort((a, b) => (b.saved_at > a.saved_at ? 1 : -1)).map((order) => (
              <Link
                key={order.drug_request_id}
                href={`/custom-drug/${order.drug_request_id}`}
                className="block bg-white rounded-2xl border border-slate-200 p-5 hover:border-cyan-300 hover:shadow-sm transition-all"
              >
                <div className="flex items-start justify-between flex-wrap gap-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <p className="font-bold text-slate-900 text-base">{order.target_gene} - {order.cancer_type}</p>
                      <StatusBadge status={order.status} />
                    </div>
                    <p className="text-xs text-slate-400">Request ID: {order.drug_request_id}</p>
                    {order.saved_at && (
                      <p className="text-xs text-slate-400">Submitted: {new Date(order.saved_at).toLocaleString()}</p>
                    )}
                  </div>
                  <span className="text-cyan-700 text-sm font-semibold">View Brief -&gt;</span>
                </div>
              </Link>
            ))}
          </div>
        )}

        <p className="text-xs text-slate-400 mt-8 text-center">
          Orders are tracked in your browser. In production, orders are linked to your account and accessible from any device.
        </p>
      </div>
    </main>
  );
}
