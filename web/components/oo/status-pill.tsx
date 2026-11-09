import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { STATUS_LABEL, normalizeStatus, type SubmissionStatus } from "@/lib/status";

function Glyph({ status }: { status: SubmissionStatus }) {
  const common = { width: 14, height: 14, viewBox: "0 0 14 14", "aria-hidden": true } as const;
  switch (status) {
    case "queued":
      return (
        <svg {...common} className="stroke-oo-status-queued-fg" fill="none">
          <circle cx="7" cy="7" r="5.5" strokeWidth="1.5" strokeDasharray="2.4 2" />
        </svg>
      );
    case "analyzing":
      return (
        <svg {...common} fill="none">
          <circle cx="7" cy="7" r="5.5" strokeWidth="1.5" className="stroke-oo-status-analyzing-fg" />
          <path d="M7 1.5a5.5 5.5 0 0 1 0 11z" className="fill-oo-status-analyzing-fg" />
        </svg>
      );
    case "complete":
      return (
        <svg {...common} fill="none">
          <circle cx="7" cy="7" r="6.25" className="fill-oo-status-complete-fg" />
          <path d="M4.3 7.2 6.2 9l3.5-3.9" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "failed":
      return <AlertTriangle size={14} className="text-oo-status-failed-fg" aria-hidden="true" />;
    default:
      return (
        <svg {...common} className="stroke-oo-ink-3" fill="none">
          <circle cx="7" cy="7" r="5.5" strokeWidth="1.5" />
        </svg>
      );
  }
}

export function StatusPill({ status, className }: { status: string | null | undefined; className?: string }) {
  const s = normalizeStatus(status);
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[13px] font-medium text-oo-ink-2", className)}>
      <Glyph status={s} />
      <span className="sr-only">Status: </span>
      {STATUS_LABEL[s]}
    </span>
  );
}
