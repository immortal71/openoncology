import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowUpRight, Github } from "lucide-react";
import { HeroScroll, type HeroCandidate } from "@/components/marketing/hero-scroll";
import { ReviewState } from "@/components/oo/clinical";
import { HighlightProvider } from "@/components/oo/highlight";
import { ProteinLollipop } from "@/components/results/protein-lollipop";
import { RankLadder } from "@/components/results/rank-ladder";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { displayFont } from "@/lib/display-font";
import { displaySources, usesClinicalPhaseSignal } from "@/lib/evidence";
import { predictionLabel } from "@/lib/evidence-levels";
import { domainAt, parseProteinChange } from "@/lib/protein";

export const metadata: Metadata = {
  title: "Landing (redesign) | OpenOncology",
  robots: { index: false, follow: false },
};

const GITHUB_URL = "https://github.com/immortal71/openoncology";
const BENCHMARK_URL = "https://github.com/immortal71/openoncology/blob/main/docs/BENCHMARK.md#msk-chord-evidence-lookup-benchmark";
const PREPRINT_URL = "https://doi.org/10.21203/rs.3.rs-9707913/v1";
const DOI = "10.21203/rs.3.rs-9707913/v1";
const DEMO_HREF = "/lab/results";
const NEAR_TIE = 0.02;

const STEPS = [
  { num: "01", title: "Supply findings", desc: "Start with genomic findings and cancer context. Lab integration remains in development." },
  { num: "02", title: "Find drug evidence", desc: "Look up treatment evidence for the supplied findings and record gaps in the available information." },
  { num: "03", title: "Review the shortlist", desc: "Read the ranked candidates with their evidence sources and limitations." },
  { num: "04", title: "Decide next steps", desc: "A qualified oncologist checks the evidence in the patient's clinical context." },
];

const LIMITS = [
  "Retrospective lookup results do not establish clinical benefit.",
  "Patient-wide ranking and clinical-context integration need further work.",
  "Discovery, marketplace and crowdfunding modules are separate experiments.",
];

const container = "mx-auto max-w-[1200px] px-5 md:px-8";
const h2 = "text-balance font-display text-[30px] font-semibold leading-[1.12] tracking-[-0.015em] text-oo-ink sm:text-[34px]";
const artifact = "self-start rounded-lg border border-oo-line bg-oo-surface p-3";
const textLink =
  "inline-flex items-center gap-1.5 rounded-sm font-medium text-oo-hema underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-oo-hema";
const primaryCta =
  "inline-flex h-11 items-center rounded-md bg-oo-hema px-5 text-[15px] font-medium text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.12),0_1px_2px_rgb(27_22_38/0.2)] transition-colors duration-150 hover:bg-oo-hema-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema";
const secondaryCta =
  "inline-flex h-11 items-center gap-2 rounded-md border border-oo-line bg-oo-surface px-5 text-[15px] font-medium text-oo-ink shadow-[0_1px_2px_rgb(27_22_38/0.06)] transition-colors duration-150 hover:border-oo-ink-3/40 hover:bg-oo-paper focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema";

