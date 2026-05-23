"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import GenomicStream from "@/components/ui/genomic-stream";

const DEMO_ID = "demo-nsclc-kras-g12c";

const pipelineSteps = [
  {
    num: "01",
    tag: "VARIANT CALL",
    title: "Actionability Check",
    desc: "Validate clinical relevance in your cancer context. If not actionable, we state it directly.",
  },
  {
    num: "02",
    tag: "DRUG RANK",
    title: "Repurposed Options",
    desc: "Rank already-approved candidates first — lower cost, lower risk, faster decision.",
  },
  {
    num: "03",
    tag: "CUSTOM BRIEF",
    title: "Custom Discovery Brief",
    desc: "Structure prediction, docking, and lead ranking generated only when repurposing fails.",
  },
  {
    num: "04",
    tag: "SYNTHESIS",
    title: "Manufacture + Funding",
    desc: "Place a synthesis request and launch crowdfunding from the same case in one step.",
  },
];

const metrics = [
  { label: "Decision Stages", value: "4" },
  { label: "File Families", value: "12+" },
  { label: "Status Tracking", value: "Live" },
  { label: "Long Job Fallback", value: "Orders" },
];

const timelineItems = [
  {
    label: "T+0min",
    title: "Minutes — Initial triage",
    desc: "Actionability and repurposing checks appear quickly for VCF and document uploads.",
  },
  {
    label: "T+2hr",
    title: "Hours — Deep processing",
    desc: "Large FASTQ/BAM jobs run in background while you monitor status in My Orders.",
  },
  {
    label: "T+weeks",
    title: "Weeks — Wet-lab validation",
    desc: "Custom leads pass through synthesis and biological validation before clinical use.",
  },
];

const LOG_LINES: { text: string; color: string }[] = [
  { text: "$ openoncology analyze --sample KRAS_G12C_NSCLC", color: "text-slate-500 text-xs" },
  { text: "[✓] Variant called: KRAS p.Gly12Cys", color: "text-green-400" },
  { text: "[✓] OncoKB Level 1 — actionable", color: "text-green-400" },
  { text: "[✓] Sotorasib ranked #1 (DiffDock 0.847)", color: "text-green-400" },
  { text: "[→] Custom brief: not required", color: "text-cyan-400" },
  { text: "[✓] Report ready — 3 candidates found", color: "text-green-400" },
];

