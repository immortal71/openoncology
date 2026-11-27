"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { WsCandidate, WsCase } from "@/lib/workspace";
import { sendLink, type LinkDetail, type LinkKey } from "@/components/atlas/story-thread";

const LIT = "rounded-[3px] bg-[#c9aade]/[0.16] text-white shadow-[0_0_0_4px_rgba(201,170,222,0.16)]";
const CELL = "transition-[background-color,box-shadow,color] duration-150";

export type ShotData = { ws: WsCase; list: WsCandidate[]; caseHref: string };

export function ProductShot({ data }: { data: ShotData }) {
  const { ws, list, caseHref } = data;
  const [selectedId, setSelectedId] = useState(list[0]?.id);
  const [flash, setFlash] = useState<string | null>(null);
  const shot = useRef<HTMLDivElement>(null);
  const rows = useRef<Record<string, HTMLButtonElement | null>>({});
  const [link, setLink] = useState<LinkDetail>({ key: null });
  const panel = useRef<HTMLDivElement>(null);
  const card = useRef<HTMLDivElement>(null);
  const [place, setPlace] = useState<{ top: number; pad: number } | null>(null);

  useEffect(() => {
    const frame = shot.current;
    const box = panel.current;
    const summary = card.current;
    if (!frame || !box || !summary) return;
    const measure = () => {
      const last = Object.values(rows.current).filter(Boolean).at(-1);
      if (!last) return;
      const f = frame.getBoundingClientRect();
      const top = Math.round(last.getBoundingClientRect().bottom - f.top + 14);
      const panelBottom = box.getBoundingClientRect().bottom - f.top;
      setPlace({ top, pad: Math.max(64, Math.round(top + summary.offsetHeight - panelBottom + 32)) });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(frame);
    ro.observe(summary);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const onLink = (e: Event) => setLink((e as CustomEvent<LinkDetail>).detail);
    window.addEventListener("atlas:link", onLink);
    return () => window.removeEventListener("atlas:link", onLink);
  }, []);

  useEffect(() => {
    let io: IntersectionObserver | null = null;
    let timer = 0;
    const onPick = (e: Event) => {
      const { id, instant } = (e as CustomEvent<{ id: string; instant: boolean }>).detail;
      const row = rows.current[id];
      const frame = shot.current;
      if (!row || !frame) return;
      io?.disconnect();
      window.clearTimeout(timer);
      setFlash(null);
      setSelectedId(id);
      window.scrollTo({ top: frame.getBoundingClientRect().top + window.scrollY - 96, behavior: instant ? "auto" : "smooth" });
      row.focus({ preventScroll: true });
      if (instant) return;
      io = new IntersectionObserver(
        ([entry]) => {
          if (!entry.isIntersecting) return;
          io?.disconnect();
          setFlash(id);
          timer = window.setTimeout(() => setFlash(null), 1100);
        },
        { threshold: 1 },
      );
      io.observe(row);
    };
    window.addEventListener("atlas:pick", onPick);
    return () => {
      window.removeEventListener("atlas:pick", onPick);
      io?.disconnect();
      window.clearTimeout(timer);
    };
  }, []);
  const selected = list.find((candidate) => candidate.id === selectedId) ?? list[0];
  if (!selected) return null;
  const variant = ws.variants.find((item) => selected.matched.some((term) => term.toUpperCase() === item.name.toUpperCase()));
  const lit = (key: LinkKey) => link.key === key;
  const rowLink = (el: EventTarget, id: string): LinkDetail => {
    const key = (el as HTMLElement).closest<HTMLElement>("[data-link]")?.dataset.link as LinkKey | undefined;
    return key ? { key } : { key: "drug", id };
  };
  const summaryLit = lit("drug") && link.id === selected.id;

  return (
    <div ref={shot} data-shot className="relative w-full pb-16 pt-4 text-[#e9e7ec] lg:pb-[var(--card-pad,224px)] lg:pr-8" style={place ? ({ "--card-top": `${place.top}px`, "--card-pad": `${place.pad}px` } as React.CSSProperties) : undefined}>
      <div ref={panel} className="overflow-hidden rounded-xl border border-[#3a373f] bg-[#151519] shadow-[0_18px_45px_-20px_rgba(34,28,40,0.38)] lg:mr-8">
        <div className="border-b border-[#303036] px-6 py-4 text-sm text-[#cbc8d0]">
          Case review / {ws.title} <span className="float-right text-xs text-[#a7a3ad]">Demo case</span>
        </div>
        <div className="relative flex min-h-[270px]">
          <span data-thread-in aria-hidden="true" className="pointer-events-none absolute top-0 hidden h-px w-px lg:block" style={{ left: "40%" }} />
          <div className="min-w-0 flex-1 px-5 py-5 lg:px-7">
            <h3 className="text-[16px] font-semibold text-white">Candidates</h3>
            <p className="mt-1 text-xs text-[#aaa4ae]">{list.length} ranked therapies · {ws.tumorShort ?? ws.tumor}</p>
            <div className="mt-5 grid grid-cols-[minmax(110px,1fr)_90px] gap-3 border-b border-[#35323a] px-3 pb-3 text-[10px] font-semibold uppercase tracking-wide text-[#9c96a1] md:grid-cols-[minmax(110px,1.4fr)_minmax(90px,1fr)_minmax(80px,1fr)_80px]">
              <span>Candidate</span><span className="hidden md:block"><span className={`${CELL} ${lit("variant") ? "text-[#e0cae9]" : ""}`}>Variant</span></span><span className="hidden md:block"><span className={`${CELL} ${lit("evidence") ? "text-[#e0cae9]" : ""}`}>Evidence</span></span><span className="text-right">Case score</span>
            </div>
            {list.map((candidate) => (
              <button key={candidate.id} id={`shot-row-${candidate.id}`} ref={(el) => { rows.current[candidate.id] = el; }} type="button" onClick={() => setSelectedId(candidate.id)} onMouseOver={(e) => sendLink(rowLink(e.target, candidate.id))} onMouseLeave={() => sendLink({ key: null })} onFocus={() => sendLink({ key: "drug", id: candidate.id })} onBlur={() => sendLink({ key: null })} aria-pressed={candidate.id === selected.id} className={`grid w-full grid-cols-[minmax(110px,1fr)_90px] items-center gap-3 border-b border-[#302d34] px-3 py-3 text-left text-[13px] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#c9aade] md:grid-cols-[minmax(110px,1.4fr)_minmax(90px,1fr)_minmax(80px,1fr)_80px] ${candidate.id === selected.id ? "rounded-md bg-[#302936] text-white" : "text-[#c4bfc8] hover:bg-[#242129]"} ${flash === candidate.id ? "animate-[oo-row-flash_1.1s_ease-out]" : ""} ${lit("drug") && link.id === candidate.id ? "shadow-[inset_0_0_0_1px_rgba(201,170,222,0.55)]" : ""} scroll-mt-28`}>
                <span><span className="mr-3 text-[#c2a6d5]">●</span>{candidate.name}</span><span data-link="variant" className="hidden text-[#aaa4ae] md:block"><span className={`${CELL} ${lit("variant") ? LIT : ""}`}>{candidate.matched.find((term) => ws.variants.some((item) => item.name.toUpperCase() === term.toUpperCase())) ?? "—"}</span></span><span data-link="evidence" className="hidden text-[#bcaec4] md:block"><span className={`${CELL} ${lit("evidence") ? LIT : ""}`}>{ws.variants.find((item) => candidate.matched.some((term) => term.toUpperCase() === item.name.toUpperCase()))?.level?.short ?? "—"}</span></span><span className="text-right tabular-nums">{candidate.score?.toFixed(2) ?? "—"}</span>
              </button>
            ))}
            <p className="mt-5 text-xs leading-5 text-[#aaa4ae] lg:max-w-[44%]">Scores rank candidates within this case.<br />They are not response probabilities.</p>
          </div>
        </div>
      </div>
      <div ref={card} className="relative mt-5 rounded-lg border border-[#514b55] bg-[#202025] p-5 shadow-[0_16px_36px_-14px_rgba(25,19,29,0.4)] lg:absolute lg:right-0 lg:top-[var(--card-top,230px)] lg:mt-0 lg:w-[55%]">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-[#b2a9b5]">Evidence summary</p>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-[15px] font-semibold text-white"><span className={`${CELL} ${summaryLit ? LIT : ""}`}>{selected.name}</span></h3>
          {variant?.level && <span className="rounded-full bg-[#3b303f] px-3 py-1 text-xs font-medium text-[#e0cae9]">{variant.level.label}</span>}
        </div>
        <p className="mt-2 text-xs text-[#bcb5c0]">{variant?.name ?? "Variant not recorded"} · {ws.tumor}</p>
        <dl className="mt-4 space-y-3 border-t border-[#403b44] pt-4 text-xs leading-5">
          <div className="grid grid-cols-[90px_1fr] gap-3"><dt className="text-[#a9a1ad]">Biomarker</dt><dd><span className={`${CELL} ${lit("variant") ? LIT : ""}`}>{variant?.name ?? "Not recorded"}</span>{variant?.hgvs && <span className="block text-[#aaa4ae]">{variant.hgvs}</span>}</dd></div>
          <div className="grid grid-cols-[90px_1fr] gap-3"><dt className="text-[#a9a1ad]">Evidence</dt><dd><span className={`${CELL} ${lit("evidence") ? LIT : ""}`}>{variant?.level?.meaning ?? "Not recorded in this result"}</span></dd></div>
          <div className="grid grid-cols-[90px_1fr] gap-3 border-t border-[#403b44] pt-3"><dt className="text-[#a9a1ad]">Sources</dt><dd><span className={`${CELL} ${lit("evidence") ? LIT : ""}`}>{selected.sources.join(" · ") || "Not recorded"}</span></dd></div>
        </dl>
        <p className="mt-3 text-xs text-[#b7adb9]">Exact lookup record not stored</p>
        <Link href={`${caseHref}?view=candidates&candidate=${encodeURIComponent(selected.id)}`} className="mt-4 inline-block text-sm font-medium text-[#d6b7e6] underline underline-offset-4">View the demo case →</Link>
      </div>
    </div>
  );
}
