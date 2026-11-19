"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, ChevronDown, ChevronRight, Info } from "lucide-react";
import { groupByTier } from "@/lib/therapy-groups";
import { levelApplies, NEAR_TIE, type WsCandidate, type WsCase } from "@/lib/workspace";
import { Fade, focus, ink, label, line, linkText, Missing, muted, Spine, SpineStep, StatTile } from "./parts";

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
  const tie = ws.nearTies.find((t) => t.name === c.name || t.above === c.name);
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
      {compact ? (
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
      ) : (
        <div className={`mt-4 border-t ${line} pt-5`}>
          <div className={`grid grid-cols-3 gap-px overflow-hidden rounded-[8px] border ${line} bg-[#E2DEE6]`}>
            <StatTile label="Score">
              <p className={`mt-1 font-mono text-[22px] font-semibold leading-none tabular-nums ${ink}`}>{c.score !== null ? c.score.toFixed(2) : "—"}</p>
            </StatTile>
            <StatTile label="Rank">
              <p className={`mt-1 text-[22px] font-semibold leading-none ${ink}`}>
                {c.rank}
                <span className={`ml-1 text-[13px] font-normal ${muted}`}>of {ws.candidates.length}</span>
              </p>
            </StatTile>
            <StatTile label="Evidence">
              <p className={`mt-1.5 text-[15px] font-semibold leading-[20px] ${ink}`}>{applies && ws.lead?.level ? ws.lead.level.label : (c.tierInfo.badge ?? "—")}</p>
            </StatTile>
          </div>
          <p className={`mt-2 text-[12.5px] leading-[18px] ${muted}`}>
            Ranks candidates within this case. It is not a response probability.
            {tie ? (
              <>
                {" "}
                {tie.name} scores within {NEAR_TIE} of {tie.above}: treat the pair as a near-tie.
              </>
            ) : null}
          </p>
          <Spine>
            <SpineStep title="Why it appears">
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
            </SpineStep>
            <SpineStep title="Approval">
              <p className={`text-[14px] leading-[22px] ${ink}`}>
                {c.approval.label}, as reported <span className={muted}>· {approvalNote}</span>
              </p>
            </SpineStep>
            <SpineStep title="Side effects">
              <p className="text-[14px] leading-[22px]">
                <Missing>Not supplied in this result — no adverse-event source is wired into the ranking pipeline yet</Missing>
              </p>
            </SpineStep>
            <SpineStep title="Sources">
              <p className={`text-[14px] leading-[22px] ${ink}`}>{c.sources.length ? c.sources.join(" · ") : "No verified source on this row"}</p>
              <p className="mt-1 text-[14px] leading-[21px]">
                <Missing>Exact lookup record not stored in this result</Missing>
              </p>
              <button type="button" onClick={onSources} className={`mt-1 inline-flex min-h-[44px] items-center gap-1 text-[13.5px] lg:min-h-[44px] ${linkText}`}>
                Inspect sources <ArrowRight size={14} aria-hidden="true" />
              </button>
            </SpineStep>
            <SpineStep title="Mechanism">
              <p className={`text-[13.5px] leading-[24px] ${ink}`}>{c.mechanism ?? <span className={muted}>Not reported</span>}</p>
            </SpineStep>
            {identifier ? <SpineStep title="Identifiers">{identifier}</SpineStep> : null}
          </Spine>
        </div>
      )}
    </Fade>
  );
}

