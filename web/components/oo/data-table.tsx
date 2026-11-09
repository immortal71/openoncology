import * as React from "react";
import { cn } from "@/lib/utils";

export type Column<T> = {
  key: string;
  header: string;
  cell: (row: T) => React.ReactNode;
  align?: "left" | "right";
  mono?: boolean;
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  empty,
  className,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  caption: string;
  empty: React.ReactNode;
  className?: string;
}) {
  if (rows.length === 0) return <>{empty}</>;

  return (
    <div className={className}>
      <div className="hidden overflow-x-auto rounded-[10px] border border-oo-line bg-oo-surface md:block">
        <table className="w-full text-[14px] text-oo-ink">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr className="text-left text-[12px] text-oo-ink-3">
              {columns.map((c) => (
                <th key={c.key} scope="col" className={cn("h-10 px-4 font-medium", c.align === "right" && "text-right")}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={rowKey(row)}
                className="h-11 border-t border-oo-line-soft transition-colors duration-150 ease-oo-out focus-within:bg-oo-paper hover:bg-oo-paper motion-reduce:transition-none"
              >
                {columns.map((c) => (
                  <td key={c.key} className={cn("px-4", c.align === "right" && "text-right", c.mono && "font-mono text-[13px] tabular-nums")}>
                    {c.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="space-y-2 md:hidden" aria-label={caption}>
        {rows.map((row) => (
          <li key={rowKey(row)} className="rounded-[10px] border border-oo-line bg-oo-surface p-4">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[14px]">
              {columns.map((c) => (
                <React.Fragment key={c.key}>
                  <dt className="text-[12px] font-medium text-oo-ink-3">{c.header}</dt>
                  <dd className={cn("text-oo-ink", c.mono && "font-mono text-[13px] tabular-nums")}>{c.cell(row)}</dd>
                </React.Fragment>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    </div>
  );
}
