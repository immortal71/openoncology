"use client";

import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { useEffect, useRef, useState } from "react";

gsap.registerPlugin(useGSAP);

const LEVELS = [
  { code: "1", group: 0, value: "1.00" },
  { code: "2", group: 0, value: "0.80" },
  { code: "3A", group: 1, value: "0.60" },
  { code: "3B", group: 1, value: "0.40" },
  { code: "4", group: 1, value: "0.20" },
  { code: "R1", group: 2, value: "0.10" },
  { code: "R2", group: 2, value: "0.05" },
];
const GROUPS = [
  { tier: "Standard care", note: "Ranked as approved options for this context" },
  { tier: "Weaker or off-label evidence", note: "Shown as repurposing candidates" },
  { tier: "Resistance", note: "Blocks the drug from ranking" },
];

const EASE = "cubic-bezier(0.4, 0, 0.2, 1)";
const CAP = "0.08";
const MARK_AT = 0.75;
const TILT = 10;
const GLARE = 0.1;
const LIFT = 24;
const DEPTH = [30, 20, 12];
const POP = `transform 500ms ${EASE}`;
const R1 = LEVELS.findIndex((l) => l.code === "R1");

const TONE = [
  { lift: "linear-gradient(180deg, #3A3150 0%, #2E283C 70%)", edge: "rgba(185,168,236,0.7)", num: "#DCD2F7", dot: "#DCD2F7", rule: "rgba(185,168,236,0.35)" },
  { lift: "linear-gradient(180deg, #3A3150 0%, #2E283C 70%)", edge: "rgba(185,168,236,0.7)", num: "#F7F5F0", dot: "#8270A4", rule: "rgba(185,168,236,0.35)" },
  { lift: "linear-gradient(180deg, #3D2E3B 0%, #2E283C 70%)", edge: "rgba(201,119,106,0.7)", num: "#F4C7BC", dot: "#C9776A", rule: "rgba(201,119,106,0.4)" },
];
const CARD = "#2E283C";
const REST = "rgba(247,245,240,0.15)";
const QUIET = "rgba(247,245,240,0.12)";

const range = (g: number) => {
  if (g === 2) return { big: CAP, small: "Later score cap" };
  const v = LEVELS.filter((l) => l.group === g);
  return { big: v[0].value, small: `to ${v[v.length - 1].value}` };
};

type Foot = { label?: string; text: string };

function useEnter() {
  const ref = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"ssr" | "idle" | "play" | "still">("ssr");
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setState("still");
      return;
    }
    setState("idle");
    const io = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting) return;
        io.disconnect();
        setState("play");
      },
      { threshold: 0, rootMargin: "0px 0px -15% 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return { ref, state };
}

function Footer({ target, resolve, instant, color }: { target: string; resolve: (key: string) => Foot | null; instant: boolean; color: string }) {
  const [shownKey, setShownKey] = useState("");
  useEffect(() => {
    if (instant || target === shownKey) return;
    const t = window.setTimeout(() => setShownKey(target), shownKey ? 150 : 0);
    return () => window.clearTimeout(t);
  }, [target, shownKey, instant]);
  const key = instant ? target : shownKey;
  const visible = key !== "" && key === target;
  const shown = resolve(key);
  return (
    <div className="mt-auto">
      <div
        className="flex min-h-[42px] flex-col justify-end gap-0.5 pb-3 text-[14px] leading-5"
        style={{ opacity: visible ? 1 : 0, transition: instant ? "none" : `opacity 150ms ${EASE}` }}
      >
        {shown?.label ? <p className="text-[#F7F5F0]/55">{shown.label}</p> : null}
        <p className={shown?.label ? "truncate font-medium text-[#F7F5F0]" : "text-[#F7F5F0]/45"}>{shown?.text ?? " "}</p>
      </div>
      <div className="h-px" style={{ backgroundColor: color, transition: instant ? "none" : `background-color 300ms ${EASE}` }} />
    </div>
  );
}

