"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, ChevronDown, ChevronRight, Database, Info, Search, ArrowLeft } from "lucide-react";
import { groupByTier } from "@/lib/therapy-groups";
import { levelApplies, NEAR_TIE, type WsCandidate, type WsCase } from "@/lib/workspace";
import { Fade, focus, ink, label, line, linkText, Missing, muted } from "./parts";

function Block({ title, stacked, children }: { title: string; stacked: boolean; children: React.ReactNode }) {
  if (stacked)
    return (
      <section className="mt-4 grid gap-1 first:mt-0 sm:grid-cols-[124px_minmax(0,1fr)] sm:gap-4">
        <h4 className={`${label} sm:leading-[22px]`}>{title}</h4>
        <div className="min-w-0 max-w-[560px]">{children}</div>
      </section>
    );
  return (
    <section className="mt-4 grid gap-1 first:mt-0 lg:grid-cols-[120px_minmax(0,1fr)] lg:gap-5">
      <h4 className={`${label} leading-[22px]`}>{title}</h4>
      <div className="min-w-0 max-w-[600px]">{children}</div>
    </section>
  );
}

export function CandidateDetail({ ws, c, compact, onSources, headRef }: { ws: WsCase; c: WsCandidate; compact: boolean; onSources: () => void; headRef?: React.Ref<HTMLParagraphElement> }) {
  const applies = levelApplies(c, ws.lead);
  const approvalNote = c.approval.qualifier ? `indication: ${c.approval.qualifier}` : "indication not stored in this result";
  const identifier = c.chembl ? (
    <span className="inline-flex flex-wrap items-center gap-x-3 text-[13.5px] leading-[22px]">
      <span className={`font-mono text-[12.5px] ${ink}`}>{c.chembl}</span>
      <a href={`https://www.ebi.ac.uk/chembl/compound_report_card/${encodeURIComponent(c.chembl)}/`} target="_blank" rel="noreferrer" className={`inline-flex items-center gap-1 ${linkText}`}>
        ChEMBL record <ArrowUpRight size={13} aria-hidden="true" />
        <span className="sr-only">(opens in a new tab)</span>
      </a>
    </span>
  ) : null;
  if (!compact) {
    return (
      <article className="min-w-0">
        <p className="flex items-center gap-2 text-[12px] text-[#625E68]">
          <span className="font-mono">Rank {c.rank} / {ws.candidates.length}</span>
          <span aria-hidden="true">·</span>
          {c.approval.label}
        </p>
        <h2 ref={headRef} tabIndex={-1} className="mt-2 break-words text-[32px] font-semibold leading-[1.12] tracking-[-0.045em] text-[#24212B] outline-none sm:text-[38px]">{c.name}</h2>
        <p className="mt-2 max-w-[62ch] text-[14px] leading-[22px] text-[#625E68]">{c.mechanism ?? "Mechanism not reported"}</p>
        <section className="mt-6 border-y border-[#DCD7DF] py-5" aria-label="Matching evidence">
          <h3 className="text-[17px] font-semibold tracking-[-0.025em]">Why it appears</h3>
          {c.matched.length ? <div className="mt-3 flex flex-wrap items-baseline gap-2">
            <span className="mr-1 text-[13px] text-[#625E68]">Matched terms</span>
            {c.matched.map((term) => <span key={term} className="rounded-[4px] border border-[#E3DFE6] bg-[#FAF9FB] px-2 py-1 font-mono text-[12px] text-[#453C52]">{term}</span>)}
          </div> : <p className="mt-2 text-[14px] text-[#625E68]">Matched terms were not supplied.</p>}
          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-3">
            <p className="flex items-center gap-2 text-[13px] text-[#514C59]"><Database size={15} aria-hidden="true" />{c.sources.join(" · ") || "No sources listed"}</p>
            <button type="button" onClick={onSources} className={`inline-flex min-h-[40px] items-center gap-2 rounded-[6px] bg-[#342B40] px-3.5 text-[13px] font-medium text-white hover:bg-[#493B57] ${focus}`}>Inspect sources <ArrowRight size={14} aria-hidden="true" /></button>
          </div>
        </section>
        <dl className="divide-y divide-[#E9E6EA] text-[13.5px] leading-[21px]">
          <div className="grid gap-1 py-3 sm:grid-cols-[128px_1fr] sm:gap-4"><dt className={muted}>Approval</dt><dd>{c.approval.label} <span className={muted}>· {approvalNote}</span></dd></div>
          <div className="grid gap-1 py-3 sm:grid-cols-[128px_1fr] sm:gap-4"><dt className={muted}>Source records</dt><dd>Exact citations were not stored.</dd></div>
          <div className="grid gap-1 py-3 sm:grid-cols-[128px_1fr] sm:gap-4"><dt className={muted}>Side effects</dt><dd>Not supplied in this result</dd></div>
          {identifier ? <div className="grid gap-1 py-3 sm:grid-cols-[128px_1fr] sm:gap-4"><dt className={muted}>Identifier</dt><dd>{identifier}</dd></div> : null}
        </dl>
      </article>
    );
  }
  return (
    <Fade key={c.id}>
      <p className={label}>Selected candidate</p>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
        <p ref={headRef} className={`text-[26px] font-semibold leading-[32px] tracking-[-0.025em] ${ink}`}>
          {c.name}
        </p>
        {applies && ws.lead?.level ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[#EEE8F5] px-2.5 py-1 text-[12.5px] font-medium leading-none text-[#4A3870]">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[#69518C]" />
            {ws.lead.level.label}
          </span>
        ) : null}
      </div>
      <p className={`mt-0.5 text-[14px] leading-[21px] ${muted}`}>
        {ws.title} · {ws.tumor}
      </p>
        <div className={`mt-4 border-t ${line} pt-5`}>
          <Block title="Why it appears" stacked>
            {applies && ws.lead?.level ? (
              <>
                <p className={`text-[16px] font-medium leading-[24px] ${ink}`}>
                  {ws.lead.level.label} · {ws.lead.name}
                </p>
                <p className={`mt-0.5 max-w-[56ch] text-[14px] leading-[21px] ${muted}`}>{ws.lead.level.meaning}</p>
              </>
            ) : (
              <p className={`text-[16px] font-medium leading-[24px] ${ink}`}>{c.tierInfo.note ?? c.tierInfo.heading}</p>
            )}
            {c.matched.length ? (
              <p className={`mt-1 text-[14px] leading-[21px] ${ink}`}>
                <span className={muted}>Matched on </span>
                {c.matched.join(", ")}
              </p>
            ) : null}
          </Block>
          <Block title="Approval" stacked>
            <p className={`text-[14px] leading-[22px] ${ink}`}>
              {c.approval.label}, as reported <span className={muted}>· {approvalNote}</span>
            </p>
          </Block>
          <Block title="Sources" stacked>
            <p className={`text-[14px] leading-[22px] ${ink}`}>{c.sources.length ? c.sources.join(" · ") : "No verified source on this row"}</p>
            <p className="mt-1 text-[14px] leading-[21px]">
              <Missing>Exact lookup record not stored in this result</Missing>
            </p>
            <button type="button" onClick={onSources} className={`mt-1 inline-flex min-h-[44px] items-center gap-1 text-[13.5px] lg:min-h-[44px] ${linkText}`}>
              Inspect sources <ArrowRight size={14} aria-hidden="true" />
            </button>
          </Block>
          <details className={`group mt-5 border-t ${line} pt-3`}>
            <summary className={`inline-flex min-h-[44px] cursor-pointer list-none items-center gap-1.5 text-[13.5px] [&::-webkit-details-marker]:hidden ${linkText}`}>
              Mechanism and identifiers
              <ChevronDown size={14} aria-hidden="true" className="transition-transform duration-150 group-open:rotate-180" />
            </summary>
            <div className="mt-2 max-w-[560px] space-y-1">
              <p className={`text-[13.5px] leading-[21px] ${ink}`}>{c.mechanism ?? <span className={muted}>Mechanism not reported</span>}</p>
              {identifier}
            </div>
          </details>
        </div>
    </Fade>
  );
}

