"use client";

import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";
import { Pause, Play } from "lucide-react";
import { TrackMark } from "@/components/brand/marks";
import type { ShotData } from "@/components/atlas/product-shot";
import { GAP_LABELS } from "@/lib/workspace";

type Cursor = { x: number; y: number; ms: number; down: boolean; hand: boolean; shown: boolean };

const STEPS = [
  { title: "Pick a candidate", body: "Select a ranked therapy and its evidence follows: biomarker, OncoKB level and the sources that were checked.", ms: 4200 },
  { title: "Compare the near-tie", body: "Adagrasib sits 0.01 behind Sotorasib. Scores rank candidates within this case. They are not response probabilities.", ms: 4800 },
  { title: "Open the gaps", body: "Everything the result doesn't contain is listed: missing allele fraction and depth, lookups that weren't stored.", ms: 6200 },
];

const C = {
  text: "#EDEDF3",
  soft: "#B4B2BE",
  dim: "#7C7A87",
  rule: "rgba(237,237,243,0.09)",
  panel: "#1A1920",
  canvas: "#131217",
  card: "#1F1E26",
  row: "rgba(237,237,243,0.06)",
  amber: "#E0B36E",
  violet: "#B9A8EC",
};

function Connector() {
  return (
    <div aria-hidden="true" className="relative mx-auto flex h-7 w-px items-center justify-center" style={{ background: C.rule }}>
      <span className="absolute grid h-4 w-4 place-items-center rounded-full text-[10px] leading-none" style={{ background: C.canvas, color: C.dim, boxShadow: `inset 0 0 0 1px ${C.rule}` }}>+</span>
    </div>
  );
}

