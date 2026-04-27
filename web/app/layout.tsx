import type { Metadata } from "next";
import Link from "next/link";
import { Manrope, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { AuthProvider } from "@/components/providers/AuthProvider";
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
    <html lang="en" suppressHydrationWarning>
      <body className={`${manrope.variable} ${plex.variable} font-[var(--font-plex)]`}>
        <QueryProvider>
          <AuthProvider>
            <nav className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/80 backdrop-blur-md">
              <div className="clinical-shell h-16 flex items-center justify-between gap-4">
                <Link href="/" className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-cyan-600" />
                  <span className="font-[var(--font-manrope)] font-extrabold text-slate-900 tracking-tight">OpenOncology</span>
                </Link>
                <div className="flex items-center gap-2 sm:gap-3 text-sm">
                  <Link href="/submit" className="text-slate-600 hover:text-slate-900 transition-colors px-2 py-1">Submit</Link>
                  <Link href="/orders" className="text-slate-600 hover:text-slate-900 transition-colors px-2 py-1">Orders</Link>
                  <Link href="/marketplace" className="hidden sm:inline text-slate-600 hover:text-slate-900 transition-colors px-2 py-1">Marketplace</Link>
                  <Link href="/submit" className="ml-1 rounded-lg bg-cyan-700 px-3 py-1.5 text-white font-semibold hover:bg-cyan-600 transition-colors">
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
