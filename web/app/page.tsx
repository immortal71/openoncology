"use client";

import Link from "next/link";
import {
  Activity,
  ArrowRight,
  BadgeDollarSign,
  Dna,
  FlaskConical,
  Microscope,
  ShieldCheck,
  TestTube2,
} from "lucide-react";

const pathwayCards = [
  {
    icon: Activity,
    title: "1. Actionability Check",
    description:
      "We validate if your mutation has proven clinical relevance in your cancer context. If not actionable, we state it directly.",
  },
  {
    icon: FlaskConical,
    title: "2. Repurposed Options",
    description:
      "For actionable cases, we rank already approved candidates first to reduce cost, risk, and time to decision.",
  },
  {
    icon: TestTube2,
    title: "3. Custom Discovery Brief",
    description:
      "If repurposing fails, we generate a custom medicinal chemistry brief with structure prediction, docking, and lead ranking.",
  },
  {
    icon: BadgeDollarSign,
    title: "4. Manufacture + Funding",
    description:
      "Place a manufacturing request from the same case and launch fundraising if the quote exceeds patient budget.",
  },
];

const metrics = [
  { label: "Decision Stages", value: "4" },
  { label: "Accepted File Families", value: "12+" },
  { label: "Auto-Refresh Tracking", value: "Live" },
  { label: "Fallback for Long Jobs", value: "My Orders" },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen text-slate-900 dark:text-slate-100">
      <section className="clinical-shell pt-10 pb-8">
        <div className="clinical-surface p-6 md:p-10 bg-gradient-to-br from-white via-cyan-50/40 to-slate-50 dark:from-slate-900 dark:via-slate-900/40 dark:to-slate-950">
          <div className="grid lg:grid-cols-[1.25fr_0.75fr] gap-8 items-start">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800 dark:border-cyan-900/50 dark:bg-cyan-950/30 dark:text-cyan-300">
                Precision Oncology Workflow
              </span>
              <h1 className="mt-4 text-4xl md:text-5xl font-[var(--font-manrope)] font-extrabold leading-tight text-slate-900 dark:text-white">
                From mutation report to treatment path, with clear clinical steps.
              </h1>
              <p className="mt-4 max-w-2xl text-slate-600 dark:text-slate-400 text-lg leading-relaxed">
                OpenOncology helps teams decide quickly: check actionability, rank repurposed options, then generate custom discovery briefs only when necessary.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <Link href="/submit" className="inline-flex items-center gap-2 rounded-xl bg-cyan-700 px-5 py-3 font-semibold text-white hover:bg-cyan-600 dark:bg-cyan-600 dark:hover:bg-cyan-500 transition-colors">
                  Start New Case <ArrowRight size={18} />
                </Link>
                <Link href="/orders" className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 px-5 py-3 font-semibold text-slate-700 dark:text-slate-300 hover:border-cyan-400 dark:hover:border-cyan-600 hover:text-cyan-700 dark:hover:text-cyan-400 transition-colors">
                  Track Existing Orders
                </Link>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5">
              <h2 className="text-base font-[var(--font-manrope)] font-bold text-slate-900 dark:text-white">Why this platform is practical</h2>
              <ul className="mt-3 space-y-3 text-sm text-slate-600 dark:text-slate-400">
                <li className="flex gap-2"><ShieldCheck className="mt-0.5 text-cyan-700 dark:text-cyan-400" size={16} /> No false promises for non-actionable biology</li>
                <li className="flex gap-2"><Microscope className="mt-0.5 text-cyan-700 dark:text-cyan-400" size={16} /> Repurposing-first strategy to reduce time/cost</li>
                <li className="flex gap-2"><Dna className="mt-0.5 text-cyan-700 dark:text-cyan-400" size={16} /> Custom discovery only when evidence supports it</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 md:grid-cols-4 gap-3">
          {metrics.map((metric) => (
            <div key={metric.label} className="clinical-surface p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{metric.label}</p>
              <p className="mt-1 text-2xl font-[var(--font-manrope)] font-extrabold text-slate-900 dark:text-white">{metric.value}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="clinical-shell py-14">
        <h2 className="text-3xl md:text-4xl font-[var(--font-manrope)] font-extrabold mb-3 text-slate-900 dark:text-white">How each case moves forward</h2>
        <p className="text-slate-600 dark:text-slate-400 mb-10 max-w-2xl">
          A fixed clinical workflow prevents random decisions and keeps every action linked to evidence.
        </p>
        <div className="grid md:grid-cols-2 gap-8">
          {pathwayCards.map((f) => (
            <div key={f.title} className="clinical-surface p-6 hover:border-cyan-300 dark:hover:border-cyan-700 hover:shadow-md transition-all">
              <f.icon className="text-cyan-700 dark:text-cyan-400 mb-4" size={26} />
              <h3 className="text-lg font-[var(--font-manrope)] font-bold mb-2 text-slate-900 dark:text-white">{f.title}</h3>
              <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed">{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="clinical-shell pb-16">
        <div className="rounded-3xl border border-cyan-100 bg-gradient-to-r from-cyan-700 to-sky-700 p-8 md:p-10 text-white shadow-2xl shadow-cyan-900/25">
          <h2 className="text-2xl md:text-3xl font-[var(--font-manrope)] font-extrabold mb-5">Designed for realistic timelines</h2>
          <div className="grid md:grid-cols-3 gap-5 text-sm">
            <div className="rounded-xl bg-white/12 p-4 border border-white/15">
              <p className="font-semibold">Minutes to initial triage</p>
              <p className="text-cyan-50 mt-1">Actionability and repurposing checks appear quickly for VCF plus document uploads.</p>
            </div>
            <div className="rounded-xl bg-white/12 p-4 border border-white/15">
              <p className="font-semibold">Hours to deep processing</p>
              <p className="text-cyan-50 mt-1">Large FASTQ/BAM jobs continue in background while patients monitor status in My Orders.</p>
            </div>
            <div className="rounded-xl bg-white/12 p-4 border border-white/15">
              <p className="font-semibold">Weeks to wet-lab validation</p>
              <p className="text-cyan-50 mt-1">Custom leads are a discovery output, then pass through synthesis and biological validation.</p>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-200/80 dark:border-slate-800/80 py-10">
        <div className="clinical-shell flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <p className="text-sm text-slate-500 dark:text-slate-400">OpenOncology - Open source precision medicine platform</p>
          <p className="text-xs text-slate-400 dark:text-slate-500">Research-use platform. Final treatment decisions must be made with licensed oncologists.</p>
        </div>
      </footer>
    </main>
  );
}
