import { cn } from "@/lib/utils";

export type VignetteCandidate = { id: string; name: string; score: number; approval: string; group: string };
export type VignetteVariant = {
  gene: string;
  short: string;
  hgvs: string;
  cancerType: string;
  level: string;
  levelMeaning: string;
  targetable: boolean;
  position: number;
  length: number;
  domain: { label: string; start: number; end: number } | null;
};
export type VignetteEvidence = { drug: string; level: string; levelMeaning: string; sources: string[] };

const card = "rounded-2xl border border-black/5 bg-white text-oo-ink shadow-[0_30px_60px_-20px_rgb(20_10_60/0.45),0_2px_6px_rgb(20_10_60/0.08)]";

export function RankedVignette({ candidates, className }: { candidates: VignetteCandidate[]; className?: string }) {
  const groups = candidates.reduce<{ name: string; items: VignetteCandidate[] }[]>((acc, c) => {
    const last = acc[acc.length - 1];
    if (last && last.name === c.group) last.items.push(c);
    else acc.push({ name: c.group, items: [c] });
    return acc;
  }, []);
  let rank = 0;
  return (
    <div className={cn(card, "overflow-hidden", className)}>
      <div className="flex items-baseline justify-between px-6 pb-3 pt-5">
        <div>
          <div className="text-[12px] font-medium uppercase tracking-[0.08em] text-oo-ink-3">Ranked candidates</div>
          <div className="mt-1 text-[19px] font-semibold tracking-[-0.015em]">KRAS G12C · NSCLC</div>
        </div>
        <span className="hidden font-mono text-[12px] text-oo-ink-3 sm:inline">evidence score</span>
      </div>
      {groups.map((g) => (
        <div key={g.name}>
          <div className="border-y border-oo-line-soft bg-[#F6F4FB] px-6 py-2 text-[12.5px] font-semibold text-oo-hema">{g.name}</div>
          <ul className="divide-y divide-oo-line-soft">
            {g.items.map((c) => {
              rank += 1;
              return (
                <li key={c.id} className="grid grid-cols-[1.25rem_minmax(0,1fr)_3rem] items-center gap-x-3 px-5 py-3.5 sm:grid-cols-[1.5rem_minmax(0,1fr)_7rem_3rem] sm:gap-x-4 sm:px-6">
                  <span className="font-mono text-[13px] text-oo-ink-3">{rank}</span>
                  <span className="min-w-0">
                    <span className="block truncate text-[17px] font-semibold tracking-[-0.01em]">{c.name}</span>
                    <span className="block text-[13px] text-oo-ink-3">{c.approval}</span>
                  </span>
                  <span aria-hidden="true" className="hidden h-2 overflow-hidden rounded-full bg-[#ECE9F5] sm:block">
                    <span className="block h-full rounded-full bg-oo-hema" style={{ width: `${c.score * 100}%` }} />
                  </span>
                  <span className="text-right font-mono text-[15px] tabular-nums">{c.score.toFixed(2)}</span>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}

export function VariantVignette({ variant, className }: { variant: VignetteVariant; className?: string }) {
  const pct = (n: number) => `${(n / variant.length) * 100}%`;
  return (
    <div className={cn(card, "p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[22px] font-semibold tracking-[-0.02em]">
            {variant.gene} <span className="text-oo-eosin">{variant.short}</span>
          </div>
          <div className="mt-0.5 font-mono text-[12px] text-oo-ink-3">
            {variant.hgvs} · {variant.cancerType}
          </div>
        </div>
        <span className="rounded-md bg-oo-ink px-2 py-1 font-mono text-[12px] text-white">{variant.level}</span>
      </div>
      <div className="relative mt-7 h-10" aria-hidden="true">
        <div className="absolute inset-x-0 top-6 h-[3px] rounded-full bg-[#ECE9F5]" />
        {variant.domain ? (
          <div
            className="absolute top-[18px] h-[15px] rounded-sm bg-oo-hema/15 ring-1 ring-inset ring-oo-hema/25"
            style={{ left: pct(variant.domain.start), width: `max(${pct(variant.domain.end - variant.domain.start)}, 10px)` }}
          />
        ) : null}
        <div className="absolute top-0 -translate-x-1/2" style={{ left: pct(variant.position) }}>
          <div className="h-3.5 w-3.5 rounded-full bg-oo-eosin ring-4 ring-oo-eosin/20" />
          <div className="mx-auto h-3 w-[2px] bg-oo-eosin" />
        </div>
      </div>
      <div className="mt-1 flex justify-between font-mono text-[11px] text-oo-ink-3">
        <span>1</span>
        {variant.domain ? (
          <span>
            {variant.domain.label} {variant.domain.start}–{variant.domain.end}
          </span>
        ) : null}
        <span>{variant.length} aa</span>
      </div>
      <div className="mt-4 border-t border-oo-line-soft pt-3 text-[13px] text-oo-ink-2">
        {variant.targetable ? "Targetable, as reported" : "Not targetable, as reported"}
      </div>
    </div>
  );
}

export function EvidenceVignette({ evidence, className }: { evidence: VignetteEvidence; className?: string }) {
  return (
    <div className={cn(card, "p-5", className)}>
      <div className="text-[12px] font-medium uppercase tracking-[0.08em] text-oo-ink-3">Evidence for {evidence.drug}</div>
      <div className="mt-2 text-[18px] font-semibold tracking-[-0.015em]">{evidence.level}</div>
      <p className="mt-1.5 text-[14px] leading-relaxed text-oo-ink-2">{evidence.levelMeaning}</p>
      <div className="mt-4 flex flex-wrap gap-1.5">
        {evidence.sources.map((s) => (
          <span key={s} className="rounded-md border border-oo-line bg-[#FAF9FD] px-2 py-1 font-mono text-[12px] text-oo-ink-2">
            {s}
          </span>
        ))}
      </div>
      <div className="mt-4 flex items-center gap-2 border-t border-oo-line-soft pt-3 text-[12.5px] text-oo-ink-3">
        <span className="h-1.5 w-1.5 rounded-full bg-oo-status-analyzing-fg" aria-hidden="true" />
        Awaiting oncologist review
      </div>
    </div>
  );
}
