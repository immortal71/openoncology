"use client";

import { useRef } from "react";
import Link from "next/link";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { useGSAP } from "@gsap/react";
import { VariantField } from "@/components/marketing/variant-field";
import {
  EvidenceVignette,
  RankedVignette,
  VariantVignette,
  type VignetteCandidate,
  type VignetteEvidence,
  type VignetteVariant,
} from "@/components/marketing/vignettes";

gsap.registerPlugin(ScrollTrigger, SplitText, useGSAP);

const METHODS_URL = "https://github.com/immortal71/openoncology/blob/main/docs/METHODS.md";
const STAGE_FIELD = { dot: "#FFFFFF", hi: "#F2A6C7", scan: "#FFFFFF" };

export function HeroLight({
  demoHref,
  candidates,
  variant,
  evidence,
}: {
  demoHref: string;
  candidates: VignetteCandidate[];
  variant: VignetteVariant;
  evidence: VignetteEvidence;
}) {
  const section = useRef<HTMLElement>(null);
  const headline = useRef<HTMLHeadingElement>(null);
  const stage = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        const split = SplitText.create(headline.current, {
          type: "lines",
          mask: "lines",
          autoSplit: true,
          onSplit: (self) => gsap.from(self.lines, { yPercent: 105, duration: 1.1, ease: "power4.out", stagger: 0.1 }),
        });
        gsap.from("[data-intro]", { y: 16, opacity: 0, duration: 0.8, ease: "power3.out", stagger: 0.08, delay: 0.5 });
        gsap.from("[data-stage]", { y: 80, duration: 1.2, ease: "power4.out", delay: 0.55 });
        gsap.from("[data-layer]", { y: 70, duration: 1.3, ease: "power4.out", stagger: 0.12, delay: 0.75 });
        return () => split.revert();
      });
      mm.add("(prefers-reduced-motion: no-preference) and (min-width: 1024px)", () => {
        const scrub = { trigger: stage.current, start: "top bottom", end: "bottom top", scrub: 0.8 };
        gsap.to("[data-depth='far']", { yPercent: -6, ease: "none", scrollTrigger: scrub });
        gsap.to("[data-depth='near']", { yPercent: -22, ease: "none", scrollTrigger: scrub });
        gsap.to("[data-depth='nearer']", { yPercent: -34, ease: "none", scrollTrigger: scrub });
      });
    },
    { scope: section }
  );

  return (
    <section ref={section} className="relative overflow-hidden bg-oo-paper text-oo-ink">
      <div className="relative mx-auto max-w-[1200px] px-5 pt-20 text-center md:px-8 md:pt-24">
        <span data-intro className="inline-flex rounded-full border border-oo-line bg-oo-surface px-3 py-1 text-[13px] font-medium text-oo-ink-3">
          Research prototype · Open source (MIT)
        </span>
        <h1
          ref={headline}
          className="mx-auto mt-7 max-w-[15ch] text-balance font-display text-[46px] font-semibold leading-[1.02] tracking-[-0.03em] sm:text-[68px] lg:text-[84px]"
        >
          From a tumor VCF to a ranked drug list, with its evidence sources named.
        </h1>
        <p data-intro className="mx-auto mt-6 max-w-[42rem] text-[17px] leading-relaxed text-oo-ink-2 sm:text-[19px]">
          OpenOncology brings drug evidence into one workspace for sequencing labs and hospitals without a molecular tumor board. An oncologist
          reviews the ranked shortlist and its sources.
        </p>
        <div data-intro className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link
            href={demoHref}
            className="inline-flex h-12 items-center rounded-md bg-oo-hema px-6 text-[15px] font-medium text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.14),0_8px_24px_-8px_rgb(61_44_141/0.6)] transition-colors duration-150 hover:bg-oo-hema-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema"
          >
            View the demo case
          </Link>
          <a
            href={METHODS_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-12 items-center rounded-md border border-oo-line bg-oo-surface px-6 text-[15px] font-medium text-oo-ink transition-colors duration-150 hover:bg-oo-paper focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema"
          >
            Read the methods
          </a>
        </div>
        <p className="mt-5 text-[12.5px] text-oo-ink-3">Demo case, not a real patient. Oncologist review is required before any treatment decision.</p>
      </div>

      <div ref={stage} className="relative mx-auto mt-16 max-w-[1240px] px-5 pb-20 md:px-8">
        <div data-stage className="relative overflow-hidden rounded-[32px] bg-oo-hema px-5 py-8 sm:px-10 lg:h-[600px] xl:h-[560px] lg:p-0">
          <div className="absolute inset-0 opacity-40">
            <VariantField colors={STAGE_FIELD} count={900} trigger={stage} target={{ x: 0.5, y: 0.45 }} />
          </div>
          <div className="relative mx-auto flex max-w-[540px] flex-col gap-5 lg:block lg:max-w-none">
            <div className="lg:absolute lg:left-1/2 lg:top-[84px] lg:w-[400px] lg:-translate-x-1/2 xl:w-[500px]">
              <div data-layer>
                <div data-depth="far">
                  <RankedVignette candidates={candidates} />
                </div>
              </div>
            </div>
            <div className="lg:absolute lg:left-[2%] lg:top-[48px] lg:w-[240px] xl:left-[3%] xl:w-[280px]">
              <div data-layer>
                <div data-depth="near">
                  <VariantVignette variant={variant} />
                </div>
              </div>
            </div>
            <div className="lg:absolute lg:right-[2%] lg:top-[210px] lg:w-[240px] xl:right-[3%] xl:w-[280px]">
              <div data-layer>
                <div data-depth="nearer">
                  <EvidenceVignette evidence={evidence} />
                </div>
              </div>
            </div>
          </div>
        </div>
        <p className="mt-4 text-center text-[11.5px] text-oo-ink-3">
          Cards show the demo case&apos;s real output. Background dots are illustrative, not patient data.
        </p>
      </div>
    </section>
  );
}
