import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LenisScroll } from "@/components/marketing/lenis-scroll";
import { HeroDark } from "@/components/marketing/heroes/hero-dark";
import { displayFont } from "@/lib/display-font";

export const metadata: Metadata = { title: "Hero A (dark) | OpenOncology", robots: { index: false, follow: false } };

export default function HeroPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return (
    <main className={displayFont.variable}>
      <LenisScroll />
      <HeroDark demoHref="/lab/results" />
    </main>
  );
}
