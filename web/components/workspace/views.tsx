"use client";

import { useRef, useState } from "react";
import { ArrowUpRight, ChevronRight, Database, FileSearch } from "lucide-react";
import { parseProteinChange, PROTEIN_REFERENCE } from "@/lib/protein";
import { GAP_LABELS, sourceRow, type GapState, type WsCandidate, type WsCase, type WsVariant } from "@/lib/workspace";
import { Fade, focus, ink, label, line, linkText, Missing, muted, Th, ViewHeading } from "./parts";


function LookupDetail({ v, cancerType }: { v: WsVariant; cancerType: string }) {
  const l = v.lookup;
  if (l.kind === "level")
    return (
      <>
        <p className={`text-[16px] font-medium leading-[24px] ${ink}`}>{l.level.label}</p>
        <p className={`mt-0.5 max-w-[56ch] text-[14px] leading-[21px] ${muted}`}>{l.level.meaning}</p>
        <p className={`mt-1 text-[12.5px] ${muted}`}>
          Tumour type in this result: {cancerType}. {l.source ? `Source: ${l.source}.` : "Lookup source not recorded for this result."}
        </p>
      </>
    );
  if (l.kind === "checked_none") return <p className={`text-[14px] ${ink}`}>Checked, no OncoKB level (source: {l.source})</p>;
  if (l.kind === "not_attempted") return <p className={`text-[14px] ${muted}`}>Not checked: no protein change to look up</p>;
  if (l.kind === "unavailable") return <p className="text-[14px] font-medium text-[#9E4A3A]">Lookup failed. Absence of a level here means nothing.</p>;
  return <p className={`text-[14px] ${muted}`}>No level, and the lookup status was not recorded</p>;
}

const pad = "p-5 lg:px-8 lg:py-5";


const sectionTitle = "text-[22px] font-semibold leading-tight tracking-[-0.035em] text-[#24212B]";
const body = "text-[13px] leading-[1.55] text-[#625E68]";
const small = "text-[12px] font-medium text-[#625E68]";
const pagePad = "px-4 py-5 sm:px-7 sm:py-6 lg:px-8";

