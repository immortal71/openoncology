"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { cn } from "@/lib/utils";

gsap.registerPlugin(ScrollTrigger);

export type FieldColors = { dot: string; hi: string; scan: string };

const LANES = 23;
const HIGHLIGHTS = [
  { lane: 0, x: 0.1 },
  { lane: 8, x: 0.88 },
  { lane: 11, x: 0.14 },
  { lane: 16, x: 0.84 },
];

type Dot = { x: number; lane: number; jitter: number; size: number; alpha: number; hi: boolean };

function makeDots(count: number): Dot[] {
  let seed = 7;
  const rand = () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };
  const dots: Dot[] = [];
  for (let i = 0; i < count; i++) {
    const lane = Math.floor(rand() * LANES);
    dots.push({ x: rand(), lane, jitter: (rand() - 0.5) * 0.35, size: rand() < 0.08 ? 2 : 1.25, alpha: 0.25 + rand() * 0.55, hi: false });
  }
  HIGHLIGHTS.forEach((h) => dots.push({ x: h.x, lane: h.lane, jitter: 0, size: 3, alpha: 1, hi: true }));
  return dots;
}

const ease = (t: number) => 1 - Math.pow(1 - Math.min(Math.max(t, 0), 1), 3);

export function VariantField({
  colors,
  count = 1600,
  target = { x: 0.5, y: 1.1 },
  trigger,
  className,
}: {
  colors: FieldColors;
  count?: number;
  target?: { x: number; y: number };
  trigger?: React.RefObject<HTMLElement | null>;
  className?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const dots = makeDots(count);
    const state = { intro: 0, converge: 0 };
    let w = 0;
    let h = 0;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      const top = h * 0.08;
      const laneGap = (h * 0.78) / LANES;
      const tx = target.x * w;
      const ty = target.y * h;
      ctx.fillStyle = colors.dot;
      for (let l = 0; l < LANES; l++) {
        const lw = Math.min(state.intro * 1.5, 1) * w;
        ctx.globalAlpha = 0.07 * (1 - state.converge * 0.7);
        ctx.fillRect(0, top + l * laneGap, lw, 1);
      }
      for (const d of dots) {
        const reveal = ease((state.intro * 1.5 - d.x) / 0.35);
        if (reveal <= 0) continue;
        const bx = d.x * w;
        const by = top + d.lane * laneGap + d.jitter * laneGap * 0.7;
        if (d.hi) {
          const c = ease(state.converge * 1.15);
          const x = bx + (tx - bx) * c;
          const y = by + (ty - by) * c;
          const r = d.size + c * 1.5;
          ctx.globalAlpha = reveal * 0.18;
          ctx.fillStyle = colors.hi;
          ctx.beginPath();
          ctx.arc(x, y, r * 3.2, 0, Math.PI * 2);
          ctx.fill();
          ctx.globalAlpha = reveal;
          ctx.beginPath();
          ctx.arc(x, y, r, 0, Math.PI * 2);
          ctx.fill();
        } else {
          const fade = 1 - ease(state.converge) * 0.8;
          ctx.globalAlpha = d.alpha * reveal * fade;
          ctx.fillStyle = colors.dot;
          ctx.fillRect(bx, by + state.converge * laneGap * 1.5 * d.jitter, d.size * 2.2, d.size);
        }
      }
      if (state.intro > 0 && state.intro < 0.98) {
        ctx.globalAlpha = 0.5 * (1 - state.intro);
        ctx.fillStyle = colors.scan;
        ctx.fillRect(Math.min(state.intro * 1.5, 1) * w, top - 8, 1, h * 0.78 + 16);
      }
      ctx.globalAlpha = 1;
    };

    resize();
    const ro = new ResizeObserver(() => {
      resize();
      draw();
    });
    ro.observe(canvas);

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      state.intro = 1;
      draw();
      return () => ro.disconnect();
    }

    const ctxGsap = gsap.context(() => {
      gsap.to(state, { intro: 1, duration: 2.6, ease: "power2.out", delay: 0.2 });
      if (trigger?.current) {
        gsap.to(state, {
          converge: 1,
          ease: "none",
          scrollTrigger: { trigger: trigger.current, start: "top top", end: "+=700", scrub: 0.6 },
        });
      }
    });
    gsap.ticker.add(draw);
    return () => {
      gsap.ticker.remove(draw);
      ctxGsap.revert();
      ro.disconnect();
    };
  }, [colors.dot, colors.hi, colors.scan, count, target.x, target.y, trigger]);

  return <canvas ref={canvasRef} aria-hidden="true" className={cn("pointer-events-none block h-full w-full", className)} />;
}
