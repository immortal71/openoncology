"use client";

import { useRef } from "react";
import Image from "next/image";
import Link from "next/link";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { useGSAP } from "@gsap/react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, ArrowUpRight, FileCode2, Link2 } from "lucide-react";
import { VariantField } from "@/components/marketing/variant-field";

gsap.registerPlugin(ScrollTrigger, SplitText, useGSAP);

export type SiteCandidate = { id: string; name: string; score: number; group: string };
export type SiteVariant = { gene: string; short: string; hgvs: string; cancerType: string; level: string; position: number; length: number };

const METHODS_URL = "https://github.com/immortal71/openoncology/blob/main/docs/METHODS.md";
const REPO_URL = "https://github.com/immortal71/openoncology";
const SOURCES = ["OncoKB", "CIViC", "ClinVar", "OpenTargets", "ChEMBL", "AlphaMissense"];
const EASE = [0.22, 1, 0.36, 1] as const;
const CTA_FIELD = { dot: "#FFFFFF", hi: "#F2A6C7", scan: "#B9A9FF" };
const card =
  "rounded-2xl bg-white/[0.9] text-oo-ink ring-1 ring-white/60 backdrop-blur-xl shadow-[0_24px_48px_-28px_rgb(20_12_50/0.55),0_2px_6px_-2px_rgb(20_12_50/0.12)]";

function ResidueTrack({ position, length }: { position: number; length: number }) {
  const at = Math.max(0, Math.min(100, (position / length) * 100));
  return (
    <div className="relative mt-5 pb-4" aria-hidden="true">
      <div className="relative h-4">
        <div className="absolute inset-x-0 top-1/2 h-px bg-oo-ink/60" />
        <div className="absolute top-1/2 h-2.5 -translate-y-1/2 rounded-sm bg-oo-hema/15 ring-1 ring-oo-hema/30" style={{ left: "1%", width: "8.5%" }} />
        <div className="absolute -top-2 h-4 w-px bg-oo-eosin" style={{ left: `${at}%` }} />
        <div className="absolute -top-3 h-2.5 w-2.5 -translate-x-1/2 rounded-full bg-oo-eosin ring-4 ring-oo-eosin/20" style={{ left: `${at}%` }} />
      </div>
      <div className="absolute inset-x-0 bottom-0 flex justify-between font-mono text-[10px] text-oo-ink-3">
        <span>1</span>
        <span>P-loop</span>
        <span>{length} aa</span>
      </div>
    </div>
  );
}

function VariantCard({ variant, className }: { variant: SiteVariant; className?: string }) {
  return (
    <div className={`${card} p-5 ${className ?? ""}`}>
      <div className="flex items-center justify-between font-mono text-[10.5px] uppercase tracking-[0.12em] text-oo-ink-3">
        <span>Input · tumor.vcf</span>
        <span className="rounded-full bg-oo-eosin/10 px-2 py-0.5 normal-case tracking-normal text-[#B23D73]">{variant.cancerType}</span>
      </div>
      <div className="mt-3 text-[30px] font-semibold leading-none tracking-[-0.03em]">
        {variant.gene} <span className="text-oo-eosin">{variant.short}</span>
      </div>
      <div className="mt-2 font-mono text-[13px] text-oo-ink-2">{variant.hgvs}</div>
      <ResidueTrack position={variant.position} length={variant.length} />
    </div>
  );
}

