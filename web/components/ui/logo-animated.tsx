import Link from "next/link";
import { TrackMark, Wordmark } from "@/components/brand/marks";

export function LogoAnimated() {
  return (
    <Link href="/" className="flex items-center gap-2 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oo-hema-on-dark focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-bg">
      <TrackMark variant="bold" size={22} ink="#EDEBE4" accent="#A99CF0" />
      <Wordmark size={16} ink="#EDEBE4" accent="#A99CF0" />
    </Link>
  );
}
