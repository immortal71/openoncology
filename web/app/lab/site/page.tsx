import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { HomeLanding } from "@/components/marketing/home-landing";

export const metadata: Metadata = { title: "Landing (photo) | OpenOncology", robots: { index: false, follow: false } };

export default function SitePage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <HomeLanding demoHref="/lab/results" />;
}
