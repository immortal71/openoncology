import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { TraceFigureTall, TraceFigureWide } from "@/components/marketing/trace-figure";
import { FindingList, type Finding } from "@/components/oo/finding-list";
import { HighlightProvider } from "@/components/oo/highlight";
import { VariantDetail } from "@/components/results/variant-drawer";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { displayFont } from "@/lib/display-font";
import { displaySources, usesClinicalPhaseSignal } from "@/lib/evidence";
import { oncoKbLevel } from "@/lib/evidence-levels";
import { tierInfo } from "@/lib/therapy-groups";
import { PROTEIN_REFERENCE, parseProteinChange } from "@/lib/protein";

export const metadata: Metadata = { title: "Direction B · The Trace | OpenOncology", robots: { index: false, follow: false } };

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

export default function DirectionBPage() {
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
  const ref = PROTEIN_REFERENCE[lead.gene];
  const domain = change ? (ref?.domains.find((d) => change.position >= d.start && change.position <= d.end) ?? null) : null;
  const traceVariant = {
    gene: lead.gene,
    short: change?.short ?? lead.hgvs,
    hgvs: lead.hgvs,
    position: change?.position ?? 1,
    length: ref?.length ?? 1,
    domain: domain ? { label: domain.short, start: domain.start, end: domain.end } : null,
    context: `${level?.label ?? "No OncoKB level"} · NSCLC`,
  };
  const traceRows = ranked.map((c) => ({
    name: c.drug_name,
    score: c.rank_score ?? 0,
    group: tierInfo(c.drug_tier).key === "fda_approved" ? "OncoKB Level 1–2 (standard care)" : "Approved elsewhere, weaker evidence",
    sources: displaySources(c),
  }));

  return (
    <main className={`${displayFont.variable} bg-oo-paper text-oo-ink`}>
      <section aria-labelledby="hero-title">
        <div className={`${wrap} pb-16 pt-14 md:pt-20`}>
          <div className="grid gap-8 lg:grid-cols-12 lg:items-end">
            <div className="lg:col-span-8">
              <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-oo-hema">Open-source tumor evidence matching</p>
              <h1 id="hero-title" className="mt-5 font-display text-[40px] font-semibold leading-[1.03] tracking-[-0.028em] sm:text-[56px] lg:text-[68px]">
                Tumor variants in.
                <br />
                Drug evidence
                <br className="hidden sm:block" /> you can inspect.
              </h1>
            </div>
            <div className="lg:col-span-4 lg:pb-2">
              <p className="text-balance text-[17px] leading-[1.6] text-oo-ink-2">
                For sequencing labs and hospital oncology teams: ranked drug candidates for each case, with every source named.
              </p>
              <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3">
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
                  Methods <ArrowUpRight size={15} aria-hidden="true" />
                </a>
              </div>
            </div>
          </div>

          <figure className="mt-12 border-y border-oo-ink/15 py-6 lg:mt-14">
            <div className="hidden md:block">
              <TraceFigureWide variant={traceVariant} rows={traceRows} />
            </div>
            <div className="mx-auto max-w-[380px] md:hidden">
              <TraceFigureTall variant={traceVariant} rows={traceRows} />
            </div>
            <figcaption className="mt-4 flex flex-wrap justify-between gap-x-6 gap-y-1 text-[12.5px] text-oo-ink-3">
              <span>
                <span className="font-mono text-oo-ink-2">Fig. 1</span> The demo case, traced from variant to ranked candidates to named sources.
              </span>
              <span>All values from the demo output · research prototype · not a real patient · oncologist review required</span>
            </figcaption>
          </figure>
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
                    defaultOpenAll
                    empty={null}
                  />
                </HighlightProvider>
              </div>
              <div className="border-t border-oo-line px-5 py-4 lg:hidden">
                <Link href="/lab/results" className="inline-flex items-center gap-1 text-[14px] font-medium text-oo-hema underline-offset-4 hover:underline">
                  Open {lead.gene} {change?.short} variant evidence in the demo <ArrowRight size={14} aria-hidden="true" />
                </Link>
              </div>
              <div className="hidden min-w-0 lg:block">
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

          <div className="mt-12 grid gap-8 md:grid-cols-2 md:gap-12">
            <Footnote n={1} title="Grouped by clinical context">
              Standard-care evidence is separated from drugs approved for other indications, the way genomic reports present therapies. The
              overall rank is kept.
            </Footnote>
            <Footnote n={2} title="Every level explained, every gap stated">
              An OncoKB level comes with its meaning and tumour type. What the result doesn&apos;t contain is listed plainly, so a missing value
              is never read as zero.
            </Footnote>
          </div>
        </div>
      </section>
    </main>
  );
}
