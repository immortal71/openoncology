"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import gsap from "gsap";
import { NodeMark, pinchPoint, type Pt, type ThreadNode } from "@/components/atlas/evidence-ribbon";

const STROKE = "#69518C";
const EVIDENCE_AT = 0.5;
const LIFT = 34;
const MISSING = "#AD7629";
const STRAND_GAP = 19;
const STRAND_MIN = 14;
const STRAND_TOP = 30;
const FRAY = 16;

export type LinkKey = "variant" | "evidence" | "drug";
export type LinkDetail = { key: LinkKey | null; id?: string };
const LINK_KEYS: LinkKey[] = ["variant", "evidence", "drug"];

export function sendLink(detail: LinkDetail) {
  window.dispatchEvent(new CustomEvent<LinkDetail>("atlas:link", { detail }));
}

type Strands = { used: string[]; absent: string[] };
type Frayed = { braids: string[]; loose: { name: string; d: string; end: Pt; hairs: string }[]; gap: number } | null;

type Geo = { w: number; h: number; d: string; top: number; entry: number; start: Pt };

function useDraw(path: React.RefObject<SVGPathElement | null>, ready: boolean, delay: number, trigger?: React.RefObject<HTMLElement | null>, duration = 1.6) {
  useEffect(() => {
    const p = path.current;
    if (!p || !ready) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      p.style.strokeDashoffset = "0";
      return;
    }
    const run = () => gsap.fromTo(p, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration, delay, ease: "power2.inOut" });
    if (!trigger?.current) {
      const t = run();
      return () => {
        t.kill();
      };
    }
    let t: gsap.core.Tween | null = null;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          t = run();
          io.disconnect();
        }
      },
      { threshold: 0, rootMargin: "0px 0px -15% 0px" }
    );
    io.observe(trigger.current);
    return () => {
      io.disconnect();
      t?.kill();
    };
  }, [path, ready, delay, trigger, duration]);
}

