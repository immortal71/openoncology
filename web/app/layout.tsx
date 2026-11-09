import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { AuthProvider } from "@/components/providers/AuthProvider";
import { MotionProvider } from "@/components/providers/MotionProvider";
import { SiteNav } from "@/components/site-nav";
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
// These files are in app/fonts and ship with the repo. Every family is under
// the SIL Open Font License, which permits redistribution. See
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

const plexMono = localFont({
  src: "./fonts/IBMPlexMono-Variable-Latin1.woff2",
  variable: "--font-mono",
  weight: "100 700",
  display: "swap",
});

export const metadata: Metadata = {
  title: "OpenOncology | Drug evidence for labs and oncologists",
  description:
    "Open-source tumor evidence matching for sequencing labs and hospitals without molecular tumor boards. Research prototype; oncologist review required.",
  openGraph: {
    title: "OpenOncology",
    description: "Drug evidence for labs and oncologists. Research prototype; oncologist review required.",
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
      <body className={`${manrope.variable} ${plex.variable} ${plexMono.variable} font-sans bg-neutral-bg text-neutral-heading`}>
        <QueryProvider>
          <MotionProvider>
            <AuthProvider>
              <SiteNav />
              {children}
            </AuthProvider>
          </MotionProvider>
          <Toaster />
        </QueryProvider>
      </body>
    </html>
  );
}
