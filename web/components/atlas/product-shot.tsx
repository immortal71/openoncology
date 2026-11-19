"use client";

import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import type { WsCandidate, WsCase } from "@/lib/workspace";
import { CandidatesView } from "@/components/workspace/candidates";
import { Bar, counts, isView, Mark, muted, Sidebar, surface, type ViewKey } from "@/components/workspace/parts";
import { GapsView, SourcesView, VariantsView } from "@/components/workspace/views";

gsap.registerPlugin(ScrollTrigger, useGSAP);

export type ShotData = { ws: WsCase; list: WsCandidate[]; caseHref: string };

const ID = "shot";

export function ProductShot({ data }: { data: ShotData }) {
  const { ws, list, caseHref } = data;
  const root = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(list[0]?.id ?? "");
  const [view, setView] = useState<ViewKey>("candidates");
  const [announce, setAnnounce] = useState("");
  const current = list.find((c) => c.id === active) ?? list[0];

  const select = (id: string) => {
    setActive(id);
    const c = list.find((x) => x.id === id);
    if (c) setAnnounce(`${c.name} selected`);
  };
  const toSources = () => {
    setView("sources");
    requestAnimationFrame(() => document.getElementById(`${ID}-tab-sources`)?.focus({ preventScroll: true }));
  };

  useEffect(() => {
    const onView = (e: Event) => {
      const v = (e as CustomEvent<string>).detail;
      if (isView(v)) setView(v);
    };
    window.addEventListener("atlas:view", onView);
    return () => window.removeEventListener("atlas:view", onView);
  }, []);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from("[data-shot]", { opacity: 0, duration: 0.9, ease: "power2.out", delay: 0.2, scrollTrigger: { trigger: root.current, start: "top 95%", once: true } });
      });
    },
    { scope: root }
  );

  if (!current) return null;

  const views: [ViewKey, React.ReactNode][] = [
    ["candidates", <CandidatesView key="c" ws={ws} list={list} activeId={current.id} onSelect={select} onSources={toSources} compact caseHref={caseHref} threadIn />],
    ["variants", <VariantsView key="v" ws={ws} compact />],
    ["sources", <SourcesView key="s" ws={ws} c={current} compact />],
    ["gaps", <GapsView key="g" ws={ws} compact />],
  ];

  return (
    <div ref={root}>
      <div data-shot className={`overflow-hidden rounded-[12px] bg-white ${surface}`}>
        <Bar
          crumb={
            <>
              <Mark dark={false} />
              <span className={`hidden sm:inline ${muted}`}>Cases</span>
            </>
          }
          title={`${ws.title} · evidence review`}
          note="Demo case"
        />
        <div className="flex flex-col lg:flex-row">
          <Sidebar
            width="lg:w-[164px]"
            ws={ws}
            view={view}
            onChange={setView}
            id={ID}
            count={counts(ws, current.sources.length)}
            footer={
              <dl className="mt-6 hidden space-y-2.5 border-t border-[#E2DEE6] px-2 pt-4 text-[12.5px] leading-[17px] lg:block">
                <div>
                  <dt className={muted}>Analysis</dt>
                  <dd className="mt-0.5 flex items-center gap-1.5 font-medium text-[#24212B]">
                    <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[#69518C]" />
                    Complete
                  </dd>
                </div>
                <div>
                  <dt className={muted}>Oncologist sign-off</dt>
                  <dd className="mt-0.5 flex items-center gap-1.5 font-medium text-[#24212B]">
                    <span aria-hidden="true" className="h-2 w-2 rounded-full border-[1.5px] border-[#69518C] bg-white" />
                    Pending
                  </dd>
                </div>
              </dl>
            }
          />
          <div role="tabpanel" id={`${ID}-panel`} aria-labelledby={`${ID}-tab-${view}`} className="grid min-w-0 flex-1">
            {views.map(([key, node]) => (
              <div
                key={key}
                inert={view !== key}
                className={`[grid-area:1/1] min-w-0 motion-safe:transition-[opacity,visibility] motion-safe:duration-150 ${view === key ? "visible opacity-100" : "invisible opacity-0"}`}
              >
                {node}
              </div>
            ))}
          </div>
        </div>
      </div>
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>
    </div>
  );
}