export function StoryThread({ wrap, art, nodes, strands }: { wrap: React.RefObject<HTMLElement | null>; art: React.RefObject<HTMLElement | null>; nodes: ThreadNode[]; strands?: Strands }) {
  const path = useRef<SVGPathElement>(null);
  const pulse = useRef<SVGGElement>(null);
  const fray = useRef<SVGGElement>(null);
  const [frayed, setFrayed] = useState<Frayed>(null);
  const used = strands?.used.length ?? 0;
  const absent = strands?.absent.join("|") ?? "";
  const [geo, setGeo] = useState<Geo | null>(null);
  const [mid, setMid] = useState<Pt | null>(null);
  const [hot, setHot] = useState<number | null>(null);
  const drugId = nodes[2]?.pick;

  useEffect(() => {
    const onLink = (e: Event) => {
      const { key, id } = (e as CustomEvent<LinkDetail>).detail;
      if (!key || (key === "drug" && id !== drugId)) {
        setHot(null);
        return;
      }
      setHot(LINK_KEYS.indexOf(key));
    };
    window.addEventListener("atlas:link", onLink);
    return () => window.removeEventListener("atlas:link", onLink);
  }, [drugId]);

  const link = (i: number) => (on: boolean) => sendLink(on ? { key: LINK_KEYS[i], id: i === 2 ? drugId : undefined } : { key: null });

  useEffect(() => {
    const root = wrap.current;
    const ribbon = art.current;
    if (!root || !ribbon) return;
    const measure = () => {
      const anchor = root.querySelector<HTMLElement>("[data-thread-in]");
      const frame = root.querySelector<HTMLElement>("[data-shot]");
      if (!anchor || !frame || !anchor.offsetParent || !ribbon.offsetParent) {
        setGeo(null);
        return;
      }
      const o = root.getBoundingClientRect();
      const r = ribbon.getBoundingClientRect();
      const p = pinchPoint(r.width, r.height);
      const s = { x: r.left - o.left + p.x, y: r.top - o.top + p.y };
      const a = anchor.getBoundingClientRect();
      const x = a.left - o.left;
      const top = frame.getBoundingClientRect().top - o.top;
      const panel = a.top - o.top;
      const d = `M${s.x.toFixed(1)} ${s.y.toFixed(1)} C${(s.x - (s.x - x) * 0.6).toFixed(1)} ${(s.y - LIFT).toFixed(1)} ${x.toFixed(1)} ${(top - (top - s.y) * 0.78).toFixed(1)} ${x.toFixed(1)} ${top.toFixed(1)} V${panel.toFixed(1)}`;
      setGeo({ w: o.width, h: o.height, d, top, entry: x, start: s });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(root);
    ro.observe(ribbon);
    document.fonts?.ready.then(measure);
    return () => ro.disconnect();
  }, [wrap, art]);

  useLayoutEffect(() => {
    const p = path.current;
    if (!p || !geo) {
      setMid(null);
      return;
    }
    const len = p.getTotalLength();
    const pt = p.getPointAtLength(len * EVIDENCE_AT);
    setMid({ x: pt.x, y: pt.y });
    const names = absent ? absent.split("|") : [];
    const samples = Array.from({ length: 121 }, (_, i) => p.getPointAtLength(len * (EVIDENCE_AT + ((1 - EVIDENCE_AT) * i) / 120)));
    const gap = names.length > 1 ? Math.min(STRAND_GAP, (geo.top - 12 - (pt.y + STRAND_TOP)) / (names.length - 1)) : STRAND_GAP;
    if (!names.length || gap < STRAND_MIN) {
      setFrayed(null);
      return;
    }
    const xAt = (y: number) => (samples.find((q) => q.y >= y) ?? samples[samples.length - 1]).x;
    let walked = 0;
    const braids = Array.from({ length: Math.min(used, 3) }, (_, k) => {
      const side = (k % 2 ? -1 : 1) * (3 + Math.floor(k / 2) * 3);
      walked = 0;
      return samples
        .map((q, i) => {
          const a = samples[Math.max(0, i - 1)];
          const b = samples[Math.min(samples.length - 1, i + 1)];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const n = Math.hypot(dx, dy) || 1;
          if (i) walked += Math.hypot(q.x - samples[i - 1].x, q.y - samples[i - 1].y);
          const o = side * Math.min(1, walked / 36);
          return `${i ? "L" : "M"}${(q.x - (dy / n) * o).toFixed(1)} ${(q.y + (dx / n) * o).toFixed(1)}`;
        })
        .join(" ");
    });
    const edge = Math.min(...names.map((_, i) => xAt(pt.y + STRAND_TOP + i * gap))) - 46;
    const loose = names.map((name, i) => {
      const y0 = pt.y + 10 + i * 7;
      const from = samples.find((q) => q.y >= y0) ?? samples[0];
      const end = { x: edge, y: pt.y + STRAND_TOP + i * gap };
      const d = `M${from.x.toFixed(1)} ${from.y.toFixed(1)} C${(from.x - 4).toFixed(1)} ${(from.y + 14).toFixed(1)} ${(end.x + 22).toFixed(1)} ${end.y.toFixed(1)} ${end.x.toFixed(1)} ${end.y.toFixed(1)}`;
      return { name, d, end, hairs: `M${end.x.toFixed(1)} ${end.y.toFixed(1)} h-${FRAY}` };
    });
    setFrayed({ braids, loose, gap });
  }, [geo, used, absent]);

  useEffect(() => {
    const g = fray.current;
    if (!g || !frayed) return;
    const lines = g.querySelectorAll<SVGPathElement>("[data-strand]");
    const tips = g.querySelectorAll<SVGElement>("[data-tip]");
    const tags = wrap.current?.querySelectorAll<HTMLElement>("[data-fray-tag]") ?? [];
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      lines.forEach((l) => (l.style.strokeDashoffset = "0"));
      return;
    }
    const tl = gsap.timeline({ delay: 0.75 });
    tl.fromTo(lines, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 0.7, ease: "power2.out", stagger: 0.09 })
      .fromTo(tips, { opacity: 0 }, { opacity: 1, duration: 0.3, stagger: 0.06 }, "-=0.35")
      .fromTo(tags, { opacity: 0, x: 4 }, { opacity: 1, x: 0, duration: 0.35, ease: "power2.out", stagger: 0.06 }, "<");
    return () => {
      tl.kill();
    };
  }, [frayed, wrap]);

  useDraw(path, Boolean(geo), 0.1, undefined, 1.1);

  if (!geo) return null;
  const [variant, evidence, drug] = nodes;
  const entry = { x: geo.entry, y: geo.top - 44 };

  const pick = (id: string) => {
    const send = (instant: boolean) => window.dispatchEvent(new CustomEvent("atlas:pick", { detail: { id, instant } }));
    const p = path.current;
    const dot = pulse.current;
    if (!p || !dot || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      send(true);
      return;
    }
    const len = p.getTotalLength();
    let from = 0;
    let best = Infinity;
    for (let i = 0; i <= 80; i++) {
      const q = p.getPointAtLength((len * i) / 80);
      const d = Math.hypot(q.x - entry.x, q.y - entry.y);
      if (d < best) {
        best = d;
        from = i / 80;
      }
    }
    const run = { t: from };
    gsap.killTweensOf(dot);
    gsap.set(dot, { opacity: 1 });
    gsap.to(run, {
      t: 1,
      duration: 0.65,
      ease: "power2.in",
      onUpdate: () => {
        const q = p.getPointAtLength(len * run.t);
        dot.setAttribute("transform", `translate(${q.x.toFixed(1)} ${q.y.toFixed(1)})`);
      },
      onComplete: () => {
        gsap.to(dot, { opacity: 0, duration: 0.3, delay: 0.05 });
        send(false);
      },
    });
  };

  return (
    <div className="pointer-events-none absolute inset-0 z-20 hidden lg:block">
      <svg aria-hidden="true" className="absolute inset-0 overflow-visible" width={geo.w} height={geo.h} viewBox={`0 0 ${geo.w} ${geo.h}`}>
        <path
          ref={path}
          d={geo.d}
          pathLength={1}
          fill="none"
          stroke={STROKE}
          strokeWidth={hot !== null ? 2.25 : 1.75}
          strokeLinecap="round"
          style={{ strokeDasharray: 1, strokeDashoffset: 1 }}
          className="transition-[stroke-width] duration-150"
        />
        {frayed ? (
          <g ref={fray}>
            {frayed.braids.map((d, i) => (
              <path key={`b${i}`} data-strand="" d={d} pathLength={1} fill="none" stroke={STROKE} strokeOpacity={0.55} strokeWidth={1} style={{ strokeDasharray: 1, strokeDashoffset: 1 }} />
            ))}
            {frayed.loose.map((s) => (
              <g key={s.name}>
                <path data-strand="" d={s.d} pathLength={1} fill="none" stroke={MISSING} strokeOpacity={0.8} strokeWidth={1} style={{ strokeDasharray: 1, strokeDashoffset: 1 }} />
                <path data-tip="" d={s.hairs} fill="none" stroke={MISSING} strokeOpacity={0.75} strokeWidth={1} strokeDasharray="4 2.5 2.5 3 1.2 3" />
              </g>
            ))}
          </g>
        ) : null}
        <g ref={pulse} opacity={0}>
          <circle r={10} fill={STROKE} opacity={0.18} />
          <circle r={4.5} fill={STROKE} stroke="#F7F5F0" strokeWidth={1.5} />
        </g>
      </svg>
      {variant ? <NodeMark node={variant} at={geo.start} ring place="left" hot={hot === 0} onHot={link(0)} /> : null}
      {evidence && mid ? <NodeMark node={evidence} at={mid} ring={false} place="aboveLeft" hot={hot === 1} onHot={link(1)} /> : null}
      {frayed ? (
        <div aria-hidden="true" className="absolute flex -translate-x-full items-center gap-4" style={{ left: frayed.loose[0].end.x - FRAY - 6, top: frayed.loose[0].end.y - frayed.gap / 2 }}>
          <span data-fray-tag="" className="text-right font-mono text-[11.5px] uppercase leading-[16px] tracking-[0.06em] text-[#5B5566]">
            Not in
            <br />
            this result
          </span>
          <span data-fray-tag="" className="flex flex-col items-end font-mono text-[12px] text-[#86561A]">
            {frayed.loose.map((s) => (
              <span key={s.name} className="whitespace-nowrap" style={{ height: frayed.gap, lineHeight: `${frayed.gap}px` }}>
                {s.name}
              </span>
            ))}
          </span>
        </div>
      ) : null}
      {strands?.absent.length ? <p className="sr-only">Sources not in this result: {strands.absent.join(", ")}.</p> : null}
      {drug ? <NodeMark node={drug} at={entry} ring={false} place="right" hot={hot === 2} onHot={link(2)} onPick={pick} /> : null}
    </div>
  );
}

