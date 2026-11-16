"use client";

import { useRef, useState } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Briefcase, CircleDashed, Code, Database, Dna, FileText, LayoutGrid, Layers, List, Search } from "lucide-react";

gsap.registerPlugin(ScrollTrigger, useGSAP);

export type ShotCandidate = {
  name: string;
  approval: string;
  mechanism: string;
  chembl: string;
  matched: string[];
  signals: string[];
  score: number;
};

export type ShotCase = {
  title: string;
  tumor: string;
  level: { label: string; meaning: string };
  candidates: ShotCandidate[];
  more: string;
  unknown: string[];
};

const EASE = [0.22, 1, 0.36, 1] as const;
const focus = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[#584493]";
const lift = "shadow-[0_1px_2px_rgb(34_30_43/0.06),0_30px_60px_-28px_rgb(34_30_43/0.32)]";
const mono = "font-mono uppercase tracking-[0.12em]";

export function Backdrop({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-[20px] bg-[#EDE9E1] ring-1 ring-inset ring-[#221E2B]/[0.05] ${className ?? ""}`}>
      <div
        aria-hidden="true"
        className="absolute inset-0 opacity-70 [mask-image:radial-gradient(ellipse_at_30%_20%,black,transparent_75%)]"
        style={{ backgroundImage: "radial-gradient(rgb(34 30 43 / 0.11) 1px, transparent 1px)", backgroundSize: "22px 22px" }}
      />
      {children}
    </div>
  );
}

export function WindowBar({ title, icon = true }: { title: string; icon?: boolean }) {
  return (
    <div className="flex h-11 shrink-0 items-end border-b border-[#E6E2EA] bg-[#F5F3EF] pl-3">
      <div className="flex h-9 max-w-full items-center gap-2 rounded-t-[8px] border border-b-0 border-[#E6E2EA] bg-white px-3.5 text-[13px] text-[#221E2B]">
        {icon ? <FileText size={14} className="shrink-0 text-[#584493]" aria-hidden="true" /> : null}
        <span className="truncate">{title}</span>
      </div>
    </div>
  );
}

function Rail() {
  const icons = [Briefcase, Layers, FileText, Search, LayoutGrid];
  return (
    <div aria-hidden="true" className="flex w-[60px] shrink-0 flex-col items-center gap-6 bg-[#2A2433] pt-6">
      <span className="mb-2 h-6 w-6 rounded-[7px] bg-[#F7F5F0]/90" />
      {icons.map((Icon, i) => (
        <Icon key={i} size={18} strokeWidth={1.6} className={i === 1 ? "text-[#F7F5F0]" : "text-[#F7F5F0]/45"} />
      ))}
    </div>
  );
}

const NAV = [
  { label: "Case overview", icon: List },
  { label: "Variant context", icon: Dna },
  { label: "Candidates", icon: Layers, on: true },
  { label: "Evidence sources", icon: Database },
  { label: "Known gaps", icon: CircleDashed },
  { label: "Methods", icon: Code },
];

function Popover() {
  return (
    <div aria-hidden="true" className={`w-[208px] rounded-[10px] bg-white p-1.5 ring-1 ring-[#221E2B]/[0.07] ${lift}`}>
      {NAV.map(({ label, icon: Icon, on }) => (
        <div key={label} className={`relative flex items-center gap-2.5 rounded-[6px] px-2.5 py-2 text-[13px] ${on ? "bg-[#EEE9F5] font-medium text-[#221E2B]" : "text-[#615B69]"}`}>
          {on ? <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-full bg-[#584493]" /> : null}
          <Icon size={14} strokeWidth={1.7} className={on ? "text-[#584493]" : "text-[#8A8492]"} />
          {label}
        </div>
      ))}
    </div>
  );
}

function Tabs() {
  return (
    <div aria-hidden="true" className="flex h-11 shrink-0 items-stretch gap-7 border-b border-[#E6E2EA] px-6">
      {["Context", "Candidates", "Sources", "Methods"].map((t) => (
        <span key={t} className={`flex items-center text-[11px] ${mono} ${t === "Candidates" ? "border-b-2 border-[#584493] text-[#221E2B]" : "border-b-2 border-transparent text-[#8A8492]"}`}>
          {t}
        </span>
      ))}
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return <span className="inline-flex items-center rounded-[5px] border border-[#E2DDE6] bg-[#FAF9F7] px-2 py-0.5 text-[13px] text-[#221E2B] lg:text-[12px]">{children}</span>;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 border-t border-[#EFECF1] py-3 sm:grid-cols-[132px_1fr] sm:gap-4">
      <dt className="text-[13px] text-[#615B69] lg:text-[12.5px]">{label}</dt>
      <dd className="min-w-0 text-[14px] text-[#221E2B]">{children}</dd>
    </div>
  );
}

function Detail({ c, data }: { c: ShotCandidate; data: ShotCase }) {
  return (
    <div>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className="text-[22px] font-semibold tracking-[-0.025em] text-[#221E2B]">{c.name}</p>
        <span className="text-[13px] text-[#615B69]">{c.approval}</span>
      </div>
      <dl className="mt-3">
        <Row label="Matched terms">
          <span className="flex flex-wrap gap-1.5">
            {c.matched.map((m) => (
              <Chip key={m}>{m}</Chip>
            ))}
          </span>
        </Row>
        <Row label="Evidence level">
          <span className="font-medium">{data.level.label}</span>
          <span className="mt-0.5 block text-[14px] leading-snug text-[#615B69] lg:text-[12.5px]">{data.level.meaning}</span>
        </Row>
        <Row label="Evidence signals">
          <span className="flex flex-wrap gap-1.5">
            {c.signals.map((s) => (
              <Chip key={s}>{s}</Chip>
            ))}
          </span>
        </Row>
        <Row label="Source record">
          <span className="inline-flex items-center gap-2 text-[#615B69]">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[#B7791F]" />
            Not stored in this demo result
          </span>
        </Row>
        <Row label="Mechanism">
          <span className="leading-snug">{c.mechanism}</span>
        </Row>
        <Row label="Not in this result">
          <span className="text-[14px] leading-snug text-[#615B69] lg:text-[13px]">{data.unknown.join(" · ")}</span>
        </Row>
      </dl>
    </div>
  );
}

function CandidateList({ data, active, onSelect, idPrefix }: { data: ShotCase; active: number; onSelect: (i: number) => void; idPrefix: string }) {
  const reduce = useReducedMotion();
  return (
    <div>
      <p className={`px-1 text-[10.5px] text-[#8A8492] ${mono}`}>Candidates · ranked</p>
      <ul className="mt-2 space-y-1">
        {data.candidates.map((c, i) => {
          const on = i === active;
          return (
            <li key={c.name}>
              <button
                type="button"
                aria-pressed={on}
                aria-controls={`${idPrefix}-detail`}
                onClick={() => onSelect(i)}
                className={`relative flex w-full items-center justify-between gap-3 rounded-[7px] px-3 py-2.5 text-left transition-colors duration-150 ${on ? "" : "hover:bg-[#F5F3F8]"} ${focus}`}
              >
                {on ? (
                  <motion.span
                    layoutId={`${idPrefix}-sel`}
                    transition={reduce ? { duration: 0 } : { duration: 0.35, ease: EASE }}
                    className="absolute inset-0 rounded-[7px] bg-[#EEE9F5]"
                  >
                    <span className="absolute inset-y-2 left-0 w-[3px] rounded-full bg-[#584493]" />
                  </motion.span>
                ) : null}
                <span className="relative min-w-0">
                  <span className="block text-[15px] font-semibold tracking-[-0.01em] text-[#221E2B]">{c.name}</span>
                  <span className="block truncate text-[14px] text-[#615B69] lg:text-[12.5px]">
                    Rank {i + 1} · {c.approval}
                  </span>
                </span>
                <span className="relative shrink-0 text-right font-mono text-[12px] text-[#8A8492] lg:text-[11.5px]">
                  <span className="block text-[9.5px] uppercase tracking-[0.12em]">Score</span>
                  {c.score.toFixed(2)}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="mt-2 border-t border-[#EFECF1] px-3 pt-2.5 text-[14px] text-[#8A8492] lg:text-[12.5px]">{data.more}</p>
      <p className="mt-1.5 px-3 text-[13px] leading-snug text-[#8A8492] lg:text-[12px]">Score orders candidates within this case. It is not a response probability.</p>
    </div>
  );
}

function SwapDetail({ data, active, idPrefix }: { data: ShotCase; active: number; idPrefix: string }) {
  const reduce = useReducedMotion();
  const c = data.candidates[active];
  return (
    <div id={`${idPrefix}-detail`} aria-live="polite">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={c.name}
          initial={reduce ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduce ? undefined : { opacity: 0, y: -6 }}
          transition={{ duration: 0.22, ease: EASE }}
        >
          <Detail c={c} data={data} />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

export function ProductShot({ data }: { data: ShotCase }) {
  const root = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        const tl = gsap.timeline({ scrollTrigger: { trigger: root.current, start: "top 78%", once: true } });
        tl.from("[data-shot='window']", { y: 60, opacity: 0, duration: 1.1, ease: "power4.out" }).from(
          "[data-shot='pop']",
          { x: -28, y: 18, opacity: 0, duration: 0.9, ease: "power3.out" },
          "-=0.65"
        );
      });
      mm.add("(prefers-reduced-motion: no-preference) and (min-width: 1024px)", () => {
        const scrub = { trigger: root.current, start: "top bottom", end: "bottom top", scrub: 0.8 };
        gsap.to("[data-depth='pop']", { y: -36, ease: "none", scrollTrigger: scrub });
        gsap.to("[data-depth='window']", { y: -10, ease: "none", scrollTrigger: scrub });
      });
    },
    { scope: root }
  );

  return (
    <div ref={root}>
      <Backdrop className="hidden h-[580px] lg:block xl:h-[620px]">
        <div data-shot="window" className="absolute bottom-[-40px] left-[6%] right-[-24px] top-[56px]">
          <div data-depth="window" className={`flex h-full overflow-hidden rounded-[12px] bg-white ring-1 ring-[#221E2B]/[0.08] ${lift}`}>
            <Rail />
            <div className="flex min-w-0 flex-1 flex-col">
              <WindowBar title={`${data.title} / evidence review`} />
              <Tabs />
              <div className="grid min-h-0 flex-1 grid-cols-[232px_minmax(0,0.9fr)_minmax(0,1.25fr)]">
                <div className="border-r border-[#EFECF1] bg-[#FBFAF8]" />
                <div className="border-r border-[#EFECF1] px-5 pt-6">
                  <div className="mb-5 border-b-2 border-[#584493] pb-3">
                    <p className="text-[21px] font-semibold tracking-[-0.025em] text-[#221E2B]">Candidate evidence</p>
                    <p className="mt-1 text-[13px] text-[#615B69]">
                      {data.title} <span className="px-1.5 text-[#DCD7DF]">|</span> {data.tumor}
                    </p>
                  </div>
                  <CandidateList data={data} active={active} onSelect={setActive} idPrefix="shot-d" />
                </div>
                <div className="relative pl-7 pr-14 pt-6">
                  <SwapDetail data={data} active={active} idPrefix="shot-d" />
                </div>
              </div>
            </div>
          </div>
        </div>
        <div data-shot="pop" className="absolute left-[calc(6%+76px)] top-[164px]">
          <div data-depth="pop">
            <Popover />
          </div>
        </div>
        <p className="absolute right-8 top-5 font-mono text-[10.5px] text-[#615B69]">Illustrative interface · demo case values</p>
      </Backdrop>

      <Backdrop className="p-3 sm:p-5 lg:hidden">
        <div data-shot="window" className={`relative overflow-hidden rounded-[12px] bg-white ring-1 ring-[#221E2B]/[0.08] ${lift}`}>
          <WindowBar title={`${data.title} / evidence review`} />
          <div className="px-4 pb-5 pt-4">
            <p className="text-[19px] font-semibold tracking-[-0.025em] text-[#221E2B]">Candidate evidence</p>
            <p className="mt-0.5 text-[13px] text-[#615B69]">
              {data.title} · {data.tumor}
            </p>
            <div className="mt-4">
              <CandidateList data={data} active={active} onSelect={setActive} idPrefix="shot-m" />
            </div>
            <div className="mt-4 border-t-2 border-[#584493] pt-4">
              <SwapDetail data={data} active={active} idPrefix="shot-m" />
            </div>
          </div>
        </div>
        <p className="mt-3 px-1 font-mono text-[10.5px] text-[#615B69]">Illustrative interface · demo case values</p>
      </Backdrop>
    </div>
  );
}
