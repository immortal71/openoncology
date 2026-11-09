import * as React from "react";
import { Info, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function Disclaimer({ children, variant = "note", className }: { children: React.ReactNode; variant?: "note" | "banner"; className?: string }) {
  return (
    <div
      role="note"
      className={cn(
        "flex items-start gap-2 text-[14px] leading-relaxed text-oo-ink-2",
        variant === "note" ? "rounded-[10px] bg-oo-line-soft px-4 py-3" : "border-b border-oo-line bg-oo-line-soft px-6 py-2.5",
        className
      )}
    >
      <Info size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center rounded-[10px] border border-dashed border-oo-line px-6 py-12 text-center", className)}>
      <span className="grid h-12 w-12 place-items-center rounded-full bg-oo-line-soft text-oo-ink-3">
        <Icon size={22} aria-hidden="true" />
      </span>
      <h3 className="mt-4 text-[16px] font-semibold text-oo-ink">{title}</h3>
      <p className="mt-1.5 max-w-sm text-[14px] leading-relaxed text-oo-ink-3">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
