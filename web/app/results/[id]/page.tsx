"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { saveOrderToLocalStorage } from "@/lib/orders";
import ResultsSkeleton from "@/components/ResultsSkeleton";
import { DEMO_RESULTS, DEMO_REPURPOSING, DEMO_ID } from "@/lib/demo-data";

type MutationRow = {
	gene?: string;
	hgvs?: string;
	classification?: string;
	oncokb_level?: string;
	is_targetable?: boolean;
};

type TrialRow = {
	trial_id?: string;
	title?: string;
	phase?: string;
	status?: string;
	basket_trial?: boolean;
	expanded_access_hint?: boolean;
	trial_url?: string | null;
	drugs?: string[];
};

export default function ResultsPage({ params }: { params: { id: string } }) {
	const router = useRouter();
	const searchParams = useSearchParams();
	const isDemo = searchParams.get("demo") === "true" || params.id === DEMO_ID;
	const [customBusy, setCustomBusy] = useState(false);
	const [customError, setCustomError] = useState<string | null>(null);
	const [nearbyOpen, setNearbyOpen] = useState(false);

	const { data, isLoading, isError, error } = useQuery({
		queryKey: ["results", params.id],
		queryFn: () => isDemo ? Promise.resolve(DEMO_RESULTS as typeof DEMO_RESULTS & Record<string, unknown>) : api.getResults(params.id),
		refetchInterval: (query) => {
			if (isDemo) return false;
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
		queryFn: () => isDemo ? Promise.resolve(DEMO_REPURPOSING) : api.getRepurposing(resultId),
		enabled: Boolean(isComplete && resultId),
	});

	const nearbyQuery = useQuery({
		queryKey: ["nearby-pharmacies"],
		queryFn: () => api.getNearbyPharmacies(),
		enabled: nearbyOpen,
	});

	const trialQuery = useQuery({
		queryKey: ["clinical-trials", resultId],
		queryFn: () => api.getClinicalTrials(resultId),
		enabled: Boolean(isComplete && resultId),
	});

	const generateCustomDrug = async () => {
		if (!resultId) return;
		if (isDemo) {
			router.push(`/custom-drug/${DEMO_ID}?demo=true`);
			return;
		}
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
		return <ResultsSkeleton />;
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
		return <ResultsSkeleton />;
	}

	const mutations = (data.mutations || []) as MutationRow[];
	const candidates = repurposingQuery.data?.candidates || [];
	const trialMatches = (trialQuery.data?.trials || []) as TrialRow[];
	const repurposingFailed = !repurposingQuery.isLoading && candidates.length === 0;
	const hasActionable = Boolean(data.has_targetable_mutation || mutations.some((m) => m.is_targetable));

	const patientSummary = (data as {
		patient_summary?: {
			top_drugs?: Array<{ drug_name?: string; approval_status?: string; patient_note?: string }>;
			explanation?: string;
			what_next?: string[];
		} | null;
	}).patient_summary || null;
	const patientTopDrugs: Array<{ drug_name?: string; approval_status?: string; patient_note?: string }> =
		patientSummary?.top_drugs || [];
	const patientExplanation: string = patientSummary?.explanation || data.plain_language_summary || data.summary || "";
	const patientWhatNext: string[] = patientSummary?.what_next || [];

	const pdfBase = `/api/results/${params.id}`;

	return (
		<main className="min-h-screen py-8 px-4">
			<div className="max-w-5xl mx-auto space-y-6">

				{/* ── Patient Summary ─────────────────────────────────── */}
				<section className="clinical-surface p-6 border-t-4 border-cyan-600">
					<div className="flex items-start justify-between gap-4 flex-wrap">
						<div>
							<h1 className="text-2xl font-bold text-gray-900">Your Results Summary</h1>
							<p className="text-sm text-gray-500 mt-1">
								{data.cancer_type} · Submission {params.id.slice(0, 8)}
							</p>
							<p className="text-sm text-cyan-800 mt-3 font-medium">
								Start here: download your simple letter first, then share the doctor report.
							</p>
						</div>
						{/* PDF download buttons */}
						<div className="flex gap-3 flex-wrap">
							<a
								href={`${pdfBase}/patient-letter.pdf`}
								download
								className="inline-flex items-center gap-2 rounded-xl bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-600 transition-colors shadow"
							>
								⬇ Download Simple Letter (for me)
							</a>
							<a
								href={`${pdfBase}/oncologist-report.pdf`}
								download
								className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 transition-colors"
							>
								Download Full Report for Doctor
							</a>
						</div>
					</div>

					{patientExplanation && (
						<p className="text-gray-700 mt-4 leading-relaxed">{patientExplanation}</p>
					)}

					{patientTopDrugs.length > 0 && (
						<div className="mt-4">
							<h3 className="text-sm font-semibold text-gray-800 mb-2">Potential treatment options for your doctor to review:</h3>
							<ul className="space-y-2">
								{patientTopDrugs.map((d, i) => (
									<li key={i} className="rounded-lg border border-cyan-100 bg-cyan-50 px-4 py-3">
										<p className="font-semibold text-cyan-900">{d.drug_name || "Unknown"}</p>
										<p className="text-xs text-cyan-700">{d.approval_status}</p>
										{d.patient_note && <p className="text-sm text-gray-700 mt-1">{d.patient_note}</p>}
									</li>
								))}
							</ul>
						</div>
					)}

					{patientWhatNext.length > 0 && (
						<div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
							<p className="text-sm font-semibold text-amber-900 mb-1">Recommended next steps:</p>
							<ul className="list-disc list-inside text-sm text-amber-800 space-y-1">
								{patientWhatNext.map((item, i) => <li key={i}>{item}</li>)}
							</ul>
						</div>
					)}

					<div className="mt-4 rounded-xl border border-gray-200 bg-gray-50 p-3">
						<p className="text-sm font-medium text-gray-900">Can we do something for this mutation profile?</p>
						<p className="text-sm text-gray-600 mt-1">
							{hasActionable
								? "Yes. We prioritize Layer 1 on-label FDA, then Layer 2 off-label FDA, then Layer 3 clinical trials. Layer 4 custom design is manual-only."
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
					<h2 className="text-lg font-semibold text-gray-900 mb-3">Layer 1 + Layer 2: FDA Drugs</h2>
					{repurposingQuery.isLoading ? (
						<p className="text-sm text-gray-600">Checking on-label and off-label FDA options...</p>
					) : candidates.length === 0 ? (
						<p className="text-sm text-gray-600">No FDA-aligned options found in Layer 1 or Layer 2.</p>
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

					{repurposingFailed && (
						<div className="mt-6 rounded-xl border border-blue-200 bg-blue-50 p-4">
							<p className="text-sm text-blue-900 font-medium">Layer 3: Clinical trial matching</p>
							{trialQuery.isLoading ? (
								<p className="text-sm text-blue-800 mt-1">Searching ClinicalTrials.gov for mutation-matched and basket trials...</p>
							) : trialMatches.length === 0 ? (
								<p className="text-sm text-blue-800 mt-1">No strong trial match found from live query for this profile.</p>
							) : (
								<ul className="mt-2 space-y-2">
									{trialMatches.slice(0, 5).map((t, i) => (
										<li key={`${t.trial_id || t.title || "trial"}-${i}`} className="rounded-lg border border-blue-100 bg-white px-3 py-2">
											<p className="text-sm font-semibold text-blue-900">{t.trial_id || "Trial"} · {t.phase || "Unknown phase"}</p>
											<p className="text-xs text-blue-800 mt-0.5">{t.title || "Untitled study"}</p>
											<div className="mt-1 flex flex-wrap gap-2">
												{t.basket_trial && <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[11px] font-medium text-indigo-800">Basket trial</span>}
												{t.expanded_access_hint && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800">Expanded access hint</span>}
												{t.trial_url && (
													<a className="text-[11px] font-medium text-blue-700 hover:underline" href={t.trial_url} target="_blank" rel="noreferrer">Open trial</a>
												)}
											</div>
										</li>
									))}
								</ul>
							)}
						</div>
					)}

					{repurposingFailed && data.custom_drug_possible && (
						<div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
							<p className="text-sm text-amber-900 font-medium">Layer 4: Custom drug suggestion (manual only)</p>
							<p className="text-sm text-amber-800 mt-1">
								Only run this when your oncologist wants exploratory non-FDA computational options. The workflow uses
								molecular docking and pathway logic to propose investigational hypotheses, not prescriptions.
							</p>
							<div className="mt-3 flex flex-wrap gap-3">
								<button
									onClick={generateCustomDrug}
									disabled={customBusy}
									className="bg-cyan-700 text-white text-sm px-5 py-2.5 rounded-xl font-bold hover:bg-cyan-600 transition-colors disabled:opacity-60 shadow"
								>
									{customBusy ? "Starting..." : "Generate Custom Drug Brief (Manual) ->"}
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
