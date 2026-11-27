"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { GapState } from "@/lib/workspace";

export type Fact = { k: string; v: string; note?: string; state?: GapState };
export type Call = { gene: string; protein: string; hgvs: string };
export type CardData = { calls: Call[]; lab: Fact[]; clinic: Fact[]; clinicAll: Fact[]; more: number; total: number; tally: string };

const INK = "#24212B";
const MUTED = "#625E68";
const RULE = "#E2DEE6";
const VIOLET = "#69518C";
const AMBER = "#AD7629";
const AMBER_TEXT = "#8A5A17";
const EASE = "cubic-bezier(0.2,0.8,0.2,1)";

function useRun(count: number, stepMs: number, loop = false) {
  const ref = useRef<HTMLDivElement>(null);
  const [i, setI] = useState(count);
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let timer = 0;
    let started = false;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting && !started) {
          started = true;
          setI(-1);
          let n = -1;
          timer = window.setInterval(() => {
            n += 1;
            if (n >= count) {
              if (loop) n = 0;
              else window.clearInterval(timer);
            }
            setI(n);
          }, stepMs);
        }
      },
      { threshold: 0.45 }
    );
    io.observe(el);
    return () => {
      io.disconnect();
      window.clearInterval(timer);
    };
  }, [count, stepMs, loop]);
  return { ref, i, paused, setPaused };
}

const parts = (f: Fact) => {
  const [title, ...scope] = f.k.split(" · ");
  return { title, scope: scope.join(" · ") };
};

/* ---------------- A · Inngest step run ---------------- */

const PILL_A: Record<string, { fg: string; bg: string; label: string }> = {
  received: { fg: VIOLET, bg: "rgba(105,81,140,0.12)", label: "In file" },
  not_supplied: { fg: AMBER_TEXT, bg: "rgba(173,118,41,0.13)", label: "Not supplied" },
  not_assessed: { fg: MUTED, bg: "rgba(98,94,104,0.12)", label: "Not assessed" },
  not_recorded: { fg: MUTED, bg: "rgba(98,94,104,0.12)", label: "Not recorded" },
  lookup_failed: { fg: "#A2483A", bg: "rgba(201,119,106,0.14)", label: "Lookup failed" },
  waiting: { fg: AMBER_TEXT, bg: "rgba(173,118,41,0.13)", label: "Waiting" },
  checking: { fg: "#523E70", bg: "rgba(105,81,140,0.16)", label: "Checking" },
};

type BlockA = { key: string; status: keyof typeof PILL_A; lines: [string, string]; hold?: boolean };

const ROW_H = 58;

