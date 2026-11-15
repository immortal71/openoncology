"use client";

import { useId, useRef } from "react";
import { motion, useInView, type Variants } from "framer-motion";
import { cn } from "@/lib/utils";
import { EASE_OUT } from "@/lib/motion";
import { PROTEIN_REFERENCE, domainAt, parseProteinChange } from "@/lib/protein";

export type LollipopVariant = {
  gene: string;
  hgvs: string;
  emphasis?: boolean;
  note?: string;
};

const listVariants: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.06 } } };
const stickVariants: Variants = { hidden: { scaleY: 0 }, show: { scaleY: 1, transition: { duration: 0.3, ease: EASE_OUT } } };
const headVariants: Variants = {
  hidden: { scale: 0.6, opacity: 0 },
  show: { scale: 1, opacity: 1, transition: { delay: 0.18, duration: 0.2, ease: [0.4, 0, 0.2, 1] } },
};

function pct(position: number, length: number) {
  return ((Math.min(Math.max(position, 1), length) - 1) / (length - 1)) * 100;
}

function Row({ v }: { v: LollipopVariant }) {
  const gene = v.gene.toUpperCase();
  const change = parseProteinChange(v.hgvs);
  const ref = PROTEIN_REFERENCE[gene];

  if (!change || !ref) {
    return (
      <li className="grid grid-cols-[7.5rem_minmax(0,1fr)] items-center gap-4 py-3 sm:grid-cols-[11rem_minmax(0,1fr)]">
        <span className="text-[14px] font-semibold text-oo-ink">
          {v.gene} <span className="font-mono text-[13px] font-normal text-oo-ink-2">{change?.short ?? v.hgvs}</span>
        </span>
        <span className="text-[13px] text-oo-ink-3">No protein reference available for this gene</span>
      </li>
    );
  }

  const x = pct(change.position, ref.length);
  const domain = domainAt(gene, change.position);
  const labelLeft = x > 70;
  const description = `${v.gene} ${change.short} at residue ${change.position} of ${ref.length}${domain ? `, in the ${domain}` : ""}`;

  return (
    <li className="grid grid-cols-[7.5rem_minmax(0,1fr)] items-center gap-4 py-3 sm:grid-cols-[11rem_minmax(0,1fr)]">
      <div className="min-w-0">
        <div className="text-[14px] font-semibold text-oo-ink">
          {v.gene} <span className="font-mono text-[13px] font-medium text-oo-ink">{change.short}</span>
        </div>
        {v.note ? <div className="mt-0.5 text-[12px] leading-snug text-oo-ink-3">{v.note}</div> : null}
      </div>
      <div role="img" aria-label={description} className="relative h-[68px]">
        {ref.domains.map((d) => (
          <div
            key={d.label}
            className="absolute top-[38px] h-3"
            style={{ left: `${pct(d.start, ref.length)}%`, width: `${Math.max(pct(d.end, ref.length) - pct(d.start, ref.length), 0.8)}%` }}
          >
            <div className="h-full rounded-sm border border-oo-line bg-oo-line-soft" />
            <div className="mt-1.5 whitespace-nowrap text-[11px] text-oo-ink-3" style={pct(d.start, ref.length) < 8 ? { marginLeft: 16 } : undefined}>
              <span className="sm:hidden">{d.short}</span>
              <span className="hidden sm:inline">{d.label}</span> {d.start}–{d.end}
            </div>
          </div>
        ))}
        <div className="absolute inset-x-0 top-[44px] h-px bg-oo-ink-3/40" />
        <motion.div
          data-reveal="grow-y"
          variants={stickVariants}
          className={cn("absolute top-[14px] h-[30px] w-[2px]", v.emphasis ? "bg-oo-eosin" : "bg-oo-ink-3")}
          style={{ left: `calc(${x}% - 1px)`, originY: 1 }}
        />
        <motion.div
          data-reveal="pop"
          variants={headVariants}
          className={cn("absolute top-[7px] h-[14px] w-[14px] rounded-full ring-4", v.emphasis ? "bg-oo-eosin ring-oo-eosin-tint" : "bg-oo-ink-3 ring-oo-line-soft")}
          style={{ left: `calc(${x}% - 7px)` }}
        />
        <div
          className="absolute top-[5px] whitespace-nowrap font-mono text-[12px] font-medium text-oo-ink"
          style={labelLeft ? { right: `calc(${100 - x}% + 14px)` } : { left: `calc(${x}% + 14px)` }}
        >
          {change.short}
        </div>
        <div className="absolute left-0 top-[50px] font-mono text-[11px] text-oo-ink-3">1</div>
        <div className="absolute right-0 top-[50px] font-mono text-[11px] text-oo-ink-3">{ref.length}</div>
      </div>
    </li>
  );
}

export function ProteinLollipop({ variants, className }: { variants: LollipopVariant[]; className?: string }) {
  const listRef = useRef<HTMLUListElement>(null);
  const titleId = useId();
  const inView = useInView(listRef, { once: true, amount: 0.3 });
  if (variants.length === 0) return null;
  const sources = Array.from(
    new Set(
      variants
        .map((v) => PROTEIN_REFERENCE[v.gene.toUpperCase()])
        .filter((r): r is NonNullable<typeof r> => Boolean(r))
        .map((r) => `${r.source} (${r.length} aa)`)
    )
  );
  return (
    <section aria-labelledby={titleId} data-section="protein" className={cn("rounded-[10px] border border-oo-line bg-oo-surface px-5 py-4", className)}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id={titleId} className="text-[13px] font-medium text-oo-ink-3">
          Variant positions on the protein
        </h2>
        {sources.length > 0 ? <p className="text-[12px] text-oo-ink-3">Residue numbers from {sources.join(", ")}</p> : null}
      </div>
      <motion.ul
        ref={listRef}
        className="mt-1 divide-y divide-oo-line-soft"
        initial="hidden"
        animate={inView ? "show" : "hidden"}
        variants={listVariants}
      >
        {variants.map((v) => (
          <Row key={`${v.gene}-${v.hgvs}`} v={v} />
        ))}
      </motion.ul>
    </section>
  );
}
