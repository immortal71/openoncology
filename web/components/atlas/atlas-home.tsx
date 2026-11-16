"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { useGSAP } from "@gsap/react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { EvidenceRibbon, type ThreadNode } from "@/components/atlas/evidence-ribbon";
import { ProductShot, type ShotData } from "@/components/atlas/product-shot";
import { StepVisual, type StepVisualData } from "@/components/atlas/step-visuals";

gsap.registerPlugin(ScrollTrigger, SplitText, useGSAP);

export type AtlasData = {
  demoHref: string;
  shot: ShotData;
  steps: StepVisualData;
  heroNodes: ThreadNode[];
  compactNodes: ThreadNode[];
};

const METHODS_URL = "https://github.com/immortal71/openoncology/blob/main/docs/METHODS.md";
const REPO_URL = "https://github.com/immortal71/openoncology";
const SOURCES = ["OncoKB", "CIViC", "ClinVar", "OpenTargets", "ChEMBL", "AlphaMissense"];
const EASE = [0.22, 1, 0.36, 1] as const;
const CTA_LABEL = "View the demo case";

const wrap = "mx-auto w-full max-w-[1280px] px-5 md:px-10";
const h2 = "text-[30px] font-semibold leading-[1.1] tracking-[-0.035em] text-[#24212B] sm:text-[36px] lg:text-[38px] lg:leading-[44px]";
const label = "text-[12.5px] font-semibold uppercase tracking-[0.06em] text-[#625E68]";
const section = "py-14 lg:py-24";
const focus = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#69518C]";
const primaryBtn = `group inline-flex h-12 items-center justify-center gap-2 rounded-[8px] bg-[#25202F] px-6 text-[15px] font-medium leading-[20px] text-[#F7F5F0] transition-colors duration-150 hover:bg-[#3A3446] ${focus}`;
const textLink = `inline-flex items-center gap-1 text-[15px] font-medium text-[#24212B] underline decoration-[#24212B]/25 underline-offset-[5px] transition-colors duration-150 hover:decoration-[#24212B] ${focus}`;

