"use client";

import { useRef } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ChevronRight, CircleDashed, Database, Dna, FileText, Layers } from "lucide-react";
import type { WsCase } from "@/lib/workspace";

export const ink = "text-[#24212B]";
export const muted = "text-[#625E68]";
export const line = "border-[#E2DEE6]";
export const label = "text-[12px] font-medium uppercase tracking-[0.06em] text-[#625E68]";
export const focus = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[#69518C]";
export const linkText = `rounded-[4px] font-medium text-[#69518C] underline-offset-4 hover:text-[#523E70] hover:underline ${focus}`;
export const surface = "border border-[#E2DEE6] shadow-[0_8px_24px_rgba(36,33,43,0.06)]";

export const VIEWS = [
  { key: "variants", label: "Variants", icon: Dna },
  { key: "candidates", label: "Candidates", icon: Layers },
  { key: "sources", label: "Sources", icon: Database },
  { key: "gaps", label: "Gaps", icon: CircleDashed },
] as const;

export type ViewKey = (typeof VIEWS)[number]["key"];

export const isView = (v: unknown): v is ViewKey => VIEWS.some((x) => x.key === v);

export function Bar({ title, crumb, note, dark = false, children }: { title: string; crumb?: React.ReactNode; note?: string; dark?: boolean; children?: React.ReactNode }) {
  const soft = dark ? "text-[#F7F5F0]/70" : muted;
  return (
    <div className={`flex h-[46px] shrink-0 items-center justify-between gap-4 px-4 ${dark ? "bg-[#25202F]" : `border-b ${line} bg-white`}`}>
      <div className="flex min-w-0 items-center gap-2 text-[13px]">
        {crumb ? (
          <>
            {crumb}
            <ChevronRight size={13} aria-hidden="true" className={`hidden shrink-0 sm:block ${dark ? "text-[#F7F5F0]/35" : "text-[#B5B0BA]"}`} />
          </>
        ) : (
          <FileText size={14} aria-hidden="true" className="shrink-0 text-[#69518C]" />
        )}
        <span className={`truncate font-medium ${dark ? "text-[#F7F5F0]" : ink}`}>{title}</span>
      </div>
      <div className="flex shrink-0 items-center gap-4">
        {children}
        {note ? <span className={`hidden rounded-full border px-2.5 py-0.5 text-[12px] sm:inline ${dark ? "border-[#F7F5F0]/15" : line} ${soft}`}>{note}</span> : null}
      </div>
    </div>
  );
}

export function Mark({ dark = true }: { dark?: boolean }) {
  return (
    <span aria-hidden="true" className={`grid h-[18px] w-[18px] shrink-0 place-items-center rounded-[5px] ${dark ? "bg-[#F7F5F0]/10" : "bg-[#25202F]"}`}>
      <span className="h-[6px] w-[6px] rounded-full bg-[#B9A8EC]" />
    </span>
  );
}

export function counts(ws: WsCase, sources: number): Record<ViewKey, number> {
  return { variants: ws.variants.length, candidates: ws.candidates.length, sources, gaps: ws.gaps.length };
}

export function Sidebar({
  ws,
  view,
  onChange,
  id,
  count,
  width = "lg:w-[180px]",
  sticky = false,
  footer,
}: {
  ws: WsCase;
  view: ViewKey;
  onChange: (v: ViewKey) => void;
  id: string;
  count: Record<ViewKey, number>;
  width?: string;
  sticky?: boolean;
  footer?: React.ReactNode;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const move = (i: number) => {
    const n = (i + VIEWS.length) % VIEWS.length;
    onChange(VIEWS[n].key);
    refs.current[n]?.focus();
  };
  return (
    <div className={`flex shrink-0 flex-col border-b ${line} bg-[#FAF9F7] lg:border-b-0 lg:border-r lg:p-3 ${width}`}>
      <div className={`flex flex-col ${sticky ? "lg:sticky lg:top-[64px]" : "lg:h-full"}`}>
        <div className="hidden px-2 pb-4 pt-1 lg:block">
          <p className={`text-[13.5px] font-semibold ${ink}`}>{ws.title}</p>
          <p className={`text-[12.5px] ${muted}`}>{ws.tumorShort ?? ws.tumor}</p>
        </div>
        <p className={`hidden px-2 pb-1.5 text-[12px] font-medium lg:block ${muted}`}>Review</p>
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
                className={`relative flex min-h-[52px] flex-col items-center justify-center gap-1 text-[12.5px] transition-colors duration-100 lg:h-11 lg:min-h-0 lg:flex-row lg:justify-start lg:gap-2.5 lg:rounded-[6px] lg:px-2 lg:text-[14px] ${
                  on ? `font-medium ${ink} lg:bg-[#ECEAEF]` : `${muted} hover:text-[#24212B] lg:hover:bg-[#F1EFF3]`
                } ${focus}`}
              >
                {on ? <span aria-hidden="true" className="absolute inset-x-4 bottom-0 h-[2px] rounded-full bg-[#69518C] lg:hidden" /> : null}
                <Icon size={16} strokeWidth={1.8} aria-hidden="true" className={on ? "text-[#69518C]" : "text-[#8F899A]"} />
                {v.label}
                <span
                  className={`ml-auto hidden font-mono text-[12px] tabular-nums lg:inline ${
                    v.key === "gaps" && count.gaps > 0 ? "rounded-[4px] bg-[#F5EBDB] px-1.5 py-px font-medium text-[#7A4F14]" : "text-[#4F4A57]"
                  }`}
                >
                  {count[v.key]}
                </span>
              </button>
            );
          })}
        </div>
        {footer}
      </div>
    </div>
  );
}

export function ViewHeading({ label: eyebrow, title, sub }: { label: string; title: string; sub: string }) {
  return (
    <div className={`border-b ${line} pb-4`}>
      <p className={label}>{eyebrow}</p>
      <h3 className={`mt-1 text-[20px] font-semibold leading-[28px] tracking-[-0.02em] ${ink}`}>{title}</h3>
      <p className={`mt-0.5 text-[14px] leading-[21px] ${muted}`}>{sub}</p>
    </div>
  );
}

export function Missing({ children, tone = "amber" }: { children: React.ReactNode; tone?: "amber" | "neutral" }) {
  return (
    <span className={`inline-flex items-center gap-2 ${ink}`}>
      <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${tone === "amber" ? "bg-[#AD7629]" : "bg-[#B5B0BA]"}`} />
      <span>{children}</span>
    </span>
  );
}

export function Fade({ children }: { children: React.ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <motion.div initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.15, ease: "easeOut" }}>
      {children}
    </motion.div>
  );
}

export function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={`pb-2 pt-4 text-left ${label} ${className ?? ""}`}>{children}</th>;
}
