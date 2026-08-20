import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { AuthProvider } from "@/components/providers/AuthProvider";
import { LogoAnimated } from "@/components/ui/logo-animated";
import { Toaster } from "@/components/ui/toaster";

// Self-hosted rather than fetched from Google at build time.
//
// next/font/google downloads from fonts.gstatic.com while compiling. When the
// build machine cannot reach it the failure is a bare
// "TypeError: Cannot read properties of null (reading '1')" out of next/font,
// which fails CI for reasons unrelated to the change under test. It did exactly
// that on backend-only dependency PRs, intermittently, so a green run proved
// nothing and a red one meant nothing either.
//
// These files are in app/fonts and ship with the repo. All four families are
// under the SIL Open Font License, which permits redistribution. See
// app/fonts/OFL.md.
const manrope = localFont({
  src: "./fonts/Manrope-Variable.woff2",
  variable: "--font-manrope",
  weight: "200 800",
  display: "swap",
});

const plex = localFont({
  src: [
    { path: "./fonts/IBMPlexSans-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/IBMPlexSans-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/IBMPlexSans-600.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-plex",
  display: "swap",
});

const jetbrainsMono = localFont({
  src: "./fonts/JetBrainsMono-Variable.woff2",
  variable: "--font-mono",
  weight: "100 800",
  display: "swap",
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
      <body className={`${manrope.variable} ${plex.variable} ${jetbrainsMono.variable} font-[var(--font-plex)] bg-neutral-bg text-neutral-heading`}>
        <QueryProvider>
          <AuthProvider>
            <nav className="sticky top-0 z-50 border-b border-white/5 bg-neutral-bg/90 backdrop-blur-md">
              <div className="clinical-shell h-16 flex items-center">
                <LogoAnimated />
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
