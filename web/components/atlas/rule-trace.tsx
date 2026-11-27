"use client";

import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { useReducedMotion } from "framer-motion";

export type TraceMode = "level1" | "r1";
export type CaseScore = { name: string; score: string; tag: string };

const WISE_COLOR = "cubic-bezier(.8,.05,.2,.95)";
const WISE_RESIZE = "cubic-bezier(.4,0,.2,1)";
const AMBER = "#AD7629";
const CORAL = "#C9776A";

const WEIGHTS = [
  {
    name: "OncoKB",
    w: 0.4,
    share: 0.727,
    present: true,
    fill: "#DCD2F7",
    ink: "#25202F",
  },
  {
    name: "OpenTargets",
    w: 0.15,
    share: 0.273,
    present: true,
    fill: "#B9A8EC",
    ink: "#25202F",
  },
  {
    name: "DiffDock",
    w: 0.15,
    present: false,
    fill: "#6E5C92",
    ink: "#E6DEFA",
  },
  { name: "CIViC", w: 0.1, present: false, fill: "#5E4D80", ink: "#E6DEFA" },
  {
    name: "ClinicalPhase",
    w: 0.1,
    present: false,
    fill: "#514470",
    ink: "#E6DEFA",
  },
  {
    name: "AlphaMissense",
    w: 0.1,
    present: false,
    fill: "#463B61",
    ink: "#E6DEFA",
  },
];

const STEPS = [
  { title: "Normalise to 0–1", sub: "Level 1 → 1.00" },
  { title: "Weighted mean of sources present", sub: "Absent is not 0" },
  { title: "Rules, in order", sub: "Floor re-applied last" },
];

const rules = (mode: TraceMode) => [
  {
    verb: "Cap.",
    rule: "R1/R2 hard-capped at 0.08",
    value: mode === "r1" ? "0.209 → 0.08" : "n/a (Level 1)",
    na: mode !== "r1",
    hit: mode === "r1",
  },
  {
    verb: "Penalise.",
    rule: "Safety, up to −0.50",
    value: "depends on the drug",
  },
  {
    verb: "Discount.",
    rule: "Single-source ×0.78",
    value: "n/a (two sources)",
    na: true,
  },
  {
    verb: "Attenuate.",
    rule: "Co-mutation, low VAF",
    value: "depends on the case",
  },
  {
    verb: "Shape.",
    rule: "Conflict −0.12 · translational +0.08 · multi-source +0.04",
    value: "small terms",
  },
  {
    verb: "Floor.",
    rule: "Level 1/2 floors re-applied",
    value: mode === "r1" ? "n/a (Level R1)" : "applies",
    na: mode === "r1",
  },
];

