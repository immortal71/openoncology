"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import gsap from "gsap";
import { ScrollToPlugin } from "gsap/ScrollToPlugin";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { AnimatePresence, motion } from "framer-motion";
import { Info } from "lucide-react";
import { ApprovalLine, SourceBadges, TierPill } from "@/components/oo/clinical";
import { parseApproval } from "@/lib/approval";
import { tierInfo } from "@/lib/therapy-groups";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";

gsap.registerPlugin(ScrollTrigger, ScrollToPlugin, useGSAP);

export type HeroCandidate = {
  id: string;
  name: string;
  tier: string | null | undefined;
  score: number | null | undefined;
  approvalStatus: string | null | undefined;
  mechanism: string | null | undefined;
  sources: string[];
  phaseSignal?: boolean;
};

const METHODS_URL = "https://github.com/immortal71/openoncology/blob/main/docs/METHODS.md";
const SCENE = "(min-width: 1024px) and (min-height: 860px) and (prefers-reduced-motion: no-preference)";
const STEP_AT = [0, 0.16, 0.5, 0.8];
const NAV_OFFSET = 64;
const LAST_STEP = 4;

const STEPS = [
  { label: "Variant supplied", desc: "The ranking starts from the variant call in the uploaded VCF." },
  { label: "Ranked by evidence score", desc: "Each candidate gets a 0–1 composite of the evidence on its row." },
  { label: "Approval and mechanism", desc: "Whether the drug is approved, for which indication, and how it acts." },
  { label: "Named evidence sources", desc: "The sources behind each ranking, listed per drug." },
];

type CSSVars = React.CSSProperties & Record<`--${string}`, string | number>;

