"use client";

import { useEffect, useRef, useState } from "react";

type LineFormat = "variant" | "drug" | "sample" | "negative" | "system";

const ALL_LINES: { text: string; format: LineFormat }[] = [
  // variant — PATHOGENIC (text-cyan-400)
  { text: "chr7:55191822   EGFR p.Leu858Arg    [PATHOGENIC]", format: "variant" },
  { text: "chr17:7673803   TP53 p.Arg175His    [PATHOGENIC]", format: "variant" },
  { text: "chr12:25398284  KRAS p.Gly12Cys     [PATHOGENIC]", format: "variant" },
  { text: "chr7:140453136  BRAF p.Val600Glu    [PATHOGENIC]", format: "variant" },
  { text: "chr17:37880220  ERBB2 p.Val777Leu   [PATHOGENIC]", format: "variant" },
  { text: "chr9:21971020   CDKN2A p.Arg58Ter   [PATHOGENIC]", format: "variant" },
  { text: "chr11:108236067 ATM p.Tyr2755Cys    [PATHOGENIC]", format: "variant" },
  // drug match (text-green-400)
  { text: "→ Sotorasib     OncoKB L1  score: 0.983", format: "drug" },
  { text: "→ Osimertinib   OncoKB L1  score: 0.923", format: "drug" },
  { text: "→ Adagrasib     OncoKB L1  score: 0.973", format: "drug" },
  { text: "→ Erlotinib     OncoKB L2  score: 0.811", format: "drug" },
  { text: "→ Vemurafenib   OncoKB L1  score: 0.947", format: "drug" },
  { text: "→ Trastuzumab   OncoKB L1  score: 0.891", format: "drug" },
  { text: "→ Gefitinib     OncoKB L2  score: 0.834", format: "drug" },
  // sample ID (text-slate-400)
  { text: "SAMPLE-4821  NSCLC        2 variants called", format: "sample" },
  { text: "SAMPLE-7103  Colorectal   3 variants called", format: "sample" },
  { text: "SAMPLE-2954  Melanoma     1 variant called",  format: "sample" },
  { text: "SAMPLE-6617  Breast       4 variants called", format: "sample" },
  { text: "SAMPLE-3390  GBM          2 variants called", format: "sample" },
  // negative — ACTIONABLE (text-slate-500 + cyan badge)
  { text: "chr3:179218303  PIK3CA p.His1047Arg  [ACTIONABLE]", format: "negative" },
  { text: "chr10:89692905  PTEN p.Arg233Ter     [ACTIONABLE]", format: "negative" },
  { text: "chr1:115256529  NRAS p.Gln61Lys      [ACTIONABLE]", format: "negative" },
  // system (text-slate-500)
  { text: "Pipeline complete · 847ms  · 3 candidates ranked", format: "system" },
  { text: "Pipeline complete · 1.2s   · 2 candidates ranked", format: "system" },
  { text: "DiffDock docking complete  · batch 4/4 · done",    format: "system" },
];

const COLOR: Record<LineFormat, string> = {
  variant:  "text-cyan-400",
  drug:     "text-green-400",
  sample:   "text-slate-400",
  negative: "text-slate-500",
  system:   "text-slate-500",
};

interface StreamLine {
  id: number;
  text: string;
  format: LineFormat;
  fadingIn: boolean;
}

function renderText(line: StreamLine) {
  const base = COLOR[line.format];
  if (line.format === "variant" || line.format === "negative") {
    const parts = line.text.split(/(\[PATHOGENIC\]|\[ACTIONABLE\])/);
    return (
      <span className={base}>
        {parts.map((part, i) =>
          part === "[PATHOGENIC]" || part === "[ACTIONABLE]" ? (
            <span
              key={i}
              className="bg-cyan-500/20 text-cyan-300 px-1 rounded-sm font-mono text-[10px] ml-1"
            >
              {part}
            </span>
          ) : (
            part
          )
        )}
      </span>
    );
  }
  return <span className={base}>{line.text}</span>;
}

export default function GenomicStream() {
  const [lines, setLines] = useState<StreamLine[]>([]);
  const idxRef = useRef(0);
  const idCounter = useRef(0);

  useEffect(() => {
    const shuffled = [...ALL_LINES].sort(() => Math.random() - 0.5);

    const tick = () => {
      const entry = shuffled[idxRef.current % shuffled.length];
      idxRef.current++;
      const id = idCounter.current++;

      setLines((prev) => {
        const next: StreamLine = { id, text: entry.text, format: entry.format, fadingIn: true };
        return [next, ...prev].slice(0, 8);
      });

      // Remove fadingIn flag after one paint to trigger CSS transition
      setTimeout(() => {
        setLines((prev) =>
          prev.map((l) => (l.id === id ? { ...l, fadingIn: false } : l))
        );
      }, 16);
    };

    const interval = setInterval(tick, 1200);
    return () => clearInterval(interval);
  }, []);

  return (
    <div
      className="rounded-sm border border-slate-700/50 bg-[#0d1117] overflow-hidden"
      style={{ boxShadow: "0 0 40px rgba(6,182,212,0.08)" }}
    >
      {/* Title bar */}
      <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-slate-700/50 bg-slate-900/60">
        <div className="h-[10px] w-[10px] rounded-full bg-red-500/70" />
        <div className="h-[10px] w-[10px] rounded-full bg-yellow-500/70" />
        <div className="h-[10px] w-[10px] rounded-full bg-green-500/70" />
        <span className="ml-2 font-mono text-xs text-gray-500">live.feed</span>
      </div>

      {/* Stream body */}
      <div className="relative h-[280px] overflow-hidden">
        <div className="absolute inset-0 pt-3 px-4 flex flex-col gap-y-2.5">
          {lines.map((line) => (
            <p
              key={line.id}
              className={`font-mono text-xs transition-opacity duration-300 ${
                line.fadingIn ? "opacity-0" : "opacity-100"
              }`}
            >
              {renderText(line)}
            </p>
          ))}
        </div>
        {/* Bottom gradient fade */}
        <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-[#0d1117] to-transparent pointer-events-none" />
      </div>
    </div>
  );
}