export function LadderTiers({ names, level, r1 }: { names: string; level: string | null; r1: boolean }) {
  const { ref, state } = useEnter();
  const stage = useRef<HTMLDivElement>(null);
  const strip = useRef<HTMLDivElement>(null);
  const cards = useRef<(HTMLDivElement | null)[]>([]);
  const [marked, setMarked] = useState(false);
  const [hov, setHov] = useState<number | null>(null);

  const still = state === "still";
  const done = still || marked;
  const hit = r1 ? R1 : LEVELS.findIndex((l) => l.code === level);
  const at = done && hit >= 0 ? LEVELS[hit].group : -1;
  const last = GROUPS.length - 1;
  const raised = hov ?? at;
  const tr = (s: string) => (state === "play" ? s : "none");

  useGSAP(
    () => {
      const els = cards.current.filter(Boolean) as HTMLDivElement[];
      const rows = gsap.utils.toArray<HTMLElement>("[data-row]", stage.current);
      if (state === "idle") {
        gsap.set(els, { rotationY: 90, x: -40, autoAlpha: 0, transformOrigin: "50% 50%" });
        gsap.set(rows, { autoAlpha: 0, y: 6 });
        return;
      }
      if (state !== "play") return;
      gsap
        .timeline({ onComplete: () => void gsap.set(els, { clearProps: "transform" }) })
        .to(els, { rotationY: 0, x: 0, autoAlpha: 1, duration: 0.6, ease: "power2.out", stagger: 0.1 }, 0)
        .to(rows, { autoAlpha: 1, y: 0, duration: 0.35, ease: "power2.out", stagger: 0.05 }, 0.35)
        .call(() => setMarked(true), [], MARK_AT);
    },
    { scope: stage, dependencies: [state] }
  );

  useEffect(() => {
    const el = stage.current;
    if (!el || state === "ssr" || still) return;
    const move = (e: PointerEvent) => {
      const s = el.getBoundingClientRect();
      const px = (e.clientX - s.left) / s.width;
      const py = (e.clientY - s.top) / s.height;
      el.style.setProperty("--z", "1");
      gsap.to(strip.current, { rotationY: (px - 0.5) * 2 * TILT, rotationX: (0.5 - py) * 2 * TILT, duration: 1, ease: "power4.out" });
      cards.current.forEach((c) => {
        if (!c) return;
        const r = c.getBoundingClientRect();
        const x = e.clientX - r.left;
        const y = e.clientY - r.top;
        c.style.setProperty("--ga", `${(Math.atan2(x - r.width / 2, r.height / 2 - y) * 180) / Math.PI}deg`);
        c.style.setProperty("--go", `${Math.min(1, Math.max(0, y / r.height)) * GLARE}`);
      });
    };
    const leave = () => {
      el.style.setProperty("--z", "0");
      gsap.to(strip.current, { rotationY: 0, rotationX: 0, duration: 0.4, ease: "power3.out" });
      cards.current.forEach((c) => c?.style.setProperty("--go", "0"));
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerleave", leave);
    return () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerleave", leave);
    };
  }, [state, still]);

  const footKey = (i: number) => (!done ? "" : i === at ? (r1 ? "r1" : "case") : "na");
  const resolve = (key: string): Foot | null => {
    if (key === "case") return { label: `This case · Level ${level}`, text: names };
    if (key === "r1") return { label: `Level R1 · capped at ${CAP}`, text: "Illustrative R1 drug" };
    if (key === "na") return { text: "Not shown in this example" };
    return null;
  };

  return (
    <div ref={ref} className="w-full">
      <div ref={stage} className="py-5" style={{ perspective: 1000 }}>
      <div ref={strip} data-spine-dock="" className="grid grid-cols-3 items-stretch" style={{ transformStyle: "preserve-3d" }} onPointerLeave={() => setHov(null)}>
        {GROUPS.map((g, i) => {
          const t = TONE[i];
          const on = at === i;
          const up = raised === i;
          const head = range(i);
          const rows = LEVELS.map((l, k) => ({ ...l, k })).filter((l) => l.group === i);
          const left = up || i === 0 ? "10px" : "0px";
          const right = up || i === last ? "10px" : "0px";
          return (
            <div
              key={g.tier}
              ref={(el) => {
                cards.current[i] = el;
              }}
              className={`flex flex-col ${i > 0 ? "-ml-px" : ""} ${up ? "z-20" : on ? "z-10" : "z-0"}`}
              style={{ transformStyle: "preserve-3d" }}
              onPointerEnter={() => setHov(i)}
            >
              <div
                className="relative flex flex-1 flex-col p-px"
                style={{
                  borderRadius: `${left} ${right} ${right} ${left}`,
                  backgroundColor: up || on ? t.edge : REST,
                  marginTop: up ? -16 : 0,
                  marginBottom: up ? -16 : 0,
                  transform: `translateZ(calc(var(--z, 0) * ${up ? LIFT : 0}px))`,
                  boxShadow: up ? "0 24px 48px -24px rgba(0,0,0,0.7)" : "0 0 0 rgba(0,0,0,0)",
                  transformStyle: "preserve-3d",
                  transition: tr(`background-color 300ms ${EASE}, margin 400ms ${EASE}, border-radius 400ms ${EASE}, transform 500ms ${EASE}, box-shadow 400ms ${EASE}`),
                }}
              >
              <div
                className="relative flex flex-1 flex-col gap-7 px-6"
                style={{
                  borderRadius: `calc(${left} - 1px) calc(${right} - 1px) calc(${right} - 1px) calc(${left} - 1px)`,
                  backgroundColor: CARD,
                  backgroundImage: up ? t.lift : "none",
                  paddingTop: up ? 43 : 27,
                  paddingBottom: up ? 43 : 27,
                  transformStyle: "preserve-3d",
                  transition: tr(`padding 400ms ${EASE}`),
                }}
              >
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0"
                  style={{
                    borderRadius: "inherit",
                    background: "linear-gradient(var(--ga, 0deg), rgba(247,245,240,0) 0%, rgba(247,245,240,1) 100%)",
                    opacity: "var(--go, 0)",
                    transition: "opacity 400ms cubic-bezier(.03,.98,.52,.99)",
                  }}
                />
                <header className="relative flex flex-col gap-4" style={{ transform: `translateZ(calc(var(--z, 0) * ${DEPTH[0]}px))`, transition: POP }}>
                  <div className="flex flex-col gap-2">
                    <div className="flex min-h-[55px] items-end">
                      <h3 className="text-[20px] font-semibold leading-[27.5px] tracking-[-0.01em] text-[#F7F5F0]">{g.tier.replace("-", "‑")}</h3>
                    </div>
                    <p className="flex items-baseline gap-2">
                      <span className="text-[28px] font-semibold leading-[34px] tracking-[-0.01em] tabular-nums" style={{ color: t.num }}>
                        {head.big}
                      </span>
                      <span className="text-[14px] leading-5 text-[#F7F5F0]/55">{head.small}</span>
                    </p>
                  </div>
                  <p className="min-h-[52px] text-[16px] leading-[26px] text-[#F7F5F0]/75">{g.note}</p>
                </header>

                <div style={{ transform: `translateZ(calc(var(--z, 0) * ${DEPTH[1]}px))`, transition: POP }}>
                  <p aria-hidden={i !== 2} className={`mb-3 text-[12px] leading-4 text-[#F7F5F0]/55 ${i === 2 ? "" : "invisible"}`}>
                    Step 1 value
                  </p>
                  <ul className="flex flex-col gap-3">
                    {rows.map((l) => {
                      const mine = on && l.k === hit;
                      return (
                        <li key={l.code} data-row className="grid grid-cols-[18px_1fr_auto] items-center gap-3">
                          <span
                            className="flex h-[18px] w-[18px] items-center justify-center rounded-full"
                            style={{ backgroundColor: mine ? t.rule : "transparent", transition: tr(`background-color 300ms ${EASE}`) }}
                          >
                            {i === 2 ? (
                              <svg viewBox="0 0 24 24" fill="none" stroke={t.dot} strokeWidth={2.5} strokeLinecap="round" className="h-2.5 w-2.5" aria-hidden="true">
                                <path d="M18 6 6 18M6 6l12 12" />
                              </svg>
                            ) : (
                              <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: t.dot }} />
                            )}
                          </span>
                          <span className="text-[14px] leading-5" style={{ color: mine ? "#F7F5F0" : "rgba(247,245,240,0.78)", transition: tr(`color 300ms ${EASE}`) }}>
                            Level {l.code}
                          </span>
                          <span className="font-mono text-[13px] leading-5 tabular-nums text-[#C7BBF2]">{l.value}</span>
                        </li>
                      );
                    })}
                  </ul>
                </div>

                <div className="mt-auto" style={{ transform: `translateZ(calc(var(--z, 0) * ${DEPTH[2]}px))`, transition: POP }}>
                  <Footer target={footKey(i)} resolve={resolve} instant={still} color={on ? t.rule : QUIET} />
                </div>
              </div>
              </div>
            </div>
          );
        })}
      </div>
      </div>
      <p className="mt-5 text-[14px] leading-5 text-[#F7F5F0]/55">Step 1 values, as published</p>
    </div>
  );
}
