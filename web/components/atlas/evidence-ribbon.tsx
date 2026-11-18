"use client";

import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

export type Pt = { x: number; y: number };
type Curve = [Pt, Pt, Pt, Pt];
type Layout = "hero" | "compact" | "closing";

export type ThreadNode = { label: string; value: string; accent?: boolean; href?: string; view?: string };

const NO_NODES: ThreadNode[] = [];
const UPPER = "#8270A4";
const CONVERGE = "#69518C";
const LOWER = "#B4A5C8";
const SELECTED = "#7555A6";
const TWIST_PHASE = 0.6;
const PINCH_T = (Math.PI - TWIST_PHASE) / (1.35 * Math.PI);
const SCROLL_RANGE = 200;
const DRIFT_MAX = 14;

function bez(c: Curve, t: number): Pt {
  const u = 1 - t;
  const a = u * u * u;
  const b = 3 * u * u * t;
  const d = 3 * u * t * t;
  const e = t * t * t;
  return { x: a * c[0].x + b * c[1].x + d * c[2].x + e * c[3].x, y: a * c[0].y + b * c[1].y + d * c[2].y + e * c[3].y };
}

function tangent(c: Curve, t: number): Pt {
  const u = 1 - t;
  const x = 3 * u * u * (c[1].x - c[0].x) + 6 * u * t * (c[2].x - c[1].x) + 3 * t * t * (c[3].x - c[2].x);
  const y = 3 * u * u * (c[1].y - c[0].y) + 6 * u * t * (c[2].y - c[1].y) + 3 * t * t * (c[3].y - c[2].y);
  const len = Math.hypot(x, y) || 1;
  return { x: x / len, y: y / len };
}

function spine(layout: Layout, w: number, h: number): Curve {
  if (layout === "compact")
    return [
      { x: w * 1.15, y: -h * 0.1 },
      { x: w * 0.55, y: h * 0.2 },
      { x: w * 1.05, y: h * 0.75 },
      { x: w * 0.55, y: h * 1.2 },
    ];
  if (layout === "closing")
    return [
      { x: w * 1.05, y: -h * 0.2 },
      { x: w * 0.75, y: h * 0.4 },
      { x: w * 0.55, y: h * 0.6 },
      { x: w * 0.4, y: h * 1.3 },
    ];
  return [
    { x: w * 1.12, y: -h * 0.16 },
    { x: w * 0.36, y: h * 0.18 },
    { x: w * 1.16, y: h * 0.72 },
    { x: w * 0.5, y: h * 1.2 },
  ];
}

export function pinchPoint(w: number, h: number): Pt {
  return bez(spine("hero", w, h), PINCH_T);
}

function threadCurve(layout: Layout, w: number, h: number, from: Pt): Curve {
  if (layout === "compact") return [from, { x: from.x - w * 0.25, y: from.y + h * 0.05 }, { x: w * 0.3, y: h * 0.5 }, { x: w * 0.08, y: h * 0.78 }];
  return [from, { x: from.x - w * 0.3, y: from.y + h * 0.03 }, { x: w * 0.32, y: h * 0.38 }, { x: w * 0.1, y: h * 0.4 }];
}

function curvePath(c: Curve) {
  return `M${c[0].x.toFixed(1)} ${c[0].y.toFixed(1)} C${c[1].x.toFixed(1)} ${c[1].y.toFixed(1)} ${c[2].x.toFixed(1)} ${c[2].y.toFixed(1)} ${c[3].x.toFixed(1)} ${c[3].y.toFixed(1)}`;
}

const clamp = (v: number) => Math.min(1, Math.max(0, v));

