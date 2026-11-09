"use client";

import { useRef } from "react";
import { motion, useInView, type Variants } from "framer-motion";
import { cn } from "@/lib/utils";
import { EASE_OUT } from "@/lib/motion";
import { TierPill } from "@/components/oo/clinical";
import { highlightHandlers, useHighlightStore, useIsHighlighted } from "@/components/oo/highlight";

export type LadderItem = { id: string; name: string; score: number | null | undefined; tier?: string | null };
type Scored = LadderItem & { score: number };

const NEAR_TIE = 0.02;
const SLIDE = { duration: 0.45, ease: EASE_OUT } as const;

const ladderVariants: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } };
const lineVariants: Variants = { hidden: { scaleX: 0 }, show: (score: number) => ({ scaleX: score, transition: SLIDE }) };
const dotVariants: Variants = { hidden: { x: "0%" }, show: (score: number) => ({ x: `${score * 100}%`, transition: SLIDE }) };

type CSSVars = React.CSSProperties & Record<`--${string}`, string | number>;

function Rung({ item, rank }: { item: Scored; rank: number }) {
  const store = useHighlightStore();
  const active = useIsHighlighted(item.id);
  const x = item.score * 100;
  const labelLeft = x > 45;
  const lineStyle: CSSVars = { "--sx": item.score };
  const dotStyle: CSSVars = { "--x": `${x}%` };

  return (
    <div className="relative h-6" {...highlightHandlers(store, item.id)}>
      <div className="absolute inset-x-0 top-1/2 h-px bg-oo-line-soft" />
      <motion.div
        data-reveal="scale-x"
        custom={item.score}
        variants={lineVariants}
        style={{ ...lineStyle, originX: 0 }}
        className={cn("absolute inset-x-0 top-1/2 h-px transition-colors duration-150", active ? "bg-oo-ink-3" : "bg-oo-ink-3/30")}
      />
      <motion.div data-reveal="slide" custom={item.score} variants={dotVariants} style={dotStyle} className="absolute inset-x-0 top-1/2">
        <div
          className={cn(
            "-ml-[5px] -mt-[5px] h-2.5 w-2.5 rounded-full transition-shadow duration-150",
            rank === 1 ? "bg-oo-ink" : "bg-oo-ink-3",
            active && "ring-4 ring-oo-ink/10"
          )}
        />
      </motion.div>
      <div
        className={cn(
          "absolute top-1/2 -translate-y-1/2 whitespace-nowrap text-[12.5px] transition-colors duration-150",
          rank === 1 || active ? "font-semibold text-oo-ink" : "text-oo-ink-2"
        )}
        style={labelLeft ? { right: `calc(${100 - x}% + 12px)` } : { left: `calc(${x}% + 12px)` }}
      >
        <span className="mr-1.5 font-mono text-[11px] text-oo-ink-3">{rank}</span>
        {item.name}
      </div>
    </div>
  );
}

export function RankLadder({ items, context, className }: { items: LadderItem[]; context?: string; className?: string }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const inView = useInView(trackRef, { once: true, amount: 0.3 });
  const scored = items
    .filter((i): i is Scored => typeof i.score === "number" && !Number.isNaN(i.score))
    .sort((a, b) => b.score - a.score);
  if (scored.length === 0) return null;

  const top = scored[0];
  const ties = scored.slice(1).filter((item, i) => scored[i].score - item.score < NEAR_TIE);

  return (
    <section aria-labelledby="ladder-title" className={cn("rounded-[10px] border border-oo-line bg-oo-surface p-5 sm:p-6", className)}>
      <h2 id="ladder-title" className="text-[13px] font-medium text-oo-ink-3">
        Top candidate
      </h2>
      <div className="mt-3 grid gap-8 md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] md:items-end">
        <div>
          <div className="text-[24px] font-semibold leading-tight tracking-[-0.015em] text-oo-ink">{top.name}</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-sans text-[44px] font-semibold leading-none tabular-nums tracking-[-0.03em] text-oo-ink">{top.score.toFixed(2)}</span>
            <span className="text-[12px] text-oo-ink-3">evidence score, 0–1</span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <TierPill tier={top.tier} />
            {context ? <span className="text-[12.5px] text-oo-ink-3">{context}</span> : null}
          </div>
        </div>

        <div aria-hidden="true" ref={trackRef}>
          <motion.div className="space-y-1" initial="hidden" animate={inView ? "show" : "hidden"} variants={ladderVariants}>
            {scored.map((item, i) => (
              <Rung key={item.id} item={item} rank={i + 1} />
            ))}
          </motion.div>
          <div className="relative mt-2 h-4 border-t border-oo-line">
            {[0, 0.5, 1].map((t) => (
              <span
                key={t}
                className="absolute top-1 font-mono text-[11px] text-oo-ink-3"
                style={t === 1 ? { right: 0 } : t === 0 ? { left: 0 } : { left: "50%", transform: "translateX(-50%)" }}
              >
                {t.toFixed(1)}
              </span>
            ))}
          </div>
        </div>
      </div>

      <ol className="sr-only">
        {scored.map((item, i) => (
          <li key={item.id}>
            Rank {i + 1}: {item.name}, evidence score {item.score.toFixed(2)}
          </li>
        ))}
      </ol>

      {ties.length > 0 ? (
        <p className="mt-4 border-t border-oo-line-soft pt-3 text-[13px] text-oo-ink-2">
          {ties.map((t) => t.name).join(", ")} {ties.length === 1 ? "scores" : "score"} within {NEAR_TIE} of the candidate above. Treat
          {ties.length === 1 ? " that pair" : " those"} as a near-tie, not a meaningful difference.
        </p>
      ) : null}
    </section>
  );
}
