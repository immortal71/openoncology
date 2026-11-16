import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { HEField } from "@/components/marketing/he-field";
import { FindingList, type Finding } from "@/components/oo/finding-list";
import { HighlightProvider } from "@/components/oo/highlight";
import { RankLadder } from "@/components/results/rank-ladder";
import { VariantDetail } from "@/components/results/variant-drawer";
import { parseApproval } from "@/lib/approval";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { displayFont } from "@/lib/display-font";
import { displaySources, usesClinicalPhaseSignal } from "@/lib/evidence";
import { oncoKbLevel } from "@/lib/evidence-levels";
import { parseProteinChange } from "@/lib/protein";

export const metadata: Metadata = { title: "Direction A · Field of view | OpenOncology", robots: { index: false, follow: false } };

const METHODS_URL = "https://github.com/immortal71/openoncology/blob/main/docs/METHODS.md";
const wrap = "mx-auto max-w-[1200px] px-5 md:px-12";

function Footnote({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-oo-ink/15 pt-5">
      <div className="flex items-baseline gap-3">
        <span className="inline-grid h-6 w-6 shrink-0 place-items-center rounded-full border border-oo-hema/40 font-mono text-[11.5px] text-oo-hema">{n}</span>
        <h3 className="text-[16px] font-semibold text-oo-ink">{title}</h3>
      </div>
      <p className="mt-2 pl-9 text-[15px] leading-relaxed text-oo-ink-2">{children}</p>
    </div>
  );
}

function PaneTitle({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2.5 px-5 pb-3 pt-4 text-[13px] font-medium text-oo-ink-2">
      <span className="inline-grid h-5 w-5 place-items-center rounded-full bg-oo-hema font-mono text-[10.5px] text-white">{n}</span>
      {children}
    </div>
  );
}

