"use client";

import Link from "next/link";
import { use, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Download, FileText } from "lucide-react";
import { api } from "@/lib/api";
import { saveOrderToLocalStorage } from "@/lib/orders";
import ResultsSkeleton from "@/components/ResultsSkeleton";
import ImmunoPanel from "@/components/ImmunoPanel";
import SignatureCard from "@/components/SignatureCard";
import CombinationTable from "@/components/CombinationTable";
import SampleQCCard, { type SampleQC } from "@/components/SampleQCCard";
import { DEMO_RESULTS, DEMO_REPURPOSING, DEMO_ID } from "@/lib/demo-data";
import { atlasSans } from "@/lib/atlas-font";
import { focus, ink, line, muted, surface } from "@/components/workspace/parts";

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

const card = `rounded-[12px] border ${line} bg-white p-6 ${surface}`;
const primaryBtn = `inline-flex items-center gap-2 rounded-[8px] bg-[#25202F] px-4 py-2.5 text-[14px] font-medium text-[#F7F5F0] transition-[background-color,transform] duration-150 hover:bg-[#3A3446] active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100 ${focus}`;
const secondaryBtn = `inline-flex items-center gap-2 rounded-[8px] border ${line} bg-white px-4 py-2.5 text-[14px] font-medium ${ink} transition-colors duration-150 hover:bg-[#F6F5F8] ${focus}`;