export function CandidatesView({
  ws,
  list,
  activeId,
  onSelect,
  onSources,
  openDetail = false,
  compact = false,
  caseHref,
  threadIn = false,
}: {
  ws: WsCase;
  list: WsCandidate[];
  activeId: string;
  onSelect: (id: string) => void;
  onSources: () => void;
  openDetail?: boolean;
  compact?: boolean;
  caseHref?: string;
  threadIn?: boolean;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const box = useRef<HTMLDivElement>(null);
  const head = useRef<HTMLParagraphElement>(null);
  const [link, setLink] = useState<{ w: number; h: number; d: string; start: number; end: number; a: number; b: number } | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [search, setSearch] = useState("");
  const [mobileDetail, setMobileDetail] = useState(openDetail);
  useEffect(() => {
    if (mobileDetail) head.current?.focus({ preventScroll: true });
  }, [mobileDetail]);
  const filtered = search.trim() ? list.filter((item) => item.name.toLowerCase().includes(search.trim().toLowerCase())) : list;
  const groups = groupByTier(filtered);
  const order = groups.flatMap((g) => g.items);
  const c = filtered.find((x) => x.id === activeId) ?? order[0];
  const col = compact ? 300 : 320;
  const gutter = compact ? 24 : 28;
  const rest = ws.candidates.filter((x) => !list.some((y) => y.id === x.id));
  const restNote = rest.length ? `+${rest.length} in the full case: ${rest.map((x) => (x.approval.differentIndication ? `${x.name}, different indication` : x.name)).join("; ")}` : null;
  const ties = ws.nearTies.filter((t) => list.some((x) => x.name === t.name) && list.some((x) => x.name === t.above));

  const move = (i: number) => {
    const n = (i + order.length) % order.length;
    onSelect(order[n].id);
    refs.current[order[n].id]?.focus();
  };

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
      { threshold: 0.4 }
    );
    if (box.current) io.observe(box.current);
    return () => io.disconnect();
  }, []);

  useLayoutEffect(() => {
    const measure = () => {
      const row = c ? refs.current[c.id] : null;
      if (!box.current || !row || !head.current) return;
      const bx = box.current.getBoundingClientRect();
      const r = row.getBoundingClientRect();
      const h = head.current.getBoundingClientRect();
      const a = r.top - bx.top + r.height / 2;
      const b = h.top - bx.top + h.height / 2;
      const start = r.right - bx.left + 6;
      const x = threadIn ? col - 0.5 : col + gutter / 2;
      const end = h.left - bx.left - 10;
      const dir = b < a ? -1 : 1;
      const rad = Math.min(16, Math.abs(b - a) / 2);
      const d =
        threadIn && b > 6 && a - b > 12
          ? `M${x} 0 V${bx.height} M${x} ${a - 6} Q${x} ${a} ${x - 6} ${a} H${start} M${x} ${b - 6} Q${x} ${b} ${x + 6} ${b} H${end}`
          : Math.abs(b - a) < 1
            ? `M${start} ${a} H${end}`
            : `M${start} ${a} H${x - rad} Q${x} ${a} ${x} ${a + dir * rad} V${b - dir * rad} Q${x} ${b} ${x + rad} ${b} H${end}`;
      setLink({ w: bx.width, h: bx.height, d, start, end, a, b });
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (box.current) ro.observe(box.current);
    if (head.current) ro.observe(head.current);
    if (c && refs.current[c.id]) ro.observe(refs.current[c.id]!);
    return () => ro.disconnect();
  }, [c, col, gutter, compact, threadIn, search, mobileDetail]);



  return (
    <div ref={box} className={`relative grid lg:h-full ${compact ? "lg:grid-cols-[300px_minmax(0,1fr)]" : "lg:grid-cols-[320px_minmax(0,1fr)]"}`}>
      {link && c ? (
        <svg aria-hidden="true" className="pointer-events-none absolute left-0 top-0 z-[1] hidden overflow-visible lg:block" width={link.w} height={link.h}>
          <path
            d={link.d}
            pathLength={1}
            fill="none"
            stroke="#69518C"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={compact ? { strokeDasharray: 1, strokeDashoffset: revealed ? 0 : 1 } : undefined}
            className="motion-safe:[transition:d_150ms_ease-out,stroke-dashoffset_600ms_ease-out]"
          />
          <circle cx={link.start} cy={link.a} r="3" fill="#69518C" opacity={!compact || revealed ? 1 : 0} className="motion-safe:[transition:cy_150ms_ease-out,opacity_200ms_ease-out]" />
          <circle cx={link.end} cy={link.b} r="3" fill="#69518C" opacity={!compact || revealed ? 1 : 0} className="motion-safe:[transition:opacity_200ms_ease-out_450ms]" />
        </svg>
      ) : null}
      {threadIn ? <span data-thread-in aria-hidden="true" className="pointer-events-none absolute top-0 hidden h-px w-px lg:block" style={{ left: col - 0.5 }} /> : null}
      <div className={`${!compact && mobileDetail ? "hidden lg:flex" : "flex"} flex-col border-b ${line} p-4 lg:border-b-0 lg:border-r lg:py-5`}>
        {!compact ? <label className="mb-4 flex h-10 items-center gap-2 rounded-[6px] border border-[#DCD7DF] bg-[#FAF9F7] px-3 focus-within:border-[#69518C]">
          <Search size={15} aria-hidden="true" className={muted} />
          <input type="search" aria-label="Search candidates" placeholder="Search candidates" value={search} onChange={(event) => {
            const value = event.target.value;
            setSearch(value);
            const matches = list.filter((item) => item.name.toLowerCase().includes(value.trim().toLowerCase()));
            if (matches[0] && !matches.some((item) => item.id === activeId)) onSelect(matches[0].id);
          }} className="min-w-0 flex-1 bg-transparent text-[13px] outline-none" />
        </label> : null}
        <p id={`${ws.id}-cand-label`} className={`flex items-center justify-between border-b ${line} px-3 pb-2 ${label}`}>
          <span>Ranked candidates</span>
          <span className="inline-flex items-center gap-1" title="Ranks candidates within this case; not a response probability">
            Score
            <Info size={12} aria-hidden="true" className="text-[#8F899A]" />
            <span className="sr-only">: ranks candidates within this case, not a response probability</span>
          </span>
        </p>
        <div role="radiogroup" aria-labelledby={`${ws.id}-cand-label`} className="mt-1">
          {groups.map((g) => (
            <div key={g.key} role="group" aria-label={g.heading} className="mt-2 first:mt-1">
              <p className={`px-3 pb-1 pt-1 text-[12.5px] font-medium leading-[18px] ${muted}`}>{g.heading}</p>
              <div className="space-y-0.5">
                {g.items.map((cand) => {
                  const on = cand.id === c?.id;
                  const i = order.indexOf(cand);
                  const tieWith = ties.find((x) => x.name === cand.name || (!compact && x.above === cand.name));
                  const peer = tieWith?.name === cand.name ? tieWith.above : tieWith?.name;
                  const sub = tieWith ? (compact ? `Near-tie, within ${NEAR_TIE}` : `Near-tie with ${peer}`) : cand.approval.differentIndication ? "Approved for a different indication" : cand.approval.label !== cand.tierInfo.badge ? cand.approval.label : null;
                  return (
                    <button
                      key={cand.id}
                      ref={(el) => {
                        refs.current[cand.id] = el;
                      }}
                      type="button"
                      role="radio"
                      aria-checked={on}
                      tabIndex={on ? 0 : -1}
                      onClick={() => { onSelect(cand.id); if (!compact && !window.matchMedia("(min-width: 1024px)").matches) setMobileDetail(true); }}
                      onKeyDown={(e) => {
                        if (e.key === "ArrowDown" || e.key === "ArrowRight") {
                          e.preventDefault();
                          move(i + 1);
                        } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
                          e.preventDefault();
                          move(i - 1);
                        }
                      }}
                      className={`relative grid min-h-[48px] w-full grid-cols-[16px_minmax(0,1fr)_auto_12px] items-center gap-3 rounded-[6px] px-3 py-1.5 text-left transition-[background-color,transform] duration-100 active:scale-[0.96] ${
                        on ? "bg-[#EEE8F5]" : "hover:bg-[#F6F5F8] active:bg-[#EFEDF2]"
                      } ${focus}`}
                    >
                      {on ? <span aria-hidden="true" className="absolute inset-y-2.5 left-0 w-[2px] rounded-full bg-[#69518C]" /> : null}
                      <span className={`font-mono text-[12px] tabular-nums ${on ? "text-[#69518C]" : "text-[#625E68]"}`}>{cand.rank}</span>
                      <span className="min-w-0">
                        <span className={`block text-[15px] font-medium leading-[22px] ${ink}`}>{cand.name}</span>
                        {sub ? <span className={`block text-[12.5px] leading-[18px] ${muted}`}>{sub}</span> : null}
                      </span>
                      <span className={`font-mono text-[13px] tabular-nums ${ink}`}>{cand.score !== null ? cand.score.toFixed(2) : "–"}</span>
                      {on && compact ? <span aria-hidden="true" /> : <ChevronRight size={13} aria-hidden="true" className={`text-[#8F899A] ${on ? "lg:invisible" : ""}`} />}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        {!c ? <div className="px-3 py-5 text-[14px]">
          <p>No candidates match this search.</p>
          <button type="button" className={`min-h-10 ${linkText}`} onClick={() => setSearch("")}>Clear search</button>
        </div> : null}
        <p className={`mt-2 px-3 text-[12.5px] leading-[18px] ${muted}`}>Scores rank candidates; they are not response probabilities.</p>
        {compact && restNote ? <p className={`mt-2 px-3 text-[12.5px] leading-[18px] ${muted}`}>{restNote}</p> : null}
        {caseHref && c ? (
          <Link href={`${caseHref}?candidate=${encodeURIComponent(c.id)}`} className={`mt-3 hidden min-h-[44px] items-center gap-1.5 self-start px-3 text-[13.5px] lg:inline-flex ${linkText}`}>
            View the demo case <ArrowRight size={14} aria-hidden="true" />
          </Link>
        ) : null}
      </div>
      {c ? <div className={`min-w-0 p-5 lg:block lg:pl-14 ${compact ? "lg:py-5 lg:pr-6" : "lg:py-6 lg:pr-9"} ${!compact && !mobileDetail ? "hidden" : ""}`}>
        {!compact ? <button type="button" onClick={() => { setMobileDetail(false); requestAnimationFrame(() => refs.current[c.id]?.focus()); }} className={`mb-4 inline-flex min-h-10 items-center gap-2 text-[13px] lg:hidden ${linkText}`}><ArrowLeft size={14} />Ranked candidates</button> : null}
        <CandidateDetail ws={ws} c={c} compact={compact} onSources={onSources} headRef={head} />
        {caseHref && c ? (
          <Link href={`${caseHref}?candidate=${encodeURIComponent(c.id)}`} className={`mt-3 inline-flex min-h-[44px] items-center gap-1.5 text-[14px] lg:hidden ${linkText}`}>
            View the demo case <ArrowRight size={15} aria-hidden="true" />
          </Link>
        ) : null}
      </div> : null}
    </div>
  );
}
