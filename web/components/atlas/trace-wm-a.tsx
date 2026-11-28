"use client";

import { motion } from "framer-motion";
import { ArrowDown, ArrowUpDown, Check, CircleDashed, Minus } from "lucide-react";
import { useEffect, useRef, useState, type FocusEvent as ReactFocusEvent, type PointerEvent as ReactPointerEvent } from "react";
import { RULES, STATE, effectLabel, type Effect } from "./trace-example";

type Src = "onco" | "ot" | "absent";
type Seg = { key: string; src: Src; from: number; to: number; label: string; name: string };
type Row = { id: string; title: string; sub: string; segs: Seg[] };

const EASE = [0.4, 0, 0.2, 1] as const;
const ROW_H = 40;
const GAP = 36;
const CHART_H = ROW_H * 3 + GAP * 2;
const CAP = 0.08;

const FILL: Record<Src, string> = { onco: "#B9A8EC", ot: "#3B3350", absent: "transparent" };
const OUTLINE: Record<Src, string> = { onco: "none", ot: "inset 0 0 0 1px rgba(247,245,240,0.35)", absent: "none" };
const INK: Record<Src, string> = { onco: "#25202F", ot: "#F7F5F0", absent: "#E0B36E" };
const NAMES: Record<Src, string> = { onco: "OncoKB", ot: "OpenTargets", absent: "Absent sources" };
const RIBBON: Record<Src, string> = { onco: "rgba(185,168,236,0.08)", ot: "rgba(247,245,240,0.05)", absent: "transparent" };
const EDGE: Record<Src, string> = { onco: "rgba(185,168,236,0.45)", ot: "rgba(247,245,240,0.25)", absent: "transparent" };

const ABSENT = [
  { key: "dd", name: "DiffDock", w: 0.15, label: "0.15" },
  { key: "civic", name: "CIViC", w: 0.1, label: "0.10" },
  { key: "cp", name: "ClinicalPhase", w: 0.1, label: "0.10" },
  { key: "am", name: "AlphaMissense", w: 0.1, label: "0.10" },
];

function rows(r1: boolean): Row[] {
  const s = r1 ? 0.1 : 1;
  const onco = 0.727 * s;
  let x = 0.55;
  const absent = ABSENT.map((a) => {
    const seg: Seg = { key: a.key, src: "absent", from: x, to: x + a.w, label: a.label, name: a.name };
    x += a.w;
    return seg;
  });
  return [
    {
      id: "nominal",
      title: "Nominal weight",
      sub: "All six sources",
      segs: [
        { key: "onco", src: "onco", from: 0, to: 0.4, label: "0.40", name: "OncoKB" },
        { key: "ot", src: "ot", from: 0.4, to: 0.55, label: "0.15", name: "OpenTargets" },
        ...absent,
      ],
    },
    {
      id: "share",
      title: "Share of present weight",
      sub: "0.45 absent, re-shared",
      segs: [
        { key: "onco", src: "onco", from: 0, to: 0.727, label: "0.727", name: "OncoKB" },
        { key: "ot", src: "ot", from: 0.727, to: 1, label: "0.273", name: "OpenTargets" },
      ],
    },
    {
      id: "sum",
      title: "Share × score",
      sub: "Adds up to the base score",
      segs: [
        { key: "onco", src: "onco", from: 0, to: onco, label: "", name: "OncoKB" },
        { key: "ot", src: "ot", from: onco, to: onco + 0.1365, label: "", name: "OpenTargets" },
      ],
    },
  ];
}

const k = (v: number) => (v * 1000).toFixed(2);

function ribbon(a0: number, a1: number, b0: number, b1: number, y0: number, y1: number) {
  const m = (y0 + y1) / 2;
  return `M${k(a0)},${y0} L${k(a1)},${y0} C${k(a1)},${m} ${k(b1)},${m} ${k(b1)},${y1} L${k(b0)},${y1} C${k(b0)},${m} ${k(a0)},${m} ${k(a0)},${y0} Z`;
}