function ExternalLookup({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className={`inline-flex min-h-10 items-center gap-1.5 text-[13px] ${linkText}`}>
      {children}<ArrowUpRight size={13} aria-hidden="true" /><span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}

function ProteinAnnotation({ v }: { v: WsVariant }) {
  const change = parseProteinChange(v.hgvs);
  const reference = PROTEIN_REFERENCE[v.gene.toUpperCase()];
  if (!change || !reference || change.position < 1 || change.position > reference.length)
    return <p className={body}>Protein position unavailable for this alteration.</p>;

  const domain = reference.domains.find(d => d.start <= change.position && change.position <= d.end);
  return (
    <dl className="my-5 flex flex-wrap gap-x-8 gap-y-3 text-[13px]">
      <div><dt className={small}>Residue</dt><dd className="mt-1 font-mono">{change.position} / {reference.length}</dd></div>
      {domain && <div><dt className={small}>Protein domain</dt><dd className="mt-1">{domain.label} ({domain.start}–{domain.end})</dd></div>}
      <div><dt className={small}>Reference</dt><dd className="mt-1 font-mono">{reference.source}</dd></div>
    </dl>
  );
}

function VariantInspector({ v, ws }: { v: WsVariant; ws: WsCase }) {
  const change = parseProteinChange(v.hgvs);
  const absent = ws.gaps.filter(g => g.state === "not_supplied" && (!g.scope || g.scope === v.name));
  return (
    <article className={`min-w-0 ${pagePad}`}>
      <h3 className={sectionTitle}>{v.name}</h3>
      <p className="mt-1 font-mono text-[12px] text-[#625E68]">{v.hgvs}</p>

      <ProteinAnnotation v={v} />
      <dl className="divide-y divide-[#E7E3E8] border-y border-[#E7E3E8] text-[13px]">
        <div className="grid gap-2 py-3 sm:grid-cols-[128px_minmax(0,1fr)]"><dt className={small}>Evidence lookup</dt><dd><LookupDetail v={v} cancerType={ws.tumor} /></dd></div>
        <div className="grid gap-2 py-3 sm:grid-cols-[128px_minmax(0,1fr)]"><dt className={small}>Targetability</dt><dd>{v.targetable === null ? "Not recorded" : v.targetable ? "Targetable in this result" : "Not targetable in this result"}</dd></div>

        <div className="grid gap-2 py-3 sm:grid-cols-[128px_minmax(0,1fr)]"><dt className={small}>AlphaMissense</dt><dd>{v.prediction ?? "Not scored in this result"}{v.alphamissense !== null && <span className="ml-2 font-mono">{v.alphamissense.toFixed(2)}</span>}{v.prediction && <p className={body}>Computational prediction</p>}</dd></div>
        {absent.length > 0 && <div className="grid gap-2 py-3 sm:grid-cols-[128px_minmax(0,1fr)]"><dt className={small}>Not supplied</dt><dd className={body}>{absent.map(g => g.item).join(", ")}</dd></div>}
      </dl>
      <div className="mt-2 flex flex-wrap gap-x-5">
        {change && <ExternalLookup href={`https://www.oncokb.org/gene/${encodeURIComponent(v.gene)}/${encodeURIComponent(change.short)}`}>Search OncoKB</ExternalLookup>}
        <ExternalLookup href={`https://www.ncbi.nlm.nih.gov/clinvar/?term=${encodeURIComponent(`${v.gene}[gene] ${v.hgvs}`)}`}>Search ClinVar</ExternalLookup>
      </div>
    </article>
  );
}

export function SourcesView({ ws, c, compact = false }: { ws: WsCase; c: WsCandidate; compact?: boolean }) {
  if (compact) return <CompactSources ws={ws} c={c} />;
  return (
    <section className={pagePad}>
      <h2 className={sectionTitle}>Sources for {c.name}</h2>
      <p className={`mt-1 ${body}`}>{c.sources.length} listed providers · {ws.tumor}</p>
      {c.sources.length ? (
        <div className="mt-6">
          <div className={`hidden border-b border-[#DCD7DF] pb-2 md:grid md:grid-cols-[1.15fr_1.1fr_1fr_1fr] md:gap-4 ${small}`}><span>Provider</span><span>Evidence type</span><span>Recorded value</span><span>Exact record</span></div>
          <ul className="divide-y divide-[#E2DEE6] border-y border-[#E2DEE6] md:border-t-0">
            {c.sources.map(source => {
              const row = sourceRow(source, c, null);
              return (
                <li key={source} className="grid min-w-0 gap-x-4 gap-y-1 py-4 text-[13px] md:grid-cols-[1.15fr_1.1fr_1fr_1fr] md:items-baseline">
                  <span className="flex items-center gap-2.5 text-[15px] font-semibold"><Database size={15} className="text-[#776C84]" aria-hidden="true" />{row.name}</span>
                  <span className={body}>{row.provides}</span>
                  <span className="mt-2 font-mono text-[13px] md:mt-0"><span className="font-sans text-[#625E68] md:hidden">Recorded value · </span>{row.value}</span>
                  <div><span className="text-[#625E68]"><span className="md:hidden">Exact record · </span>Not stored</span>
                    {row.lookup && <div><ExternalLookup href={row.lookup.href}>{row.lookup.label}</ExternalLookup></div>}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : <p className={`my-6 ${body}`}>No provider was recorded for this candidate.</p>}
      <div className="mt-5 flex max-w-[76ch] items-start gap-3 rounded-md border border-[#E0DCE3] bg-[#FAF9F7] px-4 py-3">
        <FileSearch size={16} aria-hidden="true" className="mt-0.5 shrink-0 text-[#776C84]" />
        <div><h3 className="text-[13px] font-semibold">Citation availability</h3><p className={`mt-1 ${body}`}>The result records provider names. The original evidence records and citations were not saved with this candidate.</p></div>
      </div>
      {c.hidden.length > 0 && <details className="mt-4 max-w-[76ch] text-[13px]"><summary className={`cursor-pointer py-2 font-medium ${focus}`}>Other scoring inputs ({c.hidden.length})</summary><ul className="divide-y divide-[#E2DEE6]">{c.hidden.map(h => <li className="flex justify-between gap-3 py-2" key={h.name}><span>{h.name}</span><span className={muted}>{h.reason}</span></li>)}</ul></details>}
    </section>
  );
}

function CompactSources({ ws, c }: { ws: WsCase; c: WsCandidate }) {
  return (
    <div className={pad}>
      <Fade key={c.id}>
        <ViewHeading label="Evidence sources" title={`For ${c.name}`} sub={`${ws.title} · what each provider gives in this result`} />
        <table className="w-full max-w-[680px] border-collapse lg:table-fixed">
          <colgroup>
            <col className="lg:w-[170px]" />
            <col className="lg:w-[230px]" />
            <col />
          </colgroup>
          <thead className={`border-b ${line}`}>
            <tr>
              <Th>Source</Th>
              <Th className="hidden sm:table-cell">Provides</Th>
              <Th>In this result</Th>
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
                </tr>
              );
            })}
            <tr className={`border-b ${line} text-[14px]`}>
                <td className={`py-2.5 pr-4 font-semibold ${ink}`}>Exact lookup record</td>
                <td className={`hidden py-2.5 pr-4 sm:table-cell ${muted}`}>Citation behind the level</td>
                <td className="py-2.5">
                  <Missing>Not stored</Missing>
                </td>
            </tr>
          </tbody>
        </table>
        <p className={`mt-4 text-[13px] leading-snug ${muted}`}>
          A provider name is not a stored citation.
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


  const current = ws.variants.find(v => v.key === selected) ?? ws.variants[0];
  return (
    <div className="grid min-w-0 lg:grid-cols-[340px_minmax(0,1fr)]">
      <section className="min-w-0 border-b border-[#DCD7DF] bg-[#FCFBF9] p-4 sm:p-6 lg:border-b-0 lg:border-r">
        <h2 className="text-[17px] font-semibold tracking-[-0.025em]">Tumor variants</h2>
        <p className={`mb-4 mt-1 ${body}`}>{ws.variants.length} protein alterations in this result</p>
        {ws.variants.length > 0 && <div role="radiogroup" aria-label="Tumor variants" className="space-y-2">
          {ws.variants.map((v, i) => {
            const active = current?.key === v.key;
            return (
              <button key={v.key} ref={el => { refs.current[v.key] = el; }} role="radio" type="button" aria-checked={active}
                tabIndex={active ? 0 : -1} onClick={() => setSelected(v.key)} onKeyDown={event => {
                  const delta = { ArrowUp: -1, ArrowLeft: -1, ArrowDown: 1, ArrowRight: 1 }[event.key];
                  if (!delta) return;
                  event.preventDefault();
                  const next = ws.variants[(i + delta + ws.variants.length) % ws.variants.length];
                  setSelected(next.key);
                  refs.current[next.key]?.focus();
                }}
                className={`flex w-full items-center justify-between gap-2 rounded-md border p-3 text-left ${focus} ${active ? "border-[#C6B8D6] bg-[#F0EBF5]" : "border-[#E2DEE6] bg-white hover:border-[#C6B8D6]"}`}>
                <span className="min-w-0">
                  <span className="block text-[15px] font-semibold">{v.name}</span>
                  <span className="mt-0.5 block break-all font-mono text-[12px] text-[#625E68]">{v.hgvs}</span>
                  <span className="mt-2 block text-[12px] text-[#544A62]">{v.level?.label ?? "See lookup status"} · {v.targetable === null ? "Targetability unrecorded" : v.targetable ? "Targetable" : "Not targetable"}</span>
                </span>
                <ChevronRight aria-hidden="true" className="shrink-0 text-[#776C84]" size={15} />
              </button>
            );
          })}
        </div>}
      </section>
      {current ? <VariantInspector v={current} ws={ws} /> : <p className={`${pagePad} ${body}`}>No protein alteration was supplied for review.</p>}
    </div>
  );
}

const ORDER: GapState[] = ["lookup_failed", "not_recorded", "not_assessed", "not_supplied"];

export function GapsView({ ws, compact = false }: { ws: WsCase; compact?: boolean }) {
  const [filter, setFilter] = useState<GapState | null>(null);
  const heading = (
    <ViewHeading label="Known gaps" title={`${ws.gaps.length} items not in this result`} sub="Listed so a missing value isn't mistaken for a negative finding" />
  );
  const row = (g: WsCase["gaps"][number]) => (
    <li key={`${g.item}-${g.scope ?? ""}`} className={`flex items-center justify-between gap-4 border-b ${line} py-2.5 text-[14px]`}>
      <Missing tone={g.state === "not_supplied" ? "neutral" : "amber"}>
        <span className="font-medium">{g.item}</span>
        {g.scope ? <span className={muted}> · {g.scope}</span> : null}
      </Missing>
      <span className={`shrink-0 text-right text-[12.5px] ${g.state === "lookup_failed" ? "font-medium text-[#8A5A1C]" : muted}`}>{GAP_LABELS[g.state]}</span>
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

  const groups = ORDER.map(state => ({ state, items: ws.gaps.filter(g => g.state === state) })).filter(group => group.items.length > 0);
  const visible = filter ? groups.filter(g => g.state === filter) : groups;
  return (
    <section className={pagePad}>
      <h2 className={sectionTitle}>Evidence gaps</h2>
      <p className={`mt-1 ${body}`}>{ws.gaps.length} missing or unavailable fields in this result</p>
      <div role="group" aria-label="Filter gaps by status" className="my-4 flex flex-wrap gap-1.5">
        {[{ state: null, title: "All", count: ws.gaps.length }, ...groups.map(g => ({ state: g.state, title: GAP_LABELS[g.state], count: g.items.length }))].map(option => (
          <button key={option.state ?? "all"} type="button" aria-pressed={filter === option.state} onClick={() => setFilter(option.state)}
            className={`flex min-h-9 items-center gap-2 rounded-md border px-3 text-[12px] ${focus} ${filter === option.state ? "border-[#BCAACC] bg-[#F0EBF5] text-[#4A3870]" : "border-[#DED9DF] bg-white text-[#625E68] hover:bg-[#FAF9F7]"}`}>
            {option.title}<span className="font-mono text-[11px]">{option.count}</span>
          </button>
        ))}
      </div>
      <div className="divide-y divide-[#E2DEE6] border-t border-[#DCD7DF]">
        {visible.map(group => (
          <section key={group.state} className="grid gap-x-5 py-4 sm:grid-cols-[136px_minmax(0,1fr)]">
            <h3 className={`mb-2 flex items-baseline gap-2 text-[13px] font-semibold ${group.state === "lookup_failed" ? "text-[#855B18]" : ink}`}>{GAP_LABELS[group.state]}<span className="font-mono text-[11px] font-normal text-[#625E68]">{group.items.length}</span></h3>
            <ul className="divide-y divide-[#EBE8EC]">
              {group.items.map(g => <li key={`${g.item}-${g.scope}`} className="grid gap-x-5 gap-y-1 py-2.5 first:pt-0 last:pb-0 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
                <div><span className="block text-[13px] font-medium">{g.item}</span><span className="font-mono text-[11px] text-[#625E68]">{g.scope ?? "Case"}</span></div>
                <p className={body}>{g.note}</p>
              </li>)}
            </ul>
          </section>
        ))}
      </div>
    </section>
  );
}