function StepLoop({ title, sub, items, visible = 3 }: { title: string; sub: string; items: BlockA[]; visible?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const n = items.length;
  const [t, setT] = useState(visible - 1);
  const [checking, setChecking] = useState(false);
  const [live, setLive] = useState(false);
  const [hover, setHover] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const io = new IntersectionObserver(([e]) => setLive(e.isIntersecting), { threshold: 0, rootMargin: "0px 0px -12% 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!live || hover) return;
    let settle = 0;
    const step = () => {
      setT((x) => x + 1);
      setChecking(true);
      window.clearTimeout(settle);
      settle = window.setTimeout(() => setChecking(false), 750);
    };
    const first = window.setTimeout(step, 120);
    const tick = window.setInterval(step, 1700);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(tick);
      window.clearTimeout(settle);
      setChecking(false);
    };
  }, [live, hover]);

  const keys = Array.from({ length: visible }, (_, j) => t - visible + 1 + j);
  const at = (k: number) => items[((k % n) + n) % n];
  return (
    <div
      ref={ref}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className="mt-6 overflow-hidden rounded-[16px] bg-white shadow-[0_0_0_1px_rgba(37,32,47,0.07),0_1px_2px_rgba(37,32,47,0.03),0_3px_6px_rgba(37,32,47,0.035),0_8px_14px_rgba(37,32,47,0.04),0_16px_28px_rgba(37,32,47,0.045)]"
    >
      <div className="flex items-baseline justify-between gap-4 border-b px-5 py-3" style={{ borderColor: RULE }}>
        <span className="font-mono text-[12px] uppercase tracking-[0.06em] text-[#5B5566]">{title}</span>
        <span className="font-mono text-[12px] tabular-nums text-[#5B5566]">
          {sub} · {(((t % n) + n) % n) + 1} of {n}
        </span>
      </div>
      <div
        className="relative overflow-hidden px-3 py-4 font-mono text-[13px] leading-[20px] [mask-image:linear-gradient(to_bottom,transparent,#000_18%,#000)]"
        style={{ height: visible * ROW_H + 26 }}
      >
        <AnimatePresence mode="popLayout" initial={false}>
          {keys.map((k) => {
            const b = at(k);
            const newest = k === t;
            const status: keyof typeof PILL_A = newest && checking && !b.hold ? "checking" : b.status;
            const pill = PILL_A[status];
            const tone = b.status === "received" ? VIOLET : b.status === "not_supplied" || b.status === "waiting" ? AMBER : "#9C97A3";
            const lit = (newest && checking) || b.hold;
            return (
              <motion.div
                key={k}
                layout
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -18 }}
                transition={{ duration: 0.5, ease: [0.2, 0.8, 0.2, 1] }}
                className="mb-1.5 grid grid-cols-[124px_minmax(0,1fr)] items-center gap-3"
              >
                <span className="flex justify-end">
                  <span
                    className="inline-flex h-5 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-[11px] uppercase leading-none tracking-[0.06em]"
                    style={{ color: pill.fg, background: pill.bg, transition: `background-color .36s ${EASE}, color .36s ${EASE}` }}
                  >
                    {status === "checking" || b.hold ? <span className="h-1.5 w-1.5 rounded-full" style={{ background: pill.fg }} /> : null}
                    {pill.label}
                  </span>
                </span>
                <div
                  className="rounded-[8px] border-l-2 px-3.5 py-1.5"
                  style={{ borderLeftColor: tone, background: lit ? (b.hold ? "rgba(173,118,41,0.08)" : "rgba(105,81,140,0.07)") : "transparent", transition: `background-color .42s ${EASE}` }}
                >
                  <p className="truncate" style={{ color: INK }}>
                    {b.lines[0]}
                  </p>
                  <p className="truncate" style={{ color: "#8A8592" }}>
                    {b.lines[1]}
                  </p>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}

export function OptionA({ d }: { d: CardData }) {
  const lab: BlockA[] = d.calls.flatMap((c) => [
    { key: c.gene, status: "received" as const, lines: [`${c.gene}  ${c.protein}`, `// ${c.hgvs} · in the file`] as [string, string] },
    ...d.lab.map((f) => ({ key: `${c.gene}-${f.k}`, status: (f.state ?? "not_supplied") as keyof typeof PILL_A, lines: [`${f.k} · ${c.gene}`, `// ${f.note ?? f.v}`] as [string, string] })),
  ]);
  const clinic: BlockA[] = [
    ...d.clinicAll.map((f) => {
      const p = parts(f);
      return { key: f.k, status: (f.state ?? "not_supplied") as keyof typeof PILL_A, lines: [p.scope ? `${p.title} · ${p.scope}` : p.title, `// ${f.note ?? f.v}`] as [string, string] };
    }),
    { key: "signoff", status: "waiting", hold: true, lines: ["Oncologist sign-off", "// nothing is acted on until it is checked"] },
  ];
  return [<StepLoop key="a1" title="Variant calls, as received" sub="Demo case" items={lab} />, <StepLoop key="a2" title="Before any treatment decision" sub={`${d.total} open`} items={clinic} />];
}

/* ---------------- B · Attio enriching table ---------------- */

const PILL_B: Record<string, { fg: string; bg: string; ring?: string }> = {
  "Not supplied": { fg: AMBER_TEXT, bg: "#F6EBDA" },
  "Not assessed": { fg: "#4A4652", bg: "#ECEAEF" },
  "Not recorded": { fg: "#4A4652", bg: "#FFFFFF", ring: "#D5D0DA" },
  "Lookup failed": { fg: "#A2483A", bg: "#F6E1DC" },
  Pending: { fg: "#523E70", bg: "#FFFFFF", ring: "#B9A8EC" },
};

function PillB({ label, show }: { label: string; show: boolean }) {
  const s = PILL_B[label] ?? PILL_B["Not recorded"];
  return (
    <span
      className="inline-flex h-[22px] items-center whitespace-nowrap rounded-[5px] px-2 text-[12px] font-medium"
      style={{ color: s.fg, background: s.bg, boxShadow: s.ring ? `inset 0 0 0 1px ${s.ring}` : undefined, opacity: show ? 1 : 0, transform: show ? "none" : "scale(0.94)", transition: `opacity .28s ${EASE}, transform .28s ${EASE}` }}
    >
      {label}
    </span>
  );
}

function Window({ crumb, view, children, runRef }: { crumb: string; view: string; children: React.ReactNode; runRef: React.RefObject<HTMLDivElement | null> }) {
  return (
    <div ref={runRef} className="mt-6 overflow-hidden rounded-[12px] border bg-white shadow-[0_1px_2px_rgba(37,32,47,0.06),0_16px_40px_-12px_rgba(37,32,47,0.16)]" style={{ borderColor: RULE }}>
      <div className="flex h-10 items-center gap-3 border-b px-3.5" style={{ borderColor: RULE }}>
        <span className="flex gap-1.5" aria-hidden="true">
          {[0, 1, 2].map((n) => (
            <span key={n} className="h-3 w-3 rounded-full bg-[#E2DEE6]" />
          ))}
        </span>
        <span className="text-[13px] font-medium" style={{ color: INK }}>
          {crumb}
        </span>
      </div>
      <div className="flex items-center justify-between border-b px-3.5 py-2 text-[12.5px]" style={{ borderColor: RULE, color: MUTED }}>
        <span className="inline-flex items-center gap-1.5 rounded-[6px] border px-2 py-0.5 font-medium" style={{ borderColor: RULE, color: INK }}>
          <span aria-hidden="true" className="h-2 w-2 rounded-[2px]" style={{ background: VIOLET }} />
          {view}
        </span>
        <span>Demo case</span>
      </div>
      {children}
    </div>
  );
}

const th = "border-b px-3 py-2 text-left text-[12px] font-medium";
const td = "border-b px-3 py-2.5 text-[13.5px]";

function LabTableB({ d }: { d: CardData }) {
  const lab = useRun(d.calls.length * 2, 260);
  return (
    <Window crumb="Variant calls" view="As received" runRef={lab.ref}>
      <table className="w-full border-collapse">
        <thead>
          <tr style={{ color: MUTED }}>
            {["Gene", "Protein", "VAF", "Depth"].map((c) => (
              <th key={c} className={th} style={{ borderColor: RULE }}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {d.calls.map((c, r) => (
            <tr key={c.gene}>
              <td className={`${td} font-semibold`} style={{ borderColor: RULE, color: INK }}>
                {c.gene}
              </td>
              <td className={td} style={{ borderColor: RULE, color: INK }}>
                {c.protein} <span className="font-mono text-[12px]" style={{ color: MUTED }}>{c.hgvs}</span>
              </td>
              {[0, 1].map((k) => (
                <td key={k} className={td} style={{ borderColor: RULE }}>
                  <PillB label="Not supplied" show={lab.i > r * 2 + k} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="px-3.5 py-3 text-[13px]" style={{ color: MUTED }}>
        {d.lab.length} fields not in this result. Add them to the next run.
      </p>
    </Window>
  );
}

function ClinicTableB({ d }: { d: CardData }) {
  const clinic = useRun(d.clinic.length + 1, 260);
  return (
    <Window crumb="Before any treatment decision" view={`${d.total} open`} runRef={clinic.ref}>
      <table className="w-full border-collapse">
        <thead>
          <tr style={{ color: MUTED }}>
            {["Evidence", "Scope", "State"].map((c) => (
              <th key={c} className={th} style={{ borderColor: RULE }}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {d.clinic.map((f, r) => {
            const p = parts(f);
            return (
              <tr key={f.k}>
                <td className={`${td} font-medium`} style={{ borderColor: RULE, color: INK }}>
                  {p.title}
                </td>
                <td className={td} style={{ borderColor: RULE, color: MUTED }}>
                  {p.scope || "Case"}
                </td>
                <td className={td} style={{ borderColor: RULE }}>
                  <PillB label={f.v} show={clinic.i > r} />
                </td>
              </tr>
            );
          })}
          <tr>
            <td colSpan={3} className="border-b px-3 py-2 text-[12.5px]" style={{ borderColor: RULE, color: MUTED }}>
              {d.more} more in the full case · {d.tally}
            </td>
          </tr>
          <tr className="bg-[#FBFAF7]">
            <td className="px-3 py-3 text-[14px] font-semibold" style={{ color: INK }}>
              Oncologist sign-off
            </td>
            <td className="px-3 py-3 text-[13px]" style={{ color: MUTED }}>
              Decides
            </td>
            <td className="px-3 py-3">
              <PillB label="Pending" show={clinic.i > d.clinic.length - 1} />
            </td>
          </tr>
        </tbody>
      </table>
    </Window>
  );
}

export function OptionB({ d }: { d: CardData }) {
  return [<LabTableB key="b1" d={d} />, <ClinicTableB key="b2" d={d} />];
}

/* ---------------- C · Raycast palette ---------------- */

type ItemC = { key: string; title: string; tag: string; tone: string; icon: "received" | GapState | "pending"; info: [string, string][]; group: string };

function IconC({ icon }: { icon: ItemC["icon"] }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" className="h-4 w-4 shrink-0">
      {icon === "received" ? <rect x={1.5} y={1.5} width={13} height={13} rx={3.5} fill="#B9A8EC" /> : null}
      {icon === "not_supplied" ? <circle cx={8} cy={8} r={6} fill="none" stroke="#E0B36E" strokeWidth={1.5} strokeDasharray="2.6 2" /> : null}
      {icon === "not_assessed" ? (
        <>
          <circle cx={8} cy={8} r={6} fill="none" stroke="#B4B2BE" strokeWidth={1.5} />
          <line x1={5} y1={8} x2={11} y2={8} stroke="#B4B2BE" strokeWidth={1.5} strokeLinecap="round" />
        </>
      ) : null}
      {icon === "not_recorded" ? <rect x={2.25} y={2.25} width={11.5} height={11.5} rx={2.5} fill="none" stroke="#B4B2BE" strokeWidth={1.5} /> : null}
      {icon === "pending" ? (
        <>
          <circle cx={8} cy={8} r={6.5} fill="none" stroke="#E0B36E" strokeOpacity={0.4} strokeWidth={2.5} />
          <circle cx={8} cy={8} r={3.25} fill="#E0B36E" />
        </>
      ) : null}
    </svg>
  );
}

function Palette({ query, items, action }: { query: string; items: ItemC[]; action: string }) {
  const { ref, i, paused, setPaused } = useRun(items.length, 1500, true);
  const [pick, setPick] = useState<number | null>(null);
  const sel = pick ?? (i >= 0 && i < items.length ? i : 0);
  const cur = items[sel];
  const groups = [...new Set(items.map((x) => x.group))];
  return (
    <div
      ref={ref}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => {
        setPaused(false);
        setPick(null);
      }}
      data-paused={paused || undefined}
      className="mt-6 overflow-hidden rounded-[12px] border border-white/10 bg-[#25202F] text-[#F7F5F0] shadow-[0_24px_60px_-20px_rgba(37,32,47,0.55)]"
    >
      <div className="border-b border-white/10 px-4 py-3.5 text-[15px] text-white/45">{query}</div>
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
        <div className="border-r border-white/10 px-2 pb-2 pt-3">
          {groups.map((g) => (
            <div key={g}>
              <p className="px-2 pb-1.5 pt-1 text-[11px] leading-[12px] text-white/60">{g}</p>
              {items.map((x, n) =>
                x.group === g ? (
                  <button
                    key={x.key}
                    type="button"
                    onMouseEnter={() => setPick(n)}
                    onFocus={() => setPick(n)}
                    className="flex h-[38px] w-full items-center gap-2.5 rounded-[4px] px-2 text-left text-[13px] outline-none transition-colors duration-150 focus-visible:ring-1 focus-visible:ring-white/40"
                    style={{ background: n === sel ? "rgba(255,255,255,0.1)" : "transparent" }}
                  >
                    <IconC icon={x.icon} />
                    <span className="min-w-0 flex-1 truncate">{x.title}</span>
                    <span className="shrink-0 text-[11.5px]" style={{ color: x.tone }}>
                      {x.tag}
                    </span>
                  </button>
                ) : null
              )}
            </div>
          ))}
        </div>
        <div className="flex flex-col px-4 pb-3 pt-4">
          <div className="grid h-[92px] place-items-center rounded-[8px] border border-white/10 bg-white/[0.04]">
            <div className="text-center">
              <p className="text-[17px] font-semibold">{cur.title}</p>
              <p className="mt-1 text-[12.5px]" style={{ color: cur.tone }}>
                {cur.tag}
              </p>
            </div>
          </div>
          <p className="mt-4 text-[11px] leading-[13px] text-white/60">Information</p>
          <dl className="mt-1">
            {cur.info.map(([k, v]) => (
              <div key={k} className="flex items-baseline justify-between gap-4 border-b border-white/[0.07] last:border-b-0">
                <dt className="text-[11px] leading-[28px] text-white/60">{k}</dt>
                <dd className="truncate text-right text-[12px] text-white/90">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
      <div className="flex items-center justify-between border-t border-white/10 bg-white/[0.03] px-4 py-2.5 text-[12px] text-white/60">
        <span>Demo case</span>
        <span className="flex items-center gap-2 text-white/85">
          {action}
          <kbd className="rounded-[4px] bg-white/10 px-1.5 py-0.5 font-sans text-[11px] text-white/70">↵</kbd>
        </span>
      </div>
    </div>
  );
}

const TONE_C: Record<string, string> = { not_supplied: "#E0B36E", not_assessed: "#B4B2BE", not_recorded: "#B4B2BE", lookup_failed: "#F4C7BC" };

export function OptionC({ d }: { d: CardData }) {
  const lab: ItemC[] = [
    ...d.calls.map((c) => ({ key: c.gene, title: `${c.gene} ${c.protein}`, tag: "In file", tone: "#B9A8EC", icon: "received" as const, group: "Variant calls", info: [["Gene", c.gene], ["Protein change", c.hgvs], ["Allele fraction", "Not in this result"], ["Read depth", "Not in this result"]] as [string, string][] })),
    ...d.lab.map((f) => ({ key: f.k, title: f.k, tag: f.v, tone: TONE_C[f.state ?? "not_supplied"], icon: (f.state ?? "not_supplied") as GapState, group: "Next run", info: [["State", f.v], ["Why", f.note ?? ""], ["Applies to", d.calls.map((c) => c.gene).join(", ")], ["Action", "Add to the next run"]] as [string, string][] })),
  ];
  const clinic: ItemC[] = [
    ...d.clinic.map((f) => {
      const p = parts(f);
      return { key: f.k, title: p.title, tag: f.v, tone: TONE_C[f.state ?? "not_supplied"], icon: (f.state ?? "not_supplied") as GapState, group: `Evidence · ${d.total} open`, info: [["State", f.v], ["Why", f.note ?? ""], ["Scope", p.scope || "Whole case"], ["Also open", `${d.more} more in the full case`]] as [string, string][] };
    }),
    { key: "signoff", title: "Oncologist sign-off", tag: "Pending", tone: "#E0B36E", icon: "pending", group: "Decision", info: [["State", "Pending"], ["Who", "Licensed oncologist"], ["Before", "Any treatment decision"], ["Rule", "Nothing is acted on until checked"]] },
  ];
  return [<Palette key="c1" query="Search the demo case's variant calls…" items={lab} action="Add to next run" />, <Palette key="c2" query="Search what's unverified…" items={clinic} action="Hand to oncologist" />];
}
