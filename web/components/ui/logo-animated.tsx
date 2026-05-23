import Link from "next/link";

export function LogoAnimated() {
  return (
    <Link href="/" className="logo-dna-wrap flex items-center gap-2">
      <div className="relative w-6 h-6 shrink-0" style={{ perspective: "80px" }}>
        <svg
          viewBox="0 0 24 24"
          width="24"
          height="24"
          className="logo-dna"
          fill="none"
          aria-hidden="true"
        >
          {/* Base pairs (horizontal rungs) */}
          <line x1="10.5" y1="4.5"  x2="13.5" y2="4.5"  stroke="#06b6d4" strokeWidth="0.75" strokeOpacity="0.4" />
          <line x1="8.5"  y1="9"    x2="15.5" y2="9"    stroke="#06b6d4" strokeWidth="0.75" strokeOpacity="0.65" />
          <line x1="8.5"  y1="14"   x2="15.5" y2="14"   stroke="#06b6d4" strokeWidth="0.75" strokeOpacity="0.65" />
          <line x1="10.5" y1="19"   x2="13.5" y2="19"   stroke="#06b6d4" strokeWidth="0.75" strokeOpacity="0.4" />
          {/* Strand A — S-curve */}
          <path
            d="M12,2 C17,3.5 17,7.5 12,11 C7,14.5 7,18.5 12,21.5"
            stroke="#06b6d4"
            strokeWidth="1.5"
            strokeLinecap="round"
            fill="none"
          />
          {/* Strand B — reverse S-curve */}
          <path
            d="M12,2 C7,3.5 7,7.5 12,11 C17,14.5 17,18.5 12,21.5"
            stroke="rgba(6,182,212,0.32)"
            strokeWidth="1.5"
            strokeLinecap="round"
            fill="none"
          />
        </svg>
      </div>
      <span className="font-[var(--font-manrope)] font-extrabold text-white tracking-tight text-sm">
        OpenOncology
      </span>
    </Link>
  );
}
