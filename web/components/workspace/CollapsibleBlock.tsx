"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";

const INK = "#16181D";
const MUTED = "#8A8D86";
const BORDER = "#E4E2DB";

export default function CollapsibleBlock({
  label,
  defaultOpen = true,
  children,
}: {
  label: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border" style={{ borderColor: BORDER }}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-1.5 px-3 py-1.5 text-left"
      >
        {open ? (
          <ChevronDown size={13} style={{ color: MUTED }} className="shrink-0" />
        ) : (
          <ChevronRight size={13} style={{ color: MUTED }} className="shrink-0" />
        )}
        <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: open ? INK : MUTED }}>
          {label}
        </span>
      </button>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}
