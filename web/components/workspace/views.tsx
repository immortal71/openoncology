"use client";

import { useRef, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { ProteinLollipop } from "@/components/results/protein-lollipop";
import { VariantDetail } from "@/components/results/variant-drawer";
import { GAP_LABELS, sourceRow, type GapState, type WsCandidate, type WsCase } from "@/lib/workspace";
import { Fade, focus, ink, label, line, linkText, Missing, muted, Th, ViewHeading } from "./parts";

const pad = "p-5 lg:px-8 lg:py-5";

export function SourcesView({ ws, c, compact = false }: { ws: WsCase; c: WsCandidate; compact?: boolean }) {
  return (
    <div className={pad}>
      <Fade key={c.id}>
        <ViewHeading label="Evidence sources" title={`For ${c.name}`} sub={`${ws.title} · what each provider gives in this result`} />
        <table className={`w-full border-collapse lg:table-fixed ${compact ? "max-w-[680px]" : "max-w-[860px]"}`}>
          <colgroup>
            <col className="lg:w-[170px]" />
            <col className="lg:w-[230px]" />
            <col className={compact ? undefined : "lg:w-[220px]"} />
            {compact ? null : <col />}
          </colgroup>
          <thead className={`border-b ${line}`}>
            <tr>
              <Th>Source</Th>
              <Th className="hidden sm:table-cell">Provides</Th>
              <Th>In this result</Th>
              {compact ? null : <Th>Exact record</Th>}
            </tr>
          </thead>
          <tbody>
            {c.sources.map((s) => {
              const p = sourceRow(s, c, ws.lead);
              return (
                <tr key={s} className={`border-b ${line} text-[14px]`}>
                  <td className={`py-2.5 pr-4 font-semibold ${ink}`}>{p.name}</td>
                  <td className={`hidden py-2.5 pr-4 sm:table-cell ${muted}`}>{p.provides}</td>
                  <td className={`py-2.5 pr-4 tabular-nums ${ink}`}>{p.value}</td>
                  {compact ? null : (
                    <td className="py-2.5">
                      <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <Missing>Not stored</Missing>
                        {p.lookup ? (
                          <a href={p.lookup.href} target="_blank" rel="noreferrer" className={`inline-flex items-center gap-0.5 text-[13px] ${linkText}`}>
                            {p.lookup.label} <ArrowUpRight size={13} aria-hidden="true" />
                            <span className="sr-only">(external search, opens in a new tab)</span>
                          </a>
                        ) : null}
                      </span>
                    </td>
                  )}
                </tr>
              );
            })}
            {compact ? (
              <tr className={`border-b ${line} text-[14px]`}>
                <td className={`py-2.5 pr-4 font-semibold ${ink}`}>Exact lookup record</td>
                <td className={`hidden py-2.5 pr-4 sm:table-cell ${muted}`}>Citation behind the level</td>
                <td className="py-2.5">
                  <Missing>Not stored</Missing>
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
        <p className={`mt-4 text-[13px] leading-snug ${muted}`}>
          A provider name is not a stored citation.{compact ? "" : " Search links open the provider's public page, not a record saved with this result."}
        </p>
        {c.hidden.length ? (
          <p className={`mt-1 text-[13px] leading-snug ${muted}`}>
            Not shown, as in the full results view: {c.hidden.map((h) => `${h.name} (${h.reason})`).join(" · ")}.
          </p>
        ) : null}
      </Fade>
    </div>
  );
}

export function VariantsView({ ws, compact = false }: { ws: WsCase; compact?: boolean }) {
  const [selected, setSelected] = useState(ws.lead?.key ?? ws.variants[0]?.key);
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const heading = (
    <ViewHeading label="Variants" title={`${ws.variants.length} variant${ws.variants.length === 1 ? "" : "s"} in this result`} sub={`From the tumor VCF · the ranked candidates are matched to ${ws.title}`} />
  );

  if (compact) {
    return (
      <div className={pad}>
        {heading}
        <table className="w-full max-w-[680px] border-collapse lg:table-fixed">
          <colgroup>
            <col className="lg:w-[150px]" />
            <col className="lg:w-[170px]" />
            <col className="lg:w-[160px]" />
            <col />
          </colgroup>
          <thead className={`border-b ${line}`}>
            <tr>
              <Th>Variant</Th>
              <Th className="hidden sm:table-cell">HGVS</Th>
              <Th>OncoKB</Th>
              <Th className="hidden md:table-cell">Status</Th>
            </tr>
          </thead>
          <tbody>
            {ws.variants.map((v) => (
              <tr key={v.key} className={`border-b ${line} text-[14px]`}>
                <td className={`py-2.5 pr-4 font-semibold ${ink}`}>{v.name}</td>
                <td className={`hidden py-2.5 pr-4 font-mono text-[12.5px] sm:table-cell ${muted}`}>{v.hgvs}</td>
                <td className={`py-2.5 pr-4 ${ink}`}>{v.level?.label ?? "No OncoKB level"}</td>
                <td className={`hidden py-2.5 md:table-cell ${muted}`}>{v.targetable === null ? "Not reported" : v.targetable ? "Targetable" : "Not targetable in this result"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  const order = ws.variants;
  const current = order.find((v) => v.key === selected) ?? order[0];
  const move = (i: number) => {
    const n = (i + order.length) % order.length;
    setSelected(order[n].key);
    refs.current[order[n].key]?.focus();
  };

  return (
    <div className={pad}>
      {heading}
      {order.length ? (
        <>
          <ProteinLollipop
            className="mt-5"
            variants={order.map((v) => ({
              gene: v.gene,
              hgvs: v.hgvs,
              emphasis: v.key === current?.key,
              note: [v.level?.label ?? "No OncoKB level", v.targetable === null ? null : v.targetable ? "targetable" : "not targetable"].filter(Boolean).join(" · "),
            }))}
          />
          <div className="mt-6 grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
            <div>
              <p id={`${ws.id}-var-label`} className={`border-b ${line} px-3 pb-2 ${label}`}>
                Select a variant
              </p>
              <div role="radiogroup" aria-labelledby={`${ws.id}-var-label`} className="mt-1.5 space-y-0.5">
                {order.map((v, i) => {
                  const on = v.key === current?.key;
                  return (
                    <button
                      key={v.key}
                      ref={(el) => {
                        refs.current[v.key] = el;
                      }}
                      type="button"
                      role="radio"
                      aria-checked={on}
                      tabIndex={on ? 0 : -1}
                      onClick={() => setSelected(v.key)}
                      onKeyDown={(e) => {
                        if (e.key === "ArrowDown" || e.key === "ArrowRight") {
                          e.preventDefault();
                          move(i + 1);
                        } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
                          e.preventDefault();
                          move(i - 1);
                        }
                      }}
                      className={`relative flex min-h-[48px] w-full flex-col justify-center rounded-[6px] px-3 py-1.5 text-left transition-colors duration-100 ${
                        on ? "bg-[#EEE8F5]" : "hover:bg-[#F6F5F8] active:bg-[#EFEDF2]"
                      } ${focus}`}
                    >
                      {on ? <span aria-hidden="true" className="absolute inset-y-2.5 left-0 w-[2px] rounded-full bg-[#69518C]" /> : null}
                      <span className={`text-[15px] font-medium leading-[22px] ${ink}`}>{v.name}</span>
                      <span className={`font-mono text-[12px] leading-[18px] ${muted}`}>{v.hgvs}</span>
                    </button>
                  );
                })}
              </div>
            </div>
            {current ? (
              <div aria-live="polite" className="min-w-0 max-w-[620px]">
                <Fade key={current.key}>
                  <p className={`text-[20px] font-semibold leading-[28px] tracking-[-0.02em] ${ink}`}>{current.name}</p>
                  <p className={`mb-4 text-[14px] ${muted}`}>
                    {current.hgvs} · {ws.tumor}
                  </p>
                  <VariantDetail
                    cancerType={ws.tumor}
                    variant={{
                      gene: current.gene,
                      hgvs: current.hgvs,
                      classification: current.classification,
                      alphamissense_score: current.alphamissense,
                      oncokb_level: current.level?.code ?? null,
                      evidence_lookup_status: current.lookupStatus,
                      is_targetable: current.targetable,
                    }}
                  />
                </Fade>
              </div>
            ) : null}
          </div>
        </>
      ) : (
        <p className={`mt-4 text-[14px] ${muted}`}>No variants with a protein change in this result.</p>
      )}
    </div>
  );
}

const ORDER: GapState[] = ["lookup_failed", "not_recorded", "not_assessed", "not_supplied"];

export function GapsView({ ws, compact = false }: { ws: WsCase; compact?: boolean }) {
  const heading = (
    <ViewHeading label="Known gaps" title={`${ws.gaps.length} items not in this result`} sub="Listed so a missing value isn't mistaken for a negative finding" />
  );
  const row = (g: WsCase["gaps"][number]) => (
    <li key={`${g.item}-${g.scope ?? ""}`} className={`flex items-center justify-between gap-4 border-b ${line} py-2.5 text-[14px]`}>
      <Missing tone={g.state === "not_supplied" ? "neutral" : "amber"}>
        <span className="font-medium">{g.item}</span>
        {g.scope ? <span className={muted}> · {g.scope}</span> : null}
      </Missing>
      <span className={`shrink-0 text-right text-[12.5px] ${g.state === "lookup_failed" ? "font-medium text-[#8A5A1C]" : muted}`}>{compact ? GAP_LABELS[g.state] : g.note}</span>
    </li>
  );
  if (compact) {
    return (
      <div className={pad}>
        {heading}
        <ul className="mt-1 grid max-w-[720px] sm:grid-cols-2 sm:gap-x-8">{ws.gaps.map(row)}</ul>
      </div>
    );
  }
  return (
    <div className={pad}>
      {heading}
      {ORDER.filter((s) => ws.gaps.some((g) => g.state === s)).map((s) => (
        <section key={s} className="mt-5 max-w-[760px]">
          <h4 className={`${label} pb-1`}>
            {GAP_LABELS[s]} <span className="font-mono tabular-nums">{ws.gaps.filter((g) => g.state === s).length}</span>
          </h4>
          <ul className={`border-t ${line}`}>{ws.gaps.filter((g) => g.state === s).map(row)}</ul>
        </section>
      ))}
    </div>
  );
}