function RankedCard({ candidates, className, compact = false }: { candidates: SiteCandidate[]; className?: string; compact?: boolean }) {
  return (
    <div className={`${card} overflow-hidden ${className ?? ""}`}>
      <div className="flex items-center justify-between border-b border-oo-ink/[0.07] px-5 py-3.5">
        <span className="text-[13px] font-semibold">Ranked candidates</span>
        <span className="font-mono text-[11px] text-oo-ink-3">{candidates.length} drugs</span>
      </div>
      <ol className="divide-y divide-oo-ink/[0.06]">
        {candidates.map((c, i) => (
          <li key={c.id} className={`grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-x-3 px-5 ${compact ? "py-2.5" : "py-3.5"}`}>
            <span className="font-mono text-[11px] text-oo-ink-3">{i + 1}</span>
            <span className="min-w-0">
              <span className={`block truncate font-semibold tracking-[-0.01em] ${compact ? "text-[14px]" : "text-[16px]"}`}>{c.name}</span>
              {compact ? null : <span className="block truncate text-[11.5px] text-oo-ink-3">{c.group}</span>}
            </span>
            <span className="flex items-center gap-2.5">
              <span className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-oo-hema/10 sm:block">
                <span data-bar className="block h-full origin-left rounded-full bg-oo-hema" style={{ width: `${c.score * 100}%` }} />
              </span>
              <span className="font-mono text-[13px] tabular-nums">{c.score.toFixed(2)}</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ReviewPill({ className }: { className?: string }) {
  return (
    <div
      className={`inline-flex items-center gap-2 whitespace-nowrap rounded-full bg-[#1B1430] px-3.5 py-2 text-[12.5px] font-medium text-white shadow-[0_16px_32px_-16px_rgb(20_12_50/0.8)] ring-1 ring-white/10 ${className ?? ""}`}
    >
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-60 motion-reduce:hidden" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-400" />
      </span>
      Awaiting oncologist review
    </div>
  );
}

function Photo({
  src,
  alt,
  position,
  priority = false,
  sizes,
  className,
}: {
  src: string;
  alt: string;
  position?: string;
  priority?: boolean;
  sizes: string;
  className?: string;
}) {
  return (
    <Image
      src={src}
      alt={alt}
      fill
      priority={priority}
      sizes={sizes}
      className={`object-cover contrast-[1.08] saturate-[.85] ${className ?? ""}`}
      style={position ? { objectPosition: position } : undefined}
    />
  );
}

function Grade({ scrim = "bottom" }: { scrim?: "bottom" | "left" | "none" }) {
  return (
    <>
      <div aria-hidden="true" className="absolute inset-0 bg-[#2A1D6B] opacity-25 mix-blend-color" />
      {scrim === "bottom" ? <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-[#140C32]/60 via-transparent to-transparent" /> : null}
      {scrim === "left" ? <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-r from-[#120B2B] via-[#120B2B]/50 to-transparent" /> : null}
    </>
  );
}

function Reveal({ children, delay = 0, className, as = "div" }: { children: React.ReactNode; delay?: number; className?: string; as?: "div" | "li" }) {
  const reduce = useReducedMotion();
  const Tag = as === "li" ? motion.li : motion.div;
  return (
    <Tag
      className={className}
      initial={reduce ? false : { opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.9, ease: EASE, delay }}
    >
      {children}
    </Tag>
  );
}

function ClipPhoto({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { clipPath: "inset(14% 8% 0% 8% round 24px)" }}
      whileInView={{ clipPath: "inset(0% 0% 0% 0% round 24px)" }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 1.2, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

function StepText({ n, title, body, delay }: { n: string; title: string; body: string; delay: number }) {
  return (
    <Reveal delay={delay} className="mt-6 grid gap-x-6 gap-y-2 sm:grid-cols-[3rem_minmax(0,1fr)]">
      <div className="font-mono text-[12px] leading-[1.9] text-oo-hema">{n}</div>
      <div>
        <h3 className="text-[21px] font-semibold tracking-[-0.02em]">{title}</h3>
        <p className="mt-2 max-w-[34rem] text-[15.5px] leading-relaxed text-oo-ink-2">{body}</p>
      </div>
    </Reveal>
  );
}

export function SiteLanding({
  demoHref,
  candidates,
  variant,
  topSources,
  topName,
  topLevel,
  topApproval,
}: {
  demoHref: string;
  candidates: SiteCandidate[];
  variant: SiteVariant;
  topSources: string[];
  topName: string;
  topLevel: string;
  topApproval: string;
}) {
  const root = useRef<HTMLDivElement>(null);
  const headline = useRef<HTMLHeadingElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const dark = useRef<HTMLElement>(null);
  const cta = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        const split = SplitText.create(headline.current, {
          type: "lines",
          mask: "lines",
          autoSplit: true,
          onSplit: (self) => gsap.from(self.lines, { yPercent: 110, duration: 1.15, ease: "power4.out", stagger: 0.09 }),
        });
        gsap.from("[data-intro]", { y: 18, opacity: 0, duration: 0.9, ease: "power3.out", stagger: 0.08, delay: 0.45 });
        gsap.from("[data-stage]", { clipPath: "inset(12% 5% 0% 5% round 40px)", duration: 1.5, ease: "power4.out", delay: 0.35 });
        gsap.from("[data-stage-img]", { scale: 1.16, duration: 2.2, ease: "power3.out", delay: 0.35 });
        gsap.from("[data-float]", { y: 60, opacity: 0, duration: 1.2, ease: "power4.out", stagger: 0.14, delay: 0.9 });
        gsap.from("[data-stage] [data-bar]", { scaleX: 0, duration: 1.1, ease: "power3.out", stagger: 0.1, delay: 1.4 });
        return () => split.revert();
      });
      mm.add("(prefers-reduced-motion: no-preference) and (min-width: 1024px)", () => {
        const scrub = { trigger: stage.current, start: "top 70%", end: "bottom top", scrub: 0.8 };
        gsap.to("[data-stage-img]", { yPercent: 8, ease: "none", scrollTrigger: scrub });
        gsap.to("[data-depth='1']", { yPercent: -22, ease: "none", scrollTrigger: scrub });
        gsap.to("[data-depth='2']", { yPercent: -12, ease: "none", scrollTrigger: scrub });
        const darkScrub = { trigger: dark.current, start: "top bottom", end: "bottom top", scrub: 0.8 };
        gsap.fromTo("[data-dark-img]", { yPercent: -6 }, { yPercent: 6, ease: "none", scrollTrigger: darkScrub });
        gsap.fromTo("[data-dark-card]", { yPercent: 18 }, { yPercent: -18, ease: "none", scrollTrigger: darkScrub });
      });
    },
    { scope: root }
  );

  return (
    <div ref={root} className="bg-oo-paper text-oo-ink">
      <section aria-labelledby="hero-title" className="relative overflow-hidden">
        <div className="mx-auto max-w-[1200px] px-5 pt-14 text-center md:px-8 md:pt-14">
          <span data-intro className="inline-flex items-center gap-2 rounded-full border border-oo-ink/10 bg-white px-3 py-1 text-[13px] font-medium text-oo-ink-2">
            <span className="h-1.5 w-1.5 rounded-full bg-oo-eosin" />
            Open source · Research prototype
          </span>
          <h1
            id="hero-title"
            ref={headline}
            className="mx-auto mt-6 text-balance font-display text-[46px] font-semibold leading-[0.98] tracking-[-0.035em] sm:text-[68px] lg:text-[80px]"
          >
            Tumor variants in.
            <br />
            Drug evidence out.
          </h1>
          <p data-intro className="mx-auto mt-6 max-w-[36rem] text-[17px] leading-relaxed text-oo-ink-2 sm:text-[18.5px]">
            OpenOncology turns a sequencing run into a ranked shortlist of cancer drugs, with every source named, so the oncologist reviewing it
            can see exactly why.
          </p>
          <div data-intro className="mt-8 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
            <Link
              href={demoHref}
              className="group inline-flex h-12 items-center justify-center gap-2 rounded-full bg-oo-hema px-6 text-[15px] font-medium text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.16),0_10px_30px_-10px_rgb(61_44_141/0.7)] transition-colors duration-150 hover:bg-oo-hema-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema"
            >
              View the demo case
              <ArrowRight size={16} aria-hidden="true" className="transition-transform duration-200 group-hover:translate-x-0.5" />
            </Link>
            <a
              href={METHODS_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-12 items-center justify-center gap-1.5 rounded-full border border-oo-ink/15 bg-white px-6 text-[15px] font-medium text-oo-ink transition-colors duration-150 hover:border-oo-ink/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema"
            >
              Read the methods <ArrowUpRight size={15} aria-hidden="true" />
            </a>
          </div>
        </div>

        <div ref={stage} className="mx-auto mt-12 max-w-[1320px] px-3 pb-6 sm:px-5 md:mt-14 md:px-8">
          <div data-stage className="relative h-[400px] overflow-hidden rounded-[28px] bg-[#231850] sm:h-[560px] lg:h-[660px]">
            <div data-stage-img className="absolute inset-[-6%_0_-6%_0]">
              <Photo src="/marketing/stock/bench.jpg" alt="A lab technician loading sample tubes with a micropipette" priority sizes="100vw" position="center 55%" className="sm:hidden" />
              <Photo src="/marketing/stock/pipette.jpg" alt="A scientist pipetting samples into tubes" priority sizes="100vw" position="center 100%" className="hidden origin-bottom sm:block sm:scale-[1.22]" />
            </div>
            <Grade />

            <div className="absolute left-8 top-8 hidden w-[300px] sm:block lg:left-[6%] lg:top-[10%] lg:w-[330px]">
              <div data-float>
                <div data-depth="1">
                  <VariantCard variant={variant} />
                </div>
              </div>
            </div>

            <div className="absolute bottom-[12%] right-[6%] hidden w-[420px] lg:block xl:w-[460px]">
              <div data-float>
                <div data-depth="2" className="relative">
                  <RankedCard candidates={candidates} />
                  <ReviewPill className="absolute -top-12 right-0" />
                </div>
              </div>
            </div>

            <div className="absolute bottom-8 right-8 hidden sm:block lg:hidden">
              <div data-float>
                <ReviewPill />
              </div>
            </div>
          </div>

          <div className="relative z-10 -mt-20 px-3 sm:px-8 lg:hidden">
            <RankedCard candidates={candidates} compact />
          </div>
          <p className="mt-4 text-center text-[11.5px] text-oo-ink-3">Demo case, not a real patient. Photography is illustrative.</p>
        </div>
      </section>

      <section aria-label="Evidence sources" className="border-y border-oo-ink/[0.08]">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-3 px-5 py-7 md:flex-row md:items-center md:justify-between md:px-8">
          <p className="text-[13px] text-oo-ink-3">Built on public, citable evidence</p>
          <ul className="flex flex-wrap items-center gap-x-5 gap-y-1.5 font-mono md:gap-x-3 text-[12.5px] uppercase tracking-[0.12em] text-oo-ink-2">
            {SOURCES.map((s, i) => (
              <li key={s} className="flex items-center gap-3">
                {i > 0 ? <span aria-hidden="true" className="hidden text-oo-ink/25 md:inline">·</span> : null}
                {s}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id="how-it-works" aria-labelledby="how-title" className="mx-auto scroll-mt-16 max-w-[1200px] px-5 py-24 md:px-8 lg:py-32">
        <Reveal className="grid gap-6 lg:grid-cols-12 lg:items-end">
          <div className="lg:col-span-7">
            <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-oo-hema">How it works</p>
            <h2 id="how-title" className="mt-4 font-display text-[38px] font-semibold leading-[1.04] tracking-[-0.03em] sm:text-[52px]">
              From sequencing run to shortlist, in one place.
            </h2>
          </div>
          <p className="text-[17px] leading-relaxed text-oo-ink-2 lg:col-span-5">
            Built for sequencing labs and hospital teams without a molecular tumor board. Three steps, one workspace, nothing hidden.
          </p>
        </Reveal>

        <ol className="mt-14 grid gap-x-6 gap-y-14 md:grid-cols-12">
          <li className="md:col-span-7">
            <ClipPhoto className="relative h-[360px] overflow-hidden rounded-[24px] bg-[#231850] md:h-[460px]">
              <Photo src="/marketing/stock/microscope.jpg" alt="A researcher at a microscope" sizes="(min-width: 768px) 58vw, 100vw" position="20% 60%" />
              <Grade />
              <div className={`${card} absolute bottom-5 left-5 w-[min(320px,calc(100%-2.5rem))] p-4`}>
                <div className="flex items-center gap-3">
                  <span className="grid h-9 w-9 place-items-center rounded-lg bg-oo-hema/10 text-oo-hema">
                    <FileCode2 size={17} aria-hidden="true" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13.5px] font-semibold">tumor_sample.vcf</span>
                    <span className="block text-[11.5px] text-oo-ink-3">Uploaded · 2.4 MB · validating</span>
                  </span>
                </div>
                <div className="mt-3 h-1 overflow-hidden rounded-full bg-oo-hema/10">
                  <div className="h-full w-[82%] rounded-full bg-oo-hema" />
                </div>
              </div>
            </ClipPhoto>
            <StepText n="01" title="Upload the tumor VCF" body="Drop in the file your sequencing run already produces. No reformatting, no new pipeline to adopt." delay={0} />
          </li>

          <li className="md:col-span-5">
            <ClipPhoto className="relative h-[360px] overflow-hidden rounded-[24px] bg-[#231850] md:h-[460px]">
              <Photo src="/marketing/stock/sequencer.jpg" alt="A scientist operating a sequencing instrument" sizes="(min-width: 768px) 42vw, 100vw" position="62% center" />
              <Grade />
              <div className={`${card} absolute left-5 right-5 top-5 p-4`}>
                <div className="text-[11px] font-medium uppercase tracking-[0.1em] text-oo-ink-3">Annotated variant</div>
                <div className="mt-1.5 flex items-baseline justify-between gap-3">
                  <span className="text-[19px] font-semibold tracking-[-0.02em]">
                    {variant.gene} <span className="text-oo-eosin">{variant.short}</span>
                  </span>
                  <span className="rounded-md border border-oo-ink/10 px-1.5 py-0.5 font-mono text-[11px] text-oo-ink-2">{variant.level}</span>
                </div>
              </div>
            </ClipPhoto>
            <StepText n="02" title="Variants are annotated" body="Each variant is matched against curated evidence levels and pathogenicity predictions, with the gaps stated." delay={0.08} />
          </li>

          <li className="md:col-span-12">
            <ClipPhoto className="relative h-[320px] overflow-hidden rounded-[24px] bg-[#231850] md:h-[420px]">
              <Photo src="/marketing/stock/tubes.jpg" alt="A rack of sample tubes with coloured caps" sizes="100vw" position="center 55%" />
              <Grade scrim="left" />
              <div className="absolute inset-y-0 left-0 flex w-full max-w-[460px] items-center p-5 md:p-10">
                <div className={`${card} w-full p-5`}>
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-[13px] font-semibold">{topName}</span>
                    <span className="font-mono text-[13px] tabular-nums text-oo-hema">{candidates[0]?.score.toFixed(2)}</span>
                  </div>
                  <div className="mt-3 flex items-center gap-2 border-t border-oo-ink/[0.07] pt-3 text-[12px] text-oo-ink-3">
                    <Link2 size={13} aria-hidden="true" className="text-oo-hema" />
                    Evidence named for this row
                  </div>
                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {topSources.map((s) => (
                      <span key={s} className="rounded-md border border-oo-ink/10 bg-oo-paper px-2 py-1 font-mono text-[11px] text-oo-ink-2">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </ClipPhoto>
            <StepText n="03" title="Drugs are ranked, sources shown" body="Candidates are grouped by clinical context and scored, and every row names the evidence behind it." delay={0} />
          </li>
        </ol>
      </section>

      <section id="evidence" ref={dark} aria-labelledby="trace-title" className="relative scroll-mt-16 overflow-hidden bg-[#120B2B] text-white">
        <div aria-hidden="true" className="absolute -left-40 top-0 h-[520px] w-[520px] rounded-full bg-oo-hema/40 blur-[120px]" />
        <div className="relative mx-auto grid max-w-[1200px] items-center gap-14 px-5 py-24 md:px-8 lg:grid-cols-12 lg:gap-12 lg:py-32">
          <Reveal className="lg:col-span-5">
            <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-[#B9A9FF]">Transparent by design</p>
            <h2 id="trace-title" className="mt-4 font-display text-[38px] font-semibold leading-[1.04] tracking-[-0.03em] sm:text-[52px]">
              Every score shows its working.
            </h2>
            <p className="mt-5 text-[17px] leading-relaxed text-white/70">
              No black box. Each candidate carries its evidence level, its approval status and the sources it came from, so a reviewer can check
              it in seconds.
            </p>
            <ol className="mt-10 border-b border-white/10">
              {[
                { t: "Evidence levels explained", d: "What each level means, and the tumor type it applies to." },
                { t: "Sources one click away", d: "Every row links back to the database it came from." },
                { t: "Built for sign-off", d: "Designed for oncologist review, never automated decisions." },
              ].map(({ t, d }, i) => (
                <li key={t} className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-x-3 border-t border-white/10 py-4">
                  <span className="font-mono text-[12px] leading-[1.9] text-[#B9A9FF]">0{i + 1}</span>
                  <span>
                    <span className="block text-[16px] font-semibold">{t}</span>
                    <span className="mt-0.5 block text-[14.5px] leading-relaxed text-white/60">{d}</span>
                  </span>
                </li>
              ))}
            </ol>
          </Reveal>

          <div className="relative lg:col-span-7">
            <ClipPhoto className="relative aspect-[5/4] overflow-hidden rounded-[24px] bg-[#231850] sm:aspect-[4/3]">
              <div data-dark-img className="absolute inset-[-6%_0]">
                <Photo
                  src="/marketing/stock/analysis.jpg"
                  alt="A researcher at a microscope beside a laptop showing analysis curves"
                  sizes="(min-width: 1024px) 58vw, 100vw"
                  position="20% center"
                  className="scale-[1.12]"
                />
              </div>
              <Grade />
            </ClipPhoto>
            <div data-dark-card className="relative z-10 mx-4 -mt-24 sm:absolute sm:-bottom-12 sm:-right-6 sm:mx-0 sm:mt-0 sm:w-[340px]">
              <div className={`${card} p-5`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-[11px] font-medium uppercase tracking-[0.1em] text-oo-ink-3">Top candidate</div>
                    <div className="mt-1 text-[24px] font-semibold tracking-[-0.02em]">{topName}</div>
                  </div>
                  <span className="font-mono text-[22px] tabular-nums text-oo-hema">{candidates[0]?.score.toFixed(2)}</span>
                </div>
                <dl className="mt-4 space-y-2.5 border-t border-oo-ink/[0.07] pt-4 text-[13px]">
                  <div className="flex justify-between gap-3">
                    <dt className="text-oo-ink-3">Evidence level</dt>
                    <dd className="font-medium">{topLevel}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-oo-ink-3">Approval</dt>
                    <dd className="text-right font-medium">{topApproval}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-oo-ink-3">Sources</dt>
                    <dd className="font-medium">{topSources.length} named</dd>
                  </div>
                </dl>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section aria-labelledby="principles-title" className="mx-auto grid max-w-[1200px] gap-12 px-5 py-24 md:px-8 lg:grid-cols-12 lg:py-32">
        <Reveal className="lg:col-span-5">
          <h2 id="principles-title" className="max-w-[14ch] font-display text-[38px] font-semibold leading-[1.04] tracking-[-0.03em] sm:text-[52px]">
            Made to be checked, not trusted blindly.
          </h2>
        </Reveal>
        <ol className="border-b border-oo-ink/10 lg:col-span-7">
          {[
            { k: "MIT", t: "Open source, end to end", d: "Every line of the ranking is public. Read it, fork it, audit it." },
            { k: "Six", t: "Named evidence sources", d: "Curated databases and predictions, each cited on the row it informs." },
            { k: "One", t: "Oncologist signs off", d: "Each case waits for a clinician's review before anyone acts on it." },
          ].map(({ k, t, d }, i) => (
            <Reveal as="li" key={t} delay={0.06 * i} className="grid gap-x-8 gap-y-2 border-t border-oo-ink/10 py-7 sm:grid-cols-[7rem_minmax(0,1fr)]">
                <span className="font-display text-[34px] font-semibold leading-none tracking-[-0.03em] text-oo-hema">{k}</span>
                <span>
                  <span className="block text-[18px] font-semibold tracking-[-0.01em]">{t}</span>
                  <span className="mt-1.5 block text-[15.5px] leading-relaxed text-oo-ink-2">{d}</span>
                </span>
            </Reveal>
          ))}
        </ol>
      </section>

      <section ref={cta} aria-labelledby="cta-title" className="px-3 pb-6 sm:px-5 md:px-8">
        <div className="relative mx-auto max-w-[1320px] overflow-hidden rounded-[28px] bg-[#120B2B] text-white">
          <div aria-hidden="true" className="absolute inset-0 opacity-60">
            <VariantField colors={CTA_FIELD} count={1100} trigger={cta} target={{ x: 0.78, y: 0.5 }} />
          </div>
          <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-r from-[#120B2B] via-[#120B2B]/80 to-transparent" />
          <div aria-hidden="true" className="absolute -right-24 top-1/2 h-[420px] w-[420px] -translate-y-1/2 rounded-full bg-oo-hema/50 blur-[110px]" />
          <div className="relative max-w-[640px] px-7 py-16 sm:px-12 lg:px-16 lg:py-24">
            <h2 id="cta-title" className="font-display text-[38px] font-semibold leading-[1.04] tracking-[-0.03em] sm:text-[56px]">
              See a full case, end to end.
            </h2>
            <p className="mt-5 max-w-[30rem] text-[17px] leading-relaxed text-white/70">
              Walk through the demo: the variant, the ranked candidates and every source behind them.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link
                href={demoHref}
                className="group inline-flex h-12 items-center justify-center gap-2 rounded-full bg-white px-6 text-[15px] font-medium text-[#120B2B] transition-colors duration-150 hover:bg-oo-paper focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
              >
                View the demo case
                <ArrowRight size={16} aria-hidden="true" className="transition-transform duration-200 group-hover:translate-x-0.5" />
              </Link>
              <a
                href={REPO_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-12 items-center justify-center gap-1.5 rounded-full border border-white/25 px-6 text-[15px] font-medium text-white transition-colors duration-150 hover:border-white/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
              >
                View on GitHub <ArrowUpRight size={15} aria-hidden="true" />
              </a>
            </div>
          </div>
        </div>
      </section>

      <footer className="mx-auto flex max-w-[1200px] flex-col gap-4 px-5 py-12 text-[13px] text-oo-ink-3 sm:flex-row sm:items-center sm:justify-between md:px-8">
        <span className="font-semibold text-oo-ink">OpenOncology</span>
        <span>Research prototype · Not a medical device · Oncologist review required</span>
        <span>MIT licensed</span>
      </footer>
    </div>
  );
}
