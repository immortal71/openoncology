"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { useGSAP } from "@gsap/react";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { EvidenceRibbon, type ThreadNode } from "@/components/atlas/evidence-ribbon";
import { ProductShot, type ShotData } from "@/components/atlas/product-shot";
import { WorkspaceLoop } from "@/components/atlas/product-loop";
import type { StepVisualData } from "@/components/atlas/step-visuals";
import { ClosingThread, StoryThread } from "@/components/atlas/story-thread";
import { LadderTiers } from "@/components/atlas/ladder-tiers";
import { RuleTrace, type TraceMode } from "@/components/atlas/rule-trace";
import { CaseLoops } from "@/components/atlas/case-loops";

gsap.registerPlugin(ScrollTrigger, SplitText, useGSAP);


export type AtlasData = {
  demoHref: string;
  shot: ShotData;
  steps: StepVisualData;
  heroNodes: ThreadNode[];
  compactNodes: ThreadNode[];
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
const CTA_LABEL = "Get early access";

function heroStrands(sources: string[]) {
  const has = (name: string) => sources.some((s) => s === name || s.startsWith(`${name} `));
  return { used: SOURCES.filter((s) => has(s.name)).map((s) => s.name), absent: SOURCES.filter((s) => !has(s.name)).map((s) => s.name) };
}

const wrap = "mx-auto w-full max-w-[1280px] px-5 md:px-10";
const h2 = "text-balance text-[30px] font-semibold leading-[1.1] tracking-[-0.035em] text-[#24212B] sm:text-[36px] lg:text-[40px] lg:leading-[46px]";
const label = "text-[12.5px] font-semibold uppercase tracking-[0.06em] text-[#625E68]";
const aside = "max-w-[30rem] text-pretty text-[17px] leading-[1.6] text-[#4A4652] lg:col-span-5 lg:col-start-7";
const focus = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#69518C]";
const primaryBtn = `group inline-flex h-12 items-center justify-center gap-2 rounded-[8px] bg-[#25202F] px-6 text-[15px] font-medium leading-[20px] text-[#F7F5F0] transition-[background-color,transform] duration-150 hover:bg-[#3A3446] active:scale-[0.96] ${focus}`;
const textLink = `inline-flex min-h-[44px] items-center gap-1 text-[15px] font-medium text-[#24212B] underline decoration-[#24212B]/25 underline-offset-[5px] transition-colors duration-150 hover:decoration-[#24212B] ${focus}`;
const newTab = <span className="sr-only">(opens in a new tab)</span>;

function Rise({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={className}>{children}</div>;
}

function SectionHead({ id, title, children, dark = false, wide = false }: { id: string; title: React.ReactNode; children?: React.ReactNode; dark?: boolean; wide?: boolean }) {
  return (
    <Rise className="grid gap-5 lg:grid-cols-12 lg:items-end lg:gap-6">
      <div className={wide ? "lg:col-span-7" : "lg:col-span-6"}>
        <h2 id={id} className={dark ? h2.replace("text-[#24212B]", "text-[#F7F5F0]") : h2}>
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

function Workflow() {
  return (
    <Rise className="mt-12 grid items-center gap-8 lg:mt-16 lg:grid-cols-[1.6fr_1fr] lg:gap-14">
      <Image
        src="/kras-g12c-panel.svg"
        alt="KRAS G12C. The eight P-loop residues read G A C G V G K S. The raised violet C marks the glycine-to-cysteine substitution at residue 12."
        width={780}
        height={295}
        unoptimized
        className="h-auto w-full"
      />
      <ol className="divide-y divide-[#DCD7DF]">
        {STEPS.map((step) => (
          <li key={step.key} className="py-5 first:pt-0 last:pb-0">
            <h3 className="text-[21px] font-semibold tracking-[-0.025em] text-[#24212B]">{step.title}</h3>
            <p className="mt-2 max-w-[42ch] text-[15px] leading-relaxed text-[#625E68]">{step.body}</p>
          </li>
        ))}
      </ol>
    </Rise>
  );
}

function Ladder({ mark, used: raw, shot }: { mark: AtlasData["ladder"]; used: string[]; shot: ShotData }) {
  const used = raw.filter((n) => SOURCES.some((s) => s.name === n));
  const [mode, setMode] = useState<TraceMode>("level1");
  const cases = shot.ws.candidates.map((c) => ({ name: c.name, score: c.score?.toFixed(2) ?? "—", tag: c.tier === "fda_approved" && mark ? `OncoKB Level ${mark.code}` : "Repurposing candidate" }));
  const pair = shot.ws.nearTies[0];
  const ia = pair ? cases.findIndex((c) => c.name === pair.above) : -1;
  const ib = pair ? cases.findIndex((c) => c.name === pair.name) : -1;
  const tie = ia >= 0 && ib === ia + 1 ? { at: [ia, ib] as [number, number], gap: (Number(cases[ia].score) - Number(cases[ib].score)).toFixed(2) } : null;
  return (
    <figure className="mt-14">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-[15px] font-semibold text-[#F7F5F0]">How an OncoKB level decides where a drug lands</span>
        <span className="text-[13px] text-[#F7F5F0]/60">The mapping the ranking uses, as written in the methods</span>
      </figcaption>
      <div className="mt-4">
        <LadderTiers names={mark?.names ?? ""} level={mark?.code ?? null} r1={mode === "r1"} />
      </div>
      <RuleTrace mode={mode} onMode={setMode} cases={cases} tie={tie} />
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
          <div ref={art} data-art className="pointer-events-none absolute inset-y-0 left-[56%] right-0 hidden [mask-image:linear-gradient(to_bottom,transparent,#000_10%,#000_58%,transparent_94%)] lg:block">
            <EvidenceRibbon layout="hero" threads={56} weight={0.6} trace={false} className="absolute inset-0" />
          </div>
          <div className={`${wrap} pointer-events-none absolute inset-x-0 top-5 hidden justify-end lg:flex`}>
            <p className="text-[12px] leading-[18px] text-[#625E68]">Illustrative evidence pathway · demo case</p>
          </div>
          <div className={`${wrap} pointer-events-none relative flex flex-col justify-center pb-7 pt-10 lg:h-[clamp(470px,calc(100svh-340px),560px)] lg:pb-10 lg:pt-2`}>
            <div className="pointer-events-auto max-w-[560px] lg:w-[46%]">
              <h1
                id="hero-title"
                ref={headline}
                className="text-balance text-[clamp(34px,9.4vw,42px)] font-semibold leading-[1.06] tracking-[-0.035em] sm:text-[56px] lg:text-[clamp(52px,7.2vh,64px)]"
              >
                Tumor mutations, matched to cancer drug evidence.
              </h1>
              <p data-hero-in className="mt-5 max-w-[32rem] text-pretty text-[17px] leading-[1.55] text-[#4A4652] lg:text-[18px] lg:leading-[28px]">
                Sequencing labs and oncology teams can review ranked drug candidates alongside the evidence and gaps behind each match.
              </p>
              <div data-hero-in className="mt-6 flex flex-wrap items-center gap-x-7 gap-y-3">
                <Link href={data.demoHref} className={primaryBtn}>
                  Submit case files
                  <ArrowRight size={16} aria-hidden="true" />
                </Link>
                <a href={METHODS_URL} target="_blank" rel="noreferrer" className={textLink}>
                  Read the methods <ArrowUpRight size={15} aria-hidden="true" />
                  {newTab}
                </a>
              </div>
              <p data-hero-in className="flex flex-wrap items-center mt-5 gap-x-2 gap-y-1 text-[12px] text-[#625E68]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#69518C]" />
                <span>Research prototype</span>
                <span aria-hidden="true" className="hidden sm:inline">
                  ·
                </span>
                <span className="hidden sm:inline">Open source</span>
                <span aria-hidden="true">·</span>
                <span>Oncologist review required</span>
              </p>
            </div>
          </div>
          <div className="lg:hidden">
            <div className="relative h-[96px] [mask-image:linear-gradient(to_bottom,#000_40%,transparent_92%)]">
              <EvidenceRibbon layout="compact" threads={56} trace={false} className="absolute inset-0" />
              <p className="absolute left-5 top-2 text-[12.5px] text-[#625E68]">Illustrative evidence pathway · demo case</p>
            </div>
            <ol className="relative mx-5 mb-2 grid grid-cols-3 gap-x-3 border-t border-[#C8BED2] pt-3">
              {data.compactNodes.map((n, i) => (
                <li key={n.label} className="relative">
                  <span aria-hidden="true" className={`absolute left-0 -top-[17px] h-2 w-2 rounded-full border-2 border-[#F7F5F0] ${i === data.compactNodes.length - 1 ? "bg-[#69518C]" : "bg-[#8270A4]"}`} />
                  <p className="font-mono text-[12px] uppercase tracking-[0.06em] text-[#5B5566]">
                    <span className="mr-2 text-[#69518C]">0{i + 1}</span>
                    {n.label}
                  </p>
                  <p className={`mt-1 break-words text-[14px] leading-tight font-semibold ${n.accent ? "text-[#523E70]" : "text-[#24212B]"}`}>{n.value}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>
        <StoryThread wrap={story} art={art} nodes={data.heroNodes} strands={heroStrands(data.shot.list[0]?.sources ?? [])} />

        <section id="product" aria-labelledby="proof-title" className="relative z-10 scroll-mt-[88px] pb-16 pt-6 lg:pb-24 lg:pt-0">
          <div className={wrap}>
            <div className="grid items-center gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
              <div className="max-w-[390px]">
                <h2 id="proof-title" className="text-[32px] font-semibold leading-[1.12] tracking-[-0.03em] text-[#24212B]">Why did Sotorasib rank first?</h2>
                <p className="mt-5 text-[16px] leading-7 text-[#625E68]">In the KRAS G12C demo case, two candidates rank closely. Select a candidate to see the evidence behind its score.</p>
                <Link href="/lab/results" className="mt-6 inline-block text-sm font-medium text-[#5B4381] underline underline-offset-4">Explore the demo case →</Link>
              </div>
              <ProductShot data={data.shot} />
            </div>
          </div>
        </section>
      </div>

      <section id="how-it-works" aria-labelledby="how-title" className="scroll-mt-[88px] border-t border-[#E2DEE6] py-16 lg:py-24">
        <div className={wrap}>
          <SectionHead
            id="how-title"
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
          <Workflow />
          <CaseLoops ws={data.shot.ws} />
        </div>
      </section>

            <section id="workspace" data-dark aria-labelledby="workspace-title" className="scroll-mt-[88px] bg-[#151419] py-20 lg:py-28">
        <div className={wrap}>
          <div className="lg:px-12">
            <WorkspaceLoop data={data.shot} />
          </div>
        </div>
      </section>

      <section id="methods" data-dark aria-labelledby="methods-title" className="scroll-mt-[88px] bg-[#25202F] py-16 text-[#F7F5F0] lg:py-24">
        <div className={wrap}>
          <SectionHead id="methods-title" title="Every ranking follows a published rule." dark wide>
            Drugs are grouped by their OncoKB level, then ranked within the group by a weighted evidence score. The figure shows the mapping; its limits follow, starting with: not clinically validated.
          </SectionHead>
          <Rise>
            <Ladder mark={data.ladder} used={data.usedSources} shot={data.shot} />
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
            <h2 id="faq-title" className={h2}>
              <span className="sr-only">FAQ: </span>Before you trust it.
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
            <EvidenceRibbon layout="hero" tone="dark" threads={56} trace={false} className="absolute inset-0" />
          </div>
          <ClosingThread wrap={closing} art={closingArt} target={closingCta} />
          <div className={`${wrap} relative py-20 lg:py-28`}>
            <p className="text-[12.5px] font-semibold uppercase tracking-[0.06em] text-[#F7F5F0]/70">Illustrative case · KRAS G12C, non-small cell lung cancer</p>
            <h2 id="close-title" className="mt-5 max-w-[760px] text-balance text-[40px] font-semibold leading-[1.03] tracking-[-0.04em] sm:text-[56px] lg:text-[68px]">
              Follow the evidence from variant to drug.
            </h2>
            <div className="mt-10 flex flex-col items-start gap-5">
              <Link
                ref={closingCta}
                data-spine-dock=""
                href={data.demoHref}
                className="group inline-flex h-12 items-center gap-2 rounded-[8px] bg-[#B9A8EC] px-6 text-[15px] font-semibold text-[#25202F] transition-[background-color,transform] duration-150 hover:bg-[#CFC2F5] active:scale-[0.96] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#F7F5F0]"
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
            { h: "Product", l: [["Get early access", data.demoHref, false], ["How it works", "#how-it-works", false]] },
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

    </div>
  );
}
