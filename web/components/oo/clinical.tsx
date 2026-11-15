import { Ban, Check, Clock, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { parseApproval } from "@/lib/approval";
import { tierInfo } from "@/lib/therapy-groups";

export function TierPill({ tier, className }: { tier: string | null | undefined; className?: string }) {
  const info = tierInfo(tier);
  const approved = info.key === "fda_approved";
  const resistance = info.key === "resistance_mechanism";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[12px] font-medium",
        approved
          ? "border border-oo-line bg-oo-surface text-oo-ink"
          : resistance
            ? "bg-oo-status-failed-bg text-oo-status-failed-fg"
            : "bg-oo-line-soft text-oo-ink-3",
        className
      )}
    >
      {approved ? <Check size={12} aria-hidden="true" /> : null}
      {resistance ? <Ban size={12} aria-hidden="true" /> : null}
      {info.badge}
    </span>
  );
}

export function SourceBadges({ sources, phaseSignal = false, className }: { sources: string[]; phaseSignal?: boolean; className?: string }) {
  const note = phaseSignal ? <span className="text-[12.5px] text-oo-ink-3">Score also weighs the drug&apos;s clinical phase</span> : null;
  return (
    <div className={cn("flex flex-wrap items-center gap-x-3 gap-y-1.5", className)}>
      {sources.length === 0 ? (
        <span className="text-[13px] text-oo-ink-3">No named sources</span>
      ) : (
        <ul className="flex flex-wrap gap-1.5" aria-label="Evidence sources">
          {sources.map((s) => (
            <li key={s} className="rounded-md border border-oo-line bg-oo-surface px-2 py-0.5 font-mono text-[12px] text-oo-ink-2">
              {s}
            </li>
          ))}
        </ul>
      )}
      {note}
    </div>
  );
}

export function ApprovalLine({ status, className }: { status: string | null | undefined; className?: string }) {
  const a = parseApproval(status);
  return (
    <span className={cn("text-[13px] text-oo-ink-2", className)}>
      <span className="font-medium text-oo-ink">{a.label}</span>
      {a.qualifier ? (
        <>
          <span aria-hidden="true"> · </span>
          <span className={a.differentIndication ? "italic" : undefined}>{a.qualifier}</span>
        </>
      ) : null}
    </span>
  );
}

export function ReviewState({ reviewed, className }: { reviewed: boolean | null | undefined; className?: string }) {
  const done = reviewed === true;
  const Icon = done ? ShieldCheck : Clock;
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border border-oo-line bg-oo-surface px-2.5 py-1 text-[12px] font-medium text-oo-ink-2", className)}>
      <Icon size={13} aria-hidden="true" />
      {done ? "Reviewed by an oncologist" : "Awaiting oncologist review"}
    </span>
  );
}
