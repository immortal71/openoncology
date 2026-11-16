"use client";

import { useRef } from "react";
import Link from "next/link";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { useGSAP } from "@gsap/react";
import { ArrowRight } from "lucide-react";

gsap.registerPlugin(ScrollTrigger, SplitText, useGSAP);

const METHODS_URL = "https://github.com/immortal71/openoncology/blob/main/docs/METHODS.md";

export type BoldVariant = { gene: string; change: string; level: string; actionable: boolean };
export type BoldCandidate = { name: string; score: number; tier: string };

export function HeroBold({ demoHref, variants, candidates }: { demoHref: string; variants: BoldVariant[]; candidates: BoldCandidate[] }) {
  const section = useRef<HTMLElement>(null);
  const headline = useRef<HTMLHeadingElement>(null);
  const band = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        const split = SplitText.create(headline.current, {
          type: "lines",
          mask: "lines",
          autoSplit: true,
          onSplit: (self) => gsap.from(self.lines, { yPercent: 110, duration: 0.9, ease: "power4.out", stagger: 0.08 }),
        });
        const tl = gsap.timeline({ delay: 0.4, defaults: { ease: "power3.out" } });
        tl.from("[data-intro]", { y: 16, opacity: 0, duration: 0.7, stagger: 0.08 })
          .fromTo("[data-marker]", { scaleX: 0 }, { scaleX: 1, duration: 0.7, ease: "power2.inOut" }, 0.2)
          .from("[data-panel]", { y: 60, opacity: 0, duration: 1 }, 0.1)
          .fromTo("[data-scan]", { yPercent: -100, opacity: 1 }, { yPercent: 1100, opacity: 0, duration: 1.4, ease: "power1.inOut" }, 0.7)
          .fromTo("[data-pick]", { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "power2.out" }, 1.7)
          .fromTo("[data-link]", { scaleY: 0 }, { scaleY: 1, duration: 0.45, ease: "power2.inOut" }, 2.1)
          .fromTo(
            "[data-bar]",
            { scaleX: 0 },
            { scaleX: (_i: number, el: HTMLElement) => Number(el.dataset.score ?? 0), duration: 0.8, stagger: 0.08, ease: "power2.out" },
            2.45
          );
        gsap.to("[data-band-row='a']", { xPercent: -22, ease: "none", scrollTrigger: { trigger: band.current, start: "top bottom", end: "bottom top", scrub: 0.5 } });
        gsap.fromTo(
          "[data-band-row='b']",
          { xPercent: -22 },
          { xPercent: 0, ease: "none", scrollTrigger: { trigger: band.current, start: "top bottom", end: "bottom top", scrub: 0.5 } }
        );
        return () => split.revert();
      });
    },
    { scope: section }
  );

  return (
    <section ref={section} className="bg-oo-paper text-oo-ink">
      <div className="mx-auto grid max-w-[1320px] items-center gap-12 px-5 pb-20 pt-16 md:px-8 lg:min-h-[calc(100vh-4rem)] lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:gap-16 lg:py-12">
        <div>
          <span data-intro className="inline-flex rounded-md bg-oo-ink px-2.5 py-1 font-mono text-[12px] text-white">
            research prototype · MIT
          </span>
          <h1
            ref={headline}
            className="mt-7 text-[46px] font-bold leading-[0.98] tracking-[-0.045em] sm:text-[68px] xl:text-[84px]"
          >
            From a tumor VCF to a{" "}
            <span className="relative inline-block">
              <span data-marker aria-hidden="true" className="absolute inset-x-[-0.06em] bottom-[0.06em] top-[0.52em] -z-0 origin-left bg-oo-hema/20" />
              <span className="relative">ranked drug list</span>
            </span>
            , with its evidence sources named.
          </h1>
          <p data-intro className="mt-7 max-w-[34rem] text-[18px] leading-relaxed text-oo-ink-2">
            OpenOncology brings drug evidence into one workspace for sequencing labs and hospitals without a molecular tumor board. An oncologist
            reviews the ranked shortlist and its sources.
          </p>
          <div data-intro className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              href={demoHref}
              className="inline-flex h-12 items-center gap-2 rounded-md bg-oo-ink px-6 text-[15px] font-medium text-white transition-colors duration-150 hover:bg-oo-hema focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema"
            >
              View the demo case <ArrowRight size={16} aria-hidden="true" />
            </Link>
            <a
              href={METHODS_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-12 items-center rounded-md border-2 border-oo-ink px-6 text-[15px] font-medium text-oo-ink transition-colors duration-150 hover:bg-oo-ink hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema"
            >
              Read the methods
            </a>
          </div>
          <p className="mt-5 text-[12.5px] text-oo-ink-3">Demo case, not a real patient. Oncologist review is required before any treatment decision.</p>
        </div>

        <div data-panel className="rounded-[28px] bg-oo-hema p-5 text-white shadow-[0_50px_100px_-40px_rgb(61_44_141/0.7)] sm:p-7">
          <div className="flex items-center justify-between font-mono text-[12px] text-white/60">
            <span>demo case · input</span>
            <span>{variants.length} variants</span>
          </div>
          <div className="relative mt-3 overflow-hidden rounded-xl bg-[#2A1E6B] font-mono text-[13px] sm:text-[14px]">
            <span data-scan aria-hidden="true" className="absolute inset-x-0 top-0 h-[10%] bg-white/10 opacity-0" />
            <div className="grid grid-cols-[1fr_1.4fr_auto] gap-x-4 border-b border-white/10 px-4 py-2.5 text-[11.5px] text-white/45">
              <span>gene</span>
              <span>protein change</span>
              <span>OncoKB</span>
            </div>
            {variants.map((v) => (
              <div key={v.gene} className="relative grid grid-cols-[1fr_1.4fr_auto] gap-x-4 px-4 py-3">
                {v.actionable ? <span data-pick aria-hidden="true" className="absolute inset-0 origin-left bg-white/[0.14]" /> : null}
                <span className="relative font-semibold">{v.gene}</span>
                <span className="relative text-white/80">{v.change}</span>
                <span className="relative text-white/80">{v.level}</span>
              </div>
            ))}
          </div>
          <div className="ml-7 h-8 w-px origin-top bg-white/50" data-link aria-hidden="true" />
          <div className="rounded-xl bg-oo-surface p-4 text-oo-ink sm:p-5">
            <div className="flex items-baseline justify-between">
              <span className="text-[12px] font-medium text-oo-ink-3">Ranked candidates</span>
              <span className="font-mono text-[11.5px] text-oo-ink-3">evidence score</span>
            </div>
            <ol className="mt-2 divide-y divide-oo-line-soft">
              {candidates.map((c, i) => (
                <li key={c.name} className="grid grid-cols-[1.25rem_minmax(0,1fr)_7rem_2.5rem] items-center gap-x-3 py-2.5">
                  <span className="font-mono text-[12px] text-oo-ink-3">{i + 1}</span>
                  <span className="min-w-0">
                    <span className="block truncate text-[15px] font-semibold">{c.name}</span>
                    <span className="block text-[12px] text-oo-ink-3">{c.tier}</span>
                  </span>
                  <span aria-hidden="true" className="h-1.5 overflow-hidden rounded-full bg-oo-line-soft">
                    <span data-bar data-reveal="scale-x" data-score={c.score} style={{ transform: `scaleX(${c.score})`, ["--sx" as string]: c.score }} className="block h-full origin-left rounded-full bg-oo-ink" />
                  </span>
                  <span className="text-right font-mono text-[13px] tabular-nums">{c.score.toFixed(2)}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>

      <div ref={band} aria-hidden="true" className="overflow-hidden border-y border-oo-ink bg-oo-ink py-10 text-white">
        <div data-band-row="a" className="whitespace-nowrap text-[64px] font-bold leading-none tracking-[-0.04em] sm:text-[110px]">
          Variants in <span className="text-oo-hema-on-dark">→</span> evidence named <span className="text-oo-hema-on-dark">→</span> oncologist decides
        </div>
        <div data-band-row="b" className="mt-4 whitespace-nowrap text-[64px] font-bold leading-none tracking-[-0.04em] text-transparent [-webkit-text-stroke:1.5px_rgb(255_255_255/0.35)] sm:text-[110px]">
          open methods · open code · open limits · open methods · open code
        </div>
      </div>
    </section>
  );
}