function Bar({
  label,
  nominal,
  segRef,
}: {
  label: string;
  nominal: boolean;
  segRef?: (i: number) => (el: HTMLSpanElement | null) => void;
}) {
  return (
    <div>
      <p
        data-bar-label=""
        className="mb-1.5 font-mono text-[12px] text-[#F7F5F0]/60"
      >
        {label}
      </p>
      <div className="flex h-10 overflow-hidden rounded-[6px]">
        {WEIGHTS.map((s, i) => {
          const gone = !nominal && !s.present;
          const basis = nominal ? s.w : s.present ? (s.share ?? 0) : 0;
          return (
            <span
              key={s.name}
              ref={segRef?.(i)}
              title={`${s.name} ${s.w.toFixed(2)}`}
              className={`relative flex min-w-0 items-center overflow-hidden whitespace-nowrap border border-dashed px-2 font-mono text-[11.5px] ${i > 0 ? "border-l-[#25202F]" : ""}`}
              style={{
                flexBasis: `${basis * 100}%`,
                flexGrow: 0,
                flexShrink: 0,
                background: gone ? "transparent" : s.fill,
                color: s.ink,
                borderColor: "transparent",
                display: gone ? "none" : undefined,
              }}
            >
              {nominal ? null : <span className="mr-1.5 min-w-0 truncate">{s.name}</span>}
              <span data-val="" className="shrink-0 tabular-nums">
                {nominal ? s.w.toFixed(2) : (s.share ?? 0).toFixed(3)}
              </span>
            </span>
          );
        })}
      </div>
      {nominal ? (
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11.5px] text-[#F7F5F0]/70">
          {WEIGHTS.map((s) => (
            <li key={s.name} className="inline-flex items-center gap-1.5">
              <span aria-hidden="true" className="h-2 w-2 rounded-[2px]" style={{ background: s.fill }} />
              {s.name}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function RuleTrace({
  mode,
  onMode,
  cases,
  tie,
}: {
  mode: TraceMode;
  onMode: (m: TraceMode) => void;
  cases: CaseScore[];
  tie: { at: [number, number]; gap: string } | null;
}) {
  const root = useRef<HTMLDivElement>(null);
  const tl = useRef<gsap.core.Timeline | null>(null);
  const segs = useRef<(HTMLSpanElement | null)[]>([]);
  const reduce = useReducedMotion();
  const [mounted, setMounted] = useState(false);
  const [step, setStep] = useState(3);
  useEffect(() => setMounted(true), []);
  const motion = mounted && !reduce;

  useEffect(() => {
    const el = root.current;
    if (!el || !motion) {
      setStep(3);
      return;
    }
    const q = gsap.utils.selector(el.closest("figure") ?? el);
    const absent = WEIGHTS.map((s, i) =>
      s.present ? null : segs.current[i],
    ).filter(Boolean) as HTMLSpanElement[];
    const present = WEIGHTS.map((s, i) =>
      s.present ? segs.current[i] : null,
    ).filter(Boolean) as HTMLSpanElement[];
    const t = gsap.timeline({ paused: true, defaults: { ease: "power1.out" } });
    gsap.set(q("[data-ladder-value]"), { opacity: 0 });
    gsap.set(q("[data-step-group]"), { opacity: 0.28 });
    gsap.set(q("[data-reveal]"), { opacity: 0 });
    gsap.set(q("[data-rule]"), { opacity: 0.32 });
    gsap.set(q("[data-connector]"), { scaleY: 0 });
    gsap.set(q("[data-playhead]"), { scaleY: 0 });
    gsap.set(q("[data-case]"), { opacity: 0, y: 6 });
    t.addLabel("s1")
      .call(() => setStep(0))
      .to(q("[data-ladder-value]"), {
        opacity: 1,
        duration: 0.25,
        stagger: 0.05,
      })
      .to(
        q("[data-step-group='0']"),
        { opacity: 1, duration: 0.35, ease: WISE_COLOR },
        "s1+=0.2",
      )
      .to(
        q("[data-connector='0']"),
        { scaleY: 1, duration: 0.45, ease: "none" },
        "s1+=0.45",
      )
      .addLabel("s2", "s1+=0.9")
      .call(() => setStep(1), [], "s2")
      .to(
        q("[data-step-group='1']"),
        { opacity: 1, duration: 0.35, ease: WISE_COLOR },
        "s2",
      )
      .to(
        absent,
        {
          backgroundColor: "rgba(0,0,0,0)",
          borderColor: AMBER,
          color: "#E9C48C",
          duration: 0.35,
          ease: WISE_COLOR,
        },
        "s2",
      )
      .to(
        absent,
        {
          flexBasis: "0%",
          paddingLeft: 0,
          paddingRight: 0,
          borderWidth: 0,
          duration: 0.4,
          ease: WISE_RESIZE,
        },
        "s2+=0.35",
      )
      .to(
        present[0],
        {
          flexBasis: `${(WEIGHTS[0].share ?? 0) * 100}%`,
          duration: 0.4,
          ease: WISE_RESIZE,
        },
        "s2+=0.35",
      )
      .to(
        present[1],
        {
          flexBasis: `${(WEIGHTS[1].share ?? 0) * 100}%`,
          duration: 0.4,
          ease: WISE_RESIZE,
        },
        "s2+=0.35",
      )
      .call(
        () => {
          WEIGHTS.forEach((s, i) => {
            const val = segs.current[i]?.querySelector("[data-val]");
            if (val && s.present) val.textContent = (s.share ?? 0).toFixed(3);
          });
          const cap = el.querySelector("[data-bar-label]");
          if (cap) cap.textContent = "Two sources present";
        },
        [],
        "s2+=0.55",
      )
      .to(q("[data-reveal='2']"), { opacity: 1, duration: 0.5 }, "s2+=0.6")
      .to(
        q("[data-connector='1']"),
        { scaleY: 1, duration: 0.45, ease: "none" },
        "s2+=0.6",
      )
      .addLabel("s3", "s2+=1.05")
      .call(() => setStep(2), [], "s3")
      .to(
        q("[data-step-group='2']"),
        { opacity: 1, duration: 0.35, ease: WISE_COLOR },
        "s3",
      )
      .to(
        q("[data-playhead]"),
        { scaleY: 1, duration: 0.45, ease: "none" },
        "s3",
      )
      .to(
        q("[data-rule]"),
        {
          opacity: (i, target: HTMLElement) => (target.dataset.na ? 0.5 : 1),
          duration: 0.25,
          stagger: 0.125,
        },
        "s3+=0.05",
      )
      .to(q("[data-reveal='3']"), { opacity: 1, duration: 0.5 }, "s3+=0.6")
      .addLabel("s4", "s3+=0.6")
      .call(() => setStep(3), [], "s4")
      .to(
        q("[data-case]"),
        { opacity: 1, y: 0, duration: 0.5, stagger: 0.06 },
        "s4",
      )
      .to(q("[data-tie]"), { opacity: 1, duration: 0.25 }, "s4+=0.5")
      .addLabel("end");
    gsap.set(q("[data-tie]"), { opacity: 0 });
    tl.current = t;
    const io = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting) return;
        io.disconnect();
        t.play();
      },
      { threshold: 0, rootMargin: "0px 0px -18% 0px" },
    );
    io.observe(el);
    const onVis = () => {
      if (document.hidden) t.pause();
      else if (t.progress() > 0 && t.progress() < 1) t.play();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
      t.kill();
      tl.current = null;
    };
  }, [motion]);

  const jump = (i: number) => {
    const t = tl.current;
    if (!t) return;
    t.pause();
    t.tweenTo(i === 2 ? "end" : `s${i + 2}`, {
      duration: 0.4,
      ease: "power1.out",
    });
  };
  const replay = () => {
    const t = tl.current;
    if (!t) return;
    t.pause(0);
    const el = root.current;
    WEIGHTS.forEach((s, i) => {
      const val = segs.current[i]?.querySelector("[data-val]");
      if (val) val.textContent = s.w.toFixed(2);
    });
    const cap = el?.querySelector("[data-bar-label]");
    if (cap) cap.textContent = "Nominal weights";
    t.play(0);
  };

  useEffect(() => {
    const el = root.current;
    const t = tl.current;
    if (!el || (t && t.time() < (t.labels.s3 ?? 0))) return;
    gsap.to(el.querySelectorAll<HTMLElement>("[data-rule]"), {
      opacity: (_i: number, target: HTMLElement) =>
        target.dataset.na ? 0.5 : 1,
      duration: 0.25,
      ease: WISE_COLOR,
    });
  }, [mode]);

  const r1 = mode === "r1";
  const done = (i: number) => step > i || step === 3;

  return (
    <div ref={root} className="mt-14">
      <div className="rounded-[10px] border border-[#F7F5F0]/15 bg-[#3B3350]/40">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#F7F5F0]/12 px-6 py-3">
          <p className="font-mono text-[12px] uppercase tracking-[0.06em] text-[#C7BBF2]">
            Illustrative trace · published rules · not any drug&apos;s
            computation
          </p>
          <div className="flex items-center gap-3">
            <div
              role="group"
              aria-label="Example drug"
              className="flex rounded-[7px] border border-[#F7F5F0]/15 p-0.5 text-[12.5px]"
            >
              {(
                [
                  ["level1", "Level 1 example"],
                  ["r1", "Illustrative R1 drug"],
                ] as const
              ).map(([m, label]) => (
                <button
                  key={m}
                  type="button"
                  aria-pressed={mode === m}
                  onClick={() => onMode(m)}
                  className={`rounded-[5px] px-2.5 py-1 transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#DCD2F7] ${mode === m ? "bg-[#F7F5F0]/12 text-[#F7F5F0]" : "text-[#F7F5F0]/60 hover:text-[#F7F5F0]"}`}
                >
                  {label}
                </button>
              ))}
            </div>
            {motion ? (
              <button
                type="button"
                onClick={replay}
                className="rounded-[5px] px-2 py-1 text-[12.5px] text-[#F7F5F0]/70 underline decoration-[#F7F5F0]/30 underline-offset-4 hover:text-[#F7F5F0] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#DCD2F7]"
              >
                Replay
              </button>
            ) : null}
          </div>
        </div>
        <div className="grid lg:grid-cols-12">
          <div className="border-b border-[#F7F5F0]/12 lg:col-span-4 lg:border-b-0 lg:border-r">
            <ol className="p-6 lg:sticky lg:top-24">
              {STEPS.map((s, i) => (
                <li key={s.title} className="relative pb-7 pl-9 last:pb-0">
                  {i < STEPS.length - 1 ? (
                    <>
                      <span
                        aria-hidden="true"
                        className="absolute bottom-0 left-[11px] top-7 w-px bg-[#F7F5F0]/12"
                      />
                      <span
                        aria-hidden="true"
                        data-connector={i}
                        className="absolute bottom-0 left-[11px] top-7 w-px origin-top bg-[#B9A8EC]"
                      />
                    </>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => jump(i)}
                    disabled={!motion}
                    className="group text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#DCD2F7] disabled:cursor-default"
                  >
                    <span
                      aria-hidden="true"
                      className={`absolute left-0 top-0 grid h-[23px] w-[23px] place-items-center rounded-full border font-mono text-[11.5px] transition-colors duration-300 ${
                        step === i
                          ? "border-[#DCD2F7] bg-[#DCD2F7] text-[#25202F]"
                          : done(i)
                            ? "border-[#B9A8EC] text-[#DCD2F7]"
                            : "border-[#F7F5F0]/25 text-[#F7F5F0]/50"
                      }`}
                    >
                      {i + 1}
                    </span>
                    <span
                      className={`block text-[15px] font-semibold leading-[22px] transition-opacity duration-300 ${step >= i ? "opacity-100" : "opacity-50"} ${motion ? "group-hover:underline group-hover:decoration-[#B9A8EC]/60 group-hover:underline-offset-4" : ""}`}
                    >
                      {s.title}
                    </span>
                    <span className="mt-0.5 block font-mono text-[12px] text-[#F7F5F0]/60">
                      {i === 0 && r1 ? "Level R1 → 0.10" : s.sub}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
          <div className="p-6 lg:col-span-8">
            <dl data-step-group="0" className="text-[14px]">
              {[
                [
                  r1 ? "OncoKB · Level R1" : "OncoKB · Level 1",
                  r1 ? "0.10" : "1.00",
                  r1,
                ],
                ["OpenTargets · used directly", "0.50", false],
              ].map(([k, v, warn]) => (
                <div
                  key={String(k)}
                  className="flex items-baseline justify-between gap-6 border-b border-[#F7F5F0]/10 py-2"
                >
                  <dt className="text-[#F7F5F0]/70">{k}</dt>
                  <dd
                    className="font-mono tabular-nums transition-colors duration-300"
                    style={{
                      color: warn ? "#F4C7BC" : "#F7F5F0",
                      transitionTimingFunction: WISE_COLOR,
                    }}
                  >
                    {v}
                  </dd>
                </div>
              ))}
              <div
                className="mt-2 flex items-baseline justify-between gap-6 rounded-[6px] border border-dashed px-3 py-2"
                style={{ borderColor: AMBER }}
              >
                <dt className="flex items-center gap-2 text-[#F7F5F0]/80">
                  <span
                    aria-hidden="true"
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ background: AMBER }}
                  />
                  DiffDock, CIViC, ClinicalPhase, AlphaMissense
                </dt>
                <dd className="font-mono text-[13px] text-[#F7F5F0]/80">
                  absent, not 0
                </dd>
              </div>
            </dl>

            <div data-step-group="1" className="mt-6 space-y-3">
              {motion ? (
                <Bar
                  label="Nominal weights"
                  nominal
                  segRef={(i) => (el) => {
                    segs.current[i] = el;
                  }}
                />
              ) : (
                <>
                  <Bar label="Nominal weights" nominal />
                  <Bar label="Two sources present" nominal={false} />
                </>
              )}
              <div data-reveal="2">
                <p className="font-mono text-[12px] text-[#F7F5F0]/60">
                  Weight shares: OncoKB 0.40 → 0.727 · OpenTargets 0.15 → 0.273
                </p>
                <div className="mt-3 flex items-baseline justify-between gap-6 border-t border-[#F7F5F0]/20 pt-3">
                  <span className="text-[14px] font-semibold">Base score</span>
                  <span
                    className="font-mono text-[15px] tabular-nums"
                    style={{ color: r1 ? "#F4C7BC" : "#F7F5F0" }}
                  >
                    {r1 ? "0.209" : "0.864"}
                  </span>
                </div>
              </div>
            </div>

            <div
              data-step-group="2"
              className="relative mt-6 border-t border-[#F7F5F0]/20 pt-2"
            >
              <span
                aria-hidden="true"
                className="absolute -left-3 bottom-1 top-3 w-px bg-[#F7F5F0]/10"
              />
              <span
                aria-hidden="true"
                data-playhead=""
                className="absolute -left-3 bottom-1 top-3 w-px origin-top bg-[#B9A8EC]"
              />
              <ul>
                {rules(mode).map((r) => (
                  <li
                    key={r.verb}
                    data-rule=""
                    data-na={r.na ? "1" : undefined}
                    className={`grid grid-cols-[112px_minmax(0,1fr)_auto] items-baseline gap-4 border-b border-[#F7F5F0]/8 py-2 text-[14px] ${!motion && r.na ? "opacity-50" : ""}`}
                  >
                    <span
                      className="text-[15px] font-semibold"
                      style={{ color: r.hit ? CORAL : "#F7F5F0" }}
                    >
                      {r.verb}
                    </span>
                    <span className="text-[#F7F5F0]/75">{r.rule}</span>
                    <span
                      className="font-mono text-[12.5px] tabular-nums"
                      style={{
                        color: r.hit ? "#F4C7BC" : "rgba(247,245,240,0.7)",
                      }}
                    >
                      {r.value}
                    </span>
                  </li>
                ))}
              </ul>
              <p
                data-reveal="3"
                className="mt-3 text-[13px] leading-[20px] text-[#F7F5F0]/60"
              >
                {r1 ? "Capped at 0.08 · can't rank as an option. " : ""}Weights
                are research defaults, not optimised on outcome data. Rule
                effects depend on the case, so this example stops at the base
                score.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-8 border-t border-[#F7F5F0]/14 pt-6">
        <p className="font-mono text-[12px] uppercase tracking-[0.06em] text-[#C7BBF2]">
          This case · KRAS G12C, NSCLC · reported by the engine
        </p>
        <div className="mt-5 flex flex-wrap items-end gap-x-12 gap-y-6">
          {tie ? (
            <div className="relative pt-9">
              <div
                data-tie=""
                aria-hidden="true"
                className="absolute inset-x-0 top-0"
              >
                <span className="absolute left-0 top-0 whitespace-nowrap font-mono text-[12px] leading-4 text-[#DCD2F7]">
                  {tie.gap} apart · near-tie, review both
                </span>
                <span className="absolute inset-x-0 top-[24px] h-2 border-x border-t border-[#B9A8EC]/70" />
              </div>
              <p className="sr-only">{tie.gap} apart: near-tie, review both.</p>
              <div className="flex gap-16">
                {cases.slice(tie.at[0], tie.at[1] + 1).map((c) => (
                  <CaseCell key={c.name} c={c} />
                ))}
              </div>
            </div>
          ) : null}
          {cases
            .filter((_, i) => !tie || i < tie.at[0] || i > tie.at[1])
            .map((c) => (
              <CaseCell key={c.name} c={c} />
            ))}
        </div>
        <p className="mt-5 max-w-[78ch] text-[13px] leading-[20px] text-[#F7F5F0]/60">
          These scores also use a docking signal pending review and a
          clinical-phase signal, which the workspace hides. The demo has no
          per-rule breakdown, so this case is not traced.
        </p>
      </div>
    </div>
  );
}

function CaseCell({ c }: { c: CaseScore }) {
  return (
    <div data-case="">
      <p className="text-[14px] font-semibold text-[#F7F5F0]">{c.name}</p>
      <p className="mt-1 font-mono text-[28px] leading-none tabular-nums text-[#DCD2F7]">
        {c.score}
      </p>
      <p className="mt-1.5 text-[12.5px] text-[#F7F5F0]/60">{c.tag}</p>
    </div>
  );
}