export function EvidenceRibbon({
  layout = "hero",
  nodes = NO_NODES,
  threads = 90,
  className,
  thread = true,
  trace: showTrace = true,
  tone = "light",
}: {
  layout?: Layout;
  nodes?: ThreadNode[];
  threads?: number;
  className?: string;
  thread?: boolean;
  trace?: boolean;
  tone?: "light" | "dark";
}) {
  const box = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const trace = useRef<SVGPathElement>(null);
  const [geo, setGeo] = useState<{ w: number; h: number; d: string; nodes: (Pt & ThreadNode & { side: "start" | "mid" | "end" })[] } | null>(null);
  const [hot, setHot] = useState<number | null>(null);

  useEffect(() => {
    const el = box.current;
    const cv = canvas.current;
    const ctx = cv?.getContext("2d");
    if (!el || !cv || !ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scrolls = layout === "hero" && !reduce;
    let w = 0;
    let h = 0;
    let prog = scrolls ? 0 : 1;
    let len = 0;
    const seeds = Array.from({ length: threads }, (_, k) => ({
      j: Math.sin(k * 12.9898) * 0.5,
      a: (Math.sin(k * 78.233) + 1) / 2,
      lw: 0.7 + ((Math.sin(k * 3.7) + 1) / 2) * 0.3,
    }));
    const chosen = Math.round(threads * 0.42);

    const setTrace = () => {
      const p = trace.current;
      if (!p) return;
      if (!len) len = p.getTotalLength();
      const t = scrolls ? clamp((prog - 0.1) / 0.8) : 1;
      p.style.strokeDasharray = `${len}`;
      p.style.strokeDashoffset = `${len * (1 - t)}`;
    };

    const draw = () => {
      if (!w || !h) return;
      ctx.clearRect(0, 0, w, h);
      const c = spine(layout, w, h);
      const pinch = bez(c, PINCH_T);
      const base = Math.min(w, h) * (layout === "compact" ? 0.5 : layout === "hero" ? 0.46 : 0.32);
      const grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, UPPER);
      grad.addColorStop(Math.min(0.9, Math.max(0.1, pinch.y / h)), CONVERGE);
      grad.addColorStop(1, LOWER);
      ctx.lineCap = "round";
      const steps = 90;
      const at = (t: number, u: number, k: number, j: number) => {
        const p = bez(c, t);
        const n = tangent(c, t);
        const twist = Math.sin(Math.PI * (t * 1.35) + TWIST_PHASE);
        const width = base * (Math.sign(twist || 1) * 0.02 + 0.98 * twist);
        const wobble = Math.sin(t * 9 + k * 0.7) * 1.4 * j * Math.min(1, Math.abs(twist) * 4);
        const off = u * width + wobble;
        return { x: p.x - n.y * off, y: p.y + n.x * off };
      };
      const strand = (u: number, k: number, j: number) => {
        ctx.beginPath();
        for (let i = 0; i <= steps; i++) {
          const q = at(i / steps, u, k, j);
          if (i === 0) ctx.moveTo(q.x, q.y);
          else ctx.lineTo(q.x, q.y);
        }
      };
      ctx.beginPath();
      for (let i = 0; i <= steps; i++) {
        const q = at(i / steps, -0.5, 0, 0);
        if (i === 0) ctx.moveTo(q.x, q.y);
        else ctx.lineTo(q.x, q.y);
      }
      for (let i = steps; i >= 0; i--) {
        const q = at(i / steps, 0.5, 0, 0);
        ctx.lineTo(q.x, q.y);
      }
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.globalAlpha = tone === "dark" ? 0.1 : 0.06;
      ctx.fill();
      ctx.strokeStyle = grad;
      const soften = 1 - 0.25 * clamp(prog / 0.3);
      for (let k = 0; k < threads; k++) {
        if (k === chosen) continue;
        const u = k / (threads - 1) - 0.5;
        const sd = seeds[k];
        strand(u, k, sd.j);
        const edge = 1 - Math.abs(u) * 1.2;
        ctx.globalAlpha = (0.22 + sd.a * 0.16) * (0.5 + 0.5 * Math.max(0, edge)) * soften * (tone === "dark" ? 1.3 : 1);
        ctx.lineWidth = sd.lw;
        ctx.stroke();
      }
      if (thread) {
        const sd = seeds[chosen];
        strand(chosen / (threads - 1) - 0.5, chosen, sd.j);
        const lift = clamp(prog / 0.3);
        ctx.strokeStyle = SELECTED;
        ctx.globalAlpha = 0.5 + 0.5 * lift;
        ctx.lineWidth = 1.6 + 0.4 * lift;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      cv.style.transform = scrolls && showTrace ? `translate3d(0, ${(-DRIFT_MAX * prog).toFixed(2)}px, 0)` : "";
    };

    const measure = () => {
      const r = el.getBoundingClientRect();
      w = Math.round(r.width);
      h = Math.round(r.height);
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      cv.width = w * dpr;
      cv.height = h * dpr;
      cv.style.width = `${w}px`;
      cv.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const c = spine(layout, w, h);
      const tc = threadCurve(layout, w, h, bez(c, PINCH_T));
      const fr = nodes.length >= 3 ? [0, 0.55, 1] : [0, 1];
      len = 0;
      setGeo({
        w,
        h,
        d: curvePath(tc),
        nodes: nodes.slice(0, fr.length).map((nd, i) => ({ ...nd, ...bez(tc, fr[i]), side: i === 0 ? "start" : i === fr.length - 1 ? "end" : "mid" })),
      });
      draw();
    };

    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    const st = scrolls
      ? ScrollTrigger.create({
          start: 0,
          end: SCROLL_RANGE,
          scrub: 0.25,
          onUpdate: (self) => {
            prog = self.progress;
            draw();
            setTrace();
          },
        })
      : null;
    const raf = requestAnimationFrame(setTrace);
    return () => {
      ro.disconnect();
      st?.kill();
      cancelAnimationFrame(raf);
    };
  }, [layout, threads, nodes, tone, thread, showTrace]);

  useEffect(() => {
    const p = trace.current;
    if (!p || !geo) return;
    const len = p.getTotalLength();
    const scrolls = layout === "hero" && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const t = scrolls ? clamp((Math.min(window.scrollY, SCROLL_RANGE) / SCROLL_RANGE - 0.1) / 0.8) : 1;
    p.style.strokeDasharray = `${len}`;
    p.style.strokeDashoffset = `${len * (1 - t)}`;
  }, [geo, layout]);

  const place = (side: "start" | "mid" | "end") =>
    side === "start" ? "bottom-[14px] right-6 text-right" : side === "mid" ? "right-0 top-[14px] text-right" : layout === "hero" ? "bottom-[14px] left-0" : "left-0 top-[14px]";

  return (
    <div ref={box} className={className}>
      <canvas ref={canvas} aria-hidden="true" className="absolute inset-0 will-change-transform" />
      {thread && showTrace && geo ? (
        <svg aria-hidden="true" className="absolute inset-0 overflow-visible" width={geo.w} height={geo.h} viewBox={`0 0 ${geo.w} ${geo.h}`}>
          <path d={geo.d} fill="none" stroke={CONVERGE} strokeOpacity={hot !== null ? 0.55 : 0.3} strokeWidth="1.5" strokeLinecap="round" className="transition-[stroke-opacity] duration-150" />
          <path ref={trace} d={geo.d} fill="none" stroke={CONVERGE} strokeWidth={hot !== null ? 2.25 : 1.75} strokeLinecap="round" className="transition-[stroke-width] duration-150" />
        </svg>
      ) : null}
      {geo ? geo.nodes.map((n, i) => <NodeMark key={n.label} node={n} at={n} ring={n.side === "start"} place={place(n.side)} hot={hot === i} onHot={(on) => setHot(on ? i : null)} />) : null}
    </div>
  );
}

export function NodeMark({ node, at, ring, place, hot, onHot }: { node: ThreadNode; at: Pt; ring: boolean; place: string; hot: boolean; onHot: (on: boolean) => void }) {
  const dot = ring ? "-left-[8px] -top-[8px] h-4 w-4 border-[3px] border-[#F7F5F0] bg-[#69518C]" : "-left-[3px] -top-[3px] h-[6px] w-[6px] bg-[#69518C]";
  const body = (
    <>
      <span aria-hidden="true" className={`absolute rounded-full transition-transform duration-150 ${dot} ${hot ? "scale-125" : ""}`} />
      <span className={`absolute whitespace-nowrap ${place}`}>
        <span className="block text-[12px] leading-[18px] text-[#625E68]">{node.label}</span>
        <span className={`block text-[17px] font-medium leading-[24px] tracking-[-0.01em] ${node.accent ? "text-[#69518C]" : "text-[#24212B]"}`}>
          <span className={node.href ? "decoration-[#69518C]/50 decoration-1 underline-offset-[5px] group-hover:underline group-focus-visible:underline" : ""}>{node.value}</span>
          {node.href ? (
            <span aria-hidden="true" className="ml-1.5 inline-block text-[15px] text-[#69518C] opacity-60 transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100">
              →
            </span>
          ) : null}
        </span>
      </span>
    </>
  );
  return node.href ? (
    <a
      href={node.href}
      onClick={() => {
        if (node.view) window.dispatchEvent(new CustomEvent("atlas:view", { detail: node.view }));
      }}
      onMouseEnter={() => onHot(true)}
      onMouseLeave={() => onHot(false)}
      onFocus={() => onHot(true)}
      onBlur={() => onHot(false)}
      aria-label={`${node.label}: ${node.value}. Open in the demo`}
      className="group pointer-events-auto absolute block h-11 w-11 -translate-x-1/2 -translate-y-1/2 rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-[#69518C]"
      style={{ left: at.x, top: at.y }}
    >
      <span className="absolute left-1/2 top-1/2">{body}</span>
    </a>
  ) : (
    <div className="absolute" style={{ left: at.x, top: at.y }}>
      {body}
    </div>
  );
}
