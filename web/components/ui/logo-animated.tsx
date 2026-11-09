import Link from "next/link";
import { TrackMark, Wordmark } from "@/components/brand/marks";
import { cn } from "@/lib/utils";

const TONES = {
  dark: { ink: "#EDEBE4", accent: "#A99CF0", outline: "focus-visible:outline-oo-hema-on-dark" },
  light: { ink: "#1B1626", accent: "#3D2C8D", outline: "focus-visible:outline-oo-hema" },
} as const;

export function LogoAnimated({ tone = "dark" }: { tone?: keyof typeof TONES }) {
  const t = TONES[tone];
  return (
    <Link href="/" className={cn("flex items-center gap-2 rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4", t.outline)}>
      <TrackMark variant="bold" size={22} ink={t.ink} accent={t.accent} />
      <Wordmark size={16} ink={t.ink} accent={t.accent} />
    </Link>
  );
}