function layoutBox(n: HTMLElement, root: HTMLElement) {
  let x = 0;
  let y = 0;
  let c: HTMLElement | null = n;
  while (c && c !== root) {
    x += c.offsetLeft;
    y += c.offsetTop;
    c = c.offsetParent as HTMLElement | null;
  }
  return { x, y, w: n.offsetWidth, h: n.offsetHeight };
}

type Spine = { w: number; h: number; d: string; branches: { d: string; at: number }[]; docks: Pt[]; dark: [number, number][]; quiet: [number, number][] };

export function PageSpine({ root }: { root: React.RefObject<HTMLElement | null> }) {
  const path = useRef<SVGPathElement>(null);
  const dots = useRef<(SVGCircleElement | null)[]>([]);
  const arms = useRef<(SVGPathElement | null)[]>([]);
  const [geo, setGeo] = useState<Spine | null>(null);

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const wide = window.matchMedia("(min-width: 1200px)");
    const measure = () => {
      const shot = el.querySelector<HTMLElement>("[data-shot]");
      const marker = el.querySelector<HTMLElement>("[data-thread-in]");
      if (!wide.matches || !shot || !marker || !marker.offsetParent) {
        setGeo(null);
        return;
      }
      const o = el.getBoundingClientRect();
      const box = (n: HTMLElement) => {
        const r = n.getBoundingClientRect();
        return { x: r.left - o.left, y: r.top - o.top, w: r.width, h: r.height };
      };
      const s = box(shot);
      const sx = box(marker).x;
      const sy = s.y + s.h;
      const gx = s.x - Math.min(44, Math.max(14, s.x - 18));
      const drop = sy + 52;
      const turn = drop + 92;
      let d = `M${sx.toFixed(1)} ${sy.toFixed(1)} V${drop.toFixed(1)} C${sx.toFixed(1)} ${(drop + 56).toFixed(1)} ${gx.toFixed(1)} ${(drop + 24).toFixed(1)} ${gx.toFixed(1)} ${turn.toFixed(1)}`;
      const docks: Pt[] = [];
      const branches: { d: string; at: number }[] = [];
      let y = turn;
      el.querySelectorAll<HTMLElement>("[data-spine-dock]").forEach((n) => {
        const r = box(n);
        const ky = r.y + r.h / 2;
        if (ky <= y + 8) return;
        const kx = r.x - 6;
        const r2 = Math.min(22, Math.max(8, (kx - gx) / 2));
        branches.push({ d: `M${gx.toFixed(1)} ${(ky - r2).toFixed(1)} Q${gx.toFixed(1)} ${ky.toFixed(1)} ${(gx + r2).toFixed(1)} ${ky.toFixed(1)} H${kx.toFixed(1)}`, at: ky - r2 });
        docks.push({ x: kx, y: ky });
        y = ky;
      });
      if (branches.length) d += ` V${branches[branches.length - 1].at.toFixed(1)}`;
      const dark = [...el.querySelectorAll<HTMLElement>("[data-dark]")].map((n) => {
        const r = box(n);
        return [r.y, r.y + r.h] as [number, number];
      });
      const quiet = [...el.querySelectorAll<HTMLElement>("[data-quiet]")].map((n) => {
        const r = box(n);
        return [r.y, r.y + r.h] as [number, number];
      });
      setGeo({ w: o.width, h: o.height, d, branches, docks, dark, quiet });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    wide.addEventListener("change", measure);
    document.fonts?.ready.then(measure);
    window.addEventListener("load", measure);
    const late = window.setTimeout(measure, 1500);
    return () => {
      ro.disconnect();
      wide.removeEventListener("change", measure);
      window.removeEventListener("load", measure);
      window.clearTimeout(late);
    };
  }, [root]);

  useLayoutEffect(() => {
    const p = path.current;
    const el = root.current;
    if (!p || !el || !geo) return;
    const total = p.getTotalLength();
    const n = 600;
    const ys = Array.from({ length: n + 1 }, (_, i) => p.getPointAtLength((total * i) / n).y);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const update = () => {
      let t = 1;
      let target = Infinity;
      if (!reduce) {
        target = window.scrollY + window.innerHeight + 40 - (el.getBoundingClientRect().top + window.scrollY);
        let i = 0;
        while (i < n && ys[i + 1] <= target) i++;
        t = i / n;
      }
      p.style.strokeDashoffset = `${1 - t}`;
      geo.branches.forEach((b, k) => {
        const on = target >= b.at;
        const arm = arms.current[k];
        const c = dots.current[k];
        if (arm) arm.style.strokeDashoffset = on ? "0" : "1";
        if (c) c.style.opacity = on ? "1" : "0";
      });
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, [geo, root]);

  if (!geo) return null;
  const f = (v: number) => Math.min(1, Math.max(0, v / geo.h));
  return (
    <svg aria-hidden="true" className="pointer-events-none absolute inset-0 z-20 overflow-visible" width={geo.w} height={geo.h} viewBox={`0 0 ${geo.w} ${geo.h}`}>
      <defs>
        <linearGradient id="page-spine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2={geo.h}>
          {[...geo.dark.map(([a, b]) => ({ a, b, color: "#B9A8EC", op: 1 })), ...geo.quiet.map(([a, b]) => ({ a, b, color: STROKE, op: 0.28 }))]
            .sort((x, y) => x.a - y.a)
            .flatMap((r, i) => [
              <stop key={`a${i}`} offset={f(r.a)} stopColor={STROKE} stopOpacity={1} />,
              <stop key={`b${i}`} offset={f(r.a)} stopColor={r.color} stopOpacity={r.op} />,
              <stop key={`c${i}`} offset={f(r.b)} stopColor={r.color} stopOpacity={r.op} />,
              <stop key={`d${i}`} offset={f(r.b)} stopColor={STROKE} stopOpacity={1} />,
            ])}
        </linearGradient>
      </defs>
      <path ref={path} d={geo.d} pathLength={1} fill="none" stroke="url(#page-spine)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ strokeDasharray: 1, strokeDashoffset: 1 }} />
      {geo.branches.map((b, i) => (
        <path
          key={i}
          ref={(a) => {
            arms.current[i] = a;
          }}
          d={b.d}
          pathLength={1}
          fill="none"
          stroke="url(#page-spine)"
          strokeWidth="1.5"
          strokeLinecap="round"
          style={{ strokeDasharray: 1, strokeDashoffset: 1, transition: "stroke-dashoffset 420ms ease-out" }}
        />
      ))}
      {geo.docks.map((k, i) => (
        <circle
          key={i}
          ref={(c) => {
            dots.current[i] = c;
          }}
          cx={k.x}
          cy={k.y}
          r="3.5"
          fill={geo.dark.some(([a, b]) => k.y > a && k.y < b) ? "#B9A8EC" : STROKE}
          style={{ opacity: 0, transition: "opacity 200ms ease-out" }}
        />
      ))}
    </svg>
  );
}

export function CarryLines({ wrap }: { wrap: React.RefObject<HTMLElement | null> }) {
  const path = useRef<SVGPathElement>(null);
  const [geo, setGeo] = useState<{ w: number; h: number; d: string; ends: Pt[] } | null>(null);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const wide = window.matchMedia("(min-width: 1024px)");
    const measure = () => {
      const rows = ["0", "1", "2"].map((k) => el.querySelector<HTMLElement>(`[data-carry="${k}"]`));
      if (!wide.matches || rows.some((r) => !r)) {
        setGeo(null);
        return;
      }
      const boxes = rows.map((r) => layoutBox(r as HTMLElement, el));
      let d = "";
      const ends: Pt[] = [];
      for (let i = 0; i < 2; i++) {
        const a = boxes[i];
        const b = boxes[i + 1];
        const x1 = a.x + a.w + 6;
        const y1 = a.y + a.h / 2;
        const x2 = b.x - 6;
        const y2 = b.y + b.h / 2;
        const mx = (x1 + x2) / 2;
        const r = Math.min(10, Math.abs(y2 - y1) / 2);
        const dir = y2 > y1 ? 1 : -1;
        d +=
          Math.abs(y2 - y1) < 1
            ? ` M${x1} ${y1} H${x2}`
            : ` M${x1} ${y1} H${mx - r} Q${mx} ${y1} ${mx} ${y1 + dir * r} V${y2 - dir * r} Q${mx} ${y2} ${mx + r} ${y2} H${x2}`;
        ends.push({ x: x1, y: y1 }, { x: x2, y: y2 });
      }
      setGeo({ w: el.offsetWidth, h: el.offsetHeight, d: d.trim(), ends });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    wide.addEventListener("change", measure);
    document.fonts?.ready.then(measure);
    return () => {
      ro.disconnect();
      wide.removeEventListener("change", measure);
    };
  }, [wrap]);

  useDraw(path, Boolean(geo), 0.2, wrap, 1.2);

  if (!geo) return null;
  return (
    <svg aria-hidden="true" className="pointer-events-none absolute inset-0 z-10 overflow-visible" width={geo.w} height={geo.h} viewBox={`0 0 ${geo.w} ${geo.h}`}>
      <path ref={path} d={geo.d} pathLength={1} fill="none" stroke={STROKE} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" style={{ strokeDasharray: 1, strokeDashoffset: 1 }} />
      {geo.ends.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="3" fill={STROKE} />
      ))}
    </svg>
  );
}

