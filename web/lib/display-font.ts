import localFont from "next/font/local";

export const displayFont = localFont({
  src: "../app/fonts/SourceSerif4Display-Semibold.woff2",
  variable: "--font-display",
  weight: "600",
  display: "swap",
});
