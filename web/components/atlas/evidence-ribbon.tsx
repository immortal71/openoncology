"use client";

import { useEffect, useRef, useState } from "react";
import gsap from "gsap";

type Pt = { x: number; y: number };
type Curve = [Pt, Pt, Pt, Pt];
type Layout = "hero" | "compact" | "closing";

export type ThreadNode = { label: string; value: string; accent?: boolean };

const NO_NODES: ThreadNode[] = [];
const STOPS = ["#2E2170", "#4B3A9A", "#7A66CC", "#B596DF", "#D9669A"];
const TWIST_PHASE = 0.6;
const PINCH_T = (Math.PI - TWIST_PHASE) / (1.35 * Math.PI);

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

function threadCurve(layout: Layout, w: number, h: number, from: Pt): Curve {
  if (layout === "compact") return [from, { x: from.x - w * 0.25, y: from.y + h * 0.05 }, { x: w * 0.3, y: h * 0.5 }, { x: w * 0.08, y: h * 0.78 }];
  return [from, { x: from.x - w * 0.3, y: from.y + h * 0.03 }, { x: w * 0.32, y: h * 0.38 }, { x: w * 0.1, y: h * 0.4 }];
}

function curvePath(c: Curve) {
  return `M${c[0].x.toFixed(1)} ${c[0].y.toFixed(1)} C${c[1].x.toFixed(1)} ${c[1].y.toFixed(1)} ${c[2].x.toFixed(1)} ${c[2].y.toFixed(1)} ${c[3].x.toFixed(1)} ${c[3].y.toFixed(1)}`;
}

export function EvidenceRibbon({
  layout = "hero",
  nodes = NO_NODES,
  threads = 150,
  className,
  thread = true,
  tone = "light",
}: {
  layout?: Layout;
  nodes?: ThreadNode[];
  threads?: number;
  className?: string;
  thread?: boolean;
  tone?: "light" | "dark";
}) {
  const box = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const threadPath = useRef<SVGPathElement>(null);
  const [geo, setGeo] = useState<{ w: number; h: number; d: string; nodes: (Pt & ThreadNode & { side: "start" | "mid" | "end" })[] } | null>(null);

  useEffect(() => {
    const el = box.current;
    const cv = canvas.current;
    const ctx = cv?.getContext("2d");
    if (!el || !cv || !ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0;
    let h = 0;
    let drift = 0;
    let breathe = 1;
    let visible = true;
    const seeds = Array.from({ length: threads }, (_, k) => ({
      j: Math.sin(k * 12.9898) * 0.5,
      a: 0.25 + ((Math.sin(k * 78.233) + 1) / 2) * 0.55,
      lw: 0.6 + ((Math.sin(k * 3.7) + 1) / 2) * 0.9,
    }));

    const draw = () => {
      if (!w || !h) return;
      ctx.clearRect(0, 0, w, h);
      const c = spine(layout, w, h);
      const base = Math.min(w, h) * (layout === "compact" ? 0.5 : layout === "hero" ? 0.46 : 0.32) * breathe;
      const grad = ctx.createLinearGradient(w, 0, w * 0.2, h);
      STOPS.forEach((s, i) => grad.addColorStop(i / (STOPS.length - 1), s));
      ctx.lineCap = "round";
      const steps = 90;
      const at = (t: number, u: number, k: number, j: number) => {
        const p = bez(c, t);
        const n = tangent(c, t);
        const twist = Math.sin(Math.PI * (t * 1.35) + TWIST_PHASE);
        const width = base * (Math.sign(twist || 1) * 0.02 + 0.98 * twist);
        const wobble = Math.sin(t * 9 + k * 0.7 + drift) * 1.4 * j * Math.min(1, Math.abs(twist) * 4);
        const off = u * width + wobble;
        return { x: p.x - n.y * off, y: p.y + n.x * off };
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
      ctx.globalAlpha = tone === "dark" ? 0.18 : 0.1;
      ctx.fill();
      ctx.strokeStyle = grad;
      for (let k = 0; k < threads; k++) {
        const u = k / (threads - 1) - 0.5;
        const sd = seeds[k];
        ctx.beginPath();
        for (let i = 0; i <= steps; i++) {
          const q = at(i / steps, u, k, sd.j);
          if (i === 0) ctx.moveTo(q.x, q.y);
          else ctx.lineTo(q.x, q.y);
        }
        const edge = 1 - Math.abs(u) * 1.2;
        ctx.globalAlpha = Math.max(0.08, sd.a * (0.45 + 0.55 * edge)) * (tone === "dark" ? 1.2 : 0.78);
        ctx.lineWidth = sd.lw;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
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
    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting));
    io.observe(el);
    const start = performance.now();
    const tick = () => {
      if (!visible) return;
      const s = (performance.now() - start) / 1000;
      drift = s * 0.35;
      breathe = 1 + Math.sin(s / 3.2) * 0.035;
      draw();
    };
    if (!reduce) gsap.ticker.add(tick);
    return () => {
      ro.disconnect();
      io.disconnect();
      gsap.ticker.remove(tick);
    };
  }, [layout, threads, nodes, tone]);

  useEffect(() => {
    const p = threadPath.current;
    if (!p || !geo) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const len = p.getTotalLength();
    const tl = gsap.timeline({ delay: 0.8 });
    tl.fromTo(p, { strokeDasharray: len, strokeDashoffset: len }, { strokeDashoffset: 0, duration: 1.6, ease: "power2.inOut" });
    tl.fromTo(box.current!.querySelectorAll("[data-node]"), { opacity: 0 }, { opacity: 1, duration: 0.5, ease: "power2.out", stagger: 0.6 }, 0);
    return () => {
      tl.kill();
    };
  }, [geo]);

  return (
    <div ref={box} className={className}>
      <canvas ref={canvas} aria-hidden="true" className="absolute inset-0" />
      {thread && geo ? (
        <svg aria-hidden="true" className="absolute inset-0 overflow-visible" width={geo.w} height={geo.h} viewBox={`0 0 ${geo.w} ${geo.h}`}>
          <path ref={threadPath} d={geo.d} fill="none" stroke="#584493" strokeWidth="2" strokeLinecap="round" />
        </svg>
      ) : null}
      {geo
        ? geo.nodes.map((n) => (
            <div key={n.label} data-node className="absolute" style={{ left: n.x, top: n.y }}>
              <span className="absolute -left-[6px] -top-[6px] h-3 w-3 rounded-full bg-[#584493] ring-[3px] ring-[#F7F5F0]" />
              <span
                className={`absolute whitespace-nowrap [text-shadow:0_0_8px_#F7F5F0,0_0_3px_#F7F5F0] ${n.side === "start" ? "bottom-3 right-8 text-right" : n.side === "mid" ? "right-2 top-4 text-right" : layout === "hero" ? "bottom-4 left-0" : "left-0 top-4"}`}
              >
                <span className="block text-[13px] font-medium text-[#615B69]">{n.label}</span>
                <span className={`block text-[18px] font-semibold tracking-[-0.02em] ${n.accent ? "text-[#584493]" : "text-[#221E2B]"}`}>{n.value}</span>
              </span>
            </div>
          ))
        : null}
    </div>
  );
}