export function ClosingThread({ wrap, art, target }: { wrap: React.RefObject<HTMLElement | null>; art: React.RefObject<HTMLElement | null>; target: React.RefObject<HTMLElement | null> }) {
  const path = useRef<SVGPathElement>(null);
  const [geo, setGeo] = useState<{ w: number; h: number; d: string; s: Pt; e: Pt } | null>(null);

  useEffect(() => {
    const root = wrap.current;
    const ribbon = art.current;
    const end = target.current;
    if (!root || !ribbon || !end) return;
    const measure = () => {
      if (!ribbon.offsetParent) {
        setGeo(null);
        return;
      }
      const o = root.getBoundingClientRect();
      const r = ribbon.getBoundingClientRect();
      const p = pinchPoint(r.width, r.height);
      const s = { x: r.left - o.left + p.x, y: r.top - o.top + p.y };
      const b = end.getBoundingClientRect();
      const e = { x: b.right - o.left, y: b.top - o.top + b.height / 2 };
      const dx = s.x - e.x;
      const d = `M${s.x.toFixed(1)} ${s.y.toFixed(1)} C${(s.x - dx * 0.34).toFixed(1)} ${(s.y + 56).toFixed(1)} ${(e.x + dx * 0.4).toFixed(1)} ${(e.y - 44).toFixed(1)} ${e.x.toFixed(1)} ${e.y.toFixed(1)}`;
      setGeo({ w: o.width, h: o.height, d, s, e });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(root);
    document.fonts?.ready.then(measure);
    return () => ro.disconnect();
  }, [wrap, art, target]);

  useDraw(path, Boolean(geo), 0, wrap, 1);

  if (!geo) return null;
  return (
    <svg aria-hidden="true" className="pointer-events-none absolute inset-0 hidden overflow-visible md:block" width={geo.w} height={geo.h} viewBox={`0 0 ${geo.w} ${geo.h}`}>
      <path ref={path} d={geo.d} pathLength={1} fill="none" stroke="#B9A8EC" strokeWidth="1.75" strokeLinecap="round" style={{ strokeDasharray: 1, strokeDashoffset: 1 }} />
      <circle cx={geo.s.x} cy={geo.s.y} r="6" fill="#25202F" stroke="#B9A8EC" strokeWidth="2.5" />
    </svg>
  );
}
