"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { GAP_LABELS, type GapState, type WsCase } from "@/lib/workspace";

const INK = "#24212B";
const MUTED = "#625E68";
const RULE = "#E2DEE6";
const VIOLET = "#69518C";
const AMBER = "#AD7629";
const AMBER_TEXT = "#8A5A17";
const SPEED = 18;
const VIEW_H = 214;
const SEQUENCING = new Set(["Allele fraction (VAF)", "Read depth"]);

type Motion = { moving: boolean; paused: boolean };

function Loop({ label, motion, children }: { label: string; motion: Motion; children: React.ReactNode }) {
  const view = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLDivElement>(null);
  const copy = useRef<HTMLDivElement>(null);
  const anim = useRef<Animation | null>(null);
  const hold = useRef(motion.paused);
  hold.current = motion.paused;

  useLayoutEffect(() => {
    const t = track.current;
    const c = copy.current;
    if (!motion.moving || !t || !c) return;
    let a: Animation | null = null;
    const start = () => {
      const h = c.offsetHeight;
      if (!h) return;
      const at = a ? (a.currentTime as number) / ((a.effect?.getTiming().duration as number) || 1) : 0;
      a?.cancel();
      const duration = (h / SPEED) * 1000;
      a = t.animate([{ transform: "translateY(0)" }, { transform: `translateY(-${h}px)` }], { duration, iterations: Infinity, easing: "linear" });
      a.currentTime = (at % 1) * duration;
      if (hold.current) a.pause();
      anim.current = a;
    };
    start();
    let lastH = c.offsetHeight;
    const ro = new ResizeObserver(() => {
      if (c.offsetHeight === lastH) return;
      lastH = c.offsetHeight;
      start();
    });
    ro.observe(c);
    return () => {
      ro.disconnect();
      a?.cancel();
      anim.current = null;
    };
  }, [motion.moving]);

  useEffect(() => {
    const a = anim.current;
    if (!a) return;
    if (motion.paused) a.pause();
    else a.play();
  }, [motion.paused, motion.moving]);

  useEffect(() => {
    const v = view.current;
    if (!motion.moving || !v) return;
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => (e.target as HTMLElement).toggleAttribute("data-reading", e.isIntersecting)),
      { root: v, rootMargin: "-41% 0px -57% 0px", threshold: 0 }
    );
    v.querySelectorAll("[data-row]").forEach((r) => io.observe(r));
    return () => io.disconnect();
  }, [motion.moving]);

  return (
    <div
      ref={view}
      role="region"
      aria-label={label}
      tabIndex={motion.moving ? undefined : 0}
      className={`relative outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#69518C] ${motion.moving ? "overflow-hidden" : "overflow-y-auto"} [mask-image:linear-gradient(to_bottom,transparent,#000_22px,#000_calc(100%-26px),transparent)]`}
      style={{ height: VIEW_H }}
    >
      <div ref={track} className="will-change-transform">
        <div ref={copy}>{children}</div>
        {motion.moving ? <div aria-hidden="true">{children}</div> : null}
      </div>
    </div>
  );
}

type Tone = GapState | "in_file" | "not_recorded_review" | "pending" | "reviewed";

const PILL: Record<Tone, { fg: string; bg: string; rule: string; label?: string }> = {
  in_file: { fg: VIOLET, bg: "rgba(105,81,140,0.12)", rule: VIOLET, label: "In file" },
  not_supplied: { fg: AMBER_TEXT, bg: "rgba(173,118,41,0.13)", rule: AMBER },
  not_assessed: { fg: MUTED, bg: "rgba(98,94,104,0.12)", rule: "#9C97A3" },
  not_recorded: { fg: MUTED, bg: "rgba(98,94,104,0.12)", rule: "#9C97A3" },
  lookup_failed: { fg: "#A2483A", bg: "rgba(201,119,106,0.14)", rule: "#C9776A" },
  not_recorded_review: { fg: MUTED, bg: "rgba(98,94,104,0.12)", rule: "#9C97A3", label: "Not recorded" },
  pending: { fg: AMBER_TEXT, bg: "rgba(173,118,41,0.13)", rule: AMBER, label: "Waiting" },
  reviewed: { fg: VIOLET, bg: "rgba(105,81,140,0.12)", rule: VIOLET, label: "Reviewed" },
};

function Pill({ tone }: { tone: Tone }) {
  const p = PILL[tone];
  return (
    <span className="inline-flex h-5 items-center whitespace-nowrap rounded-full px-2.5 font-mono text-[11px] uppercase leading-none tracking-[0.06em]" style={{ color: p.fg, background: p.bg }}>
      {p.label ?? GAP_LABELS[tone as GapState]}
    </span>
  );
}

function HumanTag({ done }: { done: boolean }) {
  return (
    <span className="inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-[5px] border border-[#24212B]/70 bg-white px-2 font-mono text-[11px] font-medium uppercase leading-none tracking-[0.06em] text-[#24212B]">
      <span aria-hidden="true" className="h-[7px] w-[7px] rounded-full" style={{ background: done ? VIOLET : AMBER }} />
      {done ? "Reviewed" : "Waiting"}
    </span>
  );
}

