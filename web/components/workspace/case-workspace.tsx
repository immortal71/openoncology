"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowUpRight } from "lucide-react";
import { ReviewState } from "@/components/oo/clinical";
import { StatusPill } from "@/components/oo/status-pill";
import type { WsCase } from "@/lib/workspace";
import { CandidatesView } from "./candidates";
import { counts, focus, ink, isView, label, line, Mark, muted, Sidebar, surface, type ViewKey } from "./parts";
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
  const ready = useRef(false);
  const current = ws.candidates.find((c) => c.id === active) ?? ws.candidates[0];

  useEffect(() => {
    if (!ready.current) {
      ready.current = true;
      return;
    }
    const q = new URLSearchParams(window.location.search);
    q.set("view", view);
    if (active) q.set("candidate", active);
    window.history.replaceState(window.history.state, "", `${window.location.pathname}?${q.toString()}`);
  }, [view, active]);

  const select = (id: string) => {
    setActive(id);
    const c = ws.candidates.find((x) => x.id === id);
    if (c) setAnnounce(`${c.name} selected`);
  };
  const toSources = () => {
    setView("sources");
    requestAnimationFrame(() => document.getElementById(`${ID}-tab-sources`)?.focus({ preventScroll: true }));
  };

  return (
    <div className="min-h-screen bg-[#F7F5F0] font-[family-name:var(--font-atlas)] text-[#24212B] antialiased">
      <header className="sticky top-0 z-40 bg-[#25202F]">
        <div className="mx-auto flex h-12 max-w-[1440px] items-center justify-between gap-6 px-6">
          <div className="flex min-w-0 items-center gap-3 text-[13px]">
            <Link href="/lab/atlas" className={`flex items-center gap-2 rounded-[4px] font-semibold text-[#F7F5F0] ${focus}`}>
              <Mark />
              OpenOncology
            </Link>
            <span aria-hidden="true" className="h-4 w-px bg-[#F7F5F0]/20" />
            <Link href={backHref} className={`inline-flex items-center gap-1 rounded-[4px] text-[#F7F5F0]/70 hover:text-[#F7F5F0] ${focus}`}>
              <ArrowLeft size={13} aria-hidden="true" />
              {backLabel}
            </Link>
            <span aria-hidden="true" className="text-[#F7F5F0]/30">
              /
            </span>
            <h1 className="truncate font-medium text-[#F7F5F0]">
              {ws.title} · {ws.tumor}
            </h1>
          </div>
          <div className="flex shrink-0 items-center gap-4 text-[13px]">
            {ws.demo ? <span className="rounded-full border border-[#F7F5F0]/15 px-2.5 py-0.5 text-[12px] text-[#F7F5F0]/75">Demo case · not a real patient</span> : null}
            <a href={METHODS_URL} target="_blank" rel="noreferrer" className={`inline-flex items-center gap-1 rounded-[4px] text-[#F7F5F0]/75 hover:text-[#F7F5F0] ${focus}`}>
              Methods <ArrowUpRight size={13} aria-hidden="true" />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-6 py-6">
        <div className={`rounded-[12px] bg-white lg:flex ${surface}`}>
          <Sidebar
            ws={ws}
            view={view}
            onChange={setView}
            id={ID}
            count={counts(ws, current?.sources.length ?? 0)}
            width="lg:w-[192px] lg:rounded-l-[12px]"
            sticky
            footer={
              <div className={`mt-6 hidden space-y-2 border-t ${line} px-2 pt-4 lg:block`}>
                {ws.status ? (
                  <span role="status" className="block">
                    <span className={`mb-1 block text-[12px] ${muted}`}>Analysis</span>
                    {ws.status === "complete" || ws.status === "completed" ? (
                      <span className="flex items-center gap-1.5 text-[13px] font-medium text-[#24212B]">
                        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[#69518C]" />
                        Complete
                      </span>
                    ) : (
                      <StatusPill status={ws.status} />
                    )}
                  </span>
                ) : null}
                {ws.reviewed !== null ? <ReviewState reviewed={ws.reviewed} /> : null}
                {ws.reviewed !== true ? (
                  <div className="pt-1">
                    <span className={`mb-1 block text-[12px] ${muted}`}>Oncologist sign-off</span>
                    <span className="flex items-center gap-1.5 text-[13px] font-medium text-[#24212B]">
                      <span aria-hidden="true" className="h-2 w-2 rounded-full border-[1.5px] border-[#69518C] bg-white" />
                      Pending
                    </span>
                  </div>
                ) : null}
                <p className={`text-[12px] leading-snug ${muted}`}>Research prototype, not a medical device.</p>
              </div>
            }
          />
          <div role="tabpanel" id={`${ID}-panel`} aria-labelledby={`${ID}-tab-${view}`} className="min-w-0 flex-1">
            {view === "candidates" ? (
              current ? (
                <CandidatesView ws={ws} list={ws.candidates} activeId={current.id} onSelect={select} onSources={toSources} />
              ) : (
                <div className="p-8">
                  <p className={`text-[20px] font-semibold ${ink}`}>No ranked candidates</p>
                  <p className={`mt-1 text-[14px] ${muted}`}>No approved or repurposing candidates matched this mutation profile.</p>
                </div>
              )
            ) : null}
            {view === "variants" ? <VariantsView ws={ws} /> : null}
            {view === "sources" ? (
              current ? (
                <SourcesView ws={ws} c={current} />
              ) : (
                <p className={`p-8 text-[14px] ${muted}`}>No candidate selected, so there are no sources to show.</p>
              )
            ) : null}
            {view === "gaps" ? <GapsView ws={ws} /> : null}
          </div>
        </div>

        {ws.summary || ws.nextSteps.length ? (
          <section aria-label="Case summary" className={`mt-6 grid gap-8 rounded-[12px] bg-white p-6 lg:grid-cols-[minmax(0,1fr)_380px] lg:px-8 ${surface}`}>
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
                <p className={`mt-2 text-[12px] ${muted}`}>Demo text, not a recommendation.</p>
              </div>
            ) : null}
          </section>
        ) : null}
      </main>
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>
    </div>
  );
}
