"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, ChevronRight, CircleDashed, Database, Dna, FileText, Layers } from "lucide-react";

gsap.registerPlugin(ScrollTrigger, useGSAP);

export type ShotCandidate = {
  name: string;
  approval: string;
  mechanism: string;
  chembl: string;
  matched: string[];
  signals: string[];
  hidden: { name: string; reason: string }[];
  score: number;
};

export type ShotVariant = { gene: string; hgvs: string; short: string; level: string; targetable: boolean };

export type ShotCase = {
  title: string;
  tumor: string;
  tumorShort: string;
  demoHref: string;
  level: { label: string; meaning: string };
  variants: ShotVariant[];
  candidates: ShotCandidate[];
  more: string;
  unknown: string[];
};

const ink = "text-[#24212B]";
const muted = "text-[#625E68]";
const line = "border-[#E2DEE6]";
const focus = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[#69518C]";
const windowShadow = "border border-[#E2DEE6] shadow-[0_8px_24px_rgba(36,33,43,0.06)]";

export function Backdrop({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={`relative overflow-hidden rounded-[16px] bg-[#EFECE6] ${className ?? ""}`}>{children}</div>;
}

export function WindowBar({ title, crumb, note, dark = false }: { title: string; crumb?: string; note?: string; dark?: boolean }) {
  const soft = dark ? "text-[#F7F5F0]/70" : muted;
  return (
    <div className={`flex h-[46px] shrink-0 items-center justify-between gap-4 px-4 ${dark ? "bg-[#25202F]" : `border-b ${line} bg-white`}`}>
      <div className="flex min-w-0 items-center gap-2 text-[13px]">
        {crumb ? (
          <>
            <span aria-hidden="true" className={`grid h-[18px] w-[18px] shrink-0 place-items-center rounded-[5px] ${dark ? "bg-[#F7F5F0]/10" : "bg-[#25202F]"}`}>
              <span className="h-[6px] w-[6px] rounded-full bg-[#B9A8EC]" />
            </span>
            <span className={`hidden sm:inline ${soft}`}>{crumb}</span>
            <ChevronRight size={13} aria-hidden="true" className={`hidden shrink-0 sm:block ${dark ? "text-[#F7F5F0]/35" : "text-[#B5B0BA]"}`} />
          </>
        ) : (
          <FileText size={14} aria-hidden="true" className="shrink-0 text-[#69518C]" />
        )}
        <span className={`truncate font-medium ${dark ? "text-[#F7F5F0]" : ink}`}>{title}</span>
      </div>
      {note ? <span className={`hidden shrink-0 rounded-full border px-2.5 py-0.5 text-[12px] sm:inline ${dark ? "border-[#F7F5F0]/15" : line} ${soft}`}>{note}</span> : null}
    </div>
  );
}

const VIEWS = [
  { key: "variants", label: "Variants", icon: Dna },
  { key: "candidates", label: "Candidates", icon: Layers },
  { key: "sources", label: "Sources", icon: Database },
  { key: "gaps", label: "Gaps", icon: CircleDashed },
] as const;

type ViewKey = (typeof VIEWS)[number]["key"];

function sourceParts(s: string, level: string) {
  if (s.startsWith("OpenTargets")) return { name: "OpenTargets", provides: "Target–disease association", value: s.split("assoc. ")[1] ?? "Listed" };
  if (s === "OncoKB") return { name: "OncoKB", provides: "Curated evidence level", value: level };
  if (s === "ChEMBL") return { name: "ChEMBL", provides: "Bioactivity and mechanism", value: "Listed" };
  if (s === "ClinVar") return { name: "ClinVar", provides: "Variant clinical significance", value: "Listed" };
  return { name: s, provides: "Evidence provider", value: "Listed" };
}

function gapItems(data: ShotCase) {
  return [...data.unknown.map((u) => ({ k: u, v: "Not in this result" })), { k: "AlphaMissense class", v: "Not scored" }, { k: "Exact lookup record", v: "Not stored" }];
}

function Sidebar({ data, active, view, onChange, id }: { data: ShotCase; active: number; view: ViewKey; onChange: (v: ViewKey) => void; id: string }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const counts: Record<ViewKey, number> = {
    variants: data.variants.length,
    candidates: data.candidates.length,
    sources: data.candidates[active].signals.length,
    gaps: gapItems(data).length,
  };
  const move = (i: number) => {
    const n = (i + VIEWS.length) % VIEWS.length;
    onChange(VIEWS[n].key);
    refs.current[n]?.focus();
  };
  return (
    <div className={`flex shrink-0 flex-col border-b ${line} bg-[#FAF9F7] lg:w-[192px] lg:border-b-0 lg:border-r lg:p-3`}>
      <div className="hidden px-2 pb-4 pt-1 lg:block">
        <p className={`text-[13.5px] font-semibold ${ink}`}>{data.title}</p>
        <p className={`text-[12.5px] ${muted}`}>{data.tumorShort}</p>
      </div>
      <p className={`hidden px-2 pb-1.5 text-[11.5px] font-medium lg:block ${muted}`}>Review</p>
      <div role="tablist" aria-label="Case sections" aria-orientation="vertical" className="grid grid-cols-4 lg:flex lg:flex-col lg:gap-0.5">
        {VIEWS.map((v, i) => {
          const on = v.key === view;
          const Icon = v.icon;
          return (
            <button
              key={v.key}
              ref={(el) => {
                refs.current[i] = el;
              }}
              type="button"
              role="tab"
              id={`${id}-tab-${v.key}`}
              aria-selected={on}
              aria-controls={`${id}-panel`}
              tabIndex={on ? 0 : -1}
              onClick={() => onChange(v.key)}
              onKeyDown={(e) => {
                const keys: Record<string, number> = { ArrowDown: i + 1, ArrowRight: i + 1, ArrowUp: i - 1, ArrowLeft: i - 1, Home: 0, End: VIEWS.length - 1 };
                if (e.key in keys) {
                  e.preventDefault();
                  move(keys[e.key]);
                }
              }}
              className={`relative flex min-h-[52px] flex-col items-center justify-center gap-1 text-[12.5px] transition-colors duration-100 lg:h-9 lg:min-h-0 lg:flex-row lg:justify-start lg:gap-2.5 lg:rounded-[6px] lg:px-2 lg:text-[14px] ${
                on ? `font-medium ${ink} lg:bg-[#ECEAEF]` : `${muted} hover:text-[#24212B] lg:hover:bg-[#F1EFF3]`
              } ${focus}`}
            >
              {on ? <span aria-hidden="true" className="absolute inset-x-4 bottom-0 h-[2px] rounded-full bg-[#69518C] lg:hidden" /> : null}
              <Icon size={16} strokeWidth={1.8} aria-hidden="true" className={on ? "text-[#69518C]" : "text-[#8F899A]"} />
              {v.label}
              <span className={`ml-auto hidden font-mono text-[11.5px] tabular-nums lg:inline ${muted}`}>{counts[v.key]}</span>
            </button>
          );
        })}
      </div>
      <p className={`mt-auto hidden px-2 pt-6 text-[12px] leading-snug lg:block ${muted}`}>Research prototype.<br />Needs oncologist review.</p>
    </div>
  );
}

function Missing({ children }: { children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-2 ${ink}`}>
      <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#AD7629]" />
      <span>{children}</span>
    </span>
  );
}

function Fade({ children }: { children: React.ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <motion.div initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.15, ease: "easeOut" }}>
      {children}
    </motion.div>
  );
}

function Heading({ label, title, sub }: { label: string; title: string; sub: string }) {
  return (
    <div className={`border-b ${line} pb-4`}>
      <p className={`text-[11.5px] font-medium uppercase tracking-[0.06em] ${muted}`}>{label}</p>
      <h3 className={`mt-1 text-[20px] font-semibold leading-[28px] tracking-[-0.02em] ${ink}`}>{title}</h3>
      <p className={`mt-0.5 text-[14px] leading-[21px] ${muted}`}>{sub}</p>
    </div>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={`pb-2 pt-4 text-left text-[11.5px] font-medium uppercase tracking-[0.06em] ${muted} ${className ?? ""}`}>{children}</th>;
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6 grid gap-1.5 first:mt-0 lg:grid-cols-[120px_minmax(0,1fr)] lg:gap-6">
      <h4 className={`text-[11.5px] font-medium uppercase leading-[24px] tracking-[0.06em] ${muted}`}>{title}</h4>
      <div className="min-w-0 max-w-[560px]">{children}</div>
    </section>
  );
}

const COL = 272;
const GUTTER = 24;

function Candidates({ data, active, onSelect, onSources }: { data: ShotCase; active: number; onSelect: (i: number) => void; onSources: () => void }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const box = useRef<HTMLDivElement>(null);
  const head = useRef<HTMLParagraphElement>(null);
  const [link, setLink] = useState<{ w: number; h: number; d: string; start: number; end: number; a: number; b: number } | null>(null);
  const [revealed, setRevealed] = useState(false);
  const c = data.candidates[active];

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setRevealed(true);
      return;
    }
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setRevealed(true);
          io.disconnect();
        }
      },
      { threshold: 0.5 }
    );
    if (box.current) io.observe(box.current);
    return () => io.disconnect();
  }, []);
  const move = (i: number) => {
    const n = (i + data.candidates.length) % data.candidates.length;
    onSelect(n);
    refs.current[n]?.focus();
  };

  useLayoutEffect(() => {
    const measure = () => {
      const row = refs.current[active];
      if (!box.current || !row || !head.current) return;
      const bx = box.current.getBoundingClientRect();
      const r = row.getBoundingClientRect();
      const h = head.current.getBoundingClientRect();
      const a = r.top - bx.top + r.height / 2;
      const b = h.top - bx.top + h.height / 2;
      const start = r.right - bx.left + 6;
      const x = COL + GUTTER;
      const end = h.left - bx.left - 10;
      const dir = b < a ? -1 : 1;
      const rad = Math.min(6, Math.abs(b - a) / 2);
      const d =
        Math.abs(b - a) < 1
          ? `M${start} ${a} H${end}`
          : `M${start} ${a} H${x - rad} Q${x} ${a} ${x} ${a + dir * rad} V${b - dir * rad} Q${x} ${b} ${x + rad} ${b} H${end}`;
      setLink({ w: bx.width, h: bx.height, d, start, end, a, b });
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (box.current) ro.observe(box.current);
    return () => ro.disconnect();
  }, [active]);

  return (
    <div ref={box} className="relative grid lg:h-full lg:grid-cols-[272px_minmax(0,1fr)]">
      {link ? (
        <svg aria-hidden="true" className="pointer-events-none absolute left-0 top-0 hidden overflow-visible lg:block" width={link.w} height={link.h}>
          <path
            d={link.d}
            pathLength={1}
            fill="none"
            stroke="#69518C"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ strokeDasharray: 1, strokeDashoffset: revealed ? 0 : 1 }}
            className="motion-safe:[transition:d_150ms_ease-out,stroke-dashoffset_600ms_ease-out]"
          />
          <circle cx={link.start} cy={link.a} r="2.75" fill="#69518C" opacity={revealed ? 1 : 0} className="motion-safe:[transition:cy_150ms_ease-out,opacity_200ms_ease-out]" />
          <circle cx={link.end} cy={link.b} r="2.75" fill="#69518C" opacity={revealed ? 1 : 0} className="motion-safe:[transition:opacity_200ms_ease-out_450ms]" />
        </svg>
      ) : null}
      <div className={`flex flex-col border-b ${line} p-4 lg:border-b-0 lg:border-r lg:py-5`}>
        <p id="shot-cand-label" className={`flex items-center justify-between border-b ${line} px-3 pb-2 text-[11.5px] font-medium uppercase tracking-[0.06em] ${muted}`}>
          <span>Ranked candidates</span>
          <span>Score</span>
        </p>
        <div role="radiogroup" aria-labelledby="shot-cand-label" className="mt-1.5 space-y-0.5">
          {data.candidates.map((cand, i) => {
            const on = i === active;
            return (
              <button
                key={cand.name}
                ref={(el) => {
                  refs.current[i] = el;
                }}
                type="button"
                role="radio"
                aria-checked={on}
                tabIndex={on ? 0 : -1}
                onClick={() => onSelect(i)}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown" || e.key === "ArrowRight") {
                    e.preventDefault();
                    move(i + 1);
                  } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
                    e.preventDefault();
                    move(i - 1);
                  }
                }}
                className={`relative grid min-h-[48px] w-full grid-cols-[16px_minmax(0,1fr)_auto] items-center gap-3 rounded-[6px] px-3 text-left transition-colors duration-100 ${
                  on ? "bg-[#EEE8F5]" : "hover:bg-[#F6F5F8] active:bg-[#EFEDF2]"
                } ${focus}`}
              >
                {on ? <span aria-hidden="true" className="absolute inset-y-2.5 left-0 w-[2px] rounded-full bg-[#69518C]" /> : null}
                <span className={`font-mono text-[12px] tabular-nums ${on ? "text-[#69518C]" : "text-[#8F899A]"}`}>{i + 1}</span>
                <span className={`truncate text-[15px] font-medium leading-[22px] ${ink}`}>{cand.name}</span>
                <span className={`font-mono text-[13px] tabular-nums ${on ? ink : muted}`}>{cand.score.toFixed(2)}</span>
              </button>
            );
          })}
        </div>
        <p className={`mt-3 px-3 text-[12.5px] leading-[18px] ${muted}`}>{data.more}</p>
        <p className={`mt-3 px-3 text-[12px] leading-[17px] ${muted}`}>Scores order candidates within this case. They are not response probabilities.</p>
        <Link href={data.demoHref} className={`mt-5 hidden items-center gap-1.5 self-start rounded-[4px] px-3 text-[13.5px] font-medium text-[#69518C] underline-offset-4 hover:text-[#523E70] hover:underline lg:inline-flex ${focus}`}>
          Open the full case <ArrowRight size={14} aria-hidden="true" />
        </Link>
      </div>
      <div className="p-5 lg:py-5 lg:pl-14 lg:pr-6">
        <Fade key={c.name}>
          <p className={`text-[11.5px] font-medium uppercase tracking-[0.06em] ${muted}`}>Selected candidate</p>
          <p ref={head} className={`mt-1 text-[26px] font-semibold leading-[32px] tracking-[-0.025em] ${ink}`}>
            {c.name}
          </p>
          <p className={`mt-0.5 text-[14px] leading-[21px] ${muted}`}>
            {c.approval} · {data.title} · {data.tumor}
          </p>
          <div className={`mt-4 border-t ${line} pt-5`}>
            <Block title="Why it's ranked">
              <p className={`text-[16px] font-medium leading-[24px] ${ink}`}>{data.level.label}</p>
              <p className={`mt-1 max-w-[54ch] text-[14px] leading-[21px] ${muted}`}>{data.level.meaning}</p>
              <p className={`mt-1.5 text-[14px] leading-[21px] ${ink}`}>
                <span className={muted}>Matched on </span>
                {c.matched.join(", ")}
              </p>
            </Block>
            <Block title="Sources">
              <p className={`text-[14px] leading-[24px] ${ink}`}>{c.signals.join(" · ")}</p>
              <p className="mt-1 text-[14px] leading-[21px]">
                <Missing>Exact lookup record not stored in this demo result</Missing>
              </p>
              <button
                type="button"
                onClick={onSources}
                className={`mt-1 inline-flex min-h-[44px] items-center gap-1 rounded-[4px] text-[13.5px] font-medium text-[#69518C] underline-offset-4 hover:text-[#523E70] hover:underline lg:min-h-0 lg:pt-1 ${focus}`}
              >
                Inspect sources <ArrowRight size={14} aria-hidden="true" />
              </button>
            </Block>
            <Block title="Mechanism">
              <p className={`text-[13.5px] leading-[24px] ${ink}`}>
                {c.mechanism}{" "}
                <span className="whitespace-nowrap">
                  <span className={`px-1 ${muted}`}>·</span> <span className={`font-mono text-[12px] ${muted}`}>{c.chembl}</span>
                </span>
              </p>
            </Block>
          </div>
        </Fade>
        <Link href={data.demoHref} className={`mt-3 inline-flex min-h-[44px] items-center gap-1.5 text-[14px] font-medium text-[#69518C] lg:hidden ${focus}`}>
          Open the full case <ArrowRight size={15} aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}