function Disclosure({ open, animate, children }: { open: boolean; animate: boolean; children: React.ReactNode }) {
  return (
    <AnimatePresence initial={false}>
      {open ? (
        <motion.div
          initial={{ height: 0 }}
          animate={{ height: "auto" }}
          exit={{ height: 0 }}
          transition={animate ? { duration: 0.24, ease: EASE_OUT } : { duration: 0 }}
          className="overflow-hidden"
        >
          {children}
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function HeroScore({ score }: { score: number | null | undefined }) {
  if (score == null || Number.isNaN(score)) {
    return (
      <span className="font-mono text-[13px] text-oo-ink-3">
        <span aria-hidden="true">—</span>
        <span className="sr-only">No score</span>
      </span>
    );
  }
  const clamped = Math.min(1, Math.max(0, score));
  const style: CSSVars = { "--sx": clamped, transform: `scaleX(${clamped})` };
  return (
    <span className="inline-flex items-center gap-2.5">
      <span aria-hidden="true" className="h-1.5 w-16 overflow-hidden rounded-full bg-oo-line-soft sm:w-[120px]">
        <span data-hero-bar data-reveal="scale-x" data-score={clamped} style={style} className="block h-full origin-left rounded-full bg-oo-ink-3" />
      </span>
      <span className="w-9 text-right font-mono text-[13px] tabular-nums text-oo-ink-2">{clamped.toFixed(2)}</span>
    </span>
  );
}

function Stepper({ step, onSelect, fillRef }: { step: number; onSelect: (n: number) => void; fillRef: React.RefObject<HTMLSpanElement | null> }) {
  return (
    <div className="relative mt-10 hidden scene:block">
      <span aria-hidden="true" className="absolute inset-y-0 left-0 w-px bg-oo-line" />
      <span ref={fillRef} data-hero-progress aria-hidden="true" className="absolute inset-y-0 left-0 w-px origin-top scale-y-0 bg-oo-hema" />
      <ol aria-label="What the demo card shows">
        {STEPS.map((s, i) => {
          const n = i + 1;
          const active = n === step;
          return (
            <li key={s.label}>
              <button
                type="button"
                onClick={() => onSelect(n)}
                aria-current={active ? "step" : undefined}
                className={cn(
                  "group block w-full rounded-r-md py-1.5 pl-5 pr-2 text-left transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-oo-hema",
                  active ? "text-oo-ink" : "text-oo-ink-3 hover:text-oo-ink-2"
                )}
              >
                <span className="flex items-center gap-2 text-[14px] font-semibold">
                  <span className="w-4 font-mono text-[12px] font-normal">{n}</span>
                  {s.label}
                </span>
                {active ? <span className="ml-6 block text-[13.5px] font-normal leading-relaxed text-oo-ink-2">{s.desc}</span> : null}
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function HeroCard({
  candidates,
  step,
  animate,
  title,
  facts,
  input,
  inputSource,
}: {
  candidates: HeroCandidate[];
  step: number;
  animate: boolean;
  title: string;
  facts: string;
  input: string;
  inputSource: string;
}) {
  const phaseNames = candidates.filter((c) => c.phaseSignal).map((c) => c.name);
  return (
    <div data-hero-card className="rounded-2xl border border-oo-line bg-oo-surface p-5 shadow-[0_40px_80px_-40px_rgb(27_22_38/0.28)] sm:p-6">
      <div
        className={cn(
          "flex items-baseline gap-3 rounded-md border px-3 py-2 transition-colors duration-200",
          step === 1 ? "border-oo-hema/30 bg-oo-hema-tint" : "border-oo-line bg-oo-paper"
        )}
      >
        <span className={cn("text-[12px] font-medium transition-colors duration-200", step === 1 ? "text-oo-hema" : "text-oo-ink-3")}>Input</span>
        <span className="min-w-0 font-mono text-[12.5px] text-oo-ink">{input}</span>
        <span className="ml-auto hidden shrink-0 text-[12px] text-oo-ink-3 sm:inline">{inputSource}</span>
      </div>
      <div className="mt-4 min-w-0">
        <div className="text-[12px] font-medium text-oo-ink-3">Ranked candidates for</div>
        <div className="text-[17px] font-semibold tracking-[-0.01em] text-oo-ink">{title}</div>
        <div className="mt-0.5 font-mono text-[12px] text-oo-ink-3">{facts}</div>
      </div>
      <div>
        <div className="mt-3 hidden grid-cols-[1.25rem_minmax(0,1fr)_auto_10.5rem] items-center gap-x-3 border-b border-oo-line pb-2 text-[12px] font-medium text-oo-ink-3 sm:grid">
          <span>#</span>
          <span>Drug</span>
          <span>Tier</span>
          <span className={cn("justify-self-end rounded px-1.5 py-0.5 transition-colors duration-200", step === 2 ? "bg-oo-hema-tint text-oo-hema" : "")}>
            Evidence score
          </span>
        </div>
        <ul className="divide-y divide-oo-line-soft">
          {candidates.map((c, i) => {
            const approval = parseApproval(c.approvalStatus);
            const showApproval = Boolean(approval.qualifier) || approval.label !== tierInfo(c.tier).badge;
            return (
              <li key={c.id} className="py-3">
                <div className="grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 sm:grid-cols-[1.25rem_minmax(0,1fr)_auto_10.5rem]">
                  <span className="font-mono text-[12px] text-oo-ink-3">{i + 1}</span>
                  <span className="min-w-0 truncate text-[15px] font-semibold text-oo-ink">{c.name}</span>
                  <TierPill tier={c.tier} />
                  <span className="col-span-2 col-start-2 sm:col-span-1 sm:col-start-auto sm:justify-self-end">
                    <HeroScore score={c.score} />
                  </span>
                </div>
                <Disclosure open={step >= 3} animate={animate}>
                  <div className="space-y-1 pl-8 pt-2">
                    {showApproval ? <ApprovalLine status={c.approvalStatus} /> : null}
                    {c.mechanism ? <p className="max-w-[60ch] text-[13.5px] leading-relaxed text-oo-ink-2">{c.mechanism}</p> : null}
                  </div>
                </Disclosure>
                <Disclosure open={step >= 4} animate={animate}>
                  <div className="pl-8 pt-2">
                    <SourceBadges sources={c.sources} />
                  </div>
                </Disclosure>
              </li>
            );
          })}
        </ul>
      </div>
      {phaseNames.length > 0 ? (
        <Disclosure open={step >= 4} animate={animate}>
          <p className="border-t border-oo-line-soft pt-3 text-[12.5px] text-oo-ink-3">
            {phaseNames.join(" and ")} {phaseNames.length === 1 ? "score" : "scores"} also weigh the drug&apos;s clinical phase, a derived signal rather
            than a named source.
          </p>
        </Disclosure>
      ) : null}
    </div>
  );
}

export function HeroScroll({
  candidates,
  title,
  facts,
  input,
  inputSource,
  demoHref,
}: {
  candidates: HeroCandidate[];
  title: string;
  facts: string;
  input: string;
  inputSource: string;
  demoHref: string;
}) {
  const root = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLDivElement>(null);
  const fill = useRef<HTMLSpanElement>(null);
  const [step, setStep] = useState(LAST_STEP);
  const [animate, setAnimate] = useState(false);

  const distance = () => {
    const el = track.current;
    return el ? Math.max(el.offsetHeight - (window.innerHeight - NAV_OFFSET), 1) : 1;
  };

  const selectStep = (n: number) => {
    const el = track.current;
    if (!el) return;
    const trackTop = el.getBoundingClientRect().top + window.scrollY - NAV_OFFSET;
    const offset = n === 1 ? 0 : distance() * STEP_AT[n - 1] + 8;
    gsap.to(window, { scrollTo: { y: trackTop + offset, autoKill: true }, duration: 0.7, ease: "power2.inOut", overwrite: true });
  };

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add({ scene: SCENE, still: `not all and ${SCENE}` }, (ctx) => {
        if (ctx.conditions?.still) {
          setAnimate(false);
          setStep(LAST_STEP);
          return;
        }
        const el = track.current;
        if (!el) return;
        setStep(1);
        const raf = requestAnimationFrame(() => setAnimate(true));
        const bars = gsap.utils.toArray<HTMLElement>("[data-hero-bar]");
        const barValue = (_i: number, target: HTMLElement) => Number(target.dataset.score ?? 0);
        gsap.set(bars, { scaleX: 0 });
        const fillBars = () => gsap.to(bars, { scaleX: barValue, duration: 0.6, stagger: 0.06, ease: "power2.out", overwrite: true });
        const emptyBars = () => gsap.to(bars, { scaleX: 0, duration: 0.25, ease: "power2.in", overwrite: true });
        STEP_AT.slice(1).forEach((t, i) => {
          ScrollTrigger.create({
            trigger: el,
            start: () => `top+=${distance() * t} ${NAV_OFFSET}px`,
            invalidateOnRefresh: true,
            onEnter: () => {
              setStep(i + 2);
              if (i === 0) fillBars();
            },
            onLeaveBack: () => {
              setStep(i + 1);
              if (i === 0) emptyBars();
            },
          });
        });

        const scrub = { trigger: el, scrub: 0.4, invalidateOnRefresh: true };
        if (fill.current) {
          gsap.fromTo(
            fill.current,
            { scaleY: 0 },
            { scaleY: 1, ease: "none", scrollTrigger: { ...scrub, start: `top ${NAV_OFFSET}px`, end: () => `+=${distance()}` } }
          );
        }
        return () => cancelAnimationFrame(raf);
      });
      return () => mm.revert();
    },
    { scope: root }
  );

  return (
    <div ref={root}>
      <div ref={track} className="relative [overflow-anchor:none] scene:h-[170vh]">
        <div className="scene:sticky scene:top-16 scene:h-[calc(100vh-4rem)] scene:pt-[7vh]">
          <div className="mx-auto grid w-full max-w-[1200px] grid-cols-1 items-start gap-10 px-5 py-10 sm:py-14 md:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:gap-12 xl:gap-16 scene:py-0">
            <div className="min-w-0 max-w-[34rem]">
              <span className="inline-flex rounded-full border border-oo-line bg-oo-surface px-3 py-1 text-[13px] font-medium text-oo-ink-3">
                Research prototype · Open source (MIT)
              </span>
              <h1 className="mt-6 text-balance font-display text-[32px] font-semibold leading-[1.06] tracking-[-0.02em] text-oo-ink sm:text-[46px] xl:text-[52px]">
                From a tumor VCF to a ranked drug list, with its evidence sources named.
              </h1>
              <p className="mt-4 text-[16px] leading-relaxed text-oo-ink-2 sm:mt-5 sm:text-[17px]">
                OpenOncology brings drug evidence into one workspace for sequencing labs and hospitals without a molecular tumor board. An
                oncologist reviews the ranked shortlist and its sources.
              </p>
              <div className="mt-6 grid grid-cols-2 gap-3 sm:mt-7 sm:flex sm:flex-wrap sm:items-center">
                <Link
                  href={demoHref}
                  className="inline-flex h-11 items-center justify-center whitespace-nowrap rounded-md bg-oo-hema px-3 text-[14px] sm:px-5 sm:text-[15px] font-medium text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.12),0_1px_2px_rgb(27_22_38/0.2)] transition-colors duration-150 hover:bg-oo-hema-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema"
                >
                  View the demo case
                </Link>
                <a
                  href={METHODS_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex h-11 items-center justify-center whitespace-nowrap rounded-md border border-oo-line bg-oo-surface px-3 text-[14px] sm:px-5 sm:text-[15px] font-medium text-oo-ink shadow-[0_1px_2px_rgb(27_22_38/0.06)] transition-colors duration-150 hover:border-oo-ink-3/40 hover:bg-oo-paper focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema"
                >
                  Read the methods
                </a>
              </div>
              <Stepper step={step} onSelect={selectStep} fillRef={fill} />
            </div>

            <div className="min-w-0 space-y-3">
              <div className="flex items-start gap-2 rounded-lg bg-oo-line-soft px-3 py-2 text-[13px] leading-relaxed text-oo-ink-2">
                <Info size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
                <span>Demo case, not a real patient. Oncologist review is required before any treatment decision.</span>
              </div>
              <HeroCard
                candidates={candidates}
                step={step}
                animate={animate}
                title={title}
                facts={facts}
                input={input}
                inputSource={inputSource}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
