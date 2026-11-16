import { Bar } from "@/components/workspace/parts";
import type { WsCandidate } from "@/lib/workspace";

export type VcfExcerpt = { title: string; columns: string[]; rows: string[][]; highlight: number };

const surface = "border border-[#E2DEE6] shadow-[0_8px_24px_rgba(36,33,43,0.06)]";
const muted = "text-[#625E68]";
const label = "text-[11.5px] font-medium uppercase tracking-[0.06em] text-[#625E68]";

function Frame({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className={`overflow-hidden rounded-[10px] bg-white ${surface}`}>
      <Bar title={title} />
      {children}
    </div>
  );
}

function InputVisual({ vcf }: { vcf: VcfExcerpt }) {
  return (
    <Frame title={vcf.title}>
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
                <tr key={r.join("-")} className={on ? "bg-[#EEE8F5] text-[#24212B]" : muted}>
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
      <p className={`border-t border-[#E2DEE6] px-5 py-3 text-[13px] ${muted}`}>Selected variant carries into the candidate search.</p>
    </Frame>
  );
}

function OutputVisual({ candidates, more, group, evidence }: { candidates: WsCandidate[]; more: string; group: string; evidence: string }) {
  return (
    <Frame title="Ranked candidates">
      <div className="px-3 pb-3 pt-2">
        <p className={`flex justify-between px-3 pb-1.5 pt-1 ${label}`}>
          <span>{group}</span>
          <span>Score</span>
        </p>
        <ul>
          {candidates.map((c, i) => (
            <li key={c.name} className={`relative grid min-h-[44px] grid-cols-[16px_minmax(0,1fr)_auto] items-center gap-3 rounded-[6px] px-3 ${i === 0 ? "bg-[#EEE8F5]" : ""}`}>
              {i === 0 ? <span aria-hidden="true" className="absolute inset-y-2 left-0 w-[2px] rounded-full bg-[#69518C]" /> : null}
              <span className={`font-mono text-[12px] ${i === 0 ? "text-[#69518C]" : "text-[#8F899A]"}`}>{i + 1}</span>
              <span className="truncate text-[14.5px] font-medium text-[#24212B]">{c.name}</span>
              <span className="font-mono text-[12.5px] text-[#24212B]">{c.score !== null ? c.score.toFixed(2) : "–"}</span>
            </li>
          ))}
        </ul>
        <div className="relative ml-[22px] mt-1 border-l-[1.5px] border-[#69518C] pb-0.5 pl-4 pt-2.5">
          <span aria-hidden="true" className="absolute -left-[3.5px] bottom-0 h-[5.5px] w-[5.5px] rounded-full bg-[#69518C]" />
          <p className={label}>Why rank 1</p>
          <p className="mt-0.5 text-[13.5px] text-[#24212B]">{evidence}</p>
        </div>
        <p className={`mt-3 px-3 text-[12.5px] ${muted}`}>{more}</p>
      </div>
    </Frame>
  );
}

function ReviewVisual({ checks }: { checks: { k: string; v: string; missing?: boolean }[] }) {
  return (
    <Frame title="Before any treatment decision">
      <dl className="px-5 py-1">
        {checks.map((c) => (
          <div key={c.k} className="grid grid-cols-[96px_minmax(0,1fr)] gap-3 border-b sm:grid-cols-[150px_minmax(0,1fr)] sm:gap-4 border-[#E2DEE6] py-3 last:border-b-0">
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

export type StepVisualData = {
  vcf: VcfExcerpt;
  candidates: WsCandidate[];
  more: string;
  group: string;
  evidence: string;
  checks: { k: string; v: string; missing?: boolean }[];
};

function Backdrop({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={`relative overflow-hidden rounded-[16px] bg-[#EFECE6] ${className ?? ""}`}>{children}</div>;
}

export function StepVisual({ kind, caption, value, data, className }: { kind: "variant" | "evidence" | "review"; caption: string; value: string; data: StepVisualData; className?: string }) {
  return (
    <div className={className}>
      <Backdrop className="h-[340px] p-6">
        <div aria-hidden="true">
          {kind === "variant" ? <InputVisual vcf={data.vcf} /> : null}
          {kind === "evidence" ? <OutputVisual candidates={data.candidates} more={data.more} group={data.group} evidence={data.evidence} /> : null}
          {kind === "review" ? <ReviewVisual checks={data.checks} /> : null}
        </div>
      </Backdrop>
      <p className="mt-3 flex items-baseline gap-3 px-1">
        <span className={label}>{caption}</span>
        <span className="text-[15px] font-medium text-[#24212B]">{value}</span>
      </p>
    </div>
  );
}
