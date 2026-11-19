"use client";

import { useRef } from "react";
import Link from "next/link";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { useGSAP } from "@gsap/react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { EvidenceRibbon, type ThreadNode } from "@/components/atlas/evidence-ribbon";
import { ProductShot, type ShotData } from "@/components/atlas/product-shot";
import { StepContent, type StepVisualData } from "@/components/atlas/step-visuals";
import { CarryLines, ClosingThread, PageSpine, StoryThread } from "@/components/atlas/story-thread";

gsap.registerPlugin(ScrollTrigger, SplitText, useGSAP);

export type CaseFact = { k: string; v: string; missing?: boolean };

export type AtlasData = {
  demoHref: string;
  shot: ShotData;
  steps: StepVisualData;
  heroNodes: ThreadNode[];
  compactNodes: ThreadNode[];
  labFacts: CaseFact[];
  clinicFacts: CaseFact[];
  clinicMore: number;
  ladder: { code: string; names: string } | null;
  usedSources: string[];
};

const METHODS_URL = "https://github.com/immortal71/openoncology/blob/main/docs/METHODS.md";
const REPO_URL = "https://github.com/immortal71/openoncology";
const SOURCES = [
  { name: "OncoKB", kind: "Evidence levels" },
  { name: "CIViC", kind: "Clinical evidence" },
  { name: "ClinVar", kind: "Variant classification" },
  { name: "OpenTargets", kind: "Target–disease links" },
  { name: "ChEMBL", kind: "Drug records" },
  { name: "AlphaMissense", kind: "Missense prediction" },
];
const EASE = [0.22, 1, 0.36, 1] as const;
const CTA_LABEL = "View the demo case";

const wrap = "mx-auto w-full max-w-[1280px] px-5 md:px-10";
const h2 = "text-balance text-[30px] font-semibold leading-[1.1] tracking-[-0.035em] text-[#24212B] sm:text-[36px] lg:text-[40px] lg:leading-[46px]";
const label = "text-[12.5px] font-semibold uppercase tracking-[0.06em] text-[#625E68]";
const aside = "max-w-[30rem] text-pretty text-[17px] leading-[1.6] text-[#4A4652] lg:col-span-5 lg:col-start-7";
const focus = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#69518C]";
const primaryBtn = `group inline-flex h-12 items-center justify-center gap-2 rounded-[8px] bg-[#25202F] px-6 text-[15px] font-medium leading-[20px] text-[#F7F5F0] transition-colors duration-150 hover:bg-[#3A3446] ${focus}`;
const textLink = `inline-flex min-h-[44px] items-center gap-1 text-[15px] font-medium text-[#24212B] underline decoration-[#24212B]/25 underline-offset-[5px] transition-colors duration-150 hover:decoration-[#24212B] ${focus}`;
const newTab = <span className="sr-only">(opens in a new tab)</span>;

