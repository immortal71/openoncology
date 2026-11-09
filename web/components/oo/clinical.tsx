import { Check, Clock, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { parseApproval } from "@/lib/approval";

const TIER_LABEL: Record<string, string> = {
  fda_approved: "FDA approved",
  repurposed: "Repurposed",
};

export function TierPill({ tier, className }: { tier: string | null | undefined; className?: string }) {
  const label = tier ? (TIER_LABEL[tier] ?? tier.replace(/_/g, " ")) : "Unclassified";
  const approved = tier === "fda_approved";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[12px] font-medium",
        approved ? "border border-oo-line bg-oo-surface text-oo-ink" : "bg-oo-line-soft text-oo-ink-3",
        className
      )}
    >
      {approved ? <Check size={12} aria-hidden="true" /> : null}
      {label}
    </span>
  );
}

export function SourceBadges({ sources, className }: { sources: string[]; className?: string }) {
  if (sources.length === 0) return <span className={cn("text-[13px] text-oo-ink-3", className)}>No named sources</span>;
  return (
    <ul className={cn("flex flex-wrap gap-1.5", className)} aria-label="Evidence sources">
      {sources.map((s) => (
        <li key={s} className="rounded-md border border-oo-line bg-oo-surface px-2 py-0.5 font-mono text-[12px] text-oo-ink-2">
          {s}
        </li>
      ))}
    </ul>
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
