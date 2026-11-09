import * as React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-[10px] border border-oo-line bg-oo-surface", className)} {...props} />
}

export function Skeleton({ className }: { className?: string }) {
  return <span aria-hidden="true" className={cn("block animate-pulse rounded-md bg-oo-line-soft motion-reduce:animate-none", className)} />;
}

export function StatCard({
  label,
  value,
  note,
  loading = false,
  className,
}: {
  label: string;
  value: React.ReactNode;
  note?: React.ReactNode;
  loading?: boolean;
  className?: string;
}) {
  return (
    <Card className={cn("p-5", className)}>
      <div className="text-[13px] font-medium text-oo-muted">{label}</div>
      {loading ? (
        <>
          <Skeleton className="mt-3 h-8 w-20" />
          <span className="sr-only">Loading {label}</span>
        </>
      ) : (
        <div className="mt-2 text-[28px] font-semibold tabular-nums tracking-[-0.02em] text-oo-ink">{value}</div>
      )}
      {note ? <div className="mt-1.5 text-[13px] text-oo-ink-3">{note}</div> : null}
    </Card>
  );
}