export default function LandingPage() {
  const [completedLines, setCompletedLines] = useState<{ text: string; color: string }[]>([]);
  const [partialLine, setPartialLine] = useState("");
  const [partialColor, setPartialColor] = useState("");
  const [fading, setFading] = useState(false);
  const [loopKey, setLoopKey] = useState(0);

  useEffect(() => {
    let tid: ReturnType<typeof setTimeout>;

    function tick(li: number, ci: number, done: { text: string; color: string }[]) {
      if (li >= LOG_LINES.length) {
        tid = setTimeout(() => {
          setFading(true);
          tid = setTimeout(() => {
            setFading(false);
            setCompletedLines([]);
            setPartialLine("");
            setLoopKey((k) => k + 1);
          }, 500);
        }, 2000);
        return;
      }
      const line = LOG_LINES[li];
      const partial = line.text.slice(0, ci);
      setPartialLine(partial);
      setPartialColor(line.color);
      if (ci < line.text.length) {
        tid = setTimeout(() => tick(li, ci + 1, done), 30);
      } else {
        const next = [...done, line];
        tid = setTimeout(() => {
          setCompletedLines(next);
          setPartialLine("");
          tick(li + 1, 0, next);
        }, 60);
      }
    }

    tick(0, 0, []);
    return () => clearTimeout(tid);
  }, [loopKey]);

  return (
    <main className="min-h-screen bg-[#0a0f1e] text-slate-100">

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-b border-slate-800/60">
        <div className="hero-dots absolute inset-0 pointer-events-none z-0" />
        <div className="clinical-shell py-16 md:py-20 relative z-10">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">

            {/* Headline + CTA */}
            <div>
              <p className="font-mono text-xs text-cyan-400/60 mb-5 tracking-wider">
                KRAS · G12C · chr12:25398284 · COSV57014428
              </p>
              <h1 className="text-4xl md:text-5xl font-[var(--font-manrope)] font-extrabold leading-[1.1] tracking-tight text-white">
                From mutation report<br className="hidden md:block" /> to treatment path
              </h1>
              <p className="mt-4 max-w-lg text-slate-400 text-base leading-relaxed">
                Actionability check → repurposing → custom discovery brief → manufacturing.
                A fixed clinical workflow that keeps every action linked to evidence.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <Link
                  href="/submit"
                  className="inline-flex items-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white px-5 py-2.5 rounded-md font-semibold transition-colors text-sm"
                >
                  Start New Case <ArrowRight size={15} />
                </Link>
                <Link
                  href={`/results/${DEMO_ID}?demo=true`}
                  className="inline-flex items-center gap-2 border border-slate-700 text-slate-300 hover:text-white hover:border-slate-500 px-5 py-2.5 rounded-md font-semibold transition-colors text-sm"
                >
                  View Demo Results
                </Link>
              </div>
            </div>

            {/* Right: genomic data stream (desktop only) */}
            <div className="hidden lg:block">
              <GenomicStream />
            </div>

          </div>

          {/* Terminal log panel — full width */}
          <div
            className="mt-8 w-full rounded-sm border border-slate-700/50 bg-[#0d1117] overflow-hidden"
            style={{ boxShadow: "0 0 40px rgba(6,182,212,0.08)" }}
          >
              {/* macOS-style titlebar */}
              <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-slate-700/50 bg-slate-900/60">
                <div className="h-[10px] w-[10px] rounded-full bg-red-500/70" />
                <div className="h-[10px] w-[10px] rounded-full bg-yellow-500/70" />
                <div className="h-[10px] w-[10px] rounded-full bg-green-500/70" />
                <span className="ml-2 font-mono text-xs text-gray-500">analysis.log</span>
              </div>
              <div
                className={`p-5 font-mono text-sm space-y-2.5 min-h-[160px] transition-opacity duration-500 ${fading ? "opacity-0" : "opacity-100"}`}
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px)",
                }}
              >
                {completedLines.map((line, i) => (
                  <p key={i} className={line.color}>{line.text}</p>
                ))}
                {partialLine !== "" && (
                  <p className={partialColor}>
                    {partialLine}<span className="cursor-blink text-slate-400 ml-[1px]" />
                  </p>
                )}
                {completedLines.length === LOG_LINES.length && partialLine === "" && (
                  <p className="text-slate-400 mt-1">$ <span className="cursor-blink" /></p>
                )}
              </div>
          </div>
        </div>
      </section>

      {/* ── Pipeline ─────────────────────────────────────────── */}
      <div className="border-t border-white/5 mx-8" />
      <section className="clinical-shell py-14">
        <p className="font-mono text-xs uppercase tracking-widest text-slate-500 mb-2">Clinical Workflow</p>
        <h2 className="text-2xl font-[var(--font-manrope)] font-bold text-white mb-10">
          How each case moves forward
        </h2>
        <div className="flex flex-col md:flex-row md:items-stretch">
          {pipelineSteps.map((step, i) => (
            <div key={step.num} className="flex items-stretch flex-1">
              <div className="border-l-2 border-cyan-500 bg-white/[0.02] pl-4 pr-5 py-5 flex-1">
                <span className="font-mono text-cyan-400 text-xs tracking-widest">{step.num}</span>
                <p className="font-mono text-[10px] text-cyan-600/80 tracking-widest mt-1 uppercase">{step.tag}</p>
                <h3 className="text-white font-semibold text-sm mt-2 mb-1.5">{step.title}</h3>
                <p className="text-gray-400 text-sm leading-relaxed">{step.desc}</p>
              </div>
              {i < 3 && (
                <div className="hidden md:flex items-center px-2 text-gray-600 select-none">→</div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ── Stats ────────────────────────────────────────────── */}
      <div className="border-t border-white/5 mx-8" />
      <section className="clinical-shell py-10">
        <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-white/5">
          {metrics.map((m, i) => (
            <div
              key={m.label}
              className={`p-5 ${i === 0 ? "border-t-2 border-cyan-500" : "border-t-2 border-gray-700"}`}
            >
              <p className="font-mono text-3xl font-bold text-white">{m.value}</p>
              <p className="font-mono text-[10px] uppercase tracking-wider text-slate-500 mt-1.5 leading-tight">
                {m.label}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Timelines ────────────────────────────────────────── */}
      <div className="border-t border-white/5 mx-8" />
      <section className="clinical-shell py-14">
        <div
          className="border border-white/10 bg-white/[0.02] p-8 md:p-10"
          style={{ borderLeft: "4px solid rgb(6 182 212)" }}
        >
          <h2 className="text-xl font-[var(--font-manrope)] font-bold text-white mb-6">
            Designed for realistic timelines
          </h2>
          <div className="grid md:grid-cols-3 gap-7">
            {timelineItems.map((item) => (
              <div key={item.title}>
                <p className="font-mono text-[10px] text-cyan-500 tracking-widest mb-2">{item.label}</p>
                <div className="flex gap-3">
                  <div className="mt-1.5 shrink-0 h-1.5 w-1.5 rounded-full bg-cyan-500" />
                  <div>
                    <p className="text-white text-sm font-semibold">{item.title}</p>
                    <p className="text-slate-400 text-sm mt-1 leading-relaxed">{item.desc}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-800 py-10">
        <div className="clinical-shell flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <p className="text-sm text-slate-500">OpenOncology — Open source precision medicine platform</p>
          <p className="font-mono text-xs text-slate-600">
            Research-use only. Treatment decisions require a licensed oncologist.
          </p>
        </div>
      </footer>

    </main>
  );
}