export function CandidatesView({
  ws,
  list,
  activeId,
  onSelect,
  onSources,
  compact = false,
  caseHref,
  threadIn = false,
}: {
  ws: WsCase;
  list: WsCandidate[];
  activeId: string;
  onSelect: (id: string) => void;
  onSources: () => void;
  compact?: boolean;
  caseHref?: string;
  threadIn?: boolean;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const box = useRef<HTMLDivElement>(null);
  const head = useRef<HTMLParagraphElement>(null);
  const [link, setLink] = useState<{ w: number; h: number; d: string; start: number; end: number; a: number; b: number } | null>(null);
  const [revealed, setRevealed] = useState(false);
  const groups = groupByTier(list);
  const order = groups.flatMap((g) => g.items);
  const c = list.find((x) => x.id === activeId) ?? order[0];
  const col = compact ? 300 : 280;
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
      if (!compact && Math.abs(a - b) > 220) {
        setLink(null);
        return;
      }
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
    return () => ro.disconnect();
  }, [c, col, gutter, compact, threadIn]);

  if (!c) return null;

  return (
    <div ref={box} className={`relative grid lg:h-full ${compact ? "lg:grid-cols-[300px_minmax(0,1fr)]" : "lg:grid-cols-[280px_minmax(0,1fr)]"}`}>
      {link ? (
        <svg aria-hidden="true" className="pointer-events-none absolute left-0 top-0 hidden overflow-visible lg:block" width={link.w} height={link.h}>
          <path
            d={link.d}
            pathLength={1}
            fill="none"
            stroke="#69518C"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ strokeDasharray: 1, strokeDashoffset: revealed ? 0 : 1 }}
            className="motion-safe:[transition:d_150ms_ease-out,stroke-dashoffset_600ms_ease-out]"
          />
          <circle cx={link.start} cy={link.a} r="3" fill="#69518C" opacity={revealed ? 1 : 0} className="motion-safe:[transition:cy_150ms_ease-out,opacity_200ms_ease-out]" />
          <circle cx={link.end} cy={link.b} r="3" fill="#69518C" opacity={revealed ? 1 : 0} className="motion-safe:[transition:opacity_200ms_ease-out_450ms]" />
        </svg>
      ) : null}
      {threadIn ? <span data-thread-in aria-hidden="true" className="pointer-events-none absolute top-0 hidden h-px w-px lg:block" style={{ left: col - 0.5 }} /> : null}
      <div className={`flex flex-col border-b ${line} p-4 lg:border-b-0 lg:border-r lg:py-5`}>
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
                  const on = cand.id === c.id;
                  const i = order.indexOf(cand);
                  const tieWith = ties.find((x) => x.name === cand.name);
                  const sub = tieWith ? `Near-tie, within ${NEAR_TIE}` : cand.approval.differentIndication ? "Approved for a different indication" : cand.approval.label !== cand.tierInfo.badge ? cand.approval.label : null;
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
                      onClick={() => onSelect(cand.id)}
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
                      {on ? <span aria-hidden="true" /> : <ChevronRight size={13} aria-hidden="true" className="text-[#8F899A] transition-transform duration-150 group-hover:translate-x-0.5" />}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        <p className={`mt-2 px-3 text-[12.5px] leading-[18px] ${muted}`}>Scores rank candidates; they are not response probabilities.</p>
        {restNote ? <p className={`mt-2 px-3 text-[12.5px] leading-[18px] ${muted}`}>{restNote}</p> : null}
        {caseHref ? (
          <Link href={`${caseHref}?candidate=${encodeURIComponent(c.id)}`} className={`mt-3 hidden min-h-[44px] items-center gap-1.5 self-start px-3 text-[13.5px] lg:inline-flex ${linkText}`}>
            View the demo case <ArrowRight size={14} aria-hidden="true" />
          </Link>
        ) : null}
      </div>
      <div className="p-5 lg:py-5 lg:pl-14 lg:pr-6">
        <CandidateDetail ws={ws} c={c} compact={compact} onSources={onSources} headRef={head} />
        {caseHref ? (
          <Link href={`${caseHref}?candidate=${encodeURIComponent(c.id)}`} className={`mt-3 inline-flex min-h-[44px] items-center gap-1.5 text-[14px] lg:hidden ${linkText}`}>
            View the demo case <ArrowRight size={15} aria-hidden="true" />
          </Link>
        ) : null}
      </div>
    </div>
  );
}
