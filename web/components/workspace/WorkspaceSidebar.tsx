"use client";

import { useState } from "react";
import Link from "next/link";
import { Upload, Workflow, Pill, FileText, Settings, ChevronLeft, ChevronRight } from "lucide-react";

export type WorkspaceSection = "upload" | "pipeline" | "drugs" | "report" | "settings";

const ITEMS: { id: WorkspaceSection; label: string; icon: typeof Upload }[] = [
  { id: "upload", label: "Upload", icon: Upload },
  { id: "pipeline", label: "Pipeline", icon: Workflow },
  { id: "drugs", label: "Drug Results", icon: Pill },
  { id: "report", label: "Report", icon: FileText },
  { id: "settings", label: "Settings", icon: Settings },
];

const INK = "#16181D";
const MUTED = "#8A8D86";
const BORDER = "#E4E2DB";
const SURFACE = "#FFFFFF";
const HOVER = "#F5F4EF";
const ACTIVE = "#EDEBE2";

const EXPANDED_W = 200;
const COLLAPSED_W = 52;

function SidebarLogo({ collapsed }: { collapsed: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2 overflow-hidden min-w-0" title={collapsed ? "OpenOncology" : undefined}>
      <div className="relative w-5 h-5 shrink-0">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
          <line x1="10.5" y1="4.5" x2="13.5" y2="4.5" stroke={INK} strokeWidth="0.75" strokeOpacity="0.4" />
          <line x1="8.5" y1="9" x2="15.5" y2="9" stroke={INK} strokeWidth="0.75" strokeOpacity="0.65" />
          <line x1="8.5" y1="14" x2="15.5" y2="14" stroke={INK} strokeWidth="0.75" strokeOpacity="0.65" />
          <line x1="10.5" y1="19" x2="13.5" y2="19" stroke={INK} strokeWidth="0.75" strokeOpacity="0.4" />
          <path d="M12,2 C17,3.5 17,7.5 12,11 C7,14.5 7,18.5 12,21.5" stroke={INK} strokeWidth="1.5" strokeLinecap="round" fill="none" />
          <path d="M12,2 C7,3.5 7,7.5 12,11 C17,14.5 17,18.5 12,21.5" stroke={INK} strokeOpacity="0.32" strokeWidth="1.5" strokeLinecap="round" fill="none" />
        </svg>
      </div>
      <span
        className="font-[var(--font-manrope)] font-extrabold tracking-tight text-sm whitespace-nowrap transition-opacity duration-200"
        style={{ color: INK, opacity: collapsed ? 0 : 1 }}
      >
        OpenOncology
      </span>
    </Link>
  );
}

export default function WorkspaceSidebar({
  active,
  onSelect,
}: {
  active: WorkspaceSection;
  onSelect: (section: WorkspaceSection) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <nav
      className="hidden sm:flex flex-col shrink-0 border p-3 transition-[width] duration-200 ease-in-out"
      style={{ borderColor: BORDER, backgroundColor: SURFACE, width: collapsed ? COLLAPSED_W : EXPANDED_W }}
    >
      <div className="flex items-center mb-3 gap-1" style={{ justifyContent: collapsed ? "center" : "space-between" }}>
        {!collapsed && <SidebarLogo collapsed={collapsed} />}
        <button
          onClick={() => setCollapsed((c) => !c)}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="flex items-center justify-center shrink-0 w-6 h-6 rounded-[4px] transition-colors"
          style={{ color: MUTED }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = HOVER)}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
        >
          {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
        </button>
      </div>

      {collapsed && (
        <div className="flex justify-center mb-3">
          <Link href="/" title="OpenOncology" className="w-5 h-5 shrink-0">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
              <line x1="10.5" y1="4.5" x2="13.5" y2="4.5" stroke={INK} strokeWidth="0.75" strokeOpacity="0.4" />
              <line x1="8.5" y1="9" x2="15.5" y2="9" stroke={INK} strokeWidth="0.75" strokeOpacity="0.65" />
              <line x1="8.5" y1="14" x2="15.5" y2="14" stroke={INK} strokeWidth="0.75" strokeOpacity="0.65" />
              <line x1="10.5" y1="19" x2="13.5" y2="19" stroke={INK} strokeWidth="0.75" strokeOpacity="0.4" />
              <path d="M12,2 C17,3.5 17,7.5 12,11 C7,14.5 7,18.5 12,21.5" stroke={INK} strokeWidth="1.5" strokeLinecap="round" fill="none" />
              <path d="M12,2 C7,3.5 7,7.5 12,11 C17,14.5 17,18.5 12,21.5" stroke={INK} strokeOpacity="0.32" strokeWidth="1.5" strokeLinecap="round" fill="none" />
            </svg>
          </Link>
        </div>
      )}

      <div className="flex flex-col gap-0.5">
        {ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelect(item.id)}
              title={collapsed ? item.label : undefined}
              className="group relative flex items-center gap-2.5 px-2.5 py-1.5 rounded-[4px] text-sm text-left transition-colors"
              style={{
                backgroundColor: !collapsed && isActive ? ACTIVE : "transparent",
                color: isActive ? INK : MUTED,
                fontWeight: isActive ? 600 : 400,
                justifyContent: collapsed ? "center" : "flex-start",
              }}
              onMouseEnter={(e) => {
                if (!isActive || collapsed) e.currentTarget.style.backgroundColor = HOVER;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = !collapsed && isActive ? ACTIVE : "transparent";
              }}
            >
              <Icon size={16} className="shrink-0" strokeWidth={isActive ? 2.25 : 1.75} />
              <span
                className="leading-none whitespace-nowrap transition-opacity duration-200"
                style={{ opacity: collapsed ? 0 : 1, width: collapsed ? 0 : "auto", overflow: "hidden" }}
              >
                {item.label}
              </span>

              {collapsed && (
                <span
                  className="pointer-events-none absolute left-full ml-2 top-1/2 -translate-y-1/2 whitespace-nowrap px-2 py-1 text-xs rounded-[4px] opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-10"
                  style={{ backgroundColor: INK, color: SURFACE }}
                >
                  {item.label}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
