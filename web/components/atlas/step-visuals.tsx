import { Bar } from "@/components/workspace/parts";
import type { WsCandidate } from "@/lib/workspace";

export type VcfExcerpt = { title: string; columns: string[]; rows: string[][]; highlight: number };

const surface = "border border-[#E2DEE6] shadow-[0_8px_24px_rgba(36,33,43,0.06)]";
const muted = "text-[#625E68]";
const label = "text-[12px] font-medium uppercase tracking-[0.06em] text-[#625E68]";

function Frame({ title, children, bare = false }: { title: string; children: React.ReactNode; bare?: boolean }) {
  if (bare) return <div className="h-full">{children}</div>;
  return (
    <div className={`h-full overflow-hidden rounded-[10px] bg-white ${surface}`}>
      <Bar title={title} />
      {children}
    </div>
  );
}

function InputVisual({ vcf, bare }: { vcf: VcfExcerpt; bare?: boolean }) {
  return (
    <Frame title={vcf.title} bare={bare}>
      <div className="px-3 py-2">
        <table className="w-full border-collapse font-mono text-[12.5px]">
          <thead>
            <tr className={`text-left ${muted}`}>
              {vcf.columns.map((c) => (
                <th key={c} className="px-2 pb-2 pt-1 font-normal">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {vcf.rows.map((r, i) => {
              const on = i === vcf.highlight;
              return (
                <tr key={r.join("-")} data-carry={on ? "0" : undefined} data-spine-dock={on && bare ? "" : undefined} className={on ? "bg-[#EEE8F5] font-medium text-[#24212B]" : muted}>
                  {r.map((v, j) => (
                    <td key={j} className={`relative px-2 py-2.5 ${j === 0 ? "rounded-l-[6px]" : ""} ${j === r.length - 1 ? "rounded-r-[6px]" : ""}`}>
                      {on && j === 0 ? <span aria-hidden="true" className="absolute inset-y-2 left-0 w-[2px] rounded-full bg-[#69518C]" /> : null}
                      {v}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className={`text-[13px] ${muted} ${bare ? "px-3 pt-3" : "border-t border-[#E2DEE6] px-5 py-3"}`}>Selected variant carries into the candidate search.</p>
    </Frame>
  );
}

function OutputVisual({ candidates, more, group, evidence, variant, bare }: { candidates: WsCandidate[]; more: string; group: string; evidence: string; variant: string; bare?: boolean }) {
  return (
    <Frame title={`Ranked candidates · ${variant}`} bare={bare}>
      <div className="px-3 pb-3 pt-2">
        <p className={`flex justify-between px-3 pb-1.5 pt-1 ${label}`}>
          <span>{group}</span>
          <span>Score</span>
        </p>
        <ul>
          {candidates.map((c, i) => (
            <li key={c.name} data-carry={i === 0 ? "1" : undefined} className={`relative grid min-h-[44px] grid-cols-[16px_minmax(0,1fr)_auto] items-center gap-3 rounded-[6px] px-3 ${i === 0 ? "bg-[#EEE8F5]" : ""}`}>
              {i === 0 ? <span aria-hidden="true" className="absolute inset-y-2 left-0 w-[2px] rounded-full bg-[#69518C]" /> : null}
              <span className={`font-mono text-[12px] ${i === 0 ? "text-[#69518C]" : "text-[#625E68]"}`}>{i + 1}</span>
              <span className="truncate text-[14.5px] font-medium text-[#24212B]">{c.name}</span>
              <span className="font-mono text-[13px] tabular-nums text-[#24212B]">{c.score !== null ? c.score.toFixed(2) : "–"}</span>
            </li>
          ))}
        </ul>
        <div className={`relative ml-[22px] mt-1 border-l-[1.5px] border-[#69518C] pb-0.5 pl-4 pt-2.5 ${bare ? "hidden" : ""}`}>
          <span aria-hidden="true" className="absolute -left-[3.5px] bottom-0 h-[5.5px] w-[5.5px] rounded-full bg-[#69518C]" />
          <p className={label}>Why rank 1</p>
          <p className="mt-0.5 text-[13.5px] text-[#24212B]">{evidence}</p>
        </div>
        <p className={`mt-3 px-3 text-[13px] ${muted}`}>{bare ? `${candidates.length} shown · ${more}` : more}</p>
      </div>
    </Frame>
  );
}

function ReviewVisual({ checks, variant, bare }: { checks: Check[]; variant: string; bare?: boolean }) {
  return (
    <Frame title={`Handed to clinical review · ${variant}`} bare={bare}>
      <dl className="px-3 py-2">
        {checks.map((c) => (
          <div
            key={c.k}
            data-carry={c.focus ? "2" : undefined}
            className={`relative grid grid-cols-[96px_minmax(0,1fr)] gap-3 rounded-[6px] px-2 py-2.5 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-4 ${c.focus ? "bg-[#EEE8F5]" : "border-b border-[#E2DEE6] last:border-b-0"}`}
          >
            {c.focus ? <span aria-hidden="true" className="absolute inset-y-2 left-0 w-[2px] rounded-full bg-[#69518C]" /> : null}
            <dt className="text-[13px] text-[#625E68]">{c.k}</dt>
            <dd className="flex items-start gap-2 text-[13.5px] text-[#24212B]">
              {c.missing ? <span aria-hidden="true" className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#AD7629]" /> : null}
              {c.v}
            </dd>
          </div>
        ))}
      </dl>
    </Frame>
  );
}

type Check = { k: string; v: string; missing?: boolean; focus?: boolean };

export type StepVisualData = {
  variant: string;
  vcf: VcfExcerpt;
  candidates: WsCandidate[];
  more: string;
  group: string;
  evidence: string;
  checks: Check[];
};

export type StepKind = "variant" | "evidence" | "review";

function Backdrop({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={`relative overflow-hidden rounded-[16px] bg-[#EFECE6] ${className ?? ""}`}>{children}</div>;
}

export function StepContent({ kind, data, bare = false }: { kind: StepKind; data: StepVisualData; bare?: boolean }) {
  return (
    <div aria-hidden="true" className="h-full">
      {kind === "variant" ? <InputVisual vcf={data.vcf} bare={bare} /> : null}
      {kind === "evidence" ? <OutputVisual candidates={data.candidates} more={data.more} group={data.group} evidence={data.evidence} variant={data.variant} bare={bare} /> : null}
      {kind === "review" ? <ReviewVisual checks={data.checks} variant={data.variant} bare={bare} /> : null}
    </div>
  );
}

export function StepStage({ caption, value, children, className }: { caption: string; value: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={className}>
      <Backdrop className="flex min-h-[300px] flex-col p-5 sm:p-6 lg:h-[380px]">
        <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-1 pb-4">
          <span className={label}>{caption}</span>
          <span className="text-[15px] font-medium text-[#24212B]">{value}</span>
        </p>
        <div className="flex min-h-0 flex-1 items-center">
          <div className="w-full">{children}</div>
        </div>
      </Backdrop>
    </div>
  );
}

export function StepVisual({ kind, caption, value, data, className }: { kind: StepKind; caption: string; value: string; data: StepVisualData; className?: string }) {
  return (
    <StepStage caption={caption} value={value} className={className}>
      <StepContent kind={kind} data={data} />
    </StepStage>
  );
}
