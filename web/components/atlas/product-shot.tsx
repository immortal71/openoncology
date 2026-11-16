"use client";

import { useLayoutEffect, useRef, useState } from "react";
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
  demoHref: string;
  level: { label: string; meaning: string };
  variants: ShotVariant[];
  candidates: ShotCandidate[];
  more: string;
  unknown: string[];
};

const ink = "text-[#221E2B]";
const muted = "text-[#6B6573]";
const line = "border-[#EEECEF]";
const focus = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[#584493]";
const windowShadow =
  "shadow-[0_0_0_1px_rgb(34_30_43/0.07),0_1px_2px_rgb(34_30_43/0.04),0_14px_28px_-14px_rgb(34_30_43/0.12),0_50px_100px_-40px_rgb(60_44_110/0.24)]";

export function Backdrop({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={`relative overflow-hidden rounded-[16px] bg-[#EFECE6] ${className ?? ""}`}>{children}</div>;
}

export function WindowBar({ title, crumb, note, dark = false }: { title: string; crumb?: string; note?: string; dark?: boolean }) {
  const soft = dark ? "text-[#F7F5F0]/60" : muted;
  return (
    <div className={`flex h-12 shrink-0 items-center justify-between gap-4 px-4 ${dark ? "bg-[#221E2B]" : `border-b ${line} bg-white`}`}>
      <div className="flex min-w-0 items-center gap-2 text-[13px]">
        {crumb ? (
          <>
            <span aria-hidden="true" className={`grid h-[18px] w-[18px] shrink-0 place-items-center rounded-[5px] ${dark ? "bg-[#F7F5F0]/10" : "bg-[#221E2B]"}`}>
              <span className="h-[6px] w-[6px] rounded-full bg-[#B9A8EC]" />
            </span>
            <span className={`hidden sm:inline ${soft}`}>{crumb}</span>
            <ChevronRight size={13} aria-hidden="true" className={`hidden shrink-0 sm:block ${dark ? "text-[#F7F5F0]/35" : "text-[#B5B0BA]"}`} />
          </>
        ) : (
          <FileText size={14} aria-hidden="true" className="shrink-0 text-[#584493]" />
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
    <div className={`flex shrink-0 flex-col border-b ${line} bg-[#FAF9F7] lg:w-[212px] lg:border-b-0 lg:border-r lg:p-3`}>
      <div className="hidden px-2 pb-4 pt-1 lg:block">
        <p className={`text-[13.5px] font-semibold ${ink}`}>{data.title}</p>
        <p className={`text-[12.5px] ${muted}`}>{data.tumor}</p>
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
              className={`relative flex min-h-[52px] flex-col items-center justify-center gap-1 text-[12.5px] transition-colors duration-100 lg:h-9 lg:min-h-0 lg:flex-row lg:justify-start lg:gap-2.5 lg:rounded-[6px] lg:px-2 lg:text-[13.5px] ${
                on ? `font-medium ${ink} lg:bg-[#EEE9F5]` : `${muted} hover:text-[#221E2B] lg:hover:bg-[#F1EFF3]`
              } ${focus}`}
            >
              {on ? <span aria-hidden="true" className="absolute inset-x-4 bottom-0 h-[2px] rounded-full bg-[#584493] lg:hidden" /> : null}
              <Icon size={16} strokeWidth={1.8} aria-hidden="true" className={on ? "text-[#584493]" : "text-[#8F899A]"} />
              {v.label}
              <span className={`ml-auto hidden font-mono text-[11.5px] tabular-nums lg:inline ${muted}`}>{counts[v.key]}</span>
            </button>
          );
        })}
      </div>
      <p className={`mt-auto hidden px-2 pt-6 text-[12px] leading-snug lg:block ${muted}`}>Research prototype. Oncologist review required.</p>
    </div>
  );
}

function Missing({ children }: { children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-2 ${ink}`}>
      <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#B7791F]" />
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

function Heading({ title, sub }: { title: string; sub: string }) {
  return (
    <div>
      <h3 className={`text-[16.5px] font-semibold tracking-[-0.015em] ${ink}`}>{title}</h3>
      <p className={`mt-0.5 text-[13px] ${muted}`}>{sub}</p>
    </div>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={`pb-2 text-left text-[12px] font-medium ${muted} ${className ?? ""}`}>{children}</th>;
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6 first:mt-0">
      <h4 className={`text-[12px] font-semibold uppercase tracking-[0.06em] ${muted}`}>{title}</h4>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function Candidates({ data, active, onSelect, onSources }: { data: ShotCase; active: number; onSelect: (i: number) => void; onSources: () => void }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const box = useRef<HTMLDivElement>(null);
  const head = useRef<HTMLParagraphElement>(null);
  const [link, setLink] = useState<{ a: number; b: number } | null>(null);
  const c = data.candidates[active];
  const move = (i: number) => {
    const n = (i + data.candidates.length) % data.candidates.length;
    onSelect(n);
    refs.current[n]?.focus();
  };

  useLayoutEffect(() => {
    const measure = () => {
      const row = refs.current[active];
      if (!box.current || !row || !head.current) return;
      const top = box.current.getBoundingClientRect().top;
      const r = row.getBoundingClientRect();
      const h = head.current.getBoundingClientRect();
      setLink({ a: r.top - top + r.height / 2, b: h.top - top + h.height / 2 });
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (box.current) ro.observe(box.current);
    return () => ro.disconnect();
  }, [active]);

  return (
    <div ref={box} className="relative grid lg:h-full lg:grid-cols-[288px_minmax(0,1fr)]">
      {link ? (
        <div aria-hidden="true" className="pointer-events-none absolute left-[287px] top-0 hidden lg:block">
          <span
            className="absolute left-0 w-[2px] bg-[#584493] motion-safe:transition-[top,height] motion-safe:duration-150"
            style={{ top: Math.min(link.a, link.b), height: Math.max(2, Math.abs(link.a - link.b)) }}
          />
          <span className="absolute -left-[4px] h-[10px] w-[10px] rounded-full bg-[#584493] ring-[3px] ring-white motion-safe:transition-[top] motion-safe:duration-150" style={{ top: link.a - 5 }} />
          <span className="absolute -left-[4px] h-[10px] w-[10px] rounded-full bg-[#584493] ring-[3px] ring-white" style={{ top: link.b - 5 }} />
        </div>
      ) : null}
      <div className={`flex flex-col border-b ${line} p-5 lg:border-b-0 lg:border-r lg:py-6 lg:pl-5 lg:pr-6`}>
        <p className={`px-3 text-[12px] font-semibold uppercase tracking-[0.06em] ${muted}`}>Ranked candidates</p>
        <p id="shot-cand-label" className={`mt-3 flex items-center justify-between border-b ${line} px-3 pb-1.5 text-[12.5px] ${muted}`}>
          <span>{data.candidates[0]?.approval}</span>
          <span>Score</span>
        </p>
        <div role="radiogroup" aria-labelledby="shot-cand-label" className="mt-1 space-y-0.5">
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
                className={`relative flex min-h-[46px] w-full items-center gap-3 rounded-[6px] px-3 text-left transition-colors duration-100 ${
                  on ? "bg-[#EEE9F5]" : "hover:bg-[#F6F5F8] active:bg-[#EFEDF2]"
                } ${focus}`}
              >
                <span className={`w-3 font-mono text-[12px] tabular-nums ${on ? "text-[#584493]" : muted}`}>{i + 1}</span>
                <span className={`min-w-0 flex-1 text-[14.5px] ${on ? "font-semibold" : "font-medium"} ${ink}`}>{cand.name}</span>
                <span className={`font-mono text-[12.5px] tabular-nums ${on ? ink : muted}`}>{cand.score.toFixed(2)}</span>
              </button>
            );
          })}
        </div>
        <p className={`mt-3 px-3 text-[12.5px] ${muted}`}>{data.more}</p>
        <p className={`mt-4 px-3 text-[12.5px] leading-snug ${muted}`}>Scores order candidates within this case. They are not response probabilities.</p>
        <Link href={data.demoHref} className={`mt-auto hidden items-center gap-1.5 self-start rounded-[4px] px-3 pt-5 text-[13.5px] font-medium text-[#584493] hover:text-[#3F2F72] lg:inline-flex ${focus}`}>
          Open the full case <ArrowRight size={14} aria-hidden="true" />
        </Link>
      </div>
      <div className="p-5 lg:overflow-y-auto lg:py-6 lg:pl-8 lg:pr-7">
        <Fade key={c.name}>
          <p ref={head} className={`text-[22px] font-semibold leading-tight tracking-[-0.025em] ${ink}`}>
            {c.name}
          </p>
          <p className={`mt-0.5 text-[13.5px] ${muted}`}>
            {c.approval} · {data.title} · {data.tumor}
          </p>
          <div className={`mt-5 border-t ${line} pt-5`}>
            <Block title="Why it's ranked">
              <p className={`text-[15px] font-semibold ${ink}`}>{data.level.label}</p>
              <p className={`mt-0.5 max-w-[46ch] text-[13.5px] leading-snug ${muted}`}>{data.level.meaning}</p>
              <p className={`mt-2 text-[13.5px] ${ink}`}>
                <span className={muted}>Matched on </span>
                {c.matched.join(", ")}
              </p>
            </Block>
            <Block title="Sources">
              <p className={`text-[13.5px] ${ink}`}>{c.signals.join(" · ")}</p>
              <p className="mt-1.5 text-[13.5px]">
                <Missing>Exact lookup record not stored in this demo result</Missing>
              </p>
              <button
                type="button"
                onClick={onSources}
                className={`mt-1 inline-flex min-h-[44px] items-center gap-1 rounded-[4px] text-[13.5px] font-medium text-[#584493] hover:text-[#3F2F72] lg:min-h-0 lg:pt-1.5 ${focus}`}
              >
                Inspect sources <ArrowRight size={14} aria-hidden="true" />
              </button>
            </Block>
          </div>
          <p className={`mt-6 border-t ${line} pt-3 text-[12.5px] ${muted}`}>
            {c.mechanism} <span className="px-1">·</span> <span className="font-mono text-[12px]">{c.chembl}</span>
          </p>
        </Fade>
        <Link href={data.demoHref} className={`mt-3 inline-flex min-h-[44px] items-center gap-1.5 text-[14px] font-medium text-[#584493] lg:hidden ${focus}`}>
          Open the full case <ArrowRight size={15} aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}

function Variants({ data }: { data: ShotCase }) {
  return (
    <div className="p-5 lg:p-6">
      <Heading title="Variants" sub={`From the tumor VCF · ${data.variants.length} in this result`} />
      <table className="mt-5 w-full border-collapse">
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
            <tr key={v.hgvs} className={`border-b ${line} text-[13.5px]`}>
              <td className={`py-3 pr-4 font-semibold ${ink}`}>
                {v.gene} {v.short}
              </td>
              <td className={`hidden py-3 pr-4 font-mono text-[12.5px] sm:table-cell ${muted}`}>{v.hgvs}</td>
              <td className={`py-3 pr-4 ${ink}`}>{v.level}</td>
              <td className={`hidden py-3 md:table-cell ${muted}`}>{v.targetable ? "Targetable" : "Not targetable in this result"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className={`mt-4 text-[13px] ${muted}`}>The ranked candidates in this case are matched to {data.title}.</p>
    </div>
  );
}

function Sources({ data, active }: { data: ShotCase; active: number }) {
  const c = data.candidates[active];
  return (
    <div className="p-5 lg:p-6">
      <Fade key={c.name}>
        <Heading title="Evidence sources" sub={`For ${c.name} · ${data.title}`} />
        <table className="mt-5 w-full border-collapse">
          <thead className={`border-b ${line}`}>
            <tr>
              <Th>Source</Th>
              <Th className="hidden sm:table-cell">Provides</Th>
              <Th className="text-right">In this result</Th>
            </tr>
          </thead>
          <tbody>
            {c.signals.map((s) => {
              const p = sourceParts(s, data.level.label);
              return (
                <tr key={s} className={`border-b ${line} text-[13.5px]`}>
                  <td className={`py-3 pr-4 font-semibold ${ink}`}>{p.name}</td>
                  <td className={`hidden py-3 pr-4 sm:table-cell ${muted}`}>{p.provides}</td>
                  <td className={`py-3 text-right tabular-nums ${ink}`}>{p.value}</td>
                </tr>
              );
            })}
            <tr className={`border-b ${line} text-[13.5px]`}>
              <td className={`py-3 pr-4 font-semibold ${ink}`}>Exact lookup record</td>
              <td className={`hidden py-3 pr-4 sm:table-cell ${muted}`}>Citation behind the level</td>
              <td className="py-3 text-right">
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
    <div className="p-5 lg:p-6">
      <Heading title="Known gaps" sub="What this demo result doesn't contain" />
      <ul className={`mt-5 grid border-t ${line} sm:grid-cols-2 sm:gap-x-8`}>
        {gapItems(data).map((it) => (
          <li key={it.k} className={`flex items-center justify-between gap-4 border-b ${line} py-3 text-[13.5px]`}>
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
    requestAnimationFrame(() => document.getElementById(`${id}-tab-sources`)?.focus());
  };

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
        <div className="flex flex-col lg:h-[440px] lg:flex-row">
          <Sidebar data={data} active={active} view={view} onChange={setView} id={id} />
          <div role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-tab-${view}`} className="min-w-0 flex-1 lg:overflow-y-auto">
            {view === "candidates" ? <Candidates data={data} active={active} onSelect={select} onSources={toSources} /> : null}
            {view === "variants" ? <Variants data={data} /> : null}
            {view === "sources" ? <Sources data={data} active={active} /> : null}
            {view === "gaps" ? <Gaps data={data} /> : null}
          </div>
        </div>
      </div>
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>
    </div>
  );
}