export function WorkspaceLoop({ data, tone = "dark" }: { data: ShotData; tone?: "dark" | "light" }) {
  const L = tone === "light" ? { text: "#24212B", soft: "#625E68", rule: "#E2DEE6", dim: "#625E68", line: "rgba(36,33,43,0.3)" } : { text: C.text, soft: C.soft, rule: C.rule, dim: C.dim, line: "rgba(237,237,243,0.35)" };
  const { ws, list, caseHref } = data;
  const reduce = useReducedMotion();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const still = mounted && reduce;
  const first = list[0]?.id;
  const second = list[1]?.id ?? first;
  const [step, setStep] = useState(0);
  const [open, setOpen] = useState(false);
  const [selectedId, setSelectedId] = useState(second);
  const [shift, setShift] = useState(0);
  const [cursor, setCursor] = useState<Cursor>({ x: 300, y: 470, ms: 0, down: false, hand: false, shown: false });
  const [paused, setPaused] = useState(false);
  const [visible, setVisible] = useState(false);
  const frame = useRef<HTMLDivElement>(null);
  const gapsCard = useRef<HTMLDivElement>(null);
  const targets = useRef<Record<string, HTMLElement | null>>({});
  const timers = useRef<number[]>([]);
  const resumed = useRef(false);

  const selected = list.find((c) => c.id === selectedId) ?? list[0];
  const variantOf = (matched: string[]) => ws.variants.find((v) => matched.some((t) => t.toUpperCase() === v.name.toUpperCase()));
  const variant = selected ? variantOf(selected.matched) : undefined;
  const tie = selected ? ws.nearTies.find((t) => t.name === selected.name) : undefined;
  const rank = selected ? list.findIndex((c) => c.id === selected.id) + 1 : 0;

  useLayoutEffect(() => {
    const card = gapsCard.current;
    const inner = card?.parentElement;
    const canvas = inner?.parentElement;
    setShift(open && card && inner && canvas ? Math.max(0, Math.min(card.offsetTop - 16, inner.offsetHeight - canvas.clientHeight)) : 0);
  }, [open]);

  const clear = useCallback(() => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  }, []);

  const point = useCallback((key: string) => {
    const el = targets.current[key];
    const box = frame.current?.getBoundingClientRect();
    if (!el || !box) return null;
    const r = el.getBoundingClientRect();
    return { x: r.left - box.left + Math.min(r.width * 0.4, 130), y: r.top - box.top + r.height * 0.5 };
  }, []);

  const play = useCallback(
    (n: number, chain: boolean) => {
      clear();
      setStep(n);
      const at = (ms: number, fn: () => void) => timers.current.push(window.setTimeout(fn, ms));
      const move = (key: string, ms: number) => {
        const p = point(key);
        if (p) setCursor((c) => ({ ...c, ...p, ms, hand: false, shown: true }));
        at(ms, () => setCursor((c) => ({ ...c, hand: true })));
      };
      const click = (fn: () => void) => {
        setCursor((c) => ({ ...c, down: true }));
        fn();
        at(170, () => setCursor((c) => ({ ...c, down: false })));
      };
      if (n === 0) {
        setOpen(false);
        setSelectedId(second);
        at(80, () => move(`row-${first}`, 750));
        at(1000, () => click(() => setSelectedId(first)));
      } else if (n === 1) {
        setOpen(false);
        setSelectedId(first);
        at(300, () => move(`row-${second}`, 800));
        at(1300, () => click(() => setSelectedId(second)));
      } else {
        setOpen(false);
        setSelectedId(second);
        at(300, () => move("gaps-head", 950));
        at(1450, () => click(() => setOpen(true)));
        at(2300, () => setCursor((c) => ({ ...c, hand: false, x: c.x + 40, y: c.y + 150, ms: 900 })));
      }
      if (chain) at(STEPS[n].ms, () => play((n + 1) % STEPS.length, true));
    },
    [clear, point, first, second],
  );

  useEffect(() => {
    const el = frame.current;
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0, rootMargin: "0px 0px -15% 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (reduce || paused || !visible || !first) {
      clear();
      return;
    }
    const n = resumed.current ? (step + 1) % STEPS.length : step;
    resumed.current = true;
    play(n, true);
    return clear;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reduce, paused, visible, first, play, clear]);

  const choose = (n: number) => {
    if (reduce || paused || !visible) {
      clear();
      setStep(n);
      setOpen(n === 2);
      setSelectedId(n === 0 ? first : second);
      return;
    }
    play(n, true);
  };

  if (!selected) return null;
  const ref = (key: string) => (el: HTMLElement | null) => {
    targets.current[key] = el;
  };
  const gapRows = open ? ws.gaps : ws.gaps.slice(0, 2);

  return (
    <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,400px)_minmax(0,1fr)] lg:gap-16">
      <div className="min-w-0">
        <h2 id="workspace-title" className={tone === "light" ? "text-[28px] font-semibold leading-[1.15] tracking-[-0.02em]" : "text-[24px] font-[480] leading-[1.2] tracking-[0.01em]"} style={{ color: L.text }}>
          Every candidate and its evidence.
          <br />
          Every gap, written down.
        </h2>
        <ol className="mt-12 border-t" style={{ borderColor: L.rule }}>
          {STEPS.map((s, i) => {
            const on = i === step;
            return (
              <li key={s.title} className="border-b" style={{ borderColor: L.rule }}>
                <button
                  type="button"
                  onClick={() => choose(i)}
                  aria-expanded={on}
                  className="relative w-full py-3.5 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#B9A8EC]"
                >
                  {on ? <span aria-hidden="true" className="absolute -left-4 top-[23px] h-[5px] w-[5px] rounded-full" style={{ background: L.text }} /> : null}
                  <span className="block text-[16px] font-[480] leading-[1.35]" style={{ color: on ? L.text : L.soft }}>
                    {s.title}
                  </span>
                  <span className="grid transition-[grid-template-rows,opacity] duration-300 ease-out" style={{ gridTemplateRows: on ? "1fr" : "0fr", opacity: on ? 1 : 0 }}>
                    <span className="overflow-hidden">
                      <span className="block pt-1 text-[16px] leading-[1.45]" style={{ color: L.soft }}>
                        {s.body}
                      </span>
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
        <Link
          href={`${caseHref}?view=candidates`}
          className="mt-8 inline-block text-[16px] font-[480] underline underline-offset-[5px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#B9A8EC]"
          style={{ color: L.text, textDecorationColor: L.line }}
        >
          Explore the demo case
        </Link>
      </div>

      <figure className="m-0 min-w-0 lg:justify-self-end">
        <div
          ref={frame}
          aria-hidden="true"
          className="pointer-events-none relative mx-auto aspect-[4/5] w-full max-w-[480px] select-none overflow-hidden rounded-[14px]"
          style={{ background: C.panel, color: C.text, boxShadow: tone === "light" ? "0 0 0 1px rgba(36,33,43,0.08), 0 28px 60px -32px rgba(34,28,40,0.45)" : `0 0 0 1px ${C.rule}, 0 40px 90px -40px rgba(0,0,0,0.75)` }}
        >
          <div className="flex h-[48px] items-center justify-between border-b px-4" style={{ borderColor: C.rule }}>
            <span className="flex min-w-0 items-center gap-2 text-[12.5px]">
              <TrackMark variant="bold" size={14} ink={C.dim} accent={C.violet} />
              <span style={{ color: C.dim }}>Case review</span>
              <span style={{ color: C.dim }}>/</span>
              <span className="truncate">{ws.title}</span>
            </span>
            <span className="rounded-full px-2 py-0.5 text-[10.5px]" style={{ color: C.dim, boxShadow: `inset 0 0 0 1px ${C.rule}` }}>Demo case</span>
          </div>

          <div
            className="relative h-[calc(100%-48px)] overflow-hidden"
            style={{ background: C.canvas, backgroundImage: "radial-gradient(rgba(237,237,243,0.07) 1px, transparent 1px)", backgroundSize: "16px 16px" }}
          >
            <div className="px-5 pt-5 transition-transform duration-700 ease-[cubic-bezier(0.45,0,0.2,1)]" style={{ transform: `translateY(${-shift}px)` }}>
              <div className="rounded-[10px] p-1.5" style={{ background: C.card, boxShadow: `inset 0 0 0 1px ${C.rule}` }}>
                <div className="flex items-center justify-between px-2.5 pb-1.5 pt-1.5 text-[11px]" style={{ color: C.dim }}>
                  <span>Candidates · {ws.tumorShort ?? ws.tumor}</span>
                  <span>Case score</span>
                </div>
                {list.map((c) => {
                  const v = variantOf(c.matched);
                  const on = c.id === selected.id;
                  return (
                    <div key={c.id} ref={ref(`row-${c.id}`)} className="flex items-center justify-between gap-3 rounded-[7px] px-2.5 py-2 transition-colors duration-200" style={{ background: on ? C.row : "transparent" }}>
                      <span className="flex min-w-0 items-center gap-2.5">
                        <span className="grid h-[22px] w-[22px] shrink-0 place-items-center rounded-full text-[10px] font-[480]" style={{ boxShadow: `inset 0 0 0 1px ${C.rule}`, color: on ? C.text : C.soft }}>
                          {c.name.charAt(0)}
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-[12.5px]">{c.name}</span>
                          <span className="block truncate text-[10.5px]" style={{ color: C.dim }}>{v ? `${v.name} · ${v.level?.short ?? "No level"}` : "Variant not recorded"}</span>
                        </span>
                      </span>
                      <span className="text-[12.5px] tabular-nums" style={{ color: on ? C.text : C.soft }}>{c.score?.toFixed(2) ?? "—"}</span>
                    </div>
                  );
                })}
              </div>

              <Connector />

              <div key={selected.id} className="animate-[oo-fade_260ms_ease-out] rounded-[10px] px-4 py-3.5" style={{ background: C.card, boxShadow: `inset 0 0 0 1px ${C.rule}` }}>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[11px]" style={{ color: C.dim }}>Evidence</p>
                  {variant?.level ? <span className="rounded-full px-2 py-0.5 text-[10.5px]" style={{ color: C.violet, boxShadow: "inset 0 0 0 1px rgba(185,168,236,0.3)" }}>{variant.level.label}</span> : null}
                </div>
                <p className="mt-1.5 text-[14px] font-[480]">{selected.name}</p>
                <p className="mt-0.5 text-[11px]" style={{ color: tie ? C.violet : C.dim }}>{tie ? `Near-tie with ${tie.above}` : `Ranked ${rank} of ${list.length} in this case`}</p>
                <dl className="mt-3 space-y-2 border-t pt-3 text-[11.5px] leading-[1.5]" style={{ borderColor: C.rule }}>
                  {[
                    ["Biomarker", `${variant?.name ?? "Not recorded"}${variant?.hgvs ? ` · ${variant.hgvs}` : ""}`],
                    ["Evidence", variant?.level?.meaning ?? "Not recorded in this result"],
                    ["Sources", selected.sources.join(" · ") || "Not recorded"],
                  ].map(([k, v]) => (
                    <div key={k} className="grid grid-cols-[72px_1fr] gap-3">
                      <dt style={{ color: C.dim }}>{k}</dt>
                      <dd style={{ color: C.soft }}>{v}</dd>
                    </div>
                  ))}
                </dl>
              </div>

              <Connector />

              <div ref={gapsCard} className="rounded-[10px] p-1.5" style={{ background: C.card, boxShadow: open ? `inset 0 0 0 1px rgba(224,179,110,0.35)` : `inset 0 0 0 1px ${C.rule}` }}>
                <div ref={ref("gaps-head")} className="flex items-center justify-between px-2.5 pb-1 pt-1.5 text-[11px]">
                  <span style={{ color: C.dim }}>Gaps · not in this result</span>
                  <span className="tabular-nums" style={{ color: C.amber }}>{ws.gaps.length}</span>
                </div>
                {gapRows.map((g) => (
                  <div key={`${g.item}-${g.scope ?? ""}`} className="flex animate-[oo-fade_240ms_ease-out] items-center justify-between gap-3 px-2.5 py-[7px]">
                    <span className="flex min-w-0 items-center gap-2.5">
                      <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: C.amber }} />
                      <span className="truncate text-[12px]">{g.item}{g.scope ? <span style={{ color: C.dim }}> · {g.scope}</span> : null}</span>
                    </span>
                    <span className="shrink-0 text-[11px]" style={{ color: C.amber }}>{GAP_LABELS[g.state]}</span>
                  </div>
                ))}
                {!open && ws.gaps.length > 2 ? <p className="px-2.5 pb-1.5 pt-0.5 text-[11px]" style={{ color: C.dim }}>{ws.gaps.length - 2} more</p> : null}
              </div>
              <div className="h-10" />
            </div>
            <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 h-16" style={{ background: `linear-gradient(to bottom, rgba(19,18,23,0), ${C.canvas})` }} />
          </div>

          {!still ? (
            <span
              className="absolute left-0 top-0 z-10"
              style={{
                transform: `translate(${cursor.x}px, ${cursor.y}px)`,
                transition: `transform ${cursor.ms}ms cubic-bezier(0.45, 0, 0.2, 1), opacity 300ms`,
                opacity: cursor.shown ? 1 : 0,
              }}
            >
              <svg width="20" height="22" viewBox="0 0 20 22" className={`absolute -left-[3px] -top-[2px] transition-transform duration-150 ${cursor.down ? "scale-90" : ""}`} style={{ opacity: cursor.hand ? 0 : 1 }}>
                <path d="M3 2v15.2l3.9-3.8 2.7 6.3 2.5-1.1-2.7-6.2h5.4L3 2z" fill="#fff" stroke="#000" strokeWidth="1.2" strokeLinejoin="round" />
              </svg>
              <svg width="20" height="22" viewBox="0 0 20 22" className={`absolute -left-[7px] -top-[1px] transition-transform duration-150 ${cursor.down ? "scale-90" : ""}`} style={{ opacity: cursor.hand ? 1 : 0 }}>
                <path d="M7.2 1.5c.9 0 1.6.7 1.6 1.6v6l.6-.1c.8-.2 1.6.2 1.9.9l.5-.1c.8-.2 1.6.3 1.8 1l.4-.1c.9-.1 1.7.5 1.8 1.4l.2 3.2c.1 2.3-.6 4.2-2.2 5.6H8.1c-1-1-2.6-3-3.6-4.4l-1.6-2.2c-.5-.7-.4-1.7.3-2.2.7-.5 1.6-.4 2.1.2l.3.4V3.1c0-.9.7-1.6 1.6-1.6z" fill="#fff" stroke="#000" strokeWidth="1.1" strokeLinejoin="round" />
              </svg>
            </span>
          ) : null}
        </div>
        <figcaption className="mx-auto mt-3 flex max-w-[480px] items-center justify-between gap-3 font-mono text-[11.5px] uppercase tracking-[0.04em]" style={{ color: L.dim }}>
          <span><span className="hidden sm:inline">Fig 0.1 · </span>Demo case · not a patient</span>
          {!still ? (
            <button
              type="button"
              onClick={() => setPaused((p) => !p)}
              aria-label={paused ? "Play the walkthrough" : "Pause the walkthrough"}
              className={`flex h-9 shrink-0 items-center gap-1.5 rounded-md px-2 uppercase ${tone === "light" ? "hover:text-[#24212B]" : "hover:text-[#EDEDF3]"} focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#B9A8EC]`}
            >
              {paused ? <Play size={12} aria-hidden="true" /> : <Pause size={12} aria-hidden="true" />}
              {paused ? "Play" : "Pause"}
            </button>
          ) : null}
        </figcaption>
        <p className="sr-only">
          Walkthrough of the KRAS G12C demo case: selecting Sotorasib and Adagrasib shows each one&apos;s evidence and their near-tie, then the gaps card opens to list {ws.gaps.length} items the result does not contain.
        </p>
      </figure>
    </div>
  );
}
