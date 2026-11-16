"use client";

import * as React from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { EASE_OUT } from "@/lib/motion";
import { parseApproval } from "@/lib/approval";
import { ScoreBar } from "./score-bar";
import { highlightHandlers, useHighlightStore, useIsHighlighted } from "./highlight";
import { ApprovalLine, SourceBadges, TierPill } from "./clinical";
import { groupByTier, tierInfo, type TherapyGroup } from "@/lib/therapy-groups";

export type Finding = {
  id: string;
  name: string;
  tier: string | null | undefined;
  score: number | null | undefined;
  approvalStatus: string | null | undefined;
  mechanism: string | null | undefined;
  sources: string[];
  phaseSignal?: boolean;
  rank?: number;
};

const GRID = "grid-cols-[1.5rem_minmax(0,1fr)_auto] md:grid-cols-[1.5rem_minmax(0,1fr)_8.5rem_11.5rem_1.25rem]";

const FindingRow = React.memo(function FindingRow({
  finding,
  rank,
  defaultOpen,
  showTier = true,
}: {
  finding: Finding;
  rank: number;
  defaultOpen: boolean;
  showTier?: boolean;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  const reduce = useReducedMotion();
  const panelId = React.useId();
  const store = useHighlightStore();
  const active = useIsHighlighted(finding.id);
  const approval = parseApproval(finding.approvalStatus);
  const tierLabel = tierInfo(finding.tier).badge;
  const showApproval = Boolean(approval.qualifier) || approval.label !== tierLabel;

  return (
    <li>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        {...highlightHandlers(store, finding.id)}
        onFocus={() => store?.setFocus(finding.id)}
        onBlur={() => store?.setFocus(null)}
        className={cn(
          "grid w-full items-center gap-x-3 gap-y-1.5 px-4 py-2.5 text-left transition-colors duration-150 ease-oo-out hover:bg-oo-paper focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-oo-hema motion-reduce:transition-none",
          active && "bg-oo-paper",
          GRID
        )}
      >
        <span className="font-mono text-[12px] tabular-nums text-oo-ink-3">{rank}</span>
        <span className="min-w-0">
          <span className="block truncate text-[15px] font-semibold text-oo-ink">{finding.name}</span>
          {approval.differentIndication ? (
            <span className="block text-[12px] text-oo-ink-3">Approved for a different indication</span>
          ) : !showTier ? (
            <span className="block text-[12px] text-oo-ink-3">{approval.label}</span>
          ) : null}
        </span>
        <span className="col-start-2 flex items-center justify-between gap-3 md:contents">
          {showTier ? (
            <TierPill tier={finding.tier} className="justify-self-start" />
          ) : (
            <span aria-hidden="true" className="text-[12px] text-oo-ink-3 md:invisible">
              Evidence score
            </span>
          )}
          <span className="md:justify-self-end">
            <span className="sr-only">Evidence score </span>
            <ScoreBar score={finding.score} />
          </span>
        </span>
        <ChevronDown
          size={16}
          aria-hidden="true"
          className={cn(
            "col-start-3 row-start-1 text-oo-ink-3 transition-transform duration-150 ease-oo-out motion-reduce:transition-none md:col-start-auto md:row-start-auto",
            open && "rotate-180"
          )}
        />
      </button>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            id={panelId}
            key="panel"
            initial={{ height: 0 }}
            animate={{ height: "auto" }}
            exit={{ height: 0 }}
            transition={reduce ? { duration: 0 } : { duration: 0.22, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, transition: { duration: 0.08 } }}
              transition={reduce ? { duration: 0 } : { duration: 0.16, delay: 0.08, ease: EASE_OUT }}
              className="space-y-2.5 px-4 pb-4 pl-[3.25rem]"
            >
              {showApproval ? <ApprovalLine status={finding.approvalStatus} /> : null}
              {finding.mechanism ? <p className="max-w-[68ch] text-[14px] leading-relaxed text-oo-ink-2">{finding.mechanism}</p> : null}
              <SourceBadges sources={finding.sources} phaseSignal={finding.phaseSignal} />
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </li>
  );
});

function FindingGroup({
  group,
  grouped,
  caption,
  defaultOpenId,
  openAll = false,
}: {
  group: TherapyGroup<Finding & { rank: number }>;
  grouped: boolean;
  caption: string;
  defaultOpenId?: string;
  openAll?: boolean;
}) {
  const headingId = React.useId();
  const resistance = group.key === "resistance_mechanism";
  return (
    <section aria-labelledby={grouped ? headingId : undefined} className="border-b border-oo-line last:border-b-0">
      {grouped ? (
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 gap-y-0.5 bg-oo-paper px-4 py-2 md:flex md:flex-wrap">
          <h3 id={headingId} className={cn("text-[13px] font-semibold", resistance ? "text-oo-status-failed-fg" : "text-oo-ink")}>
            {group.heading}
          </h3>
          {group.note ? <span className="col-span-2 row-start-2 text-[12px] text-oo-ink-3 md:col-auto md:row-auto">{group.note}</span> : null}
          <span className="col-start-2 row-start-1 whitespace-nowrap font-mono text-[11.5px] text-oo-ink-3 md:ml-auto">
            {group.items.length} {group.items.length === 1 ? "drug" : "drugs"}
          </span>
        </div>
      ) : null}
      <ul aria-label={grouped ? undefined : caption} className="divide-y divide-oo-line-soft">
        {group.items.map((f) => (
          <FindingRow key={f.id} finding={f} rank={f.rank} defaultOpen={openAll || f.id === defaultOpenId} showTier={!grouped} />
        ))}
      </ul>
    </section>
  );
}

export function FindingList({
  findings,
  caption,
  empty,
  defaultOpenFirst = false,
  showHeader = false,
  grouped = false,
  defaultOpenAll = false,
  footer,
  className,
}: {
  findings: Finding[];
  caption: string;
  empty: React.ReactNode;
  defaultOpenFirst?: boolean;
  showHeader?: boolean;
  grouped?: boolean;
  defaultOpenAll?: boolean;
  footer?: React.ReactNode;
  className?: string;
}) {
  if (findings.length === 0) return <>{empty}</>;
  const ranked = findings.map((f, i) => ({ ...f, rank: f.rank ?? i + 1 }));
  const groups: TherapyGroup<Finding & { rank: number }>[] = grouped
    ? groupByTier(ranked)
    : [{ ...tierInfo(null), heading: caption, note: null, items: ranked }];
  const firstId = ranked[0]?.id;
  return (
    <div className={cn("overflow-hidden rounded-[10px] border border-oo-line bg-oo-surface", className)}>
      {showHeader ? (
        <div aria-hidden="true" className={cn("hidden h-9 items-center gap-x-3 border-b border-oo-line px-4 text-[12px] font-medium text-oo-ink-3 md:grid", GRID)}>
          <span>#</span>
          <span>Drug</span>
          <span>{grouped ? null : "Tier"}</span>
          <span className="justify-self-end pr-1">Evidence score</span>
          <span />
        </div>
      ) : null}
      {groups.map((g) => (
        <FindingGroup
          key={g.key}
          group={g}
          grouped={grouped}
          caption={caption}
          defaultOpenId={defaultOpenFirst ? firstId : undefined}
          openAll={defaultOpenAll}
        />
      ))}
      {footer ? <div className="border-t border-oo-line px-4 py-3 text-[13px] text-oo-ink-3">{footer}</div> : null}
    </div>
  );
}
