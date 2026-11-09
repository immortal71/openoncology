"use client";

import { usePathname } from "next/navigation";
import { LogoAnimated } from "@/components/ui/logo-animated";
import { cn } from "@/lib/utils";

const REDESIGNED_PREFIXES = ["/lab"];

export function SiteNav() {
  const pathname = usePathname() ?? "";
  const light = REDESIGNED_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  return (
    <nav className={cn("sticky top-0 z-50 border-b", light ? "border-oo-line bg-oo-paper" : "border-white/10 bg-neutral-bg")}>
      <div className="clinical-shell flex h-16 items-center">
        <LogoAnimated tone={light ? "light" : "dark"} />
      </div>
    </nav>
  );
}
