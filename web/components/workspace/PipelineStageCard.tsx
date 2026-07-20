"use client";

import { useState } from "react";
import { Lock, Play, Loader2, Check, AlertCircle, ChevronRight, ChevronDown } from "lucide-react";
import type { PipelineStage, StageStatus } from "@/lib/pipeline-stages";
import CollapsibleBlock from "@/components/workspace/CollapsibleBlock";

const INK = "#16181D";
const MUTED = "#8A8D86";
const BODY = "#5B5E64";
const BORDER = "#E4E2DB";
const SURFACE = "#FFFFFF";
const BG = "#FAFAF8";

export default function PipelineStageCard({
  index,
  stage,
  status,
  onRun,
  errorMessage,
  children,
}: {
  index: number;
  stage: PipelineStage;
  status: StageStatus;
  onRun: () => void;
  errorMessage?: string | null;
  children?: React.ReactNode;
}) {
  const locked = status === "locked";
  const running = status === "running";
  const success = status === "success";
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      className="border"
      style={{ borderColor: BORDER, backgroundColor: SURFACE, opacity: locked ? 0.55 : 1 }}
    >
      <div className="p-4 sm:p-5">
        <button
          onClick={() => !locked && setCollapsed((c) => !c)}
          disabled={locked}
          className="w-full flex items-center gap-2 text-left disabled:cursor-default"
        >
          {!locked &&
            (collapsed ? (
              <ChevronRight size={14} style={{ color: MUTED }} className="shrink-0" />
            ) : (
              <ChevronDown size={14} style={{ color: MUTED }} className="shrink-0" />
            ))}
          <span className="font-mono text-xs" style={{ color: MUTED }}>
            [{index}]
          </span>
          <span className="text-sm font-semibold" style={{ color: INK }}>
            {stage.label}
          </span>
          {stage.conditional && (
            <span
              className="font-mono text-[9px] uppercase tracking-widest px-1.5 py-0.5 border"
              style={{ color: MUTED, borderColor: BORDER }}
            >
              conditional
            </span>
          )}
          {success && <Check size={14} style={{ color: INK }} />}
        </button>

        {locked && (
          <p className="text-xs mt-3 ml-[22px]" style={{ color: MUTED }}>
            Run the preceding stage to unlock.
          </p>
        )}

        {!locked && !collapsed && (
          <div className="mt-3 flex flex-col gap-3">
            <CollapsibleBlock label="input" defaultOpen>
              <div className="flex items-center justify-between gap-4 flex-wrap pt-1">
                <div className="min-w-0">
                  <p className="font-mono text-[11px] break-all" style={{ color: MUTED }}>
                    {stage.endpoint}
                  </p>
                  <p className="text-sm mt-2 max-w-xl" style={{ color: BODY }}>
                    {stage.description}
                  </p>
                </div>
                <button
                  onClick={onRun}
                  disabled={running}
                  className="inline-flex items-center gap-2 px-4 py-1.5 font-semibold text-xs transition-colors disabled:cursor-not-allowed shrink-0"
                  style={
                    success
                      ? { border: `1px solid ${BORDER}`, color: INK, backgroundColor: SURFACE }
                      : { backgroundColor: INK, color: "#FFFFFF" }
                  }
                >
                  {running ? (
                    <>
                      <Loader2 size={12} className="animate-spin" /> Running
                    </>
                  ) : success ? (
                    <>
                      <Play size={12} /> Re-run
                    </>
                  ) : (
                    <>
                      <Play size={12} /> Run
                    </>
                  )}
                </button>
              </div>
            </CollapsibleBlock>

            {errorMessage && (
              <div
                className="flex items-center gap-2 px-3 py-2 border text-xs"
                style={{ borderColor: "#E8B4AC", backgroundColor: "#FBEEEB", color: "#B3372C" }}
              >
                <AlertCircle size={13} className="shrink-0" /> {errorMessage}
              </div>
            )}

            {children}
          </div>
        )}
      </div>
    </div>
  );
}
