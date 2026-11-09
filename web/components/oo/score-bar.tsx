import { cn } from "@/lib/utils";

export function ScoreBar({ score, className }: { score: number | null | undefined; className?: string }) {
  if (score == null || Number.isNaN(score)) {
    return (
      <span className={cn("font-mono text-[13px] text-oo-ink-3", className)}>
        <span aria-hidden="true">—</span>
        <span className="sr-only">No score</span>
      </span>
    );
  }
  const clamped = Math.min(1, Math.max(0, score));
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <span aria-hidden="true" className="h-1.5 w-16 overflow-hidden rounded-full bg-oo-line-soft sm:w-[120px]">
        <span className="block h-full rounded-full bg-oo-ink-3" style={{ width: `${clamped * 100}%` }} />
      </span>
      <span className="w-9 text-right font-mono text-[13px] tabular-nums text-oo-ink-2">{clamped.toFixed(2)}</span>
    </span>
  );
}