function edge(a: number, b: number, y0: number, y1: number) {
  const m = (y0 + y1) / 2;
  return `M${k(a)},${y0} C${k(a)},${m} ${k(b)},${m} ${k(b)},${y1}`;
}

function useStill() {
  const [still, setStill] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setStill(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  return still;
}

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(880);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, w };
}

function Was({ show, children }: { show: boolean; children: React.ReactNode }) {
  return (
    <span aria-hidden={!show} className={`ml-2 whitespace-nowrap text-[12px] font-normal leading-4 text-[#F7F5F0]/45 ${show ? "" : "invisible"}`}>
      was {children}
    </span>
  );
}

function Swatch({ src }: { src: Src }) {
  if (src === "absent") return <span className="h-3 w-3 shrink-0 border border-dashed border-[#E0B36E]/80" />;
  return <span className="h-3 w-3 shrink-0" style={{ backgroundColor: FILL[src], boxShadow: OUTLINE[src] }} />;
}

type Tip = { row: number; x: number; y: number } | null;

function Tooltip({ tip, r1, focus }: { tip: Tip; r1: boolean; focus: Src | null }) {
  if (!tip) return null;
  const st = r1 ? STATE.r1 : STATE.l1;
  const lines: { src: Src; name: string; value: string; quiet?: boolean }[][] = [
    [
      { src: "onco", name: "OncoKB", value: "0.40" },
      { src: "ot", name: "OpenTargets", value: "0.15" },
      ...ABSENT.map((a) => ({ src: "absent" as const, name: a.name, value: a.label })),
    ],
    [
      { src: "onco", name: "OncoKB", value: "0.40 → 0.727" },
      { src: "ot", name: "OpenTargets", value: "0.15 → 0.273" },
      { src: "absent", name: "Four others", value: "Absent, not 0", quiet: true },
    ],
    [
      { src: "onco", name: `OncoKB · ${st.level}`, value: `0.727 × ${st.score}` },
      { src: "ot", name: "OpenTargets", value: "0.273 × 0.50" },
    ],
  ];
  const head = ["Nominal weight", "Share of present weight", "Share × score"][tip.row];
  const foot = ["Four sources are absent, not 0. Their 0.45 is re-shared.", "The absent 0.45 is re-shared in proportion over the two present sources.", st.sum][tip.row];
  return (
    <div
      role="presentation"
      className="pointer-events-none absolute z-30 w-[360px] overflow-hidden rounded-[4px] border border-[#F7F5F0]/12 bg-[#3A3446] shadow-[0_4px_40px_rgba(0,0,0,0.5)]"
      style={{ left: tip.x + 16, top: tip.y + 16 }}
    >
      <p className="bg-[#3B3350] px-3 py-2 text-[14px] font-semibold leading-5 text-[#F7F5F0]">{head}</p>
      <ul className="flex flex-col gap-1.5 px-3 py-2.5">
        {lines[tip.row].map((l) => {
          const on = focus === l.src;
          return (
            <li key={l.name} className="flex items-center gap-2 text-[13px] leading-5" style={{ opacity: focus && !on ? 0.55 : 1 }}>
              <Swatch src={l.src} />
              <span className={on ? "font-semibold text-[#F7F5F0]" : "text-[#F7F5F0]/75"}>{l.name}</span>
              <span className={`ml-auto font-mono text-[12.5px] tabular-nums ${l.src === "absent" ? "text-[#E0B36E]" : on ? "font-semibold text-[#F7F5F0]" : "text-[#F7F5F0]/75"}`}>{l.quiet ? <span className="font-sans">{l.value}</span> : l.value}</span>
            </li>
          );
        })}
      </ul>
      <p className={`border-t border-[#F7F5F0]/10 px-3 py-2 text-[12px] leading-[18px] text-[#F7F5F0]/55 ${tip.row === 2 ? "font-mono tabular-nums" : ""}`}>{foot}</p>
    </div>
  );
}

