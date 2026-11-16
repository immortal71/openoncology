"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { groupByTier } from "@/lib/therapy-groups";
import { levelApplies, NEAR_TIE, type WsCandidate, type WsCase } from "@/lib/workspace";
import { Fade, focus, ink, label, line, linkText, Missing, muted } from "./parts";

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6 grid gap-1.5 first:mt-0 lg:grid-cols-[120px_minmax(0,1fr)] lg:gap-6">
      <h4 className={`${label} leading-[24px]`}>{title}</h4>
      <div className="min-w-0 max-w-[600px]">{children}</div>
    </section>
  );
}

export function CandidateDetail({ ws, c, compact, onSources, headRef }: { ws: WsCase; c: WsCandidate; compact: boolean; onSources: () => void; headRef?: React.Ref<HTMLParagraphElement> }) {
  const tie = ws.nearTies.find((t) => t.name === c.name || t.above === c.name);
  const applies = levelApplies(c, ws.lead);
  return (
    <Fade key={c.id}>
      <p className={label}>Selected candidate</p>
      <p ref={headRef} className={`mt-1 text-[26px] font-semibold leading-[32px] tracking-[-0.025em] ${ink}`}>
        {c.name}
      </p>
      <p className={`mt-0.5 text-[14px] leading-[21px] ${muted}`}>
        {ws.title} · {ws.tumor}
      </p>
      <div className={`mt-4 border-t ${line} pt-5`}>
        <Block title="Why it appears">
          <p className={`text-[16px] font-medium leading-[24px] ${ink}`}>{c.tierInfo.heading}</p>
          {applies && ws.lead?.level ? (
            <p className={`mt-1 max-w-[56ch] text-[14px] leading-[21px] ${muted}`}>
              {ws.lead.name}: {ws.lead.level.label}. {ws.lead.level.meaning}
            </p>
          ) : c.tierInfo.note ? (
            <p className={`mt-1 max-w-[56ch] text-[14px] leading-[21px] ${muted}`}>{c.tierInfo.note}.</p>
          ) : null}
          {c.matched.length ? (
            <p className={`mt-1.5 text-[14px] leading-[21px] ${ink}`}>
              <span className={muted}>Matched on </span>
              {c.matched.join(", ")}
            </p>
          ) : null}
        </Block>
        <Block title="Approval">
          <p className={`text-[14px] leading-[24px] ${ink}`}>
            {c.approval.label} <span className={muted}>(as reported)</span>
          </p>
          <p className={`text-[13.5px] leading-[20px] ${muted}`}>{c.approval.qualifier ? `Indication: ${c.approval.qualifier}` : "Indication not specified in this result"}</p>
        </Block>
        {compact ? null : (
          <Block title="Ranking">
            <p className={`text-[14px] leading-[24px] ${ink}`}>
              <span className="font-mono tabular-nums">{c.score !== null ? c.score.toFixed(2) : "No score"}</span>
              <span className={muted}>
                {" "}
                · rank {c.rank} of {ws.candidates.length}
              </span>
            </p>
            <p className={`text-[13.5px] leading-[20px] ${muted}`}>Orders candidates within this case. It is not a response probability.</p>
            {tie ? (
              <p className={`mt-1 text-[13.5px] leading-[20px] ${ink}`}>
                {tie.name} scores within {NEAR_TIE} of {tie.above}: treat the pair as a near-tie.
              </p>
            ) : null}
          </Block>
        )}
        <Block title="Sources">
          <p className={`text-[14px] leading-[24px] ${ink}`}>{c.sources.length ? c.sources.join(" · ") : "No verified source on this row"}</p>
          <p className="mt-1 text-[14px] leading-[21px]">
            <Missing>Exact lookup record not stored in this result</Missing>
          </p>
          <button type="button" onClick={onSources} className={`mt-1 inline-flex min-h-[44px] items-center gap-1 text-[13.5px] lg:min-h-0 lg:pt-1 ${linkText}`}>
            Inspect sources <ArrowRight size={14} aria-hidden="true" />
          </button>
        </Block>
        <Block title="Mechanism">
          <p className={`text-[13.5px] leading-[24px] ${ink}`}>
            {c.mechanism ?? <span className={muted}>Not reported</span>}
            {compact && c.chembl ? (
              <span className="whitespace-nowrap">
                {" "}
                <span className={`px-1 ${muted}`}>·</span> <span className={`font-mono text-[12px] ${muted}`}>{c.chembl}</span>
              </span>
            ) : null}
          </p>
        </Block>
        {!compact && c.chembl ? (
          <Block title="Identifiers">
            <a href={`https://www.ebi.ac.uk/chembl/compound_report_card/${encodeURIComponent(c.chembl)}/`} target="_blank" rel="noreferrer" className={`inline-flex items-center gap-1 text-[13.5px] leading-[24px] ${linkText}`}>
              <span className="font-mono text-[12.5px]">{c.chembl}</span> ChEMBL record <ArrowUpRight size={13} aria-hidden="true" />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          </Block>
        ) : null}
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
  compact = false,
  caseHref,
}: {
  ws: WsCase;
  list: WsCandidate[];
  activeId: string;
  onSelect: (id: string) => void;
  onSources: () => void;
  compact?: boolean;
  caseHref?: string;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const box = useRef<HTMLDivElement>(null);
  const head = useRef<HTMLParagraphElement>(null);
  const [link, setLink] = useState<{ w: number; h: number; d: string; start: number; end: number; a: number; b: number } | null>(null);
  const [revealed, setRevealed] = useState(false);
  const groups = groupByTier(list);
  const order = groups.flatMap((g) => g.items);
  const c = list.find((x) => x.id === activeId) ?? order[0];
  const col = compact ? 256 : 280;
  const gutter = compact ? 24 : 28;
  const rest = ws.candidates.filter((x) => !list.some((y) => y.id === x.id));
  const restNote = rest.length ? (rest.every((x) => x.approval.differentIndication) ? `${rest.length} more in a different indication` : `${rest.length} more in the full case`) : null;
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
      const x = col + gutter / 2;
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
  }, [c, col, gutter, compact]);

  if (!c) return null;

  return (
    <div ref={box} className={`relative grid lg:h-full ${compact ? "lg:grid-cols-[256px_minmax(0,1fr)]" : "lg:grid-cols-[280px_minmax(0,1fr)]"}`}>
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
        <p id={`${ws.id}-cand-label`} className={`flex items-center justify-between border-b ${line} px-3 pb-2 ${label}`}>
          <span>Ranked candidates</span>
          <span>Score</span>
        </p>
        <div role="radiogroup" aria-labelledby={`${ws.id}-cand-label`} className="mt-1">
          {groups.map((g) => (
            <div key={g.key} role="group" aria-label={g.heading} className="mt-2 first:mt-1">
              <p className={`px-3 pb-1 pt-1 text-[12.5px] font-medium leading-[18px] ${muted}`}>{g.heading}</p>
              <div className="space-y-0.5">
                {g.items.map((cand) => {
                  const on = cand.id === c.id;
                  const i = order.indexOf(cand);
                  const sub = cand.approval.differentIndication ? "Approved for a different indication" : cand.approval.label !== cand.tierInfo.badge ? cand.approval.label : null;
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
                      className={`relative grid min-h-[48px] w-full grid-cols-[16px_minmax(0,1fr)_auto] items-center gap-3 rounded-[6px] px-3 py-1.5 text-left transition-colors duration-100 ${
                        on ? "bg-[#EEE8F5]" : "hover:bg-[#F6F5F8] active:bg-[#EFEDF2]"
                      } ${focus}`}
                    >
                      {on ? <span aria-hidden="true" className="absolute inset-y-2.5 left-0 w-[2px] rounded-full bg-[#69518C]" /> : null}
                      <span className={`font-mono text-[12px] tabular-nums ${on ? "text-[#69518C]" : "text-[#8F899A]"}`}>{cand.rank}</span>
                      <span className="min-w-0">
                        <span className={`block text-[15px] font-medium leading-[22px] ${ink}`}>{cand.name}</span>
                        {sub ? <span className={`block text-[12.5px] leading-[18px] ${muted}`}>{sub}</span> : null}
                      </span>
                      <span className={`font-mono text-[13px] tabular-nums ${on ? ink : muted}`}>{cand.score !== null ? cand.score.toFixed(2) : "–"}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        {restNote ? <p className={`mt-3 px-3 text-[12.5px] leading-[18px] ${muted}`}>{restNote}</p> : null}
        {!compact && ties.length ? (
          <p className={`mt-3 px-3 text-[12.5px] leading-[18px] ${ink}`}>
            {ties.map((t) => `${t.name} is within ${NEAR_TIE} of ${t.above}`).join("; ")}. Treat as a near-tie.
          </p>
        ) : null}
        <p className={`mt-3 px-3 text-[12px] leading-[17px] ${muted}`}>Scores order candidates within this case. They are not response probabilities.</p>
        {caseHref ? (
          <Link href={`${caseHref}?candidate=${encodeURIComponent(c.id)}`} className={`mt-5 hidden items-center gap-1.5 self-start px-3 text-[13.5px] lg:inline-flex ${linkText}`}>
            Open the full case <ArrowRight size={14} aria-hidden="true" />
          </Link>
        ) : null}
      </div>
      <div className="p-5 lg:py-5 lg:pl-14 lg:pr-6">
        <CandidateDetail ws={ws} c={c} compact={compact} onSources={onSources} headRef={head} />
        {caseHref ? (
          <Link href={`${caseHref}?candidate=${encodeURIComponent(c.id)}`} className={`mt-3 inline-flex min-h-[44px] items-center gap-1.5 text-[14px] lg:hidden ${linkText}`}>
            Open the full case <ArrowRight size={15} aria-hidden="true" />
          </Link>
        ) : null}
      </div>
    </div>
  );
}
