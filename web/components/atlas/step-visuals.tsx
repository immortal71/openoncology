import { Backdrop, WindowBar, type ShotCandidate } from "@/components/atlas/product-shot";

export type VcfExcerpt = { title: string; columns: string[]; rows: string[][]; highlight: number };

const surface = "shadow-[0_0_0_1px_rgb(34_30_43/0.07),0_1px_2px_rgb(34_30_43/0.04),0_16px_32px_-20px_rgb(34_30_43/0.18)]";
const muted = "text-[#6B6573]";

function Frame({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className={`overflow-hidden rounded-[10px] bg-white ${surface}`}>
      <WindowBar title={title} />
      {children}
    </div>
  );
}

function InputVisual({ vcf }: { vcf: VcfExcerpt }) {
  return (
    <Frame title={vcf.title}>
      <div className="px-3 py-3">
        <table className="w-full border-collapse font-mono text-[12.5px]">
          <thead>
            <tr className={`text-left ${muted}`}>
              {vcf.columns.map((c) => (
                <th key={c} className="px-2 pb-2 font-normal">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {vcf.rows.map((r, i) => {
              const on = i === vcf.highlight;
              return (
                <tr key={r.join("-")} className={on ? "bg-[#EEE9F5] text-[#221E2B]" : muted}>
                  {r.map((v, j) => (
                    <td key={j} className={`px-2 py-2.5 ${j === 0 ? "rounded-l-[6px]" : ""} ${j === r.length - 1 ? "rounded-r-[6px]" : ""}`}>
                      {v}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Frame>
  );
}

function OutputVisual({ candidates, more, group }: { candidates: ShotCandidate[]; more: string; group: string }) {
  return (
    <Frame title="Ranked candidates">
      <div className="px-3 py-3">
        <p className={`flex justify-between px-3 pb-1.5 text-[12.5px] ${muted}`}>
          <span>{group}</span>
          <span>Score</span>
        </p>
        <ul>
          {candidates.map((c, i) => (
            <li key={c.name} className={`flex min-h-[46px] items-center gap-3 rounded-[6px] px-3 ${i === 0 ? "bg-[#EEE9F5]" : ""}`}>
              <span className={`w-3 font-mono text-[12px] ${i === 0 ? "text-[#584493]" : muted}`}>{i + 1}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-[14.5px] font-semibold text-[#221E2B]">{c.name}</span>
                <span className={`block truncate text-[12.5px] ${muted}`}>{c.mechanism}</span>
              </span>
              <span className="font-mono text-[12.5px] text-[#221E2B]">{c.score.toFixed(2)}</span>
            </li>
          ))}
        </ul>
        <p className={`mt-2 px-3 text-[12.5px] ${muted}`}>{more}</p>
      </div>
    </Frame>
  );
}

function ReviewVisual({ checks }: { checks: { k: string; v: string }[] }) {
  return (
    <Frame title="Before any treatment decision">
      <ul className="px-4 py-1">
        {checks.map((c) => (
          <li key={c.k} className="flex gap-3 border-b border-[#EEECEF] py-3 last:border-b-0">
            <span aria-hidden="true" className="mt-[3px] h-3.5 w-3.5 shrink-0 rounded-full border-[1.5px] border-[#C9C3CF]" />
            <span>
              <span className="block text-[14px] font-medium text-[#221E2B]">{c.k}</span>
              <span className={`block text-[12.5px] ${muted}`}>{c.v}</span>
            </span>
          </li>
        ))}
      </ul>
    </Frame>
  );
}

export type StepVisualData = {
  vcf: VcfExcerpt;
  candidates: ShotCandidate[];
  more: string;
  group: string;
  checks: { k: string; v: string }[];
};

export function StepVisual({ kind, caption, value, data, className }: { kind: "variant" | "evidence" | "review"; caption: string; value: string; data: StepVisualData; className?: string }) {
  return (
    <Backdrop className={`flex flex-col justify-center gap-5 p-5 sm:p-8 ${className ?? ""}`}>
      <div aria-hidden="true">
        {kind === "variant" ? <InputVisual vcf={data.vcf} /> : null}
        {kind === "evidence" ? <OutputVisual candidates={data.candidates} more={data.more} group={data.group} /> : null}
        {kind === "review" ? <ReviewVisual checks={data.checks} /> : null}
      </div>
      <div className="flex items-baseline gap-3 px-1">
        <span className="text-[12.5px] font-semibold uppercase tracking-[0.06em] text-[#615B69]">{caption}</span>
        <span className="text-[15px] font-semibold tracking-[-0.01em] text-[#221E2B]">{value}</span>
      </div>
    </Backdrop>
  );
}
