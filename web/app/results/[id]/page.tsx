"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { saveOrderToLocalStorage } from "@/lib/orders";

type MutationRow = {
	gene?: string;
	hgvs?: string;
	classification?: string;
	oncokb_level?: string;
	is_targetable?: boolean;
};

export default function ResultsPage({ params }: { params: { id: string } }) {
	const router = useRouter();
	const [customBusy, setCustomBusy] = useState(false);
	const [customError, setCustomError] = useState<string | null>(null);
	const [nearbyOpen, setNearbyOpen] = useState(false);

	const { data, isLoading, isError, error } = useQuery({
		queryKey: ["results", params.id],
		queryFn: () => api.getResults(params.id),
		refetchInterval: (query) => {
			const status = (query.state.data as { status?: string } | undefined)?.status;
			const done = ["complete", "completed", "failed"].includes((status || "").toLowerCase());
			return done ? false : 3000;
		},
	});

	const normalizedStatus = (data?.status || "").toLowerCase();
	const isComplete = ["complete", "completed", "done"].includes(normalizedStatus) || !data?.status;
	const resultId = data?.result_id || data?.submission_id || params.id;

	const repurposingQuery = useQuery({
		queryKey: ["repurposing", resultId],
		queryFn: () => api.getRepurposing(resultId),
		enabled: Boolean(isComplete && resultId),
	});

	const nearbyQuery = useQuery({
		queryKey: ["nearby-pharmacies"],
		queryFn: () => api.getNearbyPharmacies(),
		enabled: nearbyOpen,
	});

	const generateCustomDrug = async () => {
		if (!resultId) return;
		setCustomBusy(true);
		setCustomError(null);
		try {
			const created = await api.createDrugRequestFromResult(resultId);
			saveOrderToLocalStorage(created.drug_request_id, {
				target_gene: created.target_gene,
				cancer_type: created.cancer_type,
				result_id: resultId,
			});
			router.push(`/custom-drug/${created.drug_request_id}`);
		} catch (e: unknown) {
			setCustomError(e instanceof Error ? e.message : "Could not generate a custom-drug request.");
			setCustomBusy(false);
		}
	};

	if (isLoading) {
		return (
			<main className="min-h-screen p-6">
				<div className="max-w-4xl mx-auto clinical-surface p-6">
					<h1 className="text-xl font-[var(--font-manrope)] font-bold text-slate-900">Loading analysis...</h1>
					<p className="text-sm text-slate-500 mt-2">Fetching your latest result.</p>
				</div>
			</main>
		);
	}

	if (isError || !data) {
		return (
			<main className="min-h-screen p-6">
				<div className="max-w-4xl mx-auto clinical-surface border-red-200 p-6">
					<h1 className="text-xl font-semibold text-red-700">Unable to load result</h1>
					<p className="text-sm text-slate-600 mt-2">
						{(error as Error | undefined)?.message || "Submission not found or access denied."}
					</p>
				</div>
			</main>
		);
	}

	const stage = isComplete ? 3 : normalizedStatus === "analyzing" ? 2 : 1;
	const stages = [
		{ label: "Mutation parsing", active: stage >= 1 },
		{ label: "Actionability check", active: stage >= 2 },
		{ label: "Repurposing rank", active: stage >= 3 },
	];

	if (!isComplete) {
		return (
			<main className="min-h-screen p-6">
				<div className="max-w-4xl mx-auto clinical-surface border-cyan-200 p-6 space-y-4">
					<h1 className="text-xl font-semibold text-gray-900">Analysis in progress</h1>
					<p className="text-sm text-slate-600">Tracking ID: {params.id}</p>
					<div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
						{stages.map((s) => (
							<div key={s.label} className={`rounded-xl border p-3 ${s.active ? "border-cyan-300 bg-cyan-50" : "border-slate-200 bg-slate-50"}`}>
								<div className="flex items-center gap-2">
									<span className={`h-3 w-3 rounded-full ${s.active ? "bg-cyan-700" : "bg-slate-300"}`} />
									<p className="text-sm font-medium text-slate-800">{s.label}</p>
								</div>
							</div>
						))}
					</div>
					<p className="text-sm text-slate-600">
						Current status: <span className="font-medium">{data.status || "queued"}</span>
					</p>
					{data.message && <p className="mt-2 text-sm text-slate-600">{data.message}</p>}
					<p className="text-xs text-slate-500">This page auto-refreshes every few seconds until repurposing is ready.</p>
				</div>
			</main>
		);
	}

	const mutations = (data.mutations || []) as MutationRow[];
	const candidates = repurposingQuery.data?.candidates || [];
	const repurposingFailed = !repurposingQuery.isLoading && candidates.length === 0;
	const hasActionable = Boolean(data.has_targetable_mutation || mutations.some((m) => m.is_targetable));

	return (
		<main className="min-h-screen py-8 px-4">
			<div className="max-w-5xl mx-auto space-y-6">
				<section className="clinical-surface p-6">
					<h1 className="text-2xl font-bold text-gray-900">Result Summary</h1>
					<p className="text-sm text-gray-600 mt-2">
						{data.cancer_type} | Submission {params.id.slice(0, 8)}
					</p>
					<p className="text-gray-700 mt-4">
						{data.plain_language_summary || data.summary || "No summary is available yet."}
					</p>
					<div className="mt-4 rounded-xl border border-gray-200 bg-gray-50 p-3">
						<p className="text-sm font-medium text-gray-900">Can we do something for this mutation profile?</p>
						<p className="text-sm text-gray-600 mt-1">
							{hasActionable
								? "Yes. We found actionable molecular signal. Repurposed options are shown below and custom design is available if needed."
								: "No actionable mutation was detected in the current profile. Repurposed or custom options are unlikely from this dataset."}
						</p>
					</div>
				</section>

				<section className="clinical-surface p-6">
					<h2 className="text-lg font-semibold text-gray-900 mb-3">Mutations</h2>
					{mutations.length === 0 ? (
						<p className="text-sm text-gray-600">No mutation rows available.</p>
					) : (
						<div className="overflow-x-auto">
							<table className="w-full text-sm">
								<thead>
									<tr className="text-left text-gray-600 border-b">
										<th className="py-2 pr-3">Gene</th>
										<th className="py-2 pr-3">HGVS</th>
										<th className="py-2 pr-3">Class</th>
										<th className="py-2 pr-3">OncoKB</th>
										<th className="py-2 pr-3">Targetable</th>
									</tr>
								</thead>
								<tbody>
									{mutations.map((m, i) => (
										<tr key={`${m.gene || "gene"}-${i}`} className="border-b last:border-0">
											<td className="py-2 pr-3 font-medium text-gray-900">{m.gene || "-"}</td>
											<td className="py-2 pr-3 text-gray-700">{m.hgvs || "-"}</td>
											<td className="py-2 pr-3 text-gray-700">{m.classification || "-"}</td>
											<td className="py-2 pr-3 text-gray-700">{m.oncokb_level || "-"}</td>
											<td className="py-2 pr-3 text-gray-700">{m.is_targetable ? "Yes" : "No"}</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}
				</section>

				<section className="clinical-surface p-6">
					<h2 className="text-lg font-semibold text-gray-900 mb-3">Drug Repurposing</h2>
					{repurposingQuery.isLoading ? (
						<p className="text-sm text-gray-600">Auto-running repurposing search...</p>
					) : candidates.length === 0 ? (
						<p className="text-sm text-gray-600">No repurposed candidates found for this result.</p>
					) : (
						<ul className="space-y-2">
							{candidates.slice(0, 5).map((c) => (
								<li key={`${c.chembl_id || c.drug_name}-${c.rank_score || 0}`} className="border rounded-lg p-3">
									<p className="font-medium text-gray-900">{c.drug_name}</p>
									<p className="text-xs text-gray-600">{c.chembl_id || "Unknown ID"} | {c.approval_status || "Unknown approval"} | Rank {(c.rank_score ?? 0).toFixed(2)}</p>
									<p className="text-xs text-gray-600 mt-1">{c.mechanism || "Mechanism not provided"}</p>
									<div className="mt-2 flex flex-wrap gap-2">
										{(c.evidence_sources?.length ? c.evidence_sources : ["Unspecified"]).map((source) => (
											<span
												key={`${c.chembl_id || c.drug_name}-${source}`}
												className="rounded-full border border-blue-100 bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700"
											>
												{source}
											</span>
										))}
									</div>
								</li>
							))}
						</ul>
					)}

					{candidates.length > 0 && resultId && (
						<div className="mt-4 flex gap-3 flex-wrap">
							<Link className="text-blue-700 text-sm hover:underline" href={`/repurposing/${resultId}`}>
								View full repurposing list
							</Link>
						</div>
					)}

					{repurposingFailed && data.custom_drug_possible && (
						<div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
							<p className="text-sm text-amber-900 font-medium">No repurposed drug found for this mutation profile.</p>
							<p className="text-sm text-amber-800 mt-1">
								We can run the full AI custom-drug compute pipeline now — mutation-aware AlphaFold structure generation,
								DiffDock binding simulation, and de novo candidate ranking. The job starts immediately and this page
								updates as soon as computation completes.
							</p>
							<div className="mt-3 flex flex-wrap gap-3">
								<button
									onClick={generateCustomDrug}
									disabled={customBusy}
									className="bg-cyan-700 text-white text-sm px-5 py-2.5 rounded-xl font-bold hover:bg-cyan-600 transition-colors disabled:opacity-60 shadow"
								>
									{customBusy ? "Starting…" : "Generate Custom Drug Brief →"}
								</button>
							</div>
							{customError && <p className="mt-2 text-sm text-red-600">{customError}</p>}
						</div>
					)}

					<div className="mt-5">
						<button
							onClick={() => setNearbyOpen((v) => !v)}
							className="text-sm text-cyan-700 hover:underline"
						>
							Contact nearby pharmacy
						</button>
						{nearbyOpen && (
							<div className="mt-2 space-y-2">
								{nearbyQuery.isLoading && <p className="text-sm text-slate-600">Loading nearby pharmacies...</p>}
								{nearbyQuery.data?.pharmacies?.map((p) => (
									<div key={p.name} className="border rounded-lg p-3 text-sm">
										<p className="font-medium text-slate-900">{p.name}</p>
										<p className="text-slate-600">{p.address}</p>
										<p className="text-slate-600">{p.phone} | {p.distance_km} km away</p>
									</div>
								))}
							</div>
						)}
					</div>
				</section>
			</div>
		</main>
	);
}