function EffectMark({ e }: { e: Effect }) {
  const cls = "mt-[3px] h-3.5 w-3.5 shrink-0";
  if (e.kind === "num") return <ArrowDown className={cls} strokeWidth={2} color="#F4C7BC" aria-hidden="true" />;
  if (e.kind === "applies") return <Check className={cls} strokeWidth={2} color="#DCD2F7" aria-hidden="true" />;
  if (e.kind === "depends") return <CircleDashed className={cls} strokeWidth={2} color="#C7BBF2" aria-hidden="true" />;
  if (e.kind === "small") return <ArrowUpDown className={cls} strokeWidth={2} color="#C7BBF2" aria-hidden="true" />;
  return <Minus className={cls} strokeWidth={2} color="rgba(247,245,240,0.45)" aria-hidden="true" />;
}

function RuleStrip({ r1, changed, still }: { r1: boolean; changed: boolean; still: boolean }) {
  const last = RULES.length - 1;
  return (
    <ol className="grid grid-cols-6 items-stretch">
      {RULES.map((rule, i) => {
        const e = r1 ? rule.r1 : rule.l1;
        const prev = r1 ? rule.l1 : rule.r1;
        const hit = e.kind === "num";
        const flipped = changed && effectLabel(e) !== effectLabel(prev);
        const radius = `${i === 0 ? 10 : 0}px ${i === last ? 10 : 0}px ${i === last ? 10 : 0}px ${i === 0 ? 10 : 0}px`;
        return (
          <li key={rule.verb} className={`relative flex ${i > 0 ? "-ml-px" : ""} ${hit ? "z-10" : "z-0"}`}>
            <div
              className="flex flex-1 p-px"
              style={{
                borderRadius: radius,
                backgroundColor: hit ? "rgba(201,119,106,0.7)" : "rgba(247,245,240,0.15)",
                transition: still ? "none" : "background-color 300ms cubic-bezier(0.4,0,0.2,1)",
              }}
            >
              <div
                className="flex flex-1 flex-col gap-3 px-4 pb-4 pt-4"
                style={{
                  borderRadius: `calc(${radius.split(" ")[0]} - 1px) calc(${radius.split(" ")[1]} - 1px) calc(${radius.split(" ")[2]} - 1px) calc(${radius.split(" ")[3]} - 1px)`,
                  backgroundColor: "#2E283C",
                  backgroundImage: hit ? "linear-gradient(180deg, rgba(201,119,106,0.14) 0%, rgba(201,119,106,0) 70%)" : "none",
                }}
              >
                <p className="flex items-baseline gap-2">
                  <span className="font-mono text-[12px] leading-4 tabular-nums text-[#F7F5F0]/45">{i + 1}</span>
                  <span className="text-[15px] font-semibold leading-5 text-[#F7F5F0]">{rule.verb}</span>
                </p>
                <p className="flex-1 text-[13px] leading-5 text-[#F7F5F0]/60">{rule.rule.replace(/-/g, "\u2011")}</p>
                <div className="flex min-h-[76px] flex-col border-t border-[#F7F5F0]/10 pt-3">
                  <p className="flex items-start gap-1.5 text-[13px] leading-5" style={{ color: hit ? "#F4C7BC" : e.kind === "na" ? "rgba(247,245,240,0.5)" : "#F7F5F0" }}>
                    <EffectMark e={e} />
                    <span className={hit ? "font-mono text-[13px] font-medium tabular-nums" : ""}>{effectLabel(e)}</span>
                  </p>
                  {flipped ? <p className="mt-1 text-[12px] leading-4 text-[#F7F5F0]/45">was {effectLabel(prev)}</p> : null}
                </div>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function TraceWmA({ r1, changed }: { r1: boolean; changed: boolean }) {
  const still = useStill();
  const bar = useWidth<HTMLDivElement>();
  const chart = useRef<HTMLDivElement>(null);
  const [focus, setFocus] = useState<Src | null>(null);
  const [tip, setTip] = useState<Tip>(null);

  const data = rows(r1);
  const st = r1 ? STATE.r1 : STATE.l1;
  const was = r1 ? STATE.l1 : STATE.r1;
  const total = data[2].segs[1].to;
  const dur = still ? 0 : 0.6;
  const widthTr = still ? "none" : "left 600ms cubic-bezier(0.4,0,0.2,1), width 600ms cubic-bezier(0.4,0,0.2,1), opacity 200ms linear";

  const op = (src: Src) => (focus ? (focus === src ? 1 : 0.3) : 0.9);
  const fits = (seg: Seg) => (seg.to - seg.from) * bar.w >= seg.label.length * 7.4 + 14;

  const move = (row: number, src: Src) => (ev: ReactPointerEvent) => {
    const box = chart.current?.getBoundingClientRect();
    if (!box) return;
    setFocus(src);
    setTip({ row, x: Math.min(ev.clientX - box.left, box.width - 390), y: ev.clientY - box.top });
  };
  const show = (row: number, src: Src) => (ev: ReactFocusEvent<HTMLElement>) => {
    const box = chart.current?.getBoundingClientRect();
    const r = ev.currentTarget.getBoundingClientRect();
    if (!box) return;
    setFocus(src);
    setTip({ row, x: Math.min(r.left - box.left + r.width / 2 - 16, box.width - 390), y: r.bottom - box.top - 12 });
  };
  const leave = () => {
    setFocus(null);
    setTip(null);
  };

  const [n, s, c] = data;
  const y1 = ROW_H * 2 + GAP;
  const y2 = (ROW_H + GAP) * 2;
  const edges: { key: string; src: Src; d: string }[] = [
    { key: "e-a", src: "onco", d: edge(0.4, 0.727, ROW_H, ROW_H + GAP) },
    { key: "e-b", src: "ot", d: edge(0.55, 1, ROW_H, ROW_H + GAP) },
    { key: "e-c", src: "onco", d: edge(0.727, c.segs[0].to, y1, y2) },
    { key: "e-d", src: "ot", d: edge(1, c.segs[1].to, y1, y2) },
  ];
  const ribbons: { key: string; src: Src; d: string }[] = [
    { key: "a-onco", src: "onco", d: ribbon(0, 0.4, 0, 0.727, ROW_H, ROW_H + GAP) },
    { key: "a-ot", src: "ot", d: ribbon(0.4, 0.55, 0.727, 1, ROW_H, ROW_H + GAP) },
    { key: "b-onco", src: "onco", d: ribbon(0, 0.727, c.segs[0].from, c.segs[0].to, ROW_H * 2 + GAP, (ROW_H + GAP) * 2) },
    { key: "b-ot", src: "ot", d: ribbon(0.727, 1, c.segs[1].from, c.segs[1].to, ROW_H * 2 + GAP, (ROW_H + GAP) * 2) },
  ];

  const legend: { src: Src; label: React.ReactNode }[] = [
    { src: "onco", label: <>OncoKB · {st.level}<Was show={changed}>{was.level}</Was></> },
    { src: "ot", label: "OpenTargets · used directly" },
    { src: "absent", label: "Absent, not 0 · DiffDock, CIViC, ClinicalPhase, AlphaMissense" },
  ];

  return (
    <div className="flex flex-col gap-8 motion-reduce:[&_*]:!transition-none">
      <figure className="rounded-[10px] border border-[#F7F5F0]/15 bg-[#2E283C] px-8 pb-7 pt-7">
        <header className="flex items-baseline justify-between gap-6">
          <div>
            <h3 className="text-[20px] font-semibold leading-[27.5px] tracking-[-0.01em] text-[#F7F5F0]">
              Weighted mean of the sources present <span className="font-normal text-[#F7F5F0]/45">{st.level} example</span>
            </h3>
            <p className="mt-1 text-[14px] leading-5 text-[#F7F5F0]/55">Measured as a share of the total weight, 0 to 1. A missing source is left out, not scored 0.</p>
          </div>
        </header>

        <ul className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2" onPointerLeave={() => setFocus(null)}>
          {legend.map((l) => (
            <li key={l.src}>
              <button
                type="button"
                aria-label={"Highlight " + NAMES[l.src]}
                className="flex cursor-pointer items-center gap-2 rounded-[3px] text-[13px] leading-5 text-[#F7F5F0]/75 outline-none focus-visible:ring-2 focus-visible:ring-[#C7BBF2]/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#2E283C]"
                style={{ opacity: focus && focus !== l.src ? 0.3 : 1, transition: still ? "none" : "opacity 200ms linear" }}
                onPointerEnter={() => setFocus(l.src)}
                onFocus={() => setFocus(l.src)}
                onBlur={() => setFocus(null)}
              >
                <Swatch src={l.src} />
                <span className={l.src === "absent" ? "text-[#E0B36E]" : ""}>{l.label}</span>
              </button>
            </li>
          ))}
        </ul>

        <div ref={chart} className="relative mt-5 grid grid-cols-[176px_1fr] gap-x-5" onPointerLeave={leave}>
          <div className="relative" style={{ height: CHART_H }}>
            {data.map((row, i) => (
              <div key={row.id} className="absolute right-0 flex flex-col items-end justify-center text-right" style={{ top: i * (ROW_H + GAP), height: ROW_H }}>
                <p className="text-[13px] leading-[18px] text-[#F7F5F0]">{row.title}</p>
                <p className="text-[12px] leading-4 text-[#F7F5F0]/45">{row.sub}</p>
              </div>
            ))}
          </div>

          <div ref={bar.ref} className="relative" style={{ height: CHART_H }}>
            {[0.2, 0.4, 0.6, 0.8, 1].map((t) => (
              <svg key={t} aria-hidden="true" className="absolute top-0 h-full w-px overflow-visible" style={{ left: `${t * 100}%` }}>
                <line x1="0.5" x2="0.5" y1="0" y2={CHART_H} stroke="rgba(247,245,240,0.14)" strokeDasharray="4,4" />
              </svg>
            ))}
            <div aria-hidden="true" className="absolute left-0 top-0 h-full w-px bg-[#F7F5F0]/35" />

            <svg aria-hidden="true" viewBox={`0 0 1000 ${CHART_H}`} preserveAspectRatio="none" className="pointer-events-none absolute inset-0 h-full w-full">
              {ribbons.map((r) => (
                <motion.path
                  key={r.key}
                  initial={false}
                  animate={{ d: r.d, opacity: focus && focus !== r.src ? 0.25 : 1 }}
                  transition={{ duration: dur, ease: EASE }}
                  fill={RIBBON[r.src]}
                />
              ))}
              {edges.map((r) => (
                <motion.path
                  key={r.key}
                  initial={false}
                  animate={{ d: r.d, opacity: focus && focus !== r.src ? 0.25 : 1 }}
                  transition={{ duration: dur, ease: EASE }}
                  fill="none"
                  stroke={EDGE[r.src]}
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                />
              ))}
            </svg>

            {[n, s, c].map((row, i) => (
              <div key={row.id} className="absolute inset-x-0" style={{ top: i * (ROW_H + GAP), height: ROW_H }}>
                {i === 2 ? <div aria-hidden="true" className="absolute inset-y-0 left-0 right-0 bg-[#F7F5F0]/[0.03]" /> : null}
                {row.segs.map((seg) => (
                  <button
                    type="button"
                    key={seg.key}
                    aria-label={row.title + ", " + seg.name + (seg.src === "absent" ? ", absent, not 0" : "")}
                    className="absolute inset-y-0 flex cursor-pointer items-center justify-center overflow-hidden outline-none focus-visible:z-10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#F7F5F0]"
                    style={{
                      left: `calc(${seg.from * 100}% + ${seg.from > 0 ? 1 : 0}px)`,
                      width: `calc(${(seg.to - seg.from) * 100}% - ${seg.from > 0 ? 1 : 0}px)`,
                      backgroundColor: FILL[seg.src],
                      boxShadow: OUTLINE[seg.src],
                      border: seg.src === "absent" ? "1px dashed rgba(224,179,110,0.7)" : "none",
                      opacity: op(seg.src),
                      transition: widthTr,
                    }}
                    data-seg={`${row.id}-${seg.key}`}
                    onPointerMove={move(i, seg.src)}
                    onFocus={show(i, seg.src)}
                    onBlur={leave}
                  >
                    {seg.label && fits(seg) ? (
                      <span className="whitespace-nowrap font-mono text-[12px] leading-4 tabular-nums" style={{ color: INK[seg.src] }}>
                        {seg.label}
                      </span>
                    ) : null}
                  </button>
                ))}
                {i === 2 ? (
                  <div
                    className="pointer-events-none absolute inset-y-0 flex items-center whitespace-nowrap pl-2.5"
                    style={{ left: `${total * 100}%`, transition: still ? "none" : "left 600ms cubic-bezier(0.4,0,0.2,1)" }}
                  >
                    <span className="font-mono text-[13px] font-medium tabular-nums text-[#F7F5F0]">= {st.base}</span>
                    {r1 ? <span className="ml-2 font-mono text-[13px] font-medium tabular-nums text-[#F4C7BC]">→ 0.08</span> : null}
                  </div>
                ) : null}
                {i === 2 && r1 ? (
                  <>
                    <div
                      aria-hidden="true"
                      className="pointer-events-none absolute inset-y-0"
                      style={{
                        left: `${CAP * 100}%`,
                        width: `${(total - CAP) * 100}%`,
                        backgroundImage: "repeating-linear-gradient(135deg, rgba(244,199,188,0.8) 0 1px, transparent 1px 6px)",
                      }}
                    />
                    <div aria-hidden="true" className="pointer-events-none absolute -bottom-2 -top-2 w-[2px] -translate-x-1/2 bg-[#C9776A]" style={{ left: `${CAP * 100}%` }} />
                    <p className="pointer-events-none absolute -top-6 whitespace-nowrap font-mono text-[12px] leading-4 text-[#F4C7BC]" style={{ left: `calc(${CAP * 100}% - 1px)` }}>
                      Cap 0.08
                    </p>
                  </>
                ) : null}
              </div>
            ))}
          </div>

          <div />
          <div className="relative mt-2 h-4">
            {[0, 0.2, 0.4, 0.6, 0.8, 1].map((t) => (
              <span key={t} className="absolute -translate-x-1/2 font-mono text-[12px] leading-4 tabular-nums text-[#F7F5F0]/45" style={{ left: `${t * 100}%` }}>
                {t === 0 ? "0" : t.toFixed(1)}
              </span>
            ))}
          </div>

          <Tooltip tip={tip} r1={r1} focus={focus} />
        </div>

        <div className="mt-7 grid grid-cols-[176px_1fr] items-baseline gap-x-5 border-t border-[#F7F5F0]/10 pt-6">
          <div className="text-right">
            <p className="text-[13px] leading-[18px] text-[#F7F5F0]">Base score</p>
            <p className="text-[12px] leading-4 text-[#F7F5F0]/45">From 2 of 6 sources</p>
          </div>
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <p className="flex items-baseline">
              <span className="text-[28px] font-semibold leading-[34px] tracking-[-0.01em] tabular-nums text-[#DCD2F7]">{st.base}</span>
              <Was show={changed}>{was.base}</Was>
            </p>
            <p className="font-mono text-[13px] leading-5 tabular-nums text-[#F7F5F0]/75">{st.sum}</p>
            <p aria-hidden={!r1} className={`basis-full text-[14px] leading-5 text-[#F4C7BC] ${r1 ? "" : "invisible"}`}>
              Rule 1 then caps it at 0.08, so it can&apos;t rank as an option. The hatched span is what the cap removes.
            </p>
          </div>
        </div>
      </figure>

      <section aria-label="Rules after the base score" className="flex flex-col gap-4">
        <p className="text-[15px] font-semibold leading-5 text-[#F7F5F0]">
          Then six rules run in order <span className="font-normal text-[#F7F5F0]/55">· the floor is re-applied last</span>
        </p>
        <RuleStrip r1={r1} changed={changed} still={still} />
        <p className="text-[14px] leading-5 text-[#F7F5F0]/55">
          <span className="font-semibold text-[#F7F5F0]/75">Note:</span> Weights are research defaults, not optimised on outcome data. Rule effects depend on the case, so this example stops at the base score.
        </p>
      </section>
    </div>
  );
}