export default function ResultsPage(props: { params: Promise<{ id: string }> }) {
	const params = use(props.params);
	const router = useRouter();
	const searchParams = useSearchParams();
	const isDemo = searchParams.get("demo") === "true" || params.id === DEMO_ID;
	const [customBusy, setCustomBusy] = useState(false);
	const [customError, setCustomError] = useState<string | null>(null);
	const [nearbyOpen, setNearbyOpen] = useState(false);

	const { data, isLoading, isError, error } = useQuery<any>({
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

	const repurposingQuery = useQuery<any>({
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

	const immunoQuery = useQuery({
		queryKey: ["immunotherapy", resultId],
		queryFn: () => api.getImmunotherapyProfile(resultId),
		enabled: Boolean(isComplete && resultId),
	});

	const signatureQuery = useQuery({
		queryKey: ["signatures", resultId],
		queryFn: () => api.getMutationalSignature(resultId),
		enabled: Boolean(isComplete && resultId),
	});

	const combinationQuery = useQuery({
		queryKey: ["combinations", resultId],
		queryFn: () => api.getCombinationTherapy(resultId),
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
			<main className={`${atlasSans.variable} min-h-screen bg-[#F7F5F0] p-6 font-[family-name:var(--font-atlas)] ${ink}`}>
				<div className={`mx-auto max-w-4xl rounded-[12px] border border-[#D9B8AE] bg-[#FBF1EE] p-6`}>
					<h1 className="text-[20px] font-semibold text-[#7A3326]">Unable to load result</h1>
					<p className="mt-2 text-[14px] text-[#9E4A3A]">
						{(error as Error | undefined)?.message || "Submission not found or access denied."}
					</p>
				</div>
			</main>
		);
	}

	if (!isComplete) {
		return <ResultsSkeleton />;
	}

	const mutations = (data.mutations || []) as MutationRow[];
	const candidates = (repurposingQuery.data?.candidates || []) as any[];
	const trialMatches = (trialQuery.data?.trials || []) as TrialRow[];
	const repurposingFailed = !repurposingQuery.isLoading && candidates.length === 0;
	const hasActionable = Boolean(data.has_targetable_mutation || mutations.some((m) => m.is_targetable));
	// Always rendered. The API always sends this, and an absent verdict must be
	// stated rather than omitted — silence reads as "no problems found".
	const sampleQC = (data.sample_qc || { qc_verdict: "NOT_ASSESSED", assessed: false }) as SampleQC;

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
		<main className={`${atlasSans.variable} min-h-screen bg-[#F7F5F0] py-8 px-4 font-[family-name:var(--font-atlas)] ${ink}`}>
			<div className="mx-auto max-w-5xl space-y-6">

				{/* ── Patient Summary ─────────────────────────────────── */}
				<section className={card}>
					<div className="flex flex-wrap items-start justify-between gap-4">
						<div>
							<h1 className="text-[24px] font-semibold tracking-[-0.02em]">Your results summary</h1>
							<p className={`mt-1 text-[13.5px] ${muted}`}>
								{data.cancer_type} · Submission {params.id.slice(0, 8)}
							</p>
							<p className="mt-3 text-[13.5px] font-medium text-[#523E70]">
								Start here: download your simple letter first, then share the doctor report.
							</p>
						</div>
						{/* PDF download buttons */}
						<div className="flex flex-wrap gap-3">
							<a href={`${pdfBase}/patient-letter.pdf`} download className={primaryBtn}>
								<Download size={16} aria-hidden="true" />
								Download simple letter (for me)
							</a>
							<a href={`${pdfBase}/oncologist-report.pdf`} download className={secondaryBtn}>
								<FileText size={16} aria-hidden="true" />
								Download full report for doctor
							</a>
						</div>
					</div>

					{patientExplanation && <p className={`mt-4 text-[14.5px] leading-[22px] ${ink}`}>{patientExplanation}</p>}

					{patientTopDrugs.length > 0 && (
						<div className="mt-4">
							<h3 className={`mb-2 text-[13px] font-semibold ${ink}`}>Potential treatment options for your doctor to review:</h3>
							<ul className="space-y-2">
								{patientTopDrugs.map((d, i) => (
									<li key={i} className={`rounded-[10px] border ${line} bg-[#FAF9F7] px-4 py-3`}>
										<p className={`font-semibold ${ink}`}>{d.drug_name || "Unknown"}</p>
										<p className="text-[12.5px] text-[#69518C]">{d.approval_status}</p>
										{d.patient_note && <p className={`mt-1 text-[13.5px] ${ink}`}>{d.patient_note}</p>}
									</li>
								))}
							</ul>
						</div>
					)}

					{patientWhatNext.length > 0 && (
						<div className="mt-4 rounded-[10px] border border-[#E6D3AE] bg-[#FBF4E6] p-4">
							<p className="mb-1 text-[13px] font-semibold text-[#7A4F14]">Recommended next steps:</p>
							<ul className="list-inside list-disc space-y-1 text-[13.5px] text-[#7A4F14]">
								{patientWhatNext.map((item, i) => <li key={i}>{item}</li>)}
							</ul>
						</div>
					)}

					<div className={`mt-4 rounded-[10px] border ${line} bg-[#FAF9F7] p-3`}>
						<p className={`text-[13.5px] font-medium ${ink}`}>Can we do something for this mutation profile?</p>
						<p className={`mt-1 text-[13.5px] leading-[20px] ${muted}`}>
							{hasActionable
								? "Yes. We prioritize Layer 1 on-label FDA, then Layer 2 off-label FDA, then Layer 3 clinical trials. Layer 4 custom design is manual-only."
								: "No actionable mutation was detected in the current profile. Repurposed or custom options are unlikely from this dataset."}
						</p>
					</div>
				</section>

				{/* Sample quality qualifies every finding below it, so it comes first. */}
				<SampleQCCard qc={sampleQC} />

				<section className={card}>
					<h2 className="mb-3 text-[17px] font-semibold">Mutations</h2>
					{mutations.length === 0 ? (
						<p className={`text-[13.5px] ${muted}`}>No mutation rows available.</p>
					) : (
						<div className="overflow-x-auto">
							<table className="w-full text-[13.5px]">
								<thead>
									<tr className={`border-b ${line} text-left ${muted}`}>
										<th className="py-2 pr-3 font-medium">Gene</th>
										<th className="py-2 pr-3 font-medium">HGVS</th>
										<th className="py-2 pr-3 font-medium">Class</th>
										<th className="py-2 pr-3 font-medium">OncoKB</th>
										<th className="py-2 pr-3 font-medium">Targetable</th>
									</tr>
								</thead>
								<tbody>
									{mutations.map((m, i) => (
									<tr key={`${m.gene || "gene"}-${i}`} className={`border-b ${line} last:border-0 ${i % 2 === 1 ? "bg-[#FAF9F7]" : ""}`}>
											<td className={`py-2 pr-3 font-medium ${ink}`}>{m.gene || "-"}</td>
											<td className={`py-2 pr-3 ${ink}`}>{m.hgvs || "-"}</td>
											<td className={`py-2 pr-3 ${ink}`}>{m.classification || "-"}</td>
											<td className={`py-2 pr-3 ${ink}`}>{m.oncokb_level || "-"}</td>
											<td className={`py-2 pr-3 ${ink}`}>{m.is_targetable ? "Yes" : "No"}</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}
				</section>

				<section className={card}>
					<h2 className="mb-3 text-[17px] font-semibold">Layer 1 + Layer 2: FDA drugs</h2>
					{repurposingQuery.isLoading ? (
						<p className={`text-[13.5px] ${muted}`}>Checking on-label and off-label FDA options...</p>
					) : candidates.length === 0 ? (
						<p className={`text-[13.5px] ${muted}`}>No FDA-aligned options found in Layer 1 or Layer 2.</p>
					) : (
						<ul className="space-y-2">
						{candidates.slice(0, 5).map((c, i) => (
							<li key={`${c.chembl_id || c.drug_name}-${c.rank_score || 0}`} className={`flex items-start gap-3 rounded-[10px] border ${line} p-3 transition-colors duration-150 hover:border-[#69518C]/50`}>
								<span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#69518C] text-[12px] font-bold text-white">{i + 1}</span>
								<div className="flex-1">
									<p className={`font-medium ${ink}`}>{c.drug_name}</p>
									<p className={`text-[12px] ${muted}`}>{c.chembl_id || "Unknown ID"} · {c.approval_status || "Unknown approval"} · Rank {(c.rank_score ?? 0).toFixed(2)}</p>
									<p className={`mt-1 text-[12px] ${muted}`}>{c.mechanism || "Mechanism not provided"}</p>
									<div className="mt-2 flex flex-wrap gap-2">
										{(c.evidence_sources?.length ? c.evidence_sources : ["Unspecified"]).map((source: string) => (
											<span
												key={`${c.chembl_id || c.drug_name}-${source}`}
												className="rounded-full border border-[#D9CFEA] bg-[#EEE8F5] px-2 py-0.5 text-[11px] font-medium text-[#523E70]"
											>
												{source}
											</span>
										))}
									</div>
									</div>
								</li>
							))}
						</ul>
					)}

					{candidates.length > 0 && resultId && (
						<div className="mt-4 flex flex-wrap gap-3">
							<Link className={`text-[13.5px] font-medium text-[#69518C] underline-offset-4 hover:underline ${focus}`} href={`/repurposing/${resultId}`}>
								View full repurposing list
							</Link>
						</div>
					)}

					{repurposingFailed && (
						<div className="mt-6 rounded-[10px] border border-[#C3CFE0] bg-[#F2F5FA] p-4">
							<p className="text-[13.5px] font-medium text-[#2E4A6B]">Layer 3: Clinical trial matching</p>
							{trialQuery.isLoading ? (
								<p className="mt-1 text-[13px] text-[#4A638A]">Searching ClinicalTrials.gov for mutation-matched and basket trials...</p>
							) : trialMatches.length === 0 ? (
								<p className="mt-1 text-[13px] text-[#4A638A]">No strong trial match found from live query for this profile.</p>
							) : (
								<ul className="mt-2 space-y-2">
									{trialMatches.slice(0, 5).map((t, i) => (
										<li key={`${t.trial_id || t.title || "trial"}-${i}`} className={`rounded-[8px] border ${line} bg-white px-3 py-2`}>
											<p className="text-[13.5px] font-semibold text-[#2E4A6B]">{t.trial_id || "Trial"} · {t.phase || "Unknown phase"}</p>
											<p className="mt-0.5 text-[12.5px] text-[#4A638A]">{t.title || "Untitled study"}</p>
											<div className="mt-1 flex flex-wrap gap-2">
												{t.basket_trial && <span className="rounded-full bg-[#E6E1F5] px-2 py-0.5 text-[11px] font-medium text-[#44357A]">Basket trial</span>}
												{t.expanded_access_hint && <span className="rounded-full bg-[#F5EBDB] px-2 py-0.5 text-[11px] font-medium text-[#7A4F14]">Expanded access hint</span>}
												{t.trial_url && (
													<a className="text-[11px] font-medium text-[#2E4A6B] underline-offset-4 hover:underline" href={t.trial_url} target="_blank" rel="noreferrer">Open trial</a>
												)}
											</div>
										</li>
									))}
								</ul>
							)}
						</div>
					)}

					{repurposingFailed && data.custom_drug_possible && (
						<div className="mt-4 rounded-[10px] border border-[#E6D3AE] bg-[#FBF4E6] p-4">
							<p className="text-[13.5px] font-medium text-[#7A4F14]">Layer 4: Custom drug suggestion (manual only)</p>
							<p className="mt-1 text-[13px] text-[#7A4F14]">
								Only run this when your oncologist wants exploratory non-FDA computational options. The workflow uses
								molecular docking and pathway logic to propose investigational hypotheses, not prescriptions.
							</p>
							<div className="mt-3 flex flex-wrap gap-3">
								<button onClick={generateCustomDrug} disabled={customBusy} className={primaryBtn}>
									{customBusy ? "Starting..." : "Generate custom drug brief (manual) →"}
								</button>
							</div>
							{customError && <p className="mt-2 text-[13.5px] text-[#9E4A3A]">{customError}</p>}
						</div>
					)}

					<div className="mt-5">
						<button onClick={() => setNearbyOpen((v) => !v)} className={`text-[13.5px] font-medium text-[#69518C] underline-offset-4 hover:underline ${focus}`}>
							Contact nearby pharmacy
						</button>
						{nearbyOpen && (
							<div className="mt-2 space-y-2">
								{nearbyQuery.isLoading && <p className={`text-[13.5px] ${muted}`}>Loading nearby pharmacies...</p>}
								{nearbyQuery.data?.pharmacies?.map((p) => (
									<div key={p.name} className={`rounded-[8px] border ${line} p-3 text-[13.5px]`}>
										<p className={`font-medium ${ink}`}>{p.name}</p>
										<p className={muted}>{p.address}</p>
										<p className={muted}>{p.phone} · {p.distance_km} km away</p>
									</div>
								))}
							</div>
						)}
					</div>
				</section>

				{/* ── Immunotherapy Biomarkers ─────────────────────────── */}
				{immunoQuery.data?.available && immunoQuery.data?.profile && (
					<ImmunoPanel profile={immunoQuery.data.profile} />
				)}

				{/* ── Mutational Signature ─────────────────────────────── */}
				{signatureQuery.data?.available && signatureQuery.data?.signature && (
					<SignatureCard signature={signatureQuery.data.signature} />
				)}

				{/* ── Combination Therapy ──────────────────────────────── */}
				{combinationQuery.data?.combinations && combinationQuery.data.combinations.length > 0 && (
					<CombinationTable combinations={combinationQuery.data.combinations} />
				)}

			</div>
		</main>
	);
}
