import { Backdrop, WindowBar, type ShotCandidate } from "@/components/atlas/product-shot";

export type VcfExcerpt = { title: string; columns: string[]; rows: string[][]; highlight: number };

const lift = "shadow-[0_1px_2px_rgb(34_30_43/0.06),0_30px_60px_-28px_rgb(34_30_43/0.32)]";
const mono = "font-mono uppercase tracking-[0.12em]";

function Frame({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`overflow-hidden rounded-[12px] bg-white ring-1 ring-[#221E2B]/[0.08] ${lift} ${className ?? ""}`}>
      <WindowBar title={title} />
      {children}
    </div>
  );
}

function Plate({ caption, value }: { caption: string; value: string }) {
  return (
    <div className={`absolute bottom-4 left-4 rounded-[10px] bg-white px-4 py-3 ring-1 ring-[#221E2B]/[0.06] ${lift}`}>
      <p className={`text-[10.5px] text-[#615B69] ${mono}`}>{caption}</p>
      <p className="mt-0.5 text-[15px] font-semibold tracking-[-0.01em] text-[#221E2B]">{value}</p>
    </div>
  );
}

function InputVisual({ vcf }: { vcf: VcfExcerpt }) {
  return (
    <Frame title={vcf.title} className="absolute left-5 right-[-24px] top-6 sm:left-8 sm:top-[15%]">
      <div className="overflow-hidden px-4 py-4">
        <table className="w-full border-collapse font-mono text-[12.5px]">
          <thead>
            <tr className="text-left text-[#8A8492]">
              {vcf.columns.map((c) => (
                <th key={c} className="pb-2 pr-4 font-normal">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {vcf.rows.map((r, i) => {
              const on = i === vcf.highlight;
              return (
                <tr key={r.join("-")} className={on ? "bg-[#EEE9F5] text-[#221E2B]" : "text-[#8A8492]"}>
                  {r.map((v, j) => (
                    <td key={j} className={`py-2 pr-4 ${j === 0 ? "pl-2" : ""} ${on && j === 0 ? "shadow-[inset_3px_0_0_#584493]" : ""}`}>
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
    <Frame title="Ranked candidates" className="absolute left-5 right-5 top-6 sm:left-8 sm:right-[-24px] sm:top-[15%]">
      <div className="px-5 py-4">
        <p className={`text-[10.5px] text-[#8A8492] ${mono}`}>{group}</p>
        <ul className="mt-2">
          {candidates.map((c, i) => (
            <li key={c.name} className={`relative flex items-center gap-4 rounded-[7px] px-3 py-3 ${i === 0 ? "bg-[#EEE9F5]" : ""}`}>
              {i === 0 ? <span className="absolute inset-y-2.5 left-0 w-[3px] rounded-full bg-[#584493]" /> : null}
              <span className="w-4 font-mono text-[12px] text-[#8A8492]">{i + 1}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-[15px] font-semibold text-[#221E2B]">{c.name}</span>
                <span className="block truncate text-[12.5px] text-[#615B69]">{c.mechanism.split(" — ")[0]}</span>
              </span>
              <span className="hidden h-1 w-16 overflow-hidden rounded-full bg-[#EFECF1] sm:block">
                <span className="block h-full rounded-full bg-[#584493]/45" style={{ width: `${c.score * 100}%` }} />
              </span>
              <span className="font-mono text-[11.5px] text-[#8A8492]">{c.score.toFixed(2)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 border-t border-[#EFECF1] px-3 pt-2.5 text-[12.5px] text-[#8A8492]">{more}</p>
        <p className="mt-3 px-3 text-[11.5px] text-[#8A8492]">Score orders candidates within this case. It is not a response probability.</p>
      </div>
    </Frame>
  );
}

function ReviewVisual({ checks }: { checks: { k: string; v: string }[] }) {
  return (
    <Frame title="Before any treatment decision" className="absolute left-5 right-5 top-6 sm:left-8 sm:right-[-24px] sm:top-[15%]">
      <ul className="px-5 py-3">
        {checks.map((c) => (
          <li key={c.k} className="flex gap-3 border-b border-[#EFECF1] py-3 last:border-b-0">
            <span aria-hidden="true" className="mt-[3px] h-3.5 w-3.5 shrink-0 rounded-full border-[1.5px] border-[#C9C3CF]" />
            <span>
              <span className="block text-[14px] font-medium text-[#221E2B]">{c.k}</span>
              <span className="block text-[12.5px] text-[#615B69]">{c.v}</span>
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
    <Backdrop className={className}>
      <div aria-hidden="true">
        {kind === "variant" ? <InputVisual vcf={data.vcf} /> : null}
        {kind === "evidence" ? <OutputVisual candidates={data.candidates} more={data.more} group={data.group} /> : null}
        {kind === "review" ? <ReviewVisual checks={data.checks} /> : null}
      </div>
      <Plate caption={caption} value={value} />
    </Backdrop>
  );
}
