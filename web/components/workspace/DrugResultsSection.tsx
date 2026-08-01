"use client";

import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Download, FlaskConical, Loader2 } from "lucide-react";
import type { DrugCandidate } from "@/lib/pipeline-stages";

const INK = "#16181D";
const MUTED = "#8A8D86";
const BODY = "#5B5E64";
const BORDER = "#E4E2DB";
const BG = "#FAFAF8";
const SURFACE = "#FFFFFF";

function DrugRow({ candidate, warn }: { candidate: DrugCandidate; warn?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border" style={{ borderColor: BORDER }}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          {open ? (
            <ChevronDown size={14} style={{ color: MUTED }} className="shrink-0" />
          ) : (
            <ChevronRight size={14} style={{ color: MUTED }} className="shrink-0" />
          )}
          <span className="text-sm font-medium truncate" style={{ color: INK }}>
            {candidate.drug}
          </span>
          {warn && <AlertTriangle size={13} style={{ color: "#8A5A2B" }} className="shrink-0" />}
        </div>
        <span className="font-mono text-xs shrink-0" style={{ color: MUTED }}>
          rank {candidate.rankScore.toFixed(3)}
        </span>
      </button>
      {open && (
        <div className="px-4 pb-4 pt-1 flex flex-col gap-2" style={{ backgroundColor: BG }}>
          <div>
            <p className="font-mono text-[9px] uppercase tracking-widest" style={{ color: MUTED }}>Mechanism</p>
            <p className="text-sm mt-0.5" style={{ color: BODY }}>{candidate.mechanism}</p>
          </div>
          <div>
            <p className="font-mono text-[9px] uppercase tracking-widest" style={{ color: MUTED }}>Evidence</p>
            <p className="text-sm mt-0.5" style={{ color: BODY }}>{candidate.evidence}</p>
          </div>
          <div>
            <p className="font-mono text-[9px] uppercase tracking-widest" style={{ color: MUTED }}>Trial phase</p>
            <p className="text-sm mt-0.5" style={{ color: BODY }}>{candidate.trialPhase}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function DrugResultsSection({
  candidates,
  variantLabel,
  isLoading,
  isError,
  errorMessage,
  onDownloadReport,
}: {
  candidates: DrugCandidate[];
  variantLabel: string;
  isLoading?: boolean;
  isError?: boolean;
  errorMessage?: string | null;
  onDownloadReport?: () => void;
}) {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm" style={{ color: MUTED }}>
        <Loader2 size={15} className="animate-spin" /> Loading candidates for {variantLabel}…
      </div>
    );
  }

  if (isError) {
    return (
      <div
        className="flex items-center gap-2 px-3 py-2 border text-sm"
        style={{ borderColor: "#E8B4AC", backgroundColor: "#FBEEEB", color: "#B3372C" }}
      >
        <AlertTriangle size={15} className="shrink-0" />
        {errorMessage ?? "Could not load repurposing candidates."}
      </div>
    );
  }

  const fdaApproved = candidates.filter((c) => c.isFdaApproved);
  const nonFdaRepurposed = candidates.filter((c) => !c.isFdaApproved && c.tier !== "investigational_late" && c.tier !== "investigational_early" && c.tier !== "preclinical");
  const investigational = candidates.filter((c) => c.tier === "investigational_late" || c.tier === "investigational_early" || c.tier === "preclinical");
  const hasAnyMatch = candidates.length > 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest" style={{ color: MUTED }}>
            Drug Results
          </p>
          <p className="text-sm mt-1" style={{ color: BODY }}>
            For oncologist review — every entry cites its mechanism, evidence, and trial phase.
          </p>
        </div>
        <button
          onClick={onDownloadReport}
          disabled={!onDownloadReport}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold shrink-0 border disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ borderColor: BORDER, color: INK, backgroundColor: SURFACE }}
        >
          <Download size={13} /> Download report
        </button>
      </div>

      {/* FDA-approved */}
      <section>
        <p className="text-sm font-semibold mb-2" style={{ color: INK }}>
          FDA-Approved
        </p>
        {fdaApproved.length > 0 ? (
          <div className="flex flex-col gap-2">
            {fdaApproved.map((c) => (
              <DrugRow key={c.drug} candidate={c} />
            ))}
          </div>
        ) : (
          <p className="text-sm" style={{ color: MUTED }}>None found for this variant.</p>
        )}
      </section>

      {/* Non-FDA repurposed, with warning */}
      <section>
        <p className="text-sm font-semibold mb-2 flex items-center gap-2" style={{ color: INK }}>
          Non-FDA Repurposed
          <span
            className="inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-widest px-1.5 py-0.5 border"
            style={{ borderColor: "#D9C08A", color: "#8A5A2B" }}
          >
            <AlertTriangle size={10} /> off-label
          </span>
        </p>
        {nonFdaRepurposed.length > 0 && (
          <div
            className="border px-3 py-2 mb-3 text-xs"
            style={{ borderColor: "#D9C08A", backgroundColor: "#FAF6EA", color: "#6B4A1E" }}
          >
            Approved for a different indication, not this variant. Off-label use requires
            explicit oncologist judgment — not a validated match for this mutation.
          </div>
        )}
        {nonFdaRepurposed.length > 0 || investigational.length > 0 ? (
          <div className="flex flex-col gap-2">
            {[...nonFdaRepurposed, ...investigational].map((c) => (
              <DrugRow key={c.drug} candidate={c} warn />
            ))}
          </div>
        ) : (
          <p className="text-sm" style={{ color: MUTED }}>None found for this variant.</p>
        )}
      </section>

      {/* No match fallback */}
      {!hasAnyMatch && (
        <section
          className="border p-4 flex items-start gap-3"
          style={{ borderColor: BORDER, backgroundColor: BG }}
        >
          <FlaskConical size={18} style={{ color: MUTED }} className="shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold" style={{ color: INK }}>
              No approved or repurposed match found
            </p>
            <p className="text-sm mt-1" style={{ color: BODY }}>
              This mutation has no actionable drug candidate yet. Escalate to the custom
              discovery brief (stage 5) to generate lead and de-novo candidates.
            </p>
          </div>
        </section>
      )}
    </div>
  );
}
