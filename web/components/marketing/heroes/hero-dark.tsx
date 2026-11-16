"use client";

import { useRef } from "react";
import Image from "next/image";
import Link from "next/link";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { useGSAP } from "@gsap/react";
import { ArrowRight } from "lucide-react";
import { BrowserFrame } from "@/components/marketing/browser-frame";
import { VariantField } from "@/components/marketing/variant-field";

gsap.registerPlugin(ScrollTrigger, SplitText, useGSAP);

const METHODS_URL = "https://github.com/immortal71/openoncology/blob/main/docs/METHODS.md";
const FIELD = { dot: "#B9B2D6", hi: "#9D8CFF", scan: "#9D8CFF" };

export function HeroDark({ demoHref }: { demoHref: string }) {
  const section = useRef<HTMLElement>(null);
  const headline = useRef<HTMLHeadingElement>(null);
  const tilt = useRef<HTMLDivElement>(null);
  const features = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        const split = SplitText.create(headline.current, {
          type: "lines",
          mask: "lines",
          autoSplit: true,
          onSplit: (self) => gsap.from(self.lines, { yPercent: 110, duration: 1, ease: "power4.out", stagger: 0.09, delay: 0.1 }),
        });
        gsap.from("[data-intro]", { y: 18, opacity: 0, duration: 0.8, ease: "power3.out", stagger: 0.08, delay: 0.55 });
        gsap.from("[data-frame-intro]", { y: 90, opacity: 0, duration: 1.2, ease: "power3.out", delay: 0.75 });
        gsap.fromTo(
          tilt.current,
          { rotateX: 24, scale: 0.9 },
          { rotateX: 0, scale: 1, ease: "none", scrollTrigger: { trigger: section.current, start: "top top", end: "+=700", scrub: 0.6 } }
        );
        gsap.from("[data-feature]", {
          y: 40,
          opacity: 0,
          duration: 0.9,
          ease: "power3.out",
          stagger: 0.12,
          scrollTrigger: { trigger: features.current, start: "top 75%" },
        });
        return () => split.revert();
      });
    },
    { scope: section }
  );

  return (
    <section ref={section} className="relative overflow-hidden bg-[#0C0A12] text-[#F4F1FA]">
      <div className="absolute inset-x-0 top-0 h-[78vh] [mask-image:linear-gradient(to_bottom,black_55%,transparent)]">
        <VariantField colors={FIELD} trigger={section} target={{ x: 0.5, y: 1.15 }} />
      </div>

      <div className="relative mx-auto max-w-[1200px] px-5 pt-24 text-center md:px-8 md:pt-32">
        <span data-intro className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.04] px-3 py-1 text-[13px] text-white/70">
          <span className="h-1.5 w-1.5 rounded-full bg-[#9D8CFF]" aria-hidden="true" />
          Research prototype · Open source (MIT)
        </span>
        <h1
          ref={headline}
          className="mx-auto mt-7 max-w-[17ch] text-balance text-[44px] font-semibold leading-[1.02] tracking-[-0.04em] sm:text-[64px] lg:text-[80px]"
        >
          From a tumor VCF to a ranked drug list, with its evidence sources named.
        </h1>
        <p data-intro className="mx-auto mt-6 max-w-[44rem] text-[17px] leading-relaxed text-white/60 sm:text-[19px]">
          OpenOncology brings drug evidence into one workspace for sequencing labs and hospitals without a molecular tumor board. An oncologist
          reviews the ranked shortlist and its sources.
        </p>
        <div data-intro className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link
            href={demoHref}
            className="inline-flex h-11 items-center gap-2 rounded-md bg-[#F4F1FA] px-5 text-[15px] font-medium text-[#0C0A12] transition-colors duration-150 hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#9D8CFF]"
          >
            View the demo case <ArrowRight size={16} aria-hidden="true" />
          </Link>
          <a
            href={METHODS_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-11 items-center rounded-md border border-white/15 px-5 text-[15px] font-medium text-white/85 transition-colors duration-150 hover:bg-white/[0.06] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#9D8CFF]"
          >
            Read the methods
          </a>
        </div>
        <p className="mt-5 text-[12.5px] text-white/45">Demo case, not a real patient. Oncologist review is required before any treatment decision.</p>
      </div>

      <div className="relative mx-auto mt-16 max-w-[1120px] px-5 [perspective:1600px] md:px-8">
        <div data-frame-intro>
          <div ref={tilt} className="origin-top [transform-style:preserve-3d]">
            <BrowserFrame tone="dark">
              <Image
                src="/marketing/results-overview.jpg"
                alt="The OpenOncology Results page for the KRAS G12C demo case: protein view, summary and variant list"
                width={2560}
                height={1640}
                priority
                className="block h-auto w-full"
              />
            </BrowserFrame>
          </div>
        </div>
      </div>

      <div ref={features} className="relative mx-auto grid max-w-[1120px] gap-10 px-5 pb-28 pt-24 md:grid-cols-3 md:px-8">
        {[
          { k: "01", t: "Variants in", d: "Start from a tumor VCF. Each call keeps its gene, protein change and evidence level." },
          { k: "02", t: "Evidence, named", d: "Candidates are grouped by clinical context, and every rank lists the sources behind it." },
          { k: "03", t: "Oncologist decides", d: "The shortlist is a starting point for review, never a treatment decision." },
        ].map((f) => (
          <div key={f.k} data-feature className="border-t border-white/10 pt-6">
            <span className="font-mono text-[12px] text-[#9D8CFF]">{f.k}</span>
            <h2 className="mt-3 text-[20px] font-semibold tracking-[-0.01em]">{f.t}</h2>
            <p className="mt-2 text-[15px] leading-relaxed text-white/55">{f.d}</p>
          </div>
        ))}
      </div>
      <p className="relative pb-6 text-center text-[11px] text-white/30">Background: illustrative variant calls across chromosomes, not patient data.</p>
    </section>
  );
}
