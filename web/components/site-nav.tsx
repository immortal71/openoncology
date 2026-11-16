"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import * as Dialog from "@radix-ui/react-dialog";
import { Github, Menu, X } from "lucide-react";
import { LogoAnimated } from "@/components/ui/logo-animated";
import { cn } from "@/lib/utils";

const REDESIGNED_PREFIXES = ["/lab"];
const MARKETING_ROUTES = ["/lab/landing", "/lab/hero-a", "/lab/hero-b", "/lab/hero-c", "/lab/direction-a", "/lab/direction-b", "/lab/site", "/lab/atlas"];
const DARK_ROUTES = ["/lab/hero-a"];
const GITHUB_URL = "https://github.com/immortal71/openoncology";
const METHODS_URL = "https://github.com/immortal71/openoncology/blob/main/docs/METHODS.md";

const NAV_LINKS = [
  { href: "#how-it-works", label: "How it works", external: false },
  { href: "#evidence", label: "Evidence", external: false },
  { href: METHODS_URL, label: "Methods", external: true },
  { href: GITHUB_URL, label: "GitHub", external: true },
];

const ATLAS_LINKS = [
  { href: "#how-it-works", label: "How it works", external: false },
  { href: "#labs", label: "For labs", external: false },
  { href: "#hospitals", label: "For hospitals", external: false },
  { href: METHODS_URL, label: "Methods", external: true },
  { href: GITHUB_URL, label: "GitHub", external: true },
];

function MobileMenu({ links }: { links: typeof NAV_LINKS }) {
  return (
    <Dialog.Root>
      <Dialog.Trigger
        aria-label="Open menu"
        className="inline-grid h-9 w-9 place-items-center rounded-md border border-oo-line bg-oo-surface text-oo-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema md:hidden"
      >
        <Menu size={17} aria-hidden="true" />
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 top-16 z-40 bg-oo-ink/20" />
        <Dialog.Content className="fixed inset-x-0 top-16 z-50 border-b border-oo-line bg-oo-paper px-5 pb-6 pt-2 shadow-[0_24px_48px_-24px_rgb(27_22_38/0.3)] focus:outline-none">
          <div className="flex items-center justify-between">
            <Dialog.Title className="text-[13px] font-medium text-oo-ink-3">Menu</Dialog.Title>
            <Dialog.Close
              aria-label="Close menu"
              className="inline-grid h-9 w-9 place-items-center rounded-full text-oo-ink-2 hover:text-oo-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-oo-hema"
            >
              <X size={17} aria-hidden="true" />
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">Site sections and links</Dialog.Description>
          <ul className="divide-y divide-oo-line-soft">
            {links.map((l) => (
              <li key={l.label}>
                <Dialog.Close asChild>
                  <a
                    href={l.href}
                    {...(l.external ? { target: "_blank", rel: "noreferrer" } : {})}
                    className="flex items-center gap-2 py-3.5 text-[16px] font-medium text-oo-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-oo-hema"
                  >
                    {l.label === "GitHub" ? <Github size={17} aria-hidden="true" /> : null}
                    {l.label}
                  </a>
                </Dialog.Close>
              </li>
            ))}
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

const linkClass =
  "rounded-md px-1 py-1 text-[14px] text-oo-ink-2 transition-colors duration-150 hover:text-oo-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-oo-hema";

export function SiteNav() {
  const pathname = usePathname() ?? "";
  const dark = DARK_ROUTES.includes(pathname);
  const light = !dark && REDESIGNED_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  const marketing = MARKETING_ROUTES.includes(pathname);
  const atlas = pathname === "/lab/atlas";
  const link = dark
    ? linkClass.replace("text-oo-ink-2", "text-white/65").replace("hover:text-oo-ink", "hover:text-white")
    : atlas
      ? linkClass.replace("text-oo-ink-2", "text-[#625E68]").replace("hover:text-oo-ink", "hover:text-[#24212B]")
      : linkClass;

  return (
    <nav className={cn("sticky top-0 z-50 border-b", dark ? "border-white/10 bg-[#0C0A12]/90 backdrop-blur" : light ? "border-oo-line bg-oo-paper" : "border-white/10 bg-neutral-bg")}>
      <div
        className={cn(
          "flex h-16 items-center justify-between gap-6",
          marketing ? (atlas ? "mx-auto max-w-[1280px] px-5 md:px-10 lg:h-[72px]" : "mx-auto max-w-[1200px] px-5 md:px-8") : "clinical-shell"
        )}
      >
        <LogoAnimated tone={light ? "light" : "dark"} />
        {marketing ? (
          <div className="flex items-center gap-3 md:gap-5">
            <div className="hidden items-center gap-6 md:flex">
              <a href="#how-it-works" className={link}>
                How it works
              </a>
              {pathname === "/lab/atlas" ? (
                <>
                  <a href="#labs" className={link}>
                    For labs
                  </a>
                  <a href="#hospitals" className={link}>
                    For hospitals
                  </a>
                </>
              ) : (
                <a href="#evidence" className={link}>
                  Evidence
                </a>
              )}
              <a href={METHODS_URL} target="_blank" rel="noreferrer" className={link}>
                Methods
              </a>
              <a href={GITHUB_URL} target="_blank" rel="noreferrer" className={cn(link, "inline-flex items-center gap-1.5")}>
                <Github size={16} aria-hidden="true" />
                GitHub
              </a>
            </div>
            <Link
              href="/lab/results"
              className={cn(
                "inline-flex h-9 items-center rounded-md border px-4 text-[14px] font-medium transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema",
                dark
                  ? "border-white/15 bg-white/[0.04] text-white hover:bg-white/10"
                  : atlas
                    ? "rounded-[8px] border-transparent bg-[#25202F] text-[#F7F5F0] hover:bg-[#3A3446]"
                    : "border-oo-line bg-oo-surface text-oo-ink shadow-[0_1px_2px_rgb(27_22_38/0.06)] hover:border-oo-ink-3/40 hover:bg-oo-paper"
              )}
            >
              <span className="sm:hidden">Demo</span>
              <span className="hidden sm:inline">View the demo case</span>
            </Link>
            <MobileMenu links={pathname === "/lab/atlas" ? ATLAS_LINKS : NAV_LINKS} />
          </div>
        ) : null}
      </div>
    </nav>
  );
}