export default function LandingLabPage() {
  if (process.env.NODE_ENV === "production") notFound();

  const lead = DEMO_RESULTS.mutations.find((m) => m.is_targetable) ?? DEMO_RESULTS.mutations[0];
  const change = parseProteinChange(lead.hgvs);
  const leadLabel = `${lead.gene} ${change?.short ?? lead.hgvs}`;
  const ranked = [...DEMO_REPURPOSING.candidates].sort((a, b) => (b.rank_score ?? 0) - (a.rank_score ?? 0));
  const candidates: HeroCandidate[] = ranked.map((c) => ({
    id: c.chembl_id,
    name: c.drug_name,
    tier: c.drug_tier,
    score: c.rank_score,
    approvalStatus: c.approval_status,
    mechanism: c.mechanism,
    sources: displaySources(c),
    phaseSignal: usesClinicalPhaseSignal(c),
  }));
  const domain = change ? domainAt(lead.gene, change.position) : null;
  const leadLevel = `OncoKB Level ${lead.oncokb_level.replace("LEVEL_", "")}`;
  const predicted = (m: { classification?: string; alphamissense_score?: number | null }) => {
    const label = predictionLabel(m.classification, m.alphamissense_score);
    return label ? `AlphaMissense: ${label.toLowerCase()}` : null;
  };
  const heroFacts = [domain, predicted(lead), leadLevel].filter(Boolean).join(" · ");
  const top = ranked[0];
  const nearTie = ranked.length > 1 && (ranked[0].rank_score ?? 0) - (ranked[1].rank_score ?? 0) < NEAR_TIE;
  const variantNote = (m: (typeof DEMO_RESULTS.mutations)[number]) =>
    [predicted(m), `OncoKB Level ${m.oncokb_level.replace("LEVEL_", "")}`, m.is_targetable ? "targetable" : "not targetable"].join(" · ");

  const artifacts: Record<string, React.ReactNode> = {
    "01": (
      <figure className={artifact}>
        <figcaption className="text-[11.5px] text-oo-ink-3">Annotated variant, as supplied</figcaption>
        <pre className="mt-1.5 overflow-x-auto font-mono text-[11.5px] leading-relaxed text-oo-ink-2">
          {["GENE=KRAS", "HGVS_C=c.34G>T", "HGVS_P=p.Gly12Cys"].join("\n")}
        </pre>
      </figure>
    ),
    "02": (
      <figure className={artifact}>
        <figcaption className="text-[11.5px] text-oo-ink-3">Evidence matched</figcaption>
        <p className="mt-1.5 text-[13px] text-oo-ink">
          <span className="font-semibold">{leadLabel}</span> <span aria-hidden="true">→</span>
          <span className="sr-only">matches</span> {top.drug_name}
        </p>
        <p className="mt-0.5 font-mono text-[11.5px] text-oo-ink-3">{leadLevel}</p>
      </figure>
    ),
    "03": (
      <figure className={artifact}>
        <figcaption className="text-[11.5px] text-oo-ink-3">Flagged on the shortlist</figcaption>
        <p className="mt-1.5 text-[13px] leading-relaxed text-oo-ink">
          {nearTie
            ? `Ranks 1 and 2 score within ${NEAR_TIE} of each other, so they are marked a near-tie, not a real difference.`
            : "Each candidate lists the sources behind its rank."}
        </p>
      </figure>
    ),
    "04": (
      <figure className={artifact}>
        <figcaption className="text-[11.5px] text-oo-ink-3">Review state on the demo case</figcaption>
        <ReviewState reviewed={false} className="mt-2" />
      </figure>
    ),
  };

  return (
    <main className={`${displayFont.variable} bg-oo-paper text-oo-ink`}>
      <HeroScroll
        candidates={candidates}
        title={DEMO_RESULTS.cancer_type}
        facts={heroFacts}
        input={`${leadLabel} (${lead.hgvs})`}
        inputSource="from the demo case VCF"
        demoHref={DEMO_HREF}
      />

      <section aria-labelledby="result-title" className="border-t border-oo-line bg-oo-surface">
        <div className={`${container} py-20 md:py-24`}>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-[13px] font-medium text-oo-ink-3">From the demo case</p>
              <h2 id="result-title" className={`mt-2 ${h2}`}>
                What a result looks like
              </h2>
            </div>
            <Link href={DEMO_HREF} className={`${textLink} text-[15px]`}>
              Open the full demo case <ArrowUpRight size={15} aria-hidden="true" />
            </Link>
          </div>
          <HighlightProvider>
            <div className="mt-8 grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
              <RankLadder
                items={ranked.map((c) => ({ id: c.chembl_id, name: c.drug_name, score: c.rank_score, tier: c.drug_tier }))}
                context={`for ${leadLabel}`}
              />
              <ProteinLollipop
                variants={DEMO_RESULTS.mutations.map((m) => ({ gene: m.gene, hgvs: m.hgvs, emphasis: m === lead, note: variantNote(m) }))}
              />
            </div>
          </HighlightProvider>
        </div>
      </section>

      <section aria-labelledby="how-title" id="how-it-works" className="scroll-mt-20 border-t border-oo-line">
        <div className={`${container} py-20 md:py-24`}>
          <h2 id="how-title" className={h2}>
            How it works
          </h2>
          <p className="mt-2 max-w-[44rem] text-[16px] text-oo-ink-2">The report-review workflow, from genomic findings to an oncologist&apos;s decision.</p>
          <ol className="relative mt-12 grid gap-10 md:grid-cols-4 md:gap-x-8 md:gap-y-0">
            <span aria-hidden="true" className="absolute left-0 right-0 top-[11px] hidden h-px bg-oo-line md:block" />
            {STEPS.map((s) => (
              <li key={s.num} className="relative grid content-start md:row-span-4 md:grid-rows-subgrid">
                <span className="relative z-10 inline-grid h-6 min-w-6 place-items-center justify-self-start rounded-full border border-oo-line bg-oo-paper px-1.5 font-mono text-[11px] text-oo-ink-2">
                  {s.num}
                </span>
                <h3 className="mt-4 text-[16px] font-semibold text-oo-ink">{s.title}</h3>
                <p className="mb-5 mt-1.5 text-[14.5px] leading-relaxed text-oo-ink-2">{s.desc}</p>
                {artifacts[s.num]}
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section aria-labelledby="evidence-title" id="evidence" className="scroll-mt-20 border-t border-oo-line bg-oo-surface">
        <div className={`${container} grid gap-6 py-16 md:py-20 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] lg:gap-16`}>
          <div>
            <p className="text-[13px] font-medium text-oo-ink-3">Research and evaluation</p>
            <h2
              id="evidence-title"
              className="mt-3 max-w-[18ch] text-balance font-display text-[34px] font-semibold leading-[1.1] tracking-[-0.015em] text-oo-ink sm:text-[42px]"
            >
              How it&apos;s evaluated, and what that doesn&apos;t show.
            </h2>
          </div>
          <div className="space-y-6">
            <p className="text-[17px] leading-relaxed text-oo-ink">
              The MSK CHORD experiment evaluates evidence lookup using alterations selected from received treatments. It does not validate the
              complete application or establish clinical benefit.
            </p>
            <a href={BENCHMARK_URL} target="_blank" rel="noreferrer" className={`${textLink} text-[15px]`}>
              Methods and limits <ArrowUpRight size={15} aria-hidden="true" />
            </a>
            <p className="text-[15px] font-medium text-oo-ink">Every result requires independent oncologist review, by design.</p>
            <div>
              <h3 className="text-[13px] font-medium text-oo-ink-3">What it doesn&apos;t do yet</h3>
              <ul className="mt-2 divide-y divide-oo-line-soft border-y border-oo-line-soft">
                {LIMITS.map((item) => (
                  <li key={item} className="py-3 text-[15px] leading-relaxed text-oo-ink-2">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <figure className="border-l-2 border-oo-line pl-5">
              <figcaption className="text-[13px] text-oo-ink-3">Historical preprint covering the broader research agenda</figcaption>
              <blockquote className="mt-2 text-[15px] leading-relaxed text-oo-ink-2">
                Kharel, A. OpenOncology: An Open-Source Framework for Evidence-Based Drug Matching and De Novo Custom Drug Discovery in Precision
                Oncology. <i>Research Square</i> (2026).
              </blockquote>
              <a href={PREPRINT_URL} target="_blank" rel="noreferrer" className={`${textLink} mt-3 font-mono text-[12.5px]`}>
                DOI {DOI} <ArrowUpRight size={13} aria-hidden="true" />
              </a>
            </figure>
          </div>
        </div>
      </section>

      <section aria-labelledby="who-title" className="border-t border-oo-line">
        <div className={`${container} grid gap-6 py-16 md:py-20 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] lg:gap-16`}>
          <h2 id="who-title" className={h2}>
            Who it is for
          </h2>
          <div>
            <div className="space-y-4 text-[16px] leading-relaxed text-oo-ink-2">
              <p>
                Our first customers are sequencing labs that already produce genomic reports but need oncology interpretation support.
                Hospitals without molecular tumor boards come next. The code is open source. We plan to offer a hosted workspace with support and
                validation at each site.
              </p>
              <p>
                A drug can have strong evidence and still be out of reach. We plan to add local availability, access and affordability beside
                the evidence, starting with evaluation in Nepal. That layer and the hosted offering are still planned. The current software is a
                research prototype with no paying customers or hospital deployments.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section aria-labelledby="community-title" className="border-t border-oo-line bg-oo-surface">
        <div className={`${container} flex flex-col gap-8 py-16 md:flex-row md:items-center md:justify-between md:py-20`}>
          <div className="max-w-[40rem]">
            <h2 id="community-title" className={h2}>
              The methods, bugs and limits are public.
            </h2>
            <p className="mt-3 text-[16px] leading-relaxed text-oo-ink-2">
              We welcome contributions from oncology and computational biology, especially independent review of the evidence and the lab
              workflow.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href={DEMO_HREF} className={primaryCta}>
              View the demo case
            </Link>
            <a href={GITHUB_URL} target="_blank" rel="noreferrer" className={secondaryCta}>
              <Github size={17} aria-hidden="true" />
              Contribute on GitHub
            </a>
          </div>
        </div>
      </section>

      <footer className="border-t border-oo-line">
        <div className={`${container} flex flex-col gap-3 py-10 text-[13px] text-oo-ink-3 md:flex-row md:items-center md:justify-between`}>
          <p>OpenOncology: drug evidence for labs and oncologists</p>
          <p>Research-use only. Treatment decisions require a licensed oncologist.</p>
        </div>
      </footer>
    </main>
  );
}
