import type { Metadata } from "next";
import Link from "next/link";
import { Manrope, IBM_Plex_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { AuthProvider } from "@/components/providers/AuthProvider";
import { LogoAnimated } from "@/components/ui/logo-animated";
import { Toaster } from "@/components/ui/toaster";

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
  weight: ["500", "600", "700", "800"],
});

const plex = IBM_Plex_Sans({
  subsets: ["latin"],
  variable: "--font-plex",
  weight: ["400", "500", "600"],
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: "OpenOncology — Precision Cancer Medicine for Everyone",
  description:
    "Upload your genomic data. Get AI-powered mutation analysis. Find repurposed drugs. Raise funds for treatment. Free and open source.",
  openGraph: {
    title: "OpenOncology",
    description: "Open-source precision cancer medicine platform",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${manrope.variable} ${plex.variable} ${jetbrainsMono.variable} font-[var(--font-plex)] bg-[#020617] text-slate-100`}>
        <QueryProvider>
          <AuthProvider>
            <nav className="sticky top-0 z-50 border-b border-white/5 bg-[#0a0f1e]/90 backdrop-blur-md">
              <div className="clinical-shell h-16 flex items-center justify-between gap-4">
                <LogoAnimated />
                <div className="flex items-center gap-1 sm:gap-2 text-xs">
                  <Link href="/explore" className="uppercase tracking-wider text-slate-400 hover:text-white transition-colors px-2.5 py-1.5">Explore</Link>
                  <Link href="/submit" className="uppercase tracking-wider text-slate-400 hover:text-white transition-colors px-2.5 py-1.5">Submit</Link>
                  <Link href="/orders" className="uppercase tracking-wider text-slate-400 hover:text-white transition-colors px-2.5 py-1.5">Orders</Link>
                  <Link href="/marketplace" className="hidden sm:inline uppercase tracking-wider text-slate-400 hover:text-white transition-colors px-2.5 py-1.5">Marketplace</Link>
                  <Link href="/submit" className="ml-2 rounded-md bg-cyan-700 px-3 py-1.5 text-white font-semibold hover:bg-cyan-600 transition-colors text-xs uppercase tracking-wider">
                    Start Case
                  </Link>
                </div>
              </div>
            </nav>
            {children}
          </AuthProvider>
          <Toaster />
        </QueryProvider>
      </body>
    </html>
  );
}
