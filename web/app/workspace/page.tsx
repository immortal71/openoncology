"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { DEMO_ID, DEMO_RESULTS, DEMO_REPURPOSING } from "@/lib/demo-data";
import PipelineStageCard from "@/components/workspace/PipelineStageCard";
import CollapsibleBlock from "@/components/workspace/CollapsibleBlock";
import { VariantCallOutput, RepurposingOutput, CustomBriefOutput, type MutationRow } from "@/components/workspace/StageOutputs";
import RankBarChart from "@/components/workspace/RankBarChart";
import UploadSection from "@/components/workspace/UploadSection";
import DrugResultsSection from "@/components/workspace/DrugResultsSection";
import WorkspaceSidebar, { type WorkspaceSection } from "@/components/workspace/WorkspaceSidebar";
import { PIPELINE_STAGES, toDrugCandidate, type RealRepurposingCandidate } from "@/lib/pipeline-stages";

const INK = "#16181D";
const MUTED = "#8A8D86";
const BODY = "#5B5E64";
const BORDER = "#E4E2DB";
const BG = "#FAFAF8";
const SURFACE = "#FFFFFF";

function ReportSection({ submissionId, isDemo }: { submissionId: string; isDemo: boolean }) {
  const [state, setState] = useState<"idle" | "downloading" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function handleDownload() {
    if (isDemo) {
      setState("error");
      setErrorMsg("Demo case has no real PDF to download — submit a real sample first.");
      return;
    }
    setState("downloading");
    setErrorMsg("");
    try {
      const blob = await api.getOncologistReportPdf(submissionId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${submissionId}-oncologist-report.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      setState("idle");
    } catch (err) {
      setState("error");
      setErrorMsg(err instanceof Error ? err.message : "Download failed.");
    }
  }

  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-widest mb-1" style={{ color: MUTED }}>Report</p>
      <h1 className="text-xl font-semibold mb-4" style={{ color: INK }}>Structured clinical report</h1>
      <div className="border p-5" style={{ borderColor: BORDER, backgroundColor: SURFACE }}>
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold" style={{ color: INK }}>Oncologist report — PDF</p>
            <p className="font-mono text-[10px] mt-1" style={{ color: MUTED }}>
              GET /api/results/{submissionId}/oncologist-report.pdf
            </p>
          </div>
          <button
            onClick={handleDownload}
            disabled={state === "downloading"}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold border shrink-0 disabled:opacity-50"
            style={{ borderColor: BORDER, color: INK, backgroundColor: SURFACE }}
          >
            {state === "downloading" ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
            {state === "downloading" ? "Downloading…" : "Download"}
          </button>
        </div>
        {state === "error" && (
          <p className="text-xs mt-3" style={{ color: "#B3372C" }}>{errorMsg}</p>
        )}
      </div>
    </div>
  );
}

function WorkspaceInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [section, setSection] = useState<WorkspaceSection>("pipeline");

  const idParam = searchParams.get("result_id");
  const isDemo = searchParams.get("demo") === "true" || idParam === DEMO_ID || !idParam;
  const submissionId = idParam || DEMO_ID;

  // ── Stage 1-3: submission status / genomic pipeline / AI analysis ──────
  // api.getResults() is the same dual-purpose status+results endpoint the
  // real results page polls (app/results/[id]/page.tsx) — there is no
  // separate lightweight /status endpoint in this backend.
  const resultsQuery = useQuery<any>({
    queryKey: ["workspace-results", submissionId],
    queryFn: () => (isDemo ? Promise.resolve(DEMO_RESULTS) : api.getResults(submissionId)),
    enabled: Boolean(submissionId),
    refetchInterval: (query) => {
      if (isDemo) return false;
      const status = (query.state.data as { status?: string } | undefined)?.status;
      const done = ["complete", "completed", "failed"].includes((status || "").toLowerCase());
      return done ? false : 3000;
    },
  });

  const normalizedStatus = (resultsQuery.data?.status || "").toLowerCase();
  const isComplete = ["complete", "completed", "done"].includes(normalizedStatus) || (!resultsQuery.data?.status && !!resultsQuery.data);
  const resultId: string | undefined = resultsQuery.data?.result_id || resultsQuery.data?.submission_id || submissionId;
  const targetGene: string | null = resultsQuery.data?.target_gene ?? null;
  const mutations: MutationRow[] = resultsQuery.data?.mutations ?? [];

  // ── Stage 4: ranked repurposing candidates ──────────────────────────────
  const repurposingQuery = useQuery<any>({
    queryKey: ["workspace-repurposing", resultId],
    queryFn: () => (isDemo ? Promise.resolve(DEMO_REPURPOSING) : api.getRepurposing(resultId as string)),
    enabled: Boolean(isComplete && resultId),
  });

  const candidates: RealRepurposingCandidate[] = repurposingQuery.data?.candidates ?? [];

  // ── Stage 5: custom discovery brief — only fetched once the user opens
  // that stage, since it's conditional/expensive and not auto-triggered. ──
  const [briefRequested, setBriefRequested] = useState(false);
  const briefQuery = useQuery<any>({
    queryKey: ["workspace-brief", resultId],
    queryFn: () => api.getDiscoveryBrief(resultId as string),
    enabled: Boolean(briefRequested && resultId && !isDemo),
  });

  function pipelineStatusFor(index: number) {
    // Stage 0: submission — has data once resultsQuery has resolved at all.
    if (index === 0) {
      if (resultsQuery.isLoading) return "running" as const;
      if (resultsQuery.isError) return "locked" as const;
      return resultsQuery.data ? ("success" as const) : ("ready" as const);
    }
    // Stage 1: genomic pipeline — "done" once status has moved past queued.
    if (index === 1) {
      if (!resultsQuery.data) return "locked" as const;
      const s = normalizedStatus;
      if (["queued"].includes(s)) return "ready" as const;
      return "success" as const;
    }
    // Stage 2: AI analysis — done once isComplete.
    if (index === 2) {
      if (!resultsQuery.data) return "locked" as const;
      if (!isComplete) return "running" as const;
      return "success" as const;
    }
    // Stage 3: repurposing candidates.
    if (index === 3) {
      if (!isComplete) return "locked" as const;
      if (repurposingQuery.isLoading) return "running" as const;
      if (repurposingQuery.isError) return "ready" as const;
      return repurposingQuery.data ? ("success" as const) : ("ready" as const);
    }
    // Stages 4-6: conditional, unlock once repurposing has resolved.
    if (!isComplete || (!repurposingQuery.data && !repurposingQuery.isError)) return "locked" as const;
    if (index === 4) {
      if (briefQuery.isLoading) return "running" as const;
      if (briefQuery.data) return "success" as const;
      return "ready" as const;
    }
    return "ready" as const;
  }

  return (
    <main className="min-h-[calc(100vh-4rem)] font-[var(--font-inter)]" style={{ backgroundColor: BG, color: INK }}>
      <div className="mx-auto max-w-[1200px] px-4 sm:px-6 py-8">
        <Link href="/" className="inline-flex items-center gap-2 text-xs mb-4 transition-colors" style={{ color: MUTED }}>
          <ArrowLeft size={13} /> Back home
        </Link>

        {isDemo && (
          <div
            className="border px-3 py-2 mb-4 text-xs flex items-center gap-2"
            style={{ borderColor: "#D9C08A", backgroundColor: "#FAF6EA", color: "#6B4A1E" }}
          >
            Demo mode — showing the KRAS G12C demo case. Submit a real sample or add
            <code className="font-mono mx-1">?result_id=&lt;your submission id&gt;</code>
            to the URL to query the live backend.
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-6 items-start">
          <WorkspaceSidebar active={section} onSelect={setSection} />

          <div className="flex-1 min-w-0 w-full">
            {section === "upload" && (
              <div>
                <p className="font-mono text-[10px] uppercase tracking-widest mb-1" style={{ color: MUTED }}>Upload</p>
                <h1 className="text-xl font-semibold mb-4" style={{ color: INK }}>Submit a case</h1>
                <UploadSection
                  onSubmitted={(newSubmissionId) => {
                    router.push(`/workspace?result_id=${newSubmissionId}`);
                    setSection("pipeline");
                  }}
                />
              </div>
            )}

            {section === "pipeline" && (
              <div>
                <p className="font-mono text-[10px] uppercase tracking-widest mb-1" style={{ color: MUTED }}>Pipeline</p>
                <h1 className="text-xl font-semibold mb-1" style={{ color: INK }}>Sequential clinical workflow</h1>
                <p className="text-sm mb-6" style={{ color: BODY }}>
                  {isDemo
                    ? "Demo case — no live polling."
                    : `Polling GET /api/results/${submissionId} every 3s until complete.`}
                </p>

                <div className="flex flex-col gap-4">
                  {PIPELINE_STAGES.map((stage, i) => {
                    const status = pipelineStatusFor(i);
                    return (
                      <PipelineStageCard
                        key={stage.id}
                        index={i + 1}
                        stage={stage}
                        status={status}
                        errorMessage={
                          i === 3 && repurposingQuery.isError
                            ? (repurposingQuery.error as Error)?.message
                            : i === 4 && briefQuery.isError
                              ? (briefQuery.error as Error)?.message
                              : i === 0 && resultsQuery.isError
                                ? (resultsQuery.error as Error)?.message
                                : null
                        }
                        onRun={() => {
                          if (i === 3) repurposingQuery.refetch();
                          if (i === 4) setBriefRequested(true);
                          if (i === 0 || i === 1 || i === 2) resultsQuery.refetch();
                        }}
                      >
                        {status === "success" && i === 1 && (
                          <CollapsibleBlock label="output — mutations" defaultOpen>
                            <VariantCallOutput runStatus={normalizedStatus.toUpperCase() || "UNKNOWN"} mutations={mutations} />
                          </CollapsibleBlock>
                        )}
                        {status === "success" && i === 3 && resultId && (
                          <>
                            <CollapsibleBlock label="output — table" defaultOpen>
                              <RepurposingOutput resultId={resultId} targetGene={targetGene} candidates={candidates} />
                            </CollapsibleBlock>
                            <CollapsibleBlock label="output — chart" defaultOpen>
                              <RankBarChart
                                light
                                bars={candidates.map((c) => ({ label: c.drug_name, value: c.rank_score ?? 0 }))}
                              />
                            </CollapsibleBlock>
                          </>
                        )}
                        {status === "success" && i === 4 && briefQuery.data && (
                          <CollapsibleBlock label="output — discovery brief" defaultOpen>
                            <CustomBriefOutput
                              reason={briefQuery.data.reason}
                              leadCandidates={briefQuery.data.lead_candidates?.length ?? 0}
                              componentLibrary={briefQuery.data.component_library ?? { scaffolds: [], fragments: [] }}
                            />
                          </CollapsibleBlock>
                        )}
                      </PipelineStageCard>
                    );
                  })}
                </div>
              </div>
            )}

            {section === "drugs" && (
              <div>
                <p className="font-mono text-[10px] uppercase tracking-widest mb-1" style={{ color: MUTED }}>Drug Results</p>
                <h1 className="text-xl font-semibold mb-4" style={{ color: INK }}>
                  Candidates for {targetGene ?? "this case"}
                </h1>
                <DrugResultsSection
                  candidates={candidates.map(toDrugCandidate)}
                  variantLabel={targetGene ?? submissionId}
                  isLoading={repurposingQuery.isLoading}
                  isError={repurposingQuery.isError}
                  errorMessage={(repurposingQuery.error as Error)?.message}
                  onDownloadReport={resultId ? () => api.getCustomDrugReport(resultId).then((r) => {
                    const blob = new Blob([r.report_text], { type: "text/plain" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = r.filename;
                    a.click();
                    URL.revokeObjectURL(url);
                  }) : undefined}
                />
              </div>
            )}

            {section === "report" && (
              <ReportSection submissionId={submissionId} isDemo={isDemo} />
            )}

            {section === "settings" && (
              <div>
                <p className="font-mono text-[10px] uppercase tracking-widest mb-1" style={{ color: MUTED }}>Settings</p>
                <h1 className="text-xl font-semibold mb-4" style={{ color: INK }}>Workspace settings</h1>
                <p className="text-sm" style={{ color: BODY }}>Not wired up yet.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

export default function WorkspacePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center" style={{ backgroundColor: BG }}>
          <Loader2 className="animate-spin" style={{ color: MUTED }} size={20} />
        </div>
      }
    >
      <WorkspaceInner />
    </Suspense>
  );
}