function Rise({ children, className, delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.8, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

function SectionHead({ id, kicker, title, children, dark = false, wide = false }: { id: string; kicker: string; title: React.ReactNode; children?: React.ReactNode; dark?: boolean; wide?: boolean }) {
  return (
    <Rise className="grid gap-5 lg:grid-cols-12 lg:items-end lg:gap-6">
      <div className={wide ? "lg:col-span-7" : "lg:col-span-6"}>
        <p className={dark ? "text-[12.5px] font-semibold uppercase tracking-[0.06em] text-[#F7F5F0]/70" : label}>{kicker}</p>
        <h2 id={id} className={`mt-4 ${dark ? h2.replace("text-[#24212B]", "text-[#F7F5F0]") : h2}`}>
          {title}
        </h2>
      </div>
      {children ? <p className={`${dark ? aside.replace("text-[#4A4652]", "text-[#F7F5F0]/75") : aside} ${wide ? "lg:col-span-4 lg:col-start-9" : ""}`}>{children}</p> : null}
    </Rise>
  );
}

const STEPS = [
  {
    key: "variant",
    title: "Read the variant",
    body: "Start from the annotated variant calls your sequencing run already produces. Anything the result doesn't contain is stated.",
    caption: "Input",
  },
  {
    key: "evidence",
    title: "Rank the evidence",
    body: "Drugs are matched against curated evidence, grouped by OncoKB level and ranked within each group by a weighted score.",
    caption: "Output",
  },
  {
    key: "review",
    title: "Hand it to the oncologist",
    body: "The shortlist goes to clinical review with its gaps attached. Nothing is acted on until an oncologist has checked it.",
    caption: "Decision",
  },
] as const;

function Workflow({ data }: { data: StepVisualData }) {
  const panel = useRef<HTMLDivElement>(null);
  return (
    <Rise className="mt-12 lg:mt-16">
      <div
        ref={panel}
        className="relative overflow-hidden rounded-[14px] border border-[#E2DEE6] bg-white shadow-[0_1px_2px_rgba(37,32,47,0.06),0_12px_32px_rgba(37,32,47,0.06)]"
      >
        <div className="flex items-center justify-between gap-4 border-b border-[#E2DEE6] px-5 py-3 text-[13px]">
          <span className="truncate font-medium text-[#24212B]">{data.variant} · from variant calls to clinical review</span>
          <span className="hidden shrink-0 rounded-full border border-[#E2DEE6] px-2.5 py-0.5 text-[12px] text-[#625E68] sm:inline">Demo case</span>
        </div>
        <ol className="grid lg:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s.key} className={`flex min-w-0 flex-col p-6 lg:p-7 ${i > 0 ? "border-t border-[#E2DEE6] lg:border-l lg:border-t-0" : ""}`}>
              <div className="flex items-center gap-3">
                <span
                  aria-hidden="true"
                  className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[#69518C] font-mono text-[12px] font-medium text-white"
                >
                  {i + 1}
                </span>
                <h3 className="min-w-0 flex-1 text-[19px] font-semibold leading-[1.25] tracking-[-0.02em] text-[#24212B]">
                  <span className="sr-only">Step {i + 1}: </span>
                  {s.title}
                </h3>
                <span className={`hidden shrink-0 sm:inline ${label}`}>{s.caption}</span>
              </div>
              <div className="-mx-3 mb-6 mt-5">
                <StepContent kind={s.key} data={data} bare />
              </div>
              <p className="mt-auto max-w-[42ch] border-t border-[#E2DEE6] pt-4 text-pretty text-[14.5px] leading-[1.6] text-[#625E68]">{s.body}</p>
            </li>
          ))}
        </ol>
        <CarryLines wrap={panel} />
      </div>
    </Rise>
  );
}

function FieldsCard({ vcf, missing }: { vcf: StepVisualData["vcf"]; missing: CaseFact[] }) {
  return (
    <div className="mt-6 flex min-w-0 flex-col rounded-[12px] border border-[#E2DEE6] bg-white shadow-[0_1px_2px_rgba(37,32,47,0.06),0_12px_32px_rgba(37,32,47,0.06)]">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-[#E2DEE6] px-5 py-3">
        <span className="font-mono text-[12px] uppercase tracking-[0.06em] text-[#5B5566]">Variant calls, as received</span>
        <span className="whitespace-nowrap font-mono text-[12px] text-[#5B5566]">Demo case</span>
      </div>
      <div className="px-3 py-3">
        <table className="w-full border-collapse font-mono text-[13px]">
          <caption className="sr-only">Variant calls as received, with allele fraction and read depth missing from this result</caption>
          <thead>
            <tr className="text-left text-[#625E68]">
              {[...vcf.columns, "VAF", "DEPTH"].map((c, j) => (
                <th key={c} scope="col" className={`px-2 pb-2 pt-1 font-normal ${j === 1 ? "hidden xl:table-cell" : ""}`}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {vcf.rows.map((r, i) => (
              <tr key={r.join("-")} data-spine-dock={i === vcf.highlight ? "" : undefined} className={i === vcf.highlight ? "font-medium text-[#24212B]" : "text-[#625E68]"}>
                {r.map((v, j) => (
                  <td key={j} className={`px-2 py-2.5 ${j === 1 ? "hidden xl:table-cell" : ""}`}>
                    {v}
                  </td>
                ))}
                {["VAF", "DEPTH"].map((c) => (
                  <td key={c} className="px-1 py-1.5">
                    <span className="block whitespace-nowrap rounded-[5px] border border-dashed border-[#B5B0BA] px-2 py-1 text-center text-[12px] font-normal text-[#625E68]">
                      <span className="xl:hidden">missing</span>
                      <span className="hidden xl:inline">not in result</span>
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-auto flex items-start gap-2 border-t border-[#E2DEE6] px-5 py-3.5 text-[13.5px] leading-[20px] text-[#24212B]">
        <span aria-hidden="true" className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#AD7629]" />
        <span>
          {missing.length} fields missing: VAF and read depth aren&apos;t part of this result. Add them to the next run.
        </span>
      </p>
    </div>
  );
}

function CheckRail({ rows, more }: { rows: CaseFact[]; more: number }) {
  return (
    <div className="mt-6 flex flex-1 flex-col rounded-[12px] border border-[#E2DEE6] bg-white shadow-[0_1px_2px_rgba(37,32,47,0.06),0_12px_32px_rgba(37,32,47,0.06)]">
      <p className="border-b border-[#E2DEE6] px-5 py-3 font-mono text-[12px] uppercase tracking-[0.06em] text-[#5B5566]">Before any treatment decision</p>
      <ol className="relative flex flex-1 flex-col px-5 py-4">
        <span aria-hidden="true" className="absolute bottom-[34px] left-[24px] top-[26px] w-[1.5px] bg-[#69518C]/35" />
        {rows.map((r) => (
          <li key={r.k} className="relative flex items-center gap-3 py-2">
            <span aria-hidden="true" className="relative z-10 h-2.5 w-2.5 shrink-0 rounded-full border-2 border-white bg-[#69518C]" />
            <span className="min-w-0 flex-1 text-[14px] text-[#24212B]">{r.k}</span>
            <span className="shrink-0 rounded-full bg-[#ECEAEF] px-2.5 py-1 text-[12px] font-medium leading-none text-[#3A3542]">{r.v}</span>
          </li>
        ))}
        {more > 0 ? <li className="py-1 pl-[22px] text-[13px] text-[#625E68]">and {more} more in the full case</li> : null}
        <li className="relative mt-auto flex items-center gap-3 pt-3">
          <span aria-hidden="true" className="relative z-10 h-3 w-3 shrink-0 rounded-full border-2 border-[#69518C] bg-white" />
          <span className="min-w-0 flex-1 text-[14.5px] font-semibold text-[#24212B]">Oncologist sign-off</span>
          <span className="shrink-0 rounded-full border border-[#B5B0BA] bg-white px-2.5 py-1 text-[12.5px] font-medium leading-none text-[#3A3542]">Pending</span>
        </li>
      </ol>
    </div>
  );
}

const LEVELS = [
  { code: "1", group: 0 },
  { code: "2", group: 0 },
  { code: "3A", group: 1 },
  { code: "3B", group: 1 },
  { code: "4", group: 1 },
  { code: "R1", group: 2 },
  { code: "R2", group: 2 },
];
const GROUPS = [
  { tier: "Standard care", note: "Ranked as approved options for this context" },
  { tier: "Weaker or off-label evidence", note: "Shown as repurposing candidates" },
  { tier: "Resistance", note: "Blocks the drug from ranking" },
];

function Ladder({ mark, used: raw }: { mark: AtlasData["ladder"]; used: string[] }) {
  const used = raw.filter((n) => SOURCES.some((s) => s.name === n));
  const at = mark ? LEVELS.findIndex((l) => l.code === mark.code) : -1;
  return (
    <figure className="mt-14">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-[15px] font-semibold text-[#F7F5F0]">How an OncoKB level decides where a drug lands</span>
        <span className="text-[13px] text-[#F7F5F0]/60">The mapping the ranking uses, as written in the methods</span>
      </figcaption>
      <div className="mt-4 overflow-x-auto">
        <div className="min-w-[640px]">
          <div className="grid h-12 grid-cols-7">
            {at >= 0 && mark ? (
              <div className="relative" style={{ gridColumnStart: at + 1 }}>
                <span className="absolute bottom-2 left-0 whitespace-nowrap text-[13px] font-medium text-[#F7F5F0]">
                  This case · <span className="text-[#DCD2F7]">{mark.names}</span>
                </span>
                <span aria-hidden="true" className="absolute bottom-0 left-1/2 h-2 w-px bg-[#B9A8EC]" />
              </div>
            ) : null}
          </div>
          <div data-spine-dock="" className="flex h-12 overflow-hidden rounded-[10px] border border-[#F7F5F0]/15">
            {LEVELS.map((l, i) => (
              <span
                key={l.code}
                className={`grid flex-1 place-items-center font-mono text-[14px] font-medium ${i > 0 ? "border-l border-[#25202F]" : ""} ${
                  l.group === 0 ? "bg-[#5E4D80] text-[#E6DEFA]" : l.group === 1 ? "bg-[#3B3350] text-[#CFC4EC]" : "bg-[#C9776A]/[0.14] font-semibold text-[#F4C7BC] shadow-[inset_0_0_0_1.5px_rgba(201,119,106,0.9)]"
                } ${i === at ? "!bg-[#DCD2F7] !text-[#25202F] font-semibold" : ""}`}
              >
                {l.code}
              </span>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-7 gap-0">
            {GROUPS.map((g, i) => (
              <div key={g.tier} className={`pr-4 ${i === 0 ? "col-span-2" : i === 1 ? "col-span-3" : "col-span-2"}`}>
                <p className="text-[15px] font-semibold text-[#F7F5F0]">{g.tier}</p>
                <p className="mt-0.5 text-[13.5px] leading-[20px] text-[#F7F5F0]/70">{g.note}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
      <dl className="mt-8 grid gap-6 border-t border-[#F7F5F0]/14 pt-6 lg:grid-cols-12 lg:gap-6">
        <div className="lg:col-span-6">
          <dt className="border-l-2 border-[#F7F5F0] pl-3 text-[12.5px] font-semibold uppercase tracking-[0.06em] text-[#F7F5F0]">Not clinically validated</dt>
          <dd className="mt-2 max-w-[60ch] text-[15px] leading-[1.6] text-[#F7F5F0]/85">
            The level sets a drug&apos;s group; a weighted evidence score ranks drugs within it. A hard benchmark gates every change: the expected drugs for a set of curated cases must rank in the top three, with no false positives. It doesn&apos;t test clinical outcomes.{" "}
            <a href={`${METHODS_URL}#benchmark-methodology`} target="_blank" rel="noreferrer" className="whitespace-nowrap font-medium text-[#DCD2F7] underline decoration-[#DCD2F7]/40 underline-offset-4 hover:decoration-[#DCD2F7]">
              Benchmark methodology
              {newTab}
            </a>
          </dd>
        </div>
        <div className="lg:col-span-6 lg:col-start-7">
          <dt className="text-[12.5px] font-semibold uppercase tracking-[0.06em] text-[#B9B1C9]">Sources</dt>
          <dd className="mt-2 max-w-[60ch] text-[15px] leading-[1.6] text-[#F7F5F0]/85">
            It can query {SOURCES.map((s) => s.name).join(", ")}.{used.length ? <> This demo result used {used.join(", ")}.</> : null}
          </dd>
        </div>
      </dl>
    </figure>
  );
}

const FAQ = [
  { q: "How is this different from checking OncoKB directly?", a: "OncoKB is one of its sources. OpenOncology checks several sources for each variant, ranks the drugs it finds within the case, and records which lookups came back empty or weren't stored. It doesn't replace OncoKB." },
  { q: "What does the evidence score mean?", a: "A weighted combination of the evidence found for a drug, used to rank candidates within one case. It is not a probability that a patient will respond." },
  { q: "Is this clinical advice?", a: "No. OpenOncology is a research prototype. Every result needs independent review by a licensed oncologist before any treatment decision." },
  { q: "Can we use it today, and what data does the demo hold?", a: "The code is open source; a hosted workspace is planned and there are no hospital deployments yet. The demo is a sample case, not a real patient." },
];

export function AtlasHome({ data }: { data: AtlasData }) {
  const root = useRef<HTMLDivElement>(null);
  const headline = useRef<HTMLHeadingElement>(null);
  const story = useRef<HTMLDivElement>(null);
  const art = useRef<HTMLDivElement>(null);
  const closing = useRef<HTMLDivElement>(null);
  const closingArt = useRef<HTMLDivElement>(null);
  const closingCta = useRef<HTMLAnchorElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        const split = SplitText.create(headline.current, {
          type: "lines",
          mask: "lines",
          autoSplit: true,
          onSplit: (self) => gsap.from(self.lines, { yPercent: 105, duration: 1.1, ease: "power4.out", stagger: 0.08 }),
        });
        gsap.from("[data-hero-in]", { y: 14, opacity: 0, duration: 0.8, ease: "power3.out", stagger: 0.07, delay: 0.35 });
        gsap.from("[data-art]", { opacity: 0, duration: 1.6, ease: "power2.out", delay: 0.1 });
        return () => split.revert();
      });
    },
    { scope: root }
  );

  return (
    <div ref={root} className="relative bg-[#F7F5F0] font-[family-name:var(--font-atlas)] text-[#24212B] antialiased">
      <div ref={story} className="relative overflow-hidden">
        <section aria-labelledby="hero-title" className="relative">
          <div ref={art} data-art className="pointer-events-none absolute inset-y-0 left-[50%] right-0 hidden [mask-image:linear-gradient(to_bottom,#000_62%,transparent_96%)] lg:block">
            <EvidenceRibbon layout="hero" trace={false} className="absolute inset-0" />
          </div>
          <div className={`${wrap} pointer-events-none absolute inset-x-0 bottom-3 hidden justify-end lg:flex`}>
            <p className="text-[12px] leading-[18px] text-[#625E68]">Illustrative evidence pathway · demo case</p>
          </div>
          <div className={`${wrap} pointer-events-none relative flex flex-col justify-center pb-7 pt-10 lg:h-[clamp(470px,calc(100svh-340px),560px)] lg:pb-10 lg:pt-2`}>
            <div className="pointer-events-auto max-w-[560px] lg:w-[46%]">
              <p data-hero-in className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-[#625E68]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#69518C]" />
                <span>Research prototype</span>
                <span aria-hidden="true" className="hidden sm:inline">
                  ·
                </span>
                <span className="hidden sm:inline">Open source</span>
                <span aria-hidden="true">·</span>
                <span>Oncologist review required</span>
              </p>
              <h1
                id="hero-title"
                ref={headline}
                className="mt-5 text-balance text-[clamp(34px,9.4vw,42px)] font-semibold leading-[1.06] tracking-[-0.035em] sm:text-[56px] lg:text-[clamp(52px,7.2vh,64px)]"
              >
                Tumor mutations, matched to cancer drug evidence.
              </h1>
              <p data-hero-in className="mt-5 max-w-[32rem] text-pretty text-[17px] leading-[1.55] text-[#4A4652] lg:text-[18px] lg:leading-[28px]">
                Variant calls go in. A ranked shortlist comes out, with the evidence and the gaps behind every candidate. For sequencing labs and hospital oncology teams.
              </p>
              <div data-hero-in className="mt-6 flex flex-wrap items-center gap-x-7 gap-y-3">
                <Link href={data.demoHref} className={primaryBtn}>
                  {CTA_LABEL}
                  <ArrowRight size={16} aria-hidden="true" />
                </Link>
                <a href={METHODS_URL} target="_blank" rel="noreferrer" className={textLink}>
                  Read the methods <ArrowUpRight size={15} aria-hidden="true" />
                  {newTab}
                </a>
              </div>
            </div>
          </div>
          <div className="lg:hidden">
            <div className="relative h-[150px] [mask-image:linear-gradient(to_bottom,#000_40%,transparent_92%)]">
              <EvidenceRibbon layout="compact" threads={110} trace={false} className="absolute inset-0" />
              <p className="absolute left-5 top-2 text-[12.5px] text-[#625E68]">Illustrative evidence pathway · demo case</p>
            </div>
            <ol className="relative mx-5 -mt-6 mb-2 space-y-3 border-l-2 border-[#69518C]/50 pl-6">
              {data.compactNodes.map((n, i) => (
                <li key={n.label} className="relative">
                  <span aria-hidden="true" className={`absolute -left-[31px] top-[5px] h-3 w-3 rounded-full border-2 border-[#F7F5F0] ${i === data.compactNodes.length - 1 ? "bg-[#69518C]" : "bg-[#8270A4]"}`} />
                  <p className="font-mono text-[12px] uppercase tracking-[0.06em] text-[#5B5566]">
                    <span className="mr-2 text-[#69518C]">0{i + 1}</span>
                    {n.label}
                  </p>
                  <p className={`mt-0.5 text-[16px] font-semibold ${n.accent ? "text-[#523E70]" : "text-[#24212B]"}`}>{n.value}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>
        <StoryThread wrap={story} art={art} nodes={data.heroNodes} />

        <section id="product" aria-labelledby="proof-title" className="relative z-10 scroll-mt-[88px] pb-16 pt-6 lg:pb-24 lg:pt-0">
          <div className={wrap}>
            <h2 id="proof-title" className="sr-only">
              See why a candidate appears in the demo case
            </h2>
            <ProductShot data={data.shot} />
          </div>
        </section>
      </div>

      <section id="how-it-works" aria-labelledby="how-title" className="scroll-mt-[88px] border-t border-[#E2DEE6] py-16 lg:py-24">
        <div className={wrap}>
          <SectionHead
            id="how-title"
            kicker="How it works"
            wide
            title={
              <>
                <span className="block">Each source is checked separately.</span>
                <span className="block">Gaps rarely get written down.</span>
              </>
            }
          >
            OpenOncology checks OncoKB, CIViC, OpenTargets and its other sources for each variant, ranks the drugs it finds and writes down what it couldn&apos;t find. One case, in three steps:
          </SectionHead>
          <Workflow data={data.steps} />
          <div className="mt-14 grid gap-12 md:grid-cols-2 md:gap-6">
            <Rise className="h-full min-w-0">
              <article id="labs" className="flex h-full min-w-0 scroll-mt-[88px] flex-col rounded-[14px] outline-offset-[10px] target:outline target:outline-2 target:outline-[#69518C]">
                <p className={label}>For sequencing labs</p>
                <h3 className="mt-3 text-balance text-[22px] font-semibold leading-[1.25] tracking-[-0.02em] text-[#24212B]">What to add to the next run.</h3>
                <p className="mt-2 max-w-[46ch] text-[15.5px] leading-[1.6] text-[#4A4652]">The same calls as step 1, with the fields this result doesn&apos;t carry left visibly empty.</p>
                <FieldsCard vcf={data.steps.vcf} missing={data.labFacts} />
              </article>
            </Rise>
            <Rise delay={0.08} className="h-full min-w-0">
              <article id="hospitals" className="flex h-full min-w-0 scroll-mt-[88px] flex-col rounded-[14px] outline-offset-[10px] target:outline target:outline-2 target:outline-[#69518C]">
                <p className={label}>For hospital oncology teams</p>
                <h3 className="mt-3 text-balance text-[22px] font-semibold leading-[1.25] tracking-[-0.02em] text-[#24212B]">What to check before acting.</h3>
                <p className="mt-2 max-w-[46ch] text-[15.5px] leading-[1.6] text-[#4A4652]">Evidence that wasn&apos;t recorded or assessed, ending at the person who decides.</p>
                <CheckRail rows={data.clinicFacts} more={data.clinicMore} />
              </article>
            </Rise>
          </div>
        </div>
      </section>

      <section id="methods" data-dark aria-labelledby="methods-title" className="scroll-mt-[88px] bg-[#25202F] py-16 text-[#F7F5F0] lg:py-24">
        <div className={wrap}>
          <SectionHead id="methods-title" kicker="Methods, limits and source code" title="Every ranking follows a published rule." dark wide>
            Drugs are grouped by their OncoKB level, then ranked within the group by a weighted evidence score. The figure shows the mapping; its limits follow, starting with: not clinically validated.
          </SectionHead>
          <Rise>
            <Ladder mark={data.ladder} used={data.usedSources} />
          </Rise>
          <ul className="mt-12 grid border-t border-[#F7F5F0]/14 lg:grid-cols-3">
            {[
              ["Ranking algorithm", "How evidence is normalized, weighted and adjusted by post-hoc rules.", "METHODS.md · Ranking algorithm", `${METHODS_URL}#ranking-algorithm`],
              ["Evidence sources", "What each database contributes, and how a missing source is handled.", "METHODS.md · Evidence sources", `${METHODS_URL}#evidence-sources`],
              ["Source code", "The full pipeline and interface, MIT licensed.", "github.com/immortal71/openoncology", REPO_URL],
            ].map(([t, d, file, href], i) => (
              <li key={t} className={`min-w-0 border-b border-[#F7F5F0]/14 lg:border-b-0 lg:border-[#F7F5F0]/14 ${i > 0 ? "lg:border-l lg:pl-8" : ""} ${i < 2 ? "lg:pr-8" : ""}`}>
                <a
                  href={href}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex h-full min-w-0 flex-col py-7 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#F7F5F0]"
                >
                  <span className="flex items-center justify-between gap-4">
                    <span className="text-[18px] font-semibold tracking-[-0.02em] decoration-[#B9A8EC]/60 underline-offset-[5px] group-hover:underline">{t}</span>
                    <ArrowUpRight size={18} aria-hidden="true" className="shrink-0 text-[#B9A8EC] transition-transform duration-150 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                  </span>
                  <span className="mt-2 block text-[14.5px] leading-relaxed text-[#F7F5F0]/70">{d}</span>
                  <span className="mt-auto break-words pt-4 font-mono text-[12.5px] text-[#C7BBF2]">{file}</span>
                  {newTab}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section data-quiet aria-labelledby="faq-title" className="py-16 lg:py-24">
        <div className={`${wrap} grid gap-8 lg:grid-cols-12 lg:gap-6`}>
          <Rise className="lg:sticky lg:top-28 lg:col-span-5 lg:self-start">
            <p className={label}>FAQ</p>
            <h2 id="faq-title" className={`mt-4 ${h2}`}>
              Before you trust it.
            </h2>
            <dl className="mt-8 max-w-[22rem] divide-y divide-[#E2DEE6] border-y border-[#E2DEE6] text-[14px]">
              {[
                ["Status", "Research prototype"],
                ["Input", "Tumor variant calls (VCF)"],
                ["Hosted workspace", "Planned, not available yet"],
                ["License", "MIT, open source"],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 py-2.5">
                  <dt className="text-[#625E68]">{k}</dt>
                  <dd className="text-right font-medium text-[#24212B]">{v}</dd>
                </div>
              ))}
            </dl>
          </Rise>
          <dl className="lg:col-span-6 lg:col-start-7">
            {FAQ.map((f) => (
              <div key={f.q} className="border-t border-[#E2DEE6] py-6 first:border-t-0 first:pt-0 lg:first:border-t lg:first:pt-6">
                <dt className="text-[18px] font-semibold tracking-[-0.01em] text-[#24212B]">{f.q}</dt>
                <dd className="mt-2 max-w-[56ch] text-[16px] leading-[1.6] text-[#4A4652]">{f.a}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section data-dark aria-labelledby="close-title" className="bg-[#25202F] text-[#F7F5F0]">
        <div ref={closing} className="relative overflow-hidden">
          <div ref={closingArt} className="pointer-events-none absolute inset-y-0 left-[40%] right-0 hidden [mask-image:linear-gradient(to_bottom,transparent,#000_18%,#000_80%,transparent)] md:block">
            <EvidenceRibbon layout="hero" tone="dark" threads={110} trace={false} className="absolute inset-0" />
          </div>
          <ClosingThread wrap={closing} art={closingArt} target={closingCta} />
          <div className={`${wrap} relative py-20 lg:py-28`}>
            <p className="text-[12.5px] font-semibold uppercase tracking-[0.06em] text-[#F7F5F0]/70">Demo case · KRAS G12C, non-small cell lung cancer</p>
            <h2 id="close-title" className="mt-5 max-w-[760px] text-balance text-[40px] font-semibold leading-[1.03] tracking-[-0.04em] sm:text-[56px] lg:text-[68px]">
              Follow the evidence from variant to drug.
            </h2>
            <div className="mt-10 flex flex-col items-start gap-5">
              <Link
                ref={closingCta}
                data-spine-dock=""
                href={data.demoHref}
                className="group inline-flex h-12 items-center gap-2 rounded-[8px] bg-[#B9A8EC] px-6 text-[15px] font-semibold text-[#25202F] transition-colors duration-150 hover:bg-[#CFC2F5] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#F7F5F0]"
              >
                {CTA_LABEL}
                <ArrowRight size={16} aria-hidden="true" />
              </Link>
              <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
                {[
                  ["Read the methods", METHODS_URL],
                  ["Run it on your own VCF", `${REPO_URL}#run-locally`],
                ].map(([t, href]) => (
                  <a
                    key={t}
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex min-h-[44px] items-center gap-1 text-[15px] font-medium text-[#E6E1EE] underline decoration-[#E6E1EE]/30 underline-offset-[5px] hover:decoration-[#E6E1EE] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#F7F5F0]"
                  >
                    {t} <ArrowUpRight size={15} aria-hidden="true" />
                    {newTab}
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer data-dark className="bg-[#1C1825] text-[#F7F5F0]">
        <div className={`${wrap} grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-12 lg:gap-6`}>
          <div className="lg:col-span-6">
            <p className="text-[15px] font-semibold">OpenOncology</p>
            <p className="mt-3 max-w-[22rem] text-[13.5px] leading-relaxed text-[#F7F5F0]/70">Open-source tumor evidence matching for sequencing labs and hospital oncology teams.</p>
          </div>
          {[
            { h: "Product", l: [["Demo case", data.demoHref, false], ["How it works", "#how-it-works", false]] },
            { h: "Audiences", l: [["For sequencing labs", "#labs", false], ["For hospital teams", "#hospitals", false]] },
            { h: "Methods & source", l: [["Methods", METHODS_URL, true], ["GitHub", REPO_URL, true], ["Report an issue", `${REPO_URL}/issues`, true], ["MIT license", `${REPO_URL}/blob/main/LICENSE`, true]] },
          ].map((g) => (
            <div key={g.h} className="lg:col-span-2">
              <p className="text-[12.5px] font-semibold uppercase tracking-[0.06em] text-[#B6A9CC]">{g.h}</p>
              <ul className="mt-3">
                {g.l.map(([t, href, ext]) => (
                  <li key={t as string}>
                    <a
                      href={href as string}
                      {...(ext ? { target: "_blank", rel: "noreferrer" } : {})}
                      className="inline-flex min-h-[44px] items-center text-[14px] text-[#F7F5F0]/80 transition-colors duration-150 hover:text-[#F7F5F0] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#F7F5F0]"
                    >
                      {t}
                      {ext ? newTab : null}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="border-t border-[#F7F5F0]/10">
          <p className={`${wrap} py-5 text-[13px] leading-[1.6] text-[#B9B1C9]`}>MIT license · Research prototype, not a medical device · Every result needs oncologist review · The demo is a sample case, not a real patient</p>
        </div>
      </footer>
      <PageSpine root={root} />
    </div>
  );
}