export default function DirectionAPage() {
  if (process.env.NODE_ENV === "production") notFound();

  const ranked = [...DEMO_REPURPOSING.candidates].sort((a, b) => (b.rank_score ?? 0) - (a.rank_score ?? 0));
  const findings: Finding[] = ranked.map((c) => ({
    id: c.chembl_id,
    name: c.drug_name,
    tier: c.drug_tier,
    score: c.rank_score,
    approvalStatus: c.approval_status,
    mechanism: c.mechanism,
    sources: displaySources(c),
    phaseSignal: usesClinicalPhaseSignal(c),
  }));
  const lead = DEMO_RESULTS.mutations.find((m) => m.is_targetable) ?? DEMO_RESULTS.mutations[0];
  const change = parseProteinChange(lead.hgvs);
  const level = oncoKbLevel(lead.oncokb_level);
  const top = ranked[0];
  const topApproval = parseApproval(top.approval_status);

  return (
    <main className={`${displayFont.variable} bg-oo-paper text-oo-ink`}>
      <section aria-labelledby="hero-title" className="overflow-hidden">
        <div className={`${wrap} grid items-center gap-y-12 pb-20 pt-14 md:pt-16 lg:grid-cols-12 lg:gap-x-6 lg:pb-24`}>
          <div className="lg:col-span-5">
            <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-oo-hema">Open-source tumor evidence matching</p>
            <h1 id="hero-title" className="mt-6 font-display text-[42px] font-semibold leading-[1.04] tracking-[-0.025em] sm:text-[56px] lg:text-[62px]">
              Tumor variants in. Drug evidence you can inspect.
            </h1>
            <p className="mt-6 max-w-[30rem] text-[18px] leading-[1.6] text-oo-ink-2 lg:text-[19px]">
              For sequencing labs and hospital oncology teams: a ranked list of drug candidates for each case, grouped by clinical context, with
              every source named.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-4">
              <Link
                href="/lab/results"
                className="inline-flex h-12 items-center gap-2 rounded-md bg-oo-ink px-5 text-[15px] font-medium text-oo-paper transition-colors duration-150 hover:bg-oo-hema focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema"
              >
                Explore the demo case <ArrowRight size={16} aria-hidden="true" />
              </Link>
              <a
                href={METHODS_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-[15px] font-medium text-oo-hema underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-oo-hema"
              >
                Read the methods <ArrowUpRight size={15} aria-hidden="true" />
              </a>
            </div>
            <p className="mt-8 border-t border-oo-ink/10 pt-4 text-[13px] text-oo-ink-3">
              Research prototype · Open source (MIT) · Oncologist review required before any treatment decision
            </p>
          </div>

          <div className="relative lg:col-span-7">
            <div className="relative mx-auto aspect-square w-full max-w-[340px] sm:max-w-[460px] lg:ml-auto lg:mr-0 lg:max-w-[580px]">
              <div aria-hidden="true" className="absolute -inset-3 rounded-full border border-oo-hema/25 sm:-inset-4" />
              <div className="absolute inset-0 overflow-hidden rounded-full shadow-[inset_0_0_0_1px_rgb(61_44_141/0.15),0_40px_80px_-40px_rgb(43_29_61/0.45)]">
                <HEField id="hero-he" className="h-full w-full" />
                <div aria-hidden="true" className="absolute left-1/2 top-[8%] h-[84%] w-px -translate-x-1/2 bg-white/35" />
                <div aria-hidden="true" className="absolute left-[8%] top-1/2 h-px w-[84%] -translate-y-1/2 bg-white/35" />
              </div>
              <span className="absolute -bottom-10 right-0 hidden font-mono text-[11px] text-oo-ink-3 lg:block">Illustrative H&amp;E texture · not patient tissue</span>
            </div>

            <div className="relative z-10 mx-auto -mt-16 w-full max-w-[360px] rounded-[10px] border border-oo-ink/10 bg-white p-5 shadow-[0_24px_60px_-24px_rgb(27_22_38/0.45),0_2px_4px_rgb(27_22_38/0.06)] sm:-mt-24 lg:absolute lg:bottom-6 lg:left-0 lg:mt-0 lg:w-[350px]">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-oo-ink-3">Demo case</span>
                <span className="rounded-full border border-oo-line px-2 py-0.5 text-[11.5px] text-oo-ink-2">Awaiting oncologist review</span>
              </div>
              <div className="mt-3 text-[22px] font-semibold tracking-[-0.02em]">
                {lead.gene} <span className="text-oo-hema">{change?.short}</span>
              </div>
              <div className="text-[13.5px] text-oo-ink-3">{DEMO_RESULTS.cancer_type}</div>
              <div className="mt-4 border-t border-oo-line-soft pt-4">
                <div className="text-[12px] font-medium text-oo-ink-3">Top candidate</div>
                <div className="mt-1 flex items-baseline justify-between">
                  <span className="text-[19px] font-semibold tracking-[-0.01em]">{top.drug_name}</span>
                  <span className="font-mono text-[15px] tabular-nums">{top.rank_score?.toFixed(2)}</span>
                </div>
                <div aria-hidden="true" className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#ECE9F5]">
                  <div className="h-full rounded-full bg-oo-hema" style={{ width: `${(top.rank_score ?? 0) * 100}%` }} />
                </div>
                <p className="mt-3 text-[13px] leading-relaxed text-oo-ink-2">
                  <span className="font-medium text-oo-ink">{level?.label}</span> for {lead.gene} {change?.short} · {topApproval.label}
                </p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {displaySources(top).map((s) => (
                    <span key={s} className="rounded border border-oo-line bg-oo-paper px-1.5 py-0.5 font-mono text-[11.5px] text-oo-ink-2">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            <p className="mt-4 text-center font-mono text-[11px] text-oo-ink-3 lg:hidden">Illustrative H&amp;E texture · not patient tissue</p>
          </div>
        </div>
      </section>

      <section aria-labelledby="proof-title" className="border-t border-oo-ink/10 bg-[#F1EEE7]">
        <div className={`${wrap} py-20 lg:py-28`}>
          <div className="grid gap-6 lg:grid-cols-12 lg:items-end">
            <h2 id="proof-title" className="font-display text-[32px] font-semibold leading-[1.1] tracking-[-0.02em] sm:text-[40px] lg:col-span-7 lg:text-[46px]">
              Follow a candidate back to its evidence.
            </h2>
            <p className="text-[17px] leading-relaxed text-oo-ink-2 lg:col-span-5">
              The demo case, as the app shows it. Every number on this page comes from the demo case&apos;s output, unretouched.
            </p>
          </div>

          <div className="mt-12 overflow-hidden rounded-[12px] border border-oo-ink/[0.12] bg-white shadow-[0_30px_70px_-40px_rgb(27_22_38/0.35)]">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-oo-line px-5 py-3">
              <span className="text-[13px] text-oo-ink-3">
                Demo case <span aria-hidden="true">/</span> <span className="font-medium text-oo-ink">KRAS G12C</span> · {DEMO_RESULTS.cancer_type}
              </span>
              <span className="font-mono text-[11.5px] text-oo-ink-3">Research prototype · not a real patient</span>
            </div>
            <div className="grid lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
              <div className="min-w-0 border-b border-oo-line lg:border-b-0 lg:border-r">
                <PaneTitle n={1}>Ranked candidates, grouped by clinical context</PaneTitle>
                <HighlightProvider>
                  <FindingList
                    className="rounded-none border-x-0 border-b-0"
                    findings={findings}
                    caption="Ranked candidates"
                    showHeader
                    grouped
                    defaultOpenFirst
                    empty={null}
                  />
                  <RankLadder
                    className="rounded-none border-x-0 border-b-0"
                    items={ranked.map((c) => ({ id: c.chembl_id, name: c.drug_name, score: c.rank_score, tier: c.drug_tier }))}
                    context={`for ${lead.gene} ${change?.short ?? ""}`}
                  />
                </HighlightProvider>
              </div>
              <div className="min-w-0">
                <PaneTitle n={2}>Variant evidence · {lead.gene} {change?.short}</PaneTitle>
                <div className="px-5 pb-6">
                  <VariantDetail
                    variant={{
                      gene: lead.gene,
                      hgvs: lead.hgvs,
                      classification: lead.classification,
                      oncokb_level: lead.oncokb_level,
                      is_targetable: lead.is_targetable,
                    }}
                    cancerType={DEMO_RESULTS.cancer_type}
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="mt-12 grid gap-8 md:grid-cols-3 md:gap-10">
            <Footnote n={1} title="Grouped by clinical context">
              Standard-care evidence is separated from approved-elsewhere drugs, the way genomic reports present therapies. The overall rank is
              kept.
            </Footnote>
            <Footnote n={2} title="Every level explained">
              An OncoKB level comes with what it means and the tumour type it applies to, not just a badge.
            </Footnote>
            <Footnote n={3} title="Gaps stated, not hidden">
              What the result doesn&apos;t contain is listed plainly, so a missing value is never read as zero.
            </Footnote>
          </div>
        </div>
      </section>
    </main>
  );
}