function Rise({ children, className, delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.8, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

function Eyebrow({ children, dark = false }: { children: React.ReactNode; dark?: boolean }) {
  return (
    <p className={`flex items-center gap-2.5 text-[13.5px] font-medium ${dark ? "text-[#F7F5F0]/80" : "text-[#24212B]"}`}>
      <span aria-hidden="true" className="flex items-center">
        <span className={`h-[1.5px] w-5 ${dark ? "bg-[#B9A8EC]" : "bg-[#69518C]"}`} />
        <span className={`h-[7px] w-[7px] rounded-full ${dark ? "bg-[#B9A8EC]" : "bg-[#69518C]"}`} />
      </span>
      {children}
    </p>
  );
}

const STEPS = [
  {
    key: "variant",
    title: "Variant context",
    body: "Start from the variant calls your sequencing run already produces. Each variant is matched to its evidence level, and anything the result doesn't contain is stated.",
    caption: "01 · Input",
    value: "Tumor variant calls (VCF)",
  },
  {
    key: "evidence",
    title: "Candidate evidence",
    body: "Drugs are matched against curated evidence, grouped by clinical context and ranked within the case. Every row names the evidence behind it.",
    caption: "02 · Output",
    value: "Ranked candidates, grouped by context",
  },
  {
    key: "review",
    title: "Professional review",
    body: "The shortlist is a starting point for an oncologist, not a decision. Nothing is acted on until a clinician has reviewed the evidence.",
    caption: "03 · Decision",
    value: "Made by the oncologist, outside the app",
  },
] as const;

function Workflow({ data }: { data: StepVisualData }) {
  const [active, setActive] = useState(0);
  const reduce = useReducedMotion();
  const current = STEPS[active];
  return (
    <div className="mt-12 grid gap-10 lg:mt-14 lg:grid-cols-12 lg:items-start lg:gap-6">
      <ol className="min-w-0 border-b border-[#E2DEE6] lg:col-span-5">
        {STEPS.map((s, i) => {
          const open = active === i;
          return (
            <li key={s.key} className="border-t border-[#E2DEE6]">
              <h3>
                <button type="button" aria-expanded={open} aria-controls={`step-${s.key}`} onClick={() => setActive(i)} className={`flex w-full items-baseline gap-4 py-5 text-left ${focus}`}>
                  <span className={`font-mono text-[12px] ${open ? "text-[#69518C]" : "text-[#625E68]"}`}>0{i + 1}</span>
                  <span className={`text-[20px] font-semibold tracking-[-0.02em] transition-colors duration-150 ${open ? "text-[#24212B]" : "text-[#625E68] hover:text-[#24212B]"}`}>{s.title}</span>
                </button>
              </h3>
              <AnimatePresence initial={false}>
                {open ? (
                  <motion.div
                    id={`step-${s.key}`}
                    initial={{ height: 0 }}
                    animate={{ height: "auto" }}
                    exit={{ height: 0 }}
                    transition={reduce ? { duration: 0 } : { duration: 0.2, ease: EASE }}
                    className="overflow-hidden"
                  >
                    <p className="max-w-[48ch] pb-6 pr-4 text-[16px] leading-[1.6] text-[#625E68] sm:pl-9">{s.body}</p>
                    <div className="pb-8 lg:hidden">
                      <StepVisual kind={s.key} caption={s.caption} value={s.value} data={data} />
                    </div>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </li>
          );
        })}
      </ol>
      <div className="relative hidden h-[384px] lg:col-span-6 lg:col-start-7 lg:block">
        <AnimatePresence initial={false}>
          <motion.div
            key={current.key}
            className="absolute inset-0"
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduce ? undefined : { opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            <StepVisual kind={current.key} caption={current.caption} value={current.value} data={data} className="max-w-[540px]" />
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

const FAQ = [
  { q: "What input does it take?", a: "Variant calls from a tumor sample, typically a VCF. The demo shows the output for a KRAS G12C non-small cell lung cancer profile." },
  { q: "What does the evidence score mean?", a: "A weighted combination of the evidence found for a drug, used to order candidates within one case. It is not a probability that a patient will respond." },
  { q: "Is this clinical advice?", a: "No. OpenOncology is a research prototype. Every result needs independent review by a licensed oncologist before any treatment decision." },
  { q: "Can we use it today, and what data does the demo hold?", a: "The code is open source; a hosted workspace is planned and there are no hospital deployments yet. The demo is a sample case, not a real patient." },
];

export function AtlasHome({ data }: { data: AtlasData }) {
  const root = useRef<HTMLDivElement>(null);
  const headline = useRef<HTMLHeadingElement>(null);

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
    <div ref={root} className="bg-[#F7F5F0] font-[family-name:var(--font-atlas)] text-[#24212B] antialiased">
      <section aria-labelledby="hero-title" className="relative overflow-hidden">
        <div data-art className="pointer-events-none absolute inset-y-0 left-[50%] right-0 hidden lg:block">
          <EvidenceRibbon layout="hero" nodes={data.heroNodes} className="absolute inset-0" />
          <p className="absolute bottom-6 left-0 text-[12px] leading-[18px] text-[#625E68]">Illustrative evidence pathway · demo case</p>
        </div>
        <div className={`${wrap} pointer-events-none relative flex flex-col justify-center pb-7 pt-10 lg:h-[calc(100svh-72px)] lg:max-h-[720px] lg:min-h-[600px] lg:py-12`}>
          <div className="pointer-events-auto max-w-[560px] lg:w-[46%]">
            <p data-hero-in className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-[#625E68]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#69518C]" />
              <a href={METHODS_URL} target="_blank" rel="noreferrer" className={`underline decoration-[#625E68]/40 underline-offset-4 hover:decoration-[#24212B] ${focus}`}>
                Research prototype
              </a>
              <span aria-hidden="true" className="hidden sm:inline">
                ·
              </span>
              <span className="hidden sm:inline">Open source</span>
              <span aria-hidden="true">·</span>
              <span>Oncologist review required</span>
            </p>
            <h1 id="hero-title" ref={headline} className="mt-6 text-balance text-[42px] font-semibold leading-[1.06] tracking-[-0.035em] sm:text-[56px] lg:text-[64px] lg:leading-[68px]">
              Drug evidence, connected to the tumor.
            </h1>
            <p data-hero-in className="mt-6 max-w-[30rem] text-[17px] leading-[1.55] text-[#625E68] lg:text-[18px] lg:leading-[28px]">
              For sequencing labs and hospital oncology teams reviewing tumor variants, drug candidates and their supporting evidence.
            </p>
            <div data-hero-in className="mt-7 flex flex-wrap items-center gap-x-7 gap-y-4">
              <Link href={data.demoHref} className={primaryBtn}>
                {CTA_LABEL}
                <ArrowRight size={16} aria-hidden="true" />
              </Link>
              <a href={METHODS_URL} target="_blank" rel="noreferrer" className={textLink}>
                Read the methods <ArrowUpRight size={15} aria-hidden="true" />
              </a>
            </div>
          </div>
        </div>
        <div className="relative h-[250px] lg:hidden">
          <EvidenceRibbon layout="compact" nodes={data.compactNodes} threads={110} className="absolute inset-0" />
          <p className="absolute left-5 top-2 text-[12.5px] text-[#625E68]">Illustrative evidence pathway · demo case</p>
        </div>
      </section>

      <section aria-label="Evidence sources" className="border-y border-[#E2DEE6]">
        <div className={`${wrap} flex flex-col gap-3 py-6 md:flex-row md:items-center md:justify-between`}>
          <p className="text-[13px] text-[#625E68]">Evidence providers the prototype draws on</p>
          <ul className="flex flex-wrap gap-x-6 gap-y-2 font-mono text-[13px] text-[#24212B]/75">
            {SOURCES.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      </section>

      <section id="product" aria-labelledby="proof-title" className="scroll-mt-[96px] py-14 lg:py-20">
        <div className={wrap}>
          <Rise>
            <Eyebrow>Inside the demo</Eyebrow>
            <h2 id="proof-title" className={`mt-4 ${h2}`}>
              See why a candidate appears.
            </h2>
          </Rise>
        </div>
        <div className="mx-auto mt-8 w-full max-w-[1240px] px-5 md:px-10 lg:mt-10">
          <ProductShot data={data.shot} />
        </div>
        <div className={`${wrap} mt-8 grid gap-4 lg:grid-cols-12 lg:gap-6`}>
          <p className="max-w-[34rem] text-[17px] leading-[1.6] text-[#625E68] lg:col-span-7">
            Pick a candidate to see what it was matched on, its evidence level and which source information this result does and doesn&apos;t store.
          </p>
          <p className="text-[14px] leading-[1.6] text-[#625E68] lg:col-span-4 lg:col-start-9">
            Values from the demo case output. Research prototype, not a real patient.
          </p>
        </div>
      </section>

      <section aria-labelledby="audience-title" className="border-t border-[#E2DEE6] py-12 lg:py-[72px]">
        <div className={wrap}>
          <Rise>
            <p className={label}>Who it&apos;s for</p>
            <h2 id="audience-title" className={`mt-4 max-w-[20ch] ${h2}`}>
              One case, two teams.
            </h2>
          </Rise>
          <div className="mt-10 grid border-t border-[#E2DEE6] md:grid-cols-2">
            {[
              {
                id: "labs",
                k: "For sequencing labs",
                t: "Bring interpretation evidence into view.",
                d: "You already produce the variant calls. OpenOncology lines up the drug evidence for each case, so a report carries more than a list of mutations.",
                items: ["Start from variant calls in a VCF", "Evidence levels per variant, with gaps stated", "A ranked shortlist for each case"],
              },
              {
                id: "hospitals",
                k: "For hospital oncology teams",
                t: "Inspect the evidence behind the shortlist.",
                d: "Without a molecular tumor board, the evidence still has to be checked. Each candidate shows its tumor context and where its evidence came from.",
                items: ["Evidence read in the tumor's context", "Where each evidence level came from, or that it wasn't recorded", "The decision stays with the oncologist"],
              },
            ].map((a, i) => (
              <Rise key={a.id} delay={i * 0.08} className={`py-8 ${i === 1 ? "border-t border-[#E2DEE6] md:border-l md:border-t-0 md:pl-12" : "md:pr-12"}`}>
                <div id={a.id} className="scroll-mt-[96px]">
                  <p className={label}>{a.k}</p>
                  <h3 className="mt-4 text-[24px] font-semibold leading-[1.2] tracking-[-0.03em] text-[#24212B] sm:text-[26px]">{a.t}</h3>
                  <p className="mt-4 max-w-[30rem] text-[16.5px] leading-[1.6] text-[#625E68]">{a.d}</p>
                  <ul className="mt-7 border-b border-[#E2DEE6]">
                    {a.items.map((it) => (
                      <li key={it} className="flex gap-3 border-t border-[#E2DEE6] py-3 text-[15px] text-[#24212B]">
                        <span aria-hidden="true" className="mt-[8px] h-[5px] w-[5px] shrink-0 rounded-full bg-[#B5B0BA]" />
                        {it}
                      </li>
                    ))}
                  </ul>
                </div>
              </Rise>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" aria-labelledby="how-title" className={`scroll-mt-[96px] border-t border-[#E2DEE6] ${section}`}>
        <div className={wrap}>
          <Rise className="grid gap-5 lg:grid-cols-12 lg:items-end lg:gap-6">
            <div className="lg:col-span-6">
              <p className={label}>How it works</p>
              <h2 id="how-title" className={`mt-4 ${h2}`}>
                What goes in, what comes out, who decides.
              </h2>
            </div>
            <p className="max-w-[30rem] text-[17px] leading-[1.6] text-[#625E68] lg:col-span-5 lg:col-start-8">
              From the file your lab already has to a shortlist an oncologist can check line by line.
            </p>
          </Rise>
          <Workflow data={data.steps} />
        </div>
      </section>

      <section id="methods" aria-labelledby="methods-title" className="scroll-mt-[96px] bg-[#25202F] py-16 text-[#F7F5F0] lg:py-28">
        <div className={wrap}>
          <Rise className="grid gap-5 lg:grid-cols-12 lg:items-end lg:gap-6">
            <div className="lg:col-span-6">
              <p className="text-[12.5px] font-semibold uppercase tracking-[0.06em] text-[#F7F5F0]/60">Methods, limits and source code</p>
              <h2 id="methods-title" className="mt-4 text-[30px] font-semibold leading-[1.1] tracking-[-0.035em] sm:text-[36px] lg:text-[40px]">
                Built to be inspected.
              </h2>
            </div>
            <p className="max-w-[30rem] text-[17px] leading-[1.6] text-[#F7F5F0]/65 lg:col-span-5 lg:col-start-8">
              How candidates are matched and ranked, which sources are used and what the evaluation does and doesn&apos;t show. The code is MIT
              licensed; a hosted workspace is planned, not available yet.
            </p>
          </Rise>
          <ul className="mt-12 grid border-t border-[#F7F5F0]/15 md:grid-cols-3">
            {[
              ["Matching methods", "How variants are normalised and matched to evidence.", METHODS_URL],
              ["Sources and versions", "Which databases are used, and how a missing source is handled.", METHODS_URL],
              ["Source code", "The full pipeline and interface, MIT licensed.", REPO_URL],
            ].map(([t, d, href], i) => (
              <li key={t} className={`border-b border-[#F7F5F0]/15 md:border-b-0 ${i > 0 ? "md:border-l md:pl-8" : ""} ${i < 2 ? "md:pr-8" : ""}`}>
                <a href={href} target="_blank" rel="noreferrer" className="group block py-7 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#F7F5F0]">
                  <span className="flex items-center justify-between gap-4">
                    <span className="text-[18px] font-semibold tracking-[-0.02em]">{t}</span>
                    <ArrowUpRight size={18} aria-hidden="true" className="text-[#B9A8EC] transition-colors duration-150 group-hover:text-[#F7F5F0]" />
                  </span>
                  <span className="mt-2 block text-[14.5px] leading-relaxed text-[#F7F5F0]/60">{d}</span>
                </a>
              </li>
            ))}
          </ul>

        </div>
      </section>

      <section aria-labelledby="faq-title" className="py-14 lg:py-20">
        <div className={wrap}>
          <Rise>
            <p className={label}>Questions</p>
            <h2 id="faq-title" className={`mt-4 ${h2}`}>
              Plain answers.
            </h2>
          </Rise>
          <dl className="mt-12 grid gap-x-12 md:grid-cols-2">
            {FAQ.map((f) => (
              <div key={f.q} className="border-t border-[#E2DEE6] py-6">
                <dt className="text-[17px] font-semibold tracking-[-0.01em] text-[#24212B]">{f.q}</dt>
                <dd className="mt-2 max-w-[34rem] text-[15.5px] leading-[1.6] text-[#625E68]">{f.a}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section aria-labelledby="close-title" className="bg-[#25202F] text-[#F7F5F0]">
        <div className="relative overflow-hidden">
          <EvidenceRibbon layout="closing" tone="dark" threads={120} thread={false} className="pointer-events-none absolute inset-y-0 left-[50%] right-0 hidden md:block" />
          <div className={`${wrap} relative py-24 lg:py-32`}>
            <h2 id="close-title" className="max-w-[14ch] text-[38px] font-semibold leading-[1.04] tracking-[-0.04em] sm:text-[56px]">
              See the case for yourself.
            </h2>
            <div className="mt-10 flex flex-wrap items-center gap-x-7 gap-y-4">
              <Link
                href={data.demoHref}
                className="group inline-flex h-12 items-center gap-2 rounded-md bg-[#F7F5F0] px-5 text-[15px] font-medium text-[#25202F] transition-colors duration-150 hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#F7F5F0]"
              >
                {CTA_LABEL}
                <ArrowRight size={16} aria-hidden="true" />
              </Link>
              <a
                href={METHODS_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-[15px] font-medium text-[#F7F5F0] underline decoration-[#F7F5F0]/30 underline-offset-[5px] hover:decoration-[#F7F5F0] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#F7F5F0]"
              >
                Read the methods <ArrowUpRight size={15} aria-hidden="true" />
              </a>
            </div>
          </div>
        </div>
        <footer className="border-t border-[#F7F5F0]/10">
          <div className={`${wrap} grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-[1.4fr_1fr_1fr_1fr]`}>
            <div>
              <p className="text-[15px] font-semibold">OpenOncology</p>
              <p className="mt-3 max-w-[20rem] text-[13.5px] leading-relaxed text-[#F7F5F0]/60">
                Open-source tumor evidence matching. Research prototype, not a medical device. Oncologist review required.
              </p>
            </div>
            {[
              { h: "Product", l: [["Demo case", data.demoHref], ["How it works", "#how-it-works"]] },
              { h: "Audiences", l: [["For sequencing labs", "#labs"], ["For hospital teams", "#hospitals"]] },
              { h: "Methods & source", l: [["Methods", METHODS_URL], ["GitHub", REPO_URL], ["MIT license", `${REPO_URL}/blob/main/LICENSE`]] },
            ].map((g) => (
              <div key={g.h}>
                <p className="text-[12px] font-semibold uppercase tracking-[0.06em] text-[#F7F5F0]/50">{g.h}</p>
                <ul className="mt-4 space-y-2.5">
                  {g.l.map(([t, href]) => (
                    <li key={t}>
                      <a href={href} className="text-[14px] text-[#F7F5F0]/80 transition-colors duration-150 hover:text-[#F7F5F0] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#F7F5F0]">
                        {t}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </footer>
      </section>
    </div>
  );
}