function Variants({ data }: { data: ShotCase }) {
  return (
    <div className="p-5 lg:px-8 lg:py-5">
      <Heading label="Variants" title={`${data.variants.length} variants in this result`} sub={`From the tumor VCF · the ranked candidates are matched to ${data.title}`} />
      <table className="w-full max-w-[680px] border-collapse lg:table-fixed">
        <colgroup>
          <col className="lg:w-[150px]" />
          <col className="lg:w-[170px]" />
          <col className="lg:w-[160px]" />
          <col />
        </colgroup>
        <thead className={`border-b ${line}`}>
          <tr>
            <Th>Variant</Th>
            <Th className="hidden sm:table-cell">HGVS</Th>
            <Th>OncoKB</Th>
            <Th className="hidden md:table-cell">Status</Th>
          </tr>
        </thead>
        <tbody>
          {data.variants.map((v) => (
            <tr key={v.hgvs} className={`border-b ${line} text-[14px]`}>
              <td className={`py-2.5 pr-4 font-semibold ${ink}`}>
                {v.gene} {v.short}
              </td>
              <td className={`hidden py-2.5 pr-4 font-mono text-[12.5px] sm:table-cell ${muted}`}>{v.hgvs}</td>
              <td className={`py-2.5 pr-4 ${ink}`}>{v.level}</td>
              <td className={`hidden py-2.5 md:table-cell ${muted}`}>{v.targetable ? "Targetable" : "Not targetable in this result"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Sources({ data, active }: { data: ShotCase; active: number }) {
  const c = data.candidates[active];
  return (
    <div className="p-5 lg:px-8 lg:py-5">
      <Fade key={c.name}>
        <Heading label="Evidence sources" title={`For ${c.name}`} sub={`${data.title} · what each provider gives in this result`} />
        <table className="w-full max-w-[680px] border-collapse lg:table-fixed">
          <colgroup>
            <col className="lg:w-[190px]" />
            <col className="lg:w-[250px]" />
            <col />
          </colgroup>
          <thead className={`border-b ${line}`}>
            <tr>
              <Th>Source</Th>
              <Th className="hidden sm:table-cell">Provides</Th>
              <Th>In this result</Th>
            </tr>
          </thead>
          <tbody>
            {c.signals.map((s) => {
              const p = sourceParts(s, data.level.label);
              return (
                <tr key={s} className={`border-b ${line} text-[14px]`}>
                  <td className={`py-2.5 pr-4 font-semibold ${ink}`}>{p.name}</td>
                  <td className={`hidden py-2.5 pr-4 sm:table-cell ${muted}`}>{p.provides}</td>
                  <td className={`py-2.5 tabular-nums ${ink}`}>{p.value}</td>
                </tr>
              );
            })}
            <tr className={`border-b ${line} text-[14px]`}>
              <td className={`py-2.5 pr-4 font-semibold ${ink}`}>Exact lookup record</td>
              <td className={`hidden py-2.5 pr-4 sm:table-cell ${muted}`}>Citation behind the level</td>
              <td className="py-2.5">
                <Missing>Not stored</Missing>
              </td>
            </tr>
          </tbody>
        </table>
        <p className={`mt-4 text-[13px] leading-snug ${muted}`}>A provider name is not a stored citation.</p>
        {c.hidden.length ? (
          <p className={`mt-1 text-[13px] leading-snug ${muted}`}>
            Not shown, as in the full results view: {c.hidden.map((h) => `${h.name} (${h.reason})`).join(" · ")}.
          </p>
        ) : null}
      </Fade>
    </div>
  );
}

function Gaps({ data }: { data: ShotCase }) {
  return (
    <div className="p-5 lg:px-8 lg:py-5">
      <Heading label="Known gaps" title={`${gapItems(data).length} items not in this result`} sub="Listed so a missing value isn't mistaken for a negative finding" />
      <ul className="mt-1 grid max-w-[680px] sm:grid-cols-2 sm:gap-x-8">
        {gapItems(data).map((it) => (
          <li key={it.k} className={`flex items-center justify-between gap-4 border-b ${line} py-2.5 text-[14px]`}>
            <Missing>
              <span className="font-medium">{it.k}</span>
            </Missing>
            <span className={`shrink-0 text-[12.5px] ${muted}`}>{it.v}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ProductShot({ data }: { data: ShotCase }) {
  const root = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  const [view, setView] = useState<ViewKey>("candidates");
  const [announce, setAnnounce] = useState("");
  const id = "shot";

  const select = (i: number) => {
    setActive(i);
    setAnnounce(`${data.candidates[i].name} selected`);
  };
  const toSources = () => {
    setView("sources");
    requestAnimationFrame(() => document.getElementById(`${id}-tab-sources`)?.focus({ preventScroll: true }));
  };

  useEffect(() => {
    const onView = (e: Event) => {
      const v = (e as CustomEvent<string>).detail;
      if (VIEWS.some((x) => x.key === v)) setView(v as ViewKey);
    };
    window.addEventListener("atlas:view", onView);
    return () => window.removeEventListener("atlas:view", onView);
  }, []);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from("[data-shot]", { y: 28, opacity: 0, duration: 0.9, ease: "power3.out", scrollTrigger: { trigger: root.current, start: "top 85%", once: true } });
      });
    },
    { scope: root }
  );

  return (
    <div ref={root}>
      <div data-shot className={`overflow-hidden rounded-[12px] bg-white ${windowShadow}`}>
        <WindowBar dark crumb="Cases" title={`${data.title} · evidence review`} note="Demo case" />
        <div className="flex flex-col lg:flex-row">
          <Sidebar data={data} active={active} view={view} onChange={setView} id={id} />
          <div role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-tab-${view}`} className="grid min-w-0 flex-1">
            {(
              [
                ["candidates", <Candidates key="c" data={data} active={active} onSelect={select} onSources={toSources} />],
                ["variants", <Variants key="v" data={data} />],
                ["sources", <Sources key="s" data={data} active={active} />],
                ["gaps", <Gaps key="g" data={data} />],
              ] as const
            ).map(([key, node]) => (
              <div
                key={key}
                inert={view !== key}
                className={`[grid-area:1/1] min-w-0 motion-safe:transition-[opacity,visibility] motion-safe:duration-150 ${view === key ? "visible opacity-100" : "invisible opacity-0"}`}
              >
                {node}
              </div>
            ))}
          </div>
        </div>
      </div>
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>
    </div>
  );
}
