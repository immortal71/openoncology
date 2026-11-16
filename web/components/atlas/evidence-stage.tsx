"use client";

import { useRef } from "react";
import Image from "next/image";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(ScrollTrigger, useGSAP);

export type StageCard = { src: string; alt: string; position: string; zoom?: number; origin?: string; n: string; label: string; value: string; sub: string; note?: string };

function Photo({ card, sizes }: { card: StageCard; sizes: string }) {
  return (
    <Image
      src={card.src}
      alt={card.alt}
      fill
      sizes={sizes}
      className="object-cover contrast-[1.05] saturate-[.92]"
      style={{ objectPosition: card.position, transform: card.zoom ? `scale(${card.zoom})` : undefined, transformOrigin: card.origin }}
    />
  );
}

function Plate({ card, accent = false, compact = false, className }: { card: StageCard; accent?: boolean; compact?: boolean; className?: string }) {
  return (
    <div className={`bg-white px-4 py-3 ${className ?? ""}`}>
      <p className="font-mono text-[10.5px] uppercase tracking-[0.13em] text-[#615B69]">
        {card.n} · {card.label}
      </p>
      <p className={`mt-0.5 text-[16px] font-semibold tracking-[-0.015em] ${accent ? "text-[#584493]" : "text-[#221E2B]"}`}>{card.value}</p>
      {compact ? null : <p className="text-[12.5px] leading-snug text-[#615B69]">{card.sub}</p>}
      {card.note ? (
        <p className="mt-2 flex items-start gap-1.5 text-[12px] leading-snug text-[#6B4A13]">
          <span aria-hidden="true" className="mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#855B18]" />
          {card.note}
        </p>
      ) : null}
    </div>
  );
}

function Unknown({ items, className }: { items: string[]; className?: string }) {
  return (
    <div className={`rounded-[10px] bg-[#211D2A]/90 px-4 py-3 text-[#F7F5F0] backdrop-blur ${className ?? ""}`}>
      <p className="font-mono text-[10.5px] uppercase tracking-[0.13em] text-[#F7F5F0]/60">Still unknown in this result</p>
      <p className="mt-1 text-[13px] leading-snug">{items.join(" · ")}</p>
    </div>
  );
}

const shadow = "shadow-[0_2px_4px_rgb(34_30_43/0.06),0_40px_80px_-30px_rgb(34_30_43/0.45)]";

export function EvidenceStage({ cards, unknown = [] }: { cards: StageCard[]; unknown?: string[] }) {
  const root = useRef<HTMLDivElement>(null);
  const [left, main, right] = cards;

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from("[data-layer]", {
          y: 70,
          opacity: 0,
          duration: 1.2,
          ease: "power4.out",
          stagger: 0.14,
          scrollTrigger: { trigger: root.current, start: "top 80%", once: true },
        });
      });
      mm.add("(prefers-reduced-motion: no-preference) and (min-width: 1024px)", () => {
        const scrub = { trigger: root.current, start: "top bottom", end: "bottom top", scrub: 0.8 };
        gsap.to("[data-depth='far']", { yPercent: -3, ease: "none", scrollTrigger: scrub });
        gsap.to("[data-depth='near']", { yPercent: -16, ease: "none", scrollTrigger: scrub });
        gsap.to("[data-depth='nearer']", { yPercent: -10, ease: "none", scrollTrigger: scrub });
      });
    },
    { scope: root }
  );

  return (
    <div ref={root}>
      <div className="relative hidden h-[600px] lg:block xl:h-[640px]">
        <div data-layer className="absolute bottom-[8%] left-[11%] right-[13%] top-0">
          <div data-depth="far" className={`relative h-full overflow-hidden rounded-[18px] bg-[#241D36] ${shadow}`}>
            <Photo card={main} sizes="76vw" />
            <Plate card={main} className={`absolute left-6 top-6 max-w-[340px] rounded-[10px] ${shadow}`} />
            {unknown.length ? <Unknown items={unknown} className="absolute bottom-6 left-[30%] max-w-[300px]" /> : null}
          </div>
        </div>
        <div data-layer className="absolute bottom-0 left-0 h-[46%] w-[31%]">
          <figure data-depth="near" className={`flex h-full flex-col overflow-hidden rounded-[14px] bg-white ring-1 ring-black/5 ${shadow}`}>
            <div className="relative min-h-0 flex-1">
              <Photo card={left} sizes="31vw" />
            </div>
            <figcaption>
              <Plate card={left} />
            </figcaption>
          </figure>
        </div>
        <div data-layer className="absolute right-0 top-[7%] h-[78%] w-[27%]">
          <figure data-depth="nearer" className={`flex h-full flex-col overflow-hidden rounded-[14px] bg-white ring-1 ring-black/5 ${shadow}`}>
            <div className="relative min-h-0 flex-1">
              <Photo card={right} sizes="27vw" />
            </div>
            <figcaption>
              <Plate card={right} accent />
            </figcaption>
          </figure>
        </div>
      </div>

      <div className="relative h-[430px] lg:hidden">
        <div data-layer className={`absolute inset-x-4 top-0 h-[300px] overflow-hidden rounded-[16px] bg-[#241D36] ${shadow}`}>
          <Photo card={main} sizes="100vw" />
          <Plate card={main} compact className="absolute left-3 top-3 max-w-[78%] rounded-[8px] px-3 py-2" />
        </div>
        <figure data-layer className={`absolute bottom-0 left-0 w-[54%] overflow-hidden rounded-[12px] bg-white ring-1 ring-black/5 ${shadow}`}>
          <div className="relative h-[92px]">
            <Photo card={left} sizes="54vw" />
          </div>
          <figcaption>
            <Plate card={left} compact className="px-3 py-2" />
          </figcaption>
        </figure>
        <figure data-layer className={`absolute bottom-8 right-0 w-[43%] overflow-hidden rounded-[12px] bg-white ring-1 ring-black/5 ${shadow}`}>
          <div className="relative h-[108px]">
            <Photo card={right} sizes="43vw" />
          </div>
          <figcaption>
            <Plate card={right} accent compact className="px-3 py-2" />
          </figcaption>
        </figure>
      </div>
      {unknown.length ? <Unknown items={unknown} className="mt-4 lg:hidden" /> : null}
    </div>
  );
}