function Row({ tone, title, comment, data = true, tag }: { tone: Tone; title: React.ReactNode; comment: string; data?: boolean; tag?: React.ReactNode }) {
  return (
    <div data-row={data ? "" : undefined} className="group grid grid-cols-[112px_minmax(0,1fr)] items-center gap-3 pb-1.5 font-mono text-[13px] leading-[20px]">
      <span className="flex justify-end">
        {tag ?? <Pill tone={tone} />}
      </span>
      <div
        className="min-w-0 rounded-[8px] border-l-2 px-3.5 py-1.5 transition-[background-color] duration-300 group-data-[reading]:bg-[#69518C]/[0.07]"
        style={{ borderLeftColor: tag ? INK : PILL[tone].rule }}
      >
        <p className="truncate" style={{ color: INK }}>
          {title}
        </p>
        <p className="truncate" style={{ color: "#8A8592" }}>
          {"// "}{comment}
        </p>
      </div>
    </div>
  );
}

function Panel({ id, title, meta, className, children, footer }: { id: string; title: string; meta: string; className: string; children: React.ReactNode; footer?: React.ReactNode }) {
  return (
    <div className={`min-w-0 ${className}`}>
      <div className="flex items-baseline justify-between gap-4 border-b pb-2.5" style={{ borderColor: RULE }}>
        <h4 id={id} className="scroll-mt-[104px] font-mono text-[12px] font-normal uppercase tracking-[0.06em] text-[#5B5566]">
          {title}
        </h4>
        <span className="whitespace-nowrap font-mono text-[12px] text-[#5B5566]">{meta}</span>
      </div>
      {children}
      {footer}
    </div>
  );
}

export function CaseLoops({ ws }: { ws: WsCase }) {
  const box = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);
  const [reduce, setReduce] = useState(false);
  const [inView, setInView] = useState(false);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduce(mq.matches);
    sync();
    setMounted(true);
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setInView(e.isIntersecting), { threshold: 0 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const moving = mounted && !reduce;
  const motion: Motion = { moving, paused: paused || !inView };
  const fields = ws.gaps.filter((g) => SEQUENCING.has(g.item));
  const review = ws.gaps.filter((g) => !SEQUENCING.has(g.item));
  const signoff = ws.reviewed === null ? { text: "Review not recorded", ring: MUTED, fill: "transparent" } : ws.reviewed ? { text: "Reviewed", ring: VIOLET, fill: VIOLET } : { text: "Pending", ring: AMBER, fill: AMBER };

  return (
    <div ref={box} className="mt-16">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h3 className="text-balance text-[22px] font-semibold leading-[1.25] tracking-[-0.02em] text-[#24212B]">From variant calls to oncologist review</h3>
          <p className="mt-1.5 text-[15px] text-[#4A4652]">
            Demo case · {ws.title} · {ws.tumor}
          </p>
        </div>
        {moving ? (
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            aria-pressed={paused}
            className="inline-flex h-9 items-center gap-2 rounded-[8px] px-3 text-[14px] font-medium text-[#24212B] underline decoration-[#24212B]/25 underline-offset-[5px] transition-colors duration-150 hover:decoration-[#24212B] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#69518C]"
          >
            <svg aria-hidden="true" viewBox="0 0 12 12" className="h-3 w-3">
              {paused ? <path d="M3 1.75v8.5L10 6z" fill="currentColor" /> : <path d="M3 2h2v8H3zM7 2h2v8H7z" fill="currentColor" />}
            </svg>
            {paused ? "Play animation" : "Pause animation"}
          </button>
        ) : null}
      </div>

      <div className="mt-9 grid grid-cols-12 items-start gap-y-12 lg:gap-x-0">
        <Panel id="labs" title="Variant calls, as received" meta={`${ws.variants.length} variants in the file`} className="col-span-12 lg:col-span-5 lg:pr-8">
          <Loop label="Variant calls as received, by variant" motion={motion}>
            <div className="pt-3">
              {ws.variants.map((v) => (
                <div key={v.key}>
                  <Row tone="in_file" title={`${v.gene}  ${v.short}`} comment={`${v.hgvs} · in the file`} />
                  {fields.map((f) => (
                    <Row key={f.item} tone={f.state} title={`${f.item} · ${v.gene}`} comment={f.note} />
                  ))}
                </div>
              ))}
            </div>
          </Loop>
        </Panel>

        <Panel
          id="hospitals"
          title="Before any treatment decision"
          meta={`${review.length} gaps in this result`}
          className="col-span-12 lg:col-span-7 lg:border-l lg:border-[#E2DEE6] lg:pl-8"
          footer={
            <div className="border-t pt-3" style={{ borderColor: RULE }}>
              <Row tone={ws.reviewed ? "reviewed" : "pending"} title="Oncologist sign-off" comment={ws.reviewed ? "checked by an oncologist" : "needs an oncologist · nothing is acted on until then"} data={false} tag={<HumanTag done={Boolean(ws.reviewed)} />} />
            </div>
          }
        >
          <Loop label="Gaps the hospital reviews before acting" motion={motion}>
            <div className="pt-3">
              {review.map((g) => (
                <Row key={`${g.item}-${g.scope ?? ""}`} tone={g.state} title={g.scope ? `${g.item} · ${g.scope}` : g.item} comment={g.note} />
              ))}
            </div>
          </Loop>
        </Panel>
      </div>
    </div>
  );
}
