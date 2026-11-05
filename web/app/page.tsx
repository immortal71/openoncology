"use client";

import { useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import CyclingHeadline from "@/components/hero/CyclingHeadline";
import CasePanel from "@/components/hero/CasePanel";
import CredibilityStrip from "@/components/hero/CredibilityStrip";
import PipelineFilmstrip from "@/components/hero/PipelineFilmstrip";
import CommitStrip from "@/components/hero/CommitStrip";
import CiteThisWork from "@/components/hero/CiteThisWork";
import { Github, MessageCircle } from "lucide-react";
import { MOSAIC_CASES } from "@/lib/mosaic-cases";

// TODO: replace with the real invite link once the server exists.
const DISCORD_URL = "https://discord.com";
const GITHUB_URL = "https://github.com/immortal71/openoncology";

const CaseCluster = dynamic(() => import("@/components/hero/CaseCluster"), {
  ssr: false,
  loading: () => <div className="h-[420px] w-full sm:h-[520px] lg:h-[580px]" />,
});

export default function LandingPage() {
  const [activeId, setActiveId] = useState(MOSAIC_CASES[0].id);
  const activeCase = MOSAIC_CASES.find((c) => c.id === activeId) ?? MOSAIC_CASES[0];

  return (
    <main className="min-h-screen bg-neutral-bg text-neutral-heading">

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-b border-white/5">
        <div className="mx-auto max-w-[1600px] px-4 sm:px-6 py-16 md:py-20 relative z-10">
          <div className="grid grid-cols-1 lg:grid-cols-[0.85fr_1.15fr] gap-12 items-center">

            {/* Headline + CTA */}
            <div>
              <p className="font-mono text-xs text-neutral-muted mb-5 tracking-wider">
                Open-source tumor evidence matching
              </p>
              <CyclingHeadline />
              <p className="mt-5 max-w-lg text-neutral-body text-base leading-relaxed">
                OpenOncology brings drug evidence into one workspace for sequencing
                labs and hospitals without a molecular tumor board. An oncologist
                reviews the ranked shortlist and its sources.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <Link
                  href="/results/demo-nsclc-kras-g12c?demo=true"
                  className="inline-flex items-center gap-2 border border-white/25 text-white px-5 py-2.5 font-semibold transition-colors text-sm hover:border-white hover:bg-white/5"
                >
                  View Demo Results
                </Link>
              </div>
            </div>

            {/* 3D case cluster + live case panel */}
            <div className="grid grid-cols-1 sm:grid-cols-[1fr_260px] gap-6 items-stretch">
              <CaseCluster activeId={activeId} onSelect={setActiveId} />
              <CasePanel activeCase={activeCase} />
            </div>

          </div>
        </div>
      </section>

      {/* Research references and intended use */}
      <section className="clinical-shell py-10">
        <div className="grid md:grid-cols-[1.4fr_1fr] gap-4 items-stretch">
          <CredibilityStrip />
          <CiteThisWork />
        </div>
      </section>

      {/* ── Goal ─────────────────────────────────────────────── */}
      <section className="clinical-shell py-14">
        <p className="font-mono text-xs uppercase tracking-widest text-neutral-muted mb-4">
          Goal
        </p>
        <p className="text-lg md:text-xl text-neutral-heading leading-relaxed max-w-3xl">
          Our first customers are sequencing labs that already produce genomic
          reports but need oncology interpretation support. Hospitals without
          molecular tumor boards come next. The code is open source. We plan to
          offer a hosted workspace with support and validation at each site.
        </p>
      </section>

      {/* Intended lab workflow */}
      <section className="clinical-shell py-14 border-t border-white/5">
        <p className="font-mono text-xs uppercase tracking-widest text-neutral-muted mb-8">
          The report-review workflow
        </p>
        <PipelineFilmstrip />
      </section>

      {/* ── Vision ───────────────────────────────────────────── */}
      <section className="clinical-shell py-14">
        <p className="font-mono text-xs uppercase tracking-widest text-neutral-muted mb-4">
          What we are building next
        </p>
        <p className="text-neutral-body leading-relaxed text-base max-w-3xl mb-8">
          A drug can have strong evidence and still be out of reach. We plan to
          add local availability, access and affordability beside the evidence,
          starting with evaluation in Nepal. That layer and the hosted offering
          are still planned. The current software is a research prototype with
          no paying customers or hospital deployments.
        </p>
        <div className="flex flex-col gap-3 max-w-2xl">
          <div className="flex items-center gap-3">
            <span className="border border-white/15 px-4 py-2 text-sm text-neutral-body font-mono">
              Drug evidence
            </span>
            <span className="text-neutral-muted">→</span>
            <span className="border border-white/15 px-4 py-2 text-sm text-neutral-muted font-mono">
              Oncologist review
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="border border-white/15 px-4 py-2 text-sm text-neutral-body font-mono">
              Planned next
            </span>
            <span className="text-neutral-muted">→</span>
            <span className="border-2 border-white px-4 py-2 text-sm text-neutral-heading font-mono font-semibold">
              Local availability and affordability
            </span>
          </div>
        </div>
      </section>

      {/* ── Community ────────────────────────────────────────── */}
      <section className="clinical-shell py-14 border-t border-white/5">
        <div className="grid md:grid-cols-[1.2fr_1fr] gap-10 items-start">
          <div>
            <p className="font-mono text-xs uppercase tracking-widest text-neutral-muted mb-3">
              Community
            </p>
            <p className="text-neutral-body leading-relaxed text-base">
              The methods, bugs and evaluation limits are public. We welcome
              contributions from oncology and computational biology, especially
              independent review of the evidence and the lab workflow.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <a
                href={DISCORD_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 border border-white/25 text-neutral-heading px-5 py-2.5 font-semibold transition-colors text-sm hover:border-white hover:bg-white/5"
              >
                <MessageCircle size={15} /> Join on Discord
              </a>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 border border-white/25 text-neutral-heading px-5 py-2.5 font-semibold transition-colors text-sm hover:border-white hover:bg-white/5"
              >
                <Github size={15} /> Contribute on GitHub
              </a>
            </div>
          </div>
          {/* Part 2 (experimental) — live commit feed instead of a static
              GitHub button, pulled from the real repo at render time.
              CommitStrip renders nothing (including its own label) if the
              feed can't be fetched, so no orphaned heading is left behind. */}
          <CommitStrip />
        </div>
      </section>

      {/* ── What this doesn't do yet ────────────────────────────
          Part 2 (experimental) — sourced from README.md's "Does not"
          column, not new claims. */}
      <section className="clinical-shell py-14 border-t border-white/5">
        <p className="font-mono text-xs uppercase tracking-widest text-neutral-muted mb-8">
          Research-use prototype
        </p>
        <div className="grid sm:grid-cols-2 gap-x-10 gap-y-5 max-w-4xl">
          {[
            "Every result requires independent oncologist review.",
            "Retrospective lookup results do not establish clinical benefit.",
            "Patient-wide ranking and clinical-context integration need further work.",
            "Discovery, marketplace and crowdfunding modules are separate experiments.",
          ].map((item) => (
            <div key={item} className="flex gap-3">
              <span className="mt-1.5 shrink-0 h-1.5 w-1.5 rounded-full bg-neutral-muted" />
              <p className="text-neutral-body text-sm leading-relaxed">{item}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-white/10 py-10">
        <div className="clinical-shell flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <p className="text-sm text-neutral-muted">OpenOncology: drug evidence for labs and oncologists</p>
          <p className="font-mono text-xs text-neutral-muted">
            Research-use only. Treatment decisions require a licensed oncologist.
          </p>
        </div>
      </footer>

    </main>
  );
}
