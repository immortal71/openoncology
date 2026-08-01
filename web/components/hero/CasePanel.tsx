"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { MosaicCase } from "@/lib/mosaic-cases";

function cellShade(score: number) {
  // Sequential grayscale: higher rank score -> lighter cell. Zero saturation
  // so there is no hue skew at any lightness.
  const lightness = 18 + score * 62;
  return `hsl(0 0% ${lightness}%)`;
}

export default function CasePanel({ activeCase }: { activeCase: MosaicCase }) {
  return (
    <div className="flex h-full flex-col justify-between">
      <div className="border border-white/10 bg-white/[0.02] p-5">
        <div className="mb-4">
          <p className="font-mono text-[10px] uppercase tracking-widest text-neutral-muted">
            Case ID
          </p>
          <p className="font-mono text-sm text-neutral-heading mt-1">{activeCase.id}</p>
        </div>

        <div className="mb-4">
          <p className="font-mono text-[10px] uppercase tracking-widest text-neutral-muted">
            Variant
          </p>
          <p className="text-sm text-neutral-heading mt-1">
            {activeCase.gene} <span className="text-neutral-body">{activeCase.hgvs}</span>
          </p>
          <p className="font-mono text-[10px] text-neutral-muted mt-1">
            {activeCase.cancerType} · OncoKB {activeCase.oncokbLevel.replace("LEVEL_", "L")}
          </p>
        </div>

        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-neutral-muted mb-2">
            Candidate rank
          </p>
          <div className="flex flex-col gap-1">
            {activeCase.candidates.map((c) => (
              <div key={c.drug_name} className="flex items-center gap-2">
                <span
                  className="h-3 w-8 shrink-0 border border-white/10"
                  style={{ backgroundColor: cellShade(c.rank_score) }}
                  title={`${c.drug_name}: ${c.rank_score.toFixed(3)}`}
                />
                <span className="text-xs text-neutral-body truncate">{c.drug_name}</span>
                <span className="ml-auto font-mono text-[10px] text-neutral-muted">
                  {c.rank_score.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-col items-end gap-1.5">
        <Link
          href="/workspace"
          className="inline-flex items-center justify-center gap-2 self-end border border-white/25 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:border-white hover:bg-white/5"
        >
          Get Access <ArrowRight size={15} />
        </Link>
        <p className="font-mono text-[10px] text-neutral-muted text-right max-w-[220px]">
          Opens the live workspace with a fully worked KRAS G12C demo case.
        </p>
      </div>
    </div>
  );
}
