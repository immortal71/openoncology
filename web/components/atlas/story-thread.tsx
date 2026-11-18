"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { NodeMark, pinchPoint, type Pt, type ThreadNode } from "@/components/atlas/evidence-ribbon";

gsap.registerPlugin(ScrollTrigger);

const STROKE = "#69518C";
const ON_DARK = "#B9A8EC";
const EVIDENCE_AT = 0.4;
const INTRO = 0.46;
const FINISH_AT = 0.42;

type Geo = { w: number; h: number; d: string; top: number; panel: number; start: Pt };

export function StoryThread({ wrap, art, nodes }: { wrap: React.RefObject<HTMLElement | null>; art: React.RefObject<HTMLElement | null>; nodes: ThreadNode[] }) {
  const path = useRef<SVGPathElement>(null);
  const apply = useRef<() => void>(() => {});
  const [geo, setGeo] = useState<Geo | null>(null);
  const [mid, setMid] = useState<Pt | null>(null);
  const [hot, setHot] = useState<number | null>(null);

  useEffect(() => {
    const root = wrap.current;
    const ribbon = art.current;
    if (!root || !ribbon) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let intro = reduce ? 1 : 0;
    let scroll = 0;

    apply.current = () => {
      const p = path.current;
      if (!p) return;
      const t = reduce ? 1 : Math.max(intro, scroll > 0 ? INTRO + (1 - INTRO) * scroll : 0);
      p.style.strokeDashoffset = `${1 - t}`;
    };

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
      const d = `M${s.x.toFixed(1)} ${s.y.toFixed(1)} C${(s.x - (s.x - x) * 0.42).toFixed(1)} ${(s.y + 18).toFixed(1)} ${x.toFixed(1)} ${(top - (top - s.y) * 0.62).toFixed(1)} ${x.toFixed(1)} ${top.toFixed(1)} V${panel.toFixed(1)}`;
      setGeo({ w: o.width, h: o.height, d, top, panel, start: s });
    };

    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(root);
    ro.observe(ribbon);
    document.fonts?.ready.then(measure);

    const frameTop = () => {
      const frame = root.querySelector<HTMLElement>("[data-shot]");
      return frame ? frame.getBoundingClientRect().top + window.scrollY : window.innerHeight;
    };
    const st = reduce
      ? null
      : ScrollTrigger.create({
          start: 0,
          end: () => Math.max(1, frameTop() - window.innerHeight * FINISH_AT),
          invalidateOnRefresh: true,
          onUpdate: (self) => {
            scroll = self.progress;
            apply.current();
          },
        });
    const proxy = { v: 0 };
    const tween = reduce
      ? null
      : gsap.to(proxy, {
          v: INTRO,
          duration: 1.3,
          delay: 0.75,
          ease: "power2.inOut",
          onUpdate: () => {
            intro = proxy.v;
            apply.current();
          },
        });
    return () => {
      ro.disconnect();
      st?.kill();
      tween?.kill();
    };
  }, [wrap, art]);

  useLayoutEffect(() => {
    const p = path.current;
    if (!p || !geo) {
      setMid(null);
      return;
    }
    const pt = p.getPointAtLength(p.getTotalLength() * EVIDENCE_AT);
    setMid({ x: pt.x, y: pt.y });
    apply.current();
  }, [geo]);

  if (!geo) return null;
  const [variant, evidence] = nodes;
  const f = (v: number) => Math.min(1, Math.max(0, v / geo.h));

  return (
    <div className="pointer-events-none absolute inset-0 z-20 hidden lg:block">
      <svg aria-hidden="true" className="absolute inset-0 overflow-visible" width={geo.w} height={geo.h} viewBox={`0 0 ${geo.w} ${geo.h}`}>
        <defs>
          <linearGradient id="story-thread" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2={geo.h}>
            <stop offset={f(geo.top)} stopColor={STROKE} />
            <stop offset={f(geo.top)} stopColor={ON_DARK} />
            <stop offset={f(geo.panel)} stopColor={ON_DARK} />
            <stop offset={f(geo.panel)} stopColor={STROKE} />
          </linearGradient>
        </defs>
        <path d={geo.d} fill="none" stroke={STROKE} strokeOpacity={hot !== null ? 0.4 : 0.2} strokeWidth="1.5" strokeLinecap="round" className="transition-[stroke-opacity] duration-150" />
        <path
          ref={path}
          d={geo.d}
          pathLength={1}
          fill="none"
          stroke="url(#story-thread)"
          strokeWidth={hot !== null ? 2.25 : 1.75}
          strokeLinecap="round"
          style={{ strokeDasharray: 1, strokeDashoffset: 1 }}
          className="transition-[stroke-width] duration-150"
        />
      </svg>
      {variant ? <NodeMark node={variant} at={geo.start} ring place="bottom-[14px] right-6 text-right" hot={hot === 0} onHot={(on) => setHot(on ? 0 : null)} /> : null}
      {evidence && mid ? <NodeMark node={evidence} at={mid} ring={false} place="bottom-[12px] right-2 text-right" hot={hot === 1} onHot={(on) => setHot(on ? 1 : null)} /> : null}
    </div>
  );
}
