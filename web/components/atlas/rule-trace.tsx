"use client";

import { useState } from "react";
import { TraceWmA } from "@/components/atlas/trace-wm-a";

export type TraceMode = "level1" | "r1";
export type CaseScore = { name: string; score: string; tag: string };

export function RuleTrace({
  mode,
  onMode,
  cases,
  tie,
}: {
  mode: TraceMode;
  onMode: (m: TraceMode) => void;
  cases: CaseScore[];
  tie: { at: [number, number]; gap: string } | null;
}) {
  const [changed, setChanged] = useState(false);
  const pick = (m: TraceMode) => {
    if (m !== mode) setChanged(true);
    onMode(m);
  };

  return (
    <div className="mt-14">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="font-mono text-[12px] uppercase tracking-[0.06em] text-[#C7BBF2]">Illustrative trace · published rules · not any drug&apos;s computation</p>
        <div role="group" aria-label="Example drug" className="flex rounded-[7px] border border-[#F7F5F0]/15 p-0.5 text-[12.5px]">
          {(
            [
              ["level1", "Level 1 example"],
              ["r1", "Illustrative R1 drug"],
            ] as const
          ).map(([m, label]) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              onClick={() => pick(m)}
              className={`rounded-[5px] px-2.5 py-1 transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#DCD2F7] ${mode === m ? "bg-[#F7F5F0]/12 text-[#F7F5F0]" : "text-[#F7F5F0]/60 hover:text-[#F7F5F0]"}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <TraceWmA r1={mode === "r1"} changed={changed} />

      <div className="mt-8 border-t border-[#F7F5F0]/14 pt-6">
        <p className="font-mono text-[12px] uppercase tracking-[0.06em] text-[#C7BBF2]">This case · KRAS G12C, NSCLC · reported by the engine</p>
        <div className="mt-5 flex flex-wrap items-end gap-x-12 gap-y-6">
          {tie ? (
            <div className="relative pt-9">
              <div data-tie="" aria-hidden="true" className="absolute inset-x-0 top-0">
                <span className="absolute left-0 top-0 whitespace-nowrap font-mono text-[12px] leading-4 text-[#DCD2F7]">{tie.gap} apart · near-tie, review both</span>
                <span className="absolute inset-x-0 top-[24px] h-2 border-x border-t border-[#B9A8EC]/70" />
              </div>
              <p className="sr-only">{tie.gap} apart: near-tie, review both.</p>
              <div className="flex gap-16">
                {cases.slice(tie.at[0], tie.at[1] + 1).map((c) => (
                  <CaseCell key={c.name} c={c} />
                ))}
              </div>
            </div>
          ) : null}
          {cases
            .filter((_, i) => !tie || i < tie.at[0] || i > tie.at[1])
            .map((c) => (
              <CaseCell key={c.name} c={c} />
            ))}
        </div>
        <p className="mt-5 max-w-[78ch] text-[13px] leading-[20px] text-[#F7F5F0]/60">
          These scores also use a docking signal pending review and a clinical-phase signal, which the workspace hides. The demo has no per-rule breakdown, so this case is not traced.
        </p>
      </div>
    </div>
  );
}

function CaseCell({ c }: { c: CaseScore }) {
  return (
    <div data-case="">
      <p className="text-[14px] font-semibold text-[#F7F5F0]">{c.name}</p>
      <p className="mt-1 font-mono text-[28px] leading-none tabular-nums text-[#DCD2F7]">{c.score}</p>
      <p className="mt-1.5 text-[12.5px] text-[#F7F5F0]/60">{c.tag}</p>
    </div>
  );
}
