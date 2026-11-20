"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowUpRight, Download, Volume2, VolumeX } from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";
import { motion, useReducedMotion } from "framer-motion";
import { TrackMark, Wordmark } from "@/components/brand/marks";
import { downloadCaseReport } from "@/lib/pdf-report";
import type { WsCase } from "@/lib/workspace";
import { CandidatesView } from "./candidates";
import { counts, focus, ink, isView, label, line, muted, VIEWS, type ViewKey } from "./parts";
import { GapsView, SourcesView, VariantsView } from "./views";

const METHODS_URL = "https://github.com/immortal71/openoncology/blob/main/docs/METHODS.md";
const ID = "ws";

export function CaseWorkspace({
  ws,
  backHref,
  backLabel,
  initialView,
  initialCandidate,
}: {
  ws: WsCase;
  backHref: string;
  backLabel: string;
  initialView?: string;
  initialCandidate?: string;
}) {
  const [view, setView] = useState<ViewKey>(isView(initialView) ? initialView : "candidates");
  const [active, setActive] = useState(ws.candidates.some((c) => c.id === initialCandidate) ? (initialCandidate as string) : (ws.candidates[0]?.id ?? ""));
  const [announce, setAnnounce] = useState("");
  const [sourceDetail, setSourceDetail] = useState(initialView === "sources" && ws.candidates.some(c => c.id === initialCandidate));
  const [sound, setSound] = useState(false);
  const reducedMotion = useReducedMotion();
  const ready = useRef(false);
  const current = ws.candidates.find((c) => c.id === active) ?? ws.candidates[0];
  const providerName = (source: string) => source.startsWith("OpenTargets") ? "OpenTargets" : source;
  const providerNames = Array.from(new Set(ws.candidates.flatMap(c => c.sources.map(providerName))));
  const count = counts(ws, view === "sources" && !sourceDetail ? providerNames.length : current?.sources.length ?? 0);

  useEffect(() => {
    if (!ready.current) {
      ready.current = true;
      return;
    }
    const q = new URLSearchParams(window.location.search);
    q.set("view", view);
    if (view === "sources" && !sourceDetail) q.delete("candidate");
    else if (active) q.set("candidate", active);
    window.history.replaceState(window.history.state, "", `${window.location.pathname}?${q.toString()}`);
  }, [view, active, sourceDetail]);

  const select = (id: string) => {
    setActive(id);
    const c = ws.candidates.find((x) => x.id === id);
    if (c) setAnnounce(`${c.name} selected`);
  };
  const toSources = () => {
    if (sound) void new Audio("/audio/result-click.wav").play().catch(() => {});
    setSourceDetail(true);
    setView("sources");
    requestAnimationFrame(() => document.getElementById(`${ID}-tab-sources`)?.focus({ preventScroll: true }));
  };

  return (
    <div className="oo-workspace min-h-screen bg-[#F7F5F0] font-[family-name:var(--font-atlas)] text-[#24212B] antialiased">
      <header className="border-b border-[#dedadf] bg-[#fcfbf8] print:hidden">
        <div className="mx-auto flex min-h-14 max-w-[1440px] items-center justify-between gap-3 px-4 sm:px-9">
          <div className="flex items-center gap-4">
            <Link href={backHref} aria-label="OpenOncology home" className={`flex items-center gap-2 ${focus}`}>
              <TrackMark variant="bold" size={21} ink="#221E2B" accent="#584493" title="OpenOncology" />
              <Wordmark ink="#221E2B" accent="#584493" size={17} />
            </Link>
            <Link href={backHref} className={`hidden items-center gap-1.5 border-l pl-4 text-xs text-[#625e68] sm:flex ${focus}`}><ArrowLeft size={13} />{backLabel}</Link>
          </div>
          <div className="flex items-center gap-4">
            <button type="button" aria-label="Interface sound" aria-pressed={sound} title={sound ? "Mute interface sound" : "Enable interface sound"} onClick={() => setSound(!sound)} className={`grid h-10 w-8 place-items-center text-[#625e68] ${focus}`}>
              {sound ? <Volume2 size={16} /> : <VolumeX size={16} />}
            </button>
            <a href={METHODS_URL} target="_blank" rel="noreferrer" className={`hidden items-center gap-1 text-[13px] sm:flex ${focus}`}>Methods <ArrowUpRight size={14} /></a>
            <button type="button" disabled={!current} onClick={() => current && downloadCaseReport(ws, current)} className={`flex items-center gap-2 rounded-md bg-[#26222c] px-3 py-2 text-xs font-medium text-white hover:bg-[#493e56] ${focus}`}><Download size={14} />Candidate PDF</button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-3 pb-10 pt-4 sm:px-9 sm:pt-6">
        <div className="relative isolate overflow-hidden rounded-t-[10px] bg-[#2b2534] px-5 py-4 text-[#fbf8ff] sm:px-8 sm:py-4">
          <svg aria-hidden="true" viewBox="0 0 550 160" preserveAspectRatio="none" className="pointer-events-none absolute inset-y-0 right-0 -z-10 hidden h-full w-[50%] lg:block">
            {Array.from({length: 32}, (_, i) => <path key={i} d={`M 0 ${166+i*2} C 145 ${146-i}, 220 ${-56+i*4}, 350 ${40+i*2} S 500 ${135-i*5}, 560 ${-16+i*2}`} fill="none" stroke={i === 15 ? "#cb95ac" : "#aa9ab8"} strokeOpacity={i === 15 ? .65 : .26} strokeWidth=".8" />)}
          </svg>
          <div className="flex flex-wrap items-center gap-3 text-xs text-[#d6cddc]">
            <span>Case evidence review</span>
            {ws.demo && <span className="rounded border border-white/25 px-1.5 py-0.5 text-[10px]">Demo case</span>}
          </div>
          <h1 className="mt-2 text-[32px] font-semibold leading-none tracking-[-0.045em] sm:text-[40px]">{ws.title}</h1>
          <p className="mt-2 text-sm text-[#f0eaf3]">{ws.tumor}</p>
          <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-[#ddd4e3]">
            <span>Analysis · {ws.status === "complete" || ws.status === "completed" ? "Complete" : ws.status ?? "Not recorded"}</span>
            <span>Oncologist review · {ws.reviewed === null ? "Not recorded" : ws.reviewed ? "Reviewed" : "Pending"}</span>
          </p>
        </div>
        <Tabs.Root value={view} onValueChange={(value) => { if (isView(value)) { setSourceDetail(false); setView(value); } }} className={`rounded-b-[10px] border ${line} bg-white`}>
          <Tabs.List aria-label="Case sections" className="flex justify-between gap-1 border-b border-[#dedadf] px-3 sm:justify-start sm:gap-7 sm:px-8">
            {VIEWS.map(({key, label: name, icon: Icon}) => (
              <Tabs.Trigger key={key} value={key} id={`${ID}-tab-${key}`} aria-controls={`${ID}-panel`} className={`relative flex min-h-12 items-center gap-1.5 text-xs font-medium text-[#69636f] hover:text-[#362a43] data-[state=active]:text-[#533c75] sm:gap-2 sm:text-sm ${focus}`}>
                <Icon size={15} aria-hidden="true" className="hidden sm:block" />{name}
                <span className="rounded bg-[#f2eff3] px-1 font-mono text-[10px]">{count[key]}</span>
                {view === key && <motion.span aria-hidden="true" layoutId="case-tab-line" transition={{duration: reducedMotion ? 0 : .16}} className="absolute inset-x-0 bottom-0 h-0.5 bg-[#69518c]" />}
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          <div role="tabpanel" id={`${ID}-panel`} aria-labelledby={`${ID}-tab-${view}`} className="min-w-0">
            {view === "candidates" && (current
              ? <CandidatesView ws={ws} list={ws.candidates} activeId={current.id} onSelect={select} onSources={toSources} />
              : <p className="p-8">No ranked candidates for this case.</p>)}
            {view === "variants" ? <VariantsView ws={ws} /> : null}
            {view === "sources" ? (
              sourceDetail && current ? (
                <>
                  <button type="button" onClick={() => { setSourceDetail(false); requestAnimationFrame(() => document.getElementById(`source-entry-${active}`)?.focus()); }} className={`mx-4 mt-4 inline-flex min-h-10 items-center gap-2 rounded px-2 text-sm font-medium text-[#584493] hover:bg-[#f2eff3] sm:mx-6 ${focus}`}><ArrowLeft size={15} aria-hidden="true" />Back to Sources</button>
                  <SourcesView ws={ws} c={current} />
                </>
              ) : (
                <section className="px-5 py-6 sm:px-8">
                  <h2 className="text-xl font-semibold">Case sources</h2>
                  <p className="mt-1 text-sm text-[#625e68]">{providerNames.length} evidence providers across {ws.candidates.length} candidates</p>
                  <div aria-hidden="true" className="mt-4 hidden grid-cols-[minmax(145px,22%)_1fr_auto] gap-x-4 rounded-t-md bg-[#F7F5F8] px-3 py-2 text-xs font-medium text-[#625E68] sm:grid"><span>Candidate</span><span>Listed providers</span></div>
                  <ul aria-label="Evidence providers by candidate" className="mt-4 sm:mt-0 divide-y divide-[#e8e4ea] border-y border-[#dedadf]">
                    {ws.candidates.map(c => (
                      <li key={c.id}>
                        <button
                          id={`source-entry-${c.id}`}
                          aria-label={`Inspect sources for ${c.name}`}
                          onClick={() => { select(c.id); toSources(); }}
                          className={`group grid w-full grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 rounded-sm px-2 py-3.5 text-left hover:bg-[#faf8fb] sm:grid-cols-[minmax(145px,22%)_1fr_auto] sm:px-3 ${focus}`}
                        >
                          <span className="text-[15px] font-semibold tracking-tight">{c.name}</span>
                          <span className="col-start-1 row-start-2 text-[13px] leading-5 text-[#58525f] sm:col-start-2 sm:row-start-1">
                            {c.sources.length ? c.sources.map(providerName).join(" · ") : "No providers listed"}
                            {c.opentargets != null && c.sources.some(s => providerName(s) === "OpenTargets") && (
                              <span className="block text-xs text-[#625e68]">Target–disease association <span className="font-mono">{c.opentargets.toFixed(2)}</span></span>
                            )}
                          </span>
                          <span aria-hidden="true" className="col-start-2 row-start-1 row-span-2 text-xs font-medium text-[#584493] group-hover:underline sm:col-start-3 sm:row-span-1">View sources →</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                  {!ws.candidates.length && <p className="py-3 text-sm">No candidates with source information.</p>}
                </section>
              )
            ) : null}
            {view === "gaps" ? <GapsView ws={ws} /> : null}
          </div>
        </Tabs.Root>
        {ws.summary || ws.nextSteps.length ? (
          <section aria-label="Case summary" className={`mt-6 grid gap-8 rounded-[8px] border ${line} bg-white p-6 lg:grid-cols-[minmax(0,1fr)_380px] lg:px-8`}>
            {ws.summary ? (
              <div>
                <h2 className={label}>Plain-language summary</h2>
                <p className={`mt-2 max-w-[68ch] text-[15px] leading-[24px] ${ink}`}>{ws.summary}</p>
              </div>
            ) : null}
            {ws.nextSteps.length ? (
              <div>
                <h2 className={label}>Points to raise at clinical review</h2>
                <ol className={`mt-2 border-t ${line}`}>
                  {ws.nextSteps.map((s, i) => (
                    <li key={s} className={`flex gap-3 border-b ${line} py-2.5 text-[14px] leading-[21px] ${ink}`}>
                      <span className={`w-4 shrink-0 font-mono text-[12px] leading-[21px] ${muted}`}>{i + 1}</span>
                      {s}
                    </li>
                  ))}
                </ol>
                <p className={`mt-2 text-[12px] ${muted}`}>{ws.demo ? "Demo text, not a recommendation." : "Oncologist review required."}</p>
              </div>
            ) : null}
          </section>
        ) : null}
        <footer className="mt-5 flex justify-between gap-4 text-xs text-[#625e68]"><span>Research prototype · Oncologist review required</span><a className="underline sm:hidden" href={METHODS_URL}>Methods</a></footer>
      </main>
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>
    </div>
  );
}
