import { cn } from "@/lib/utils";

const EXONS = [
  { x: 20, w: 30 },
  { x: 78, w: 46 },
  { x: 150, w: 34 },
  { x: 212, w: 52 },
  { x: 292, w: 40 },
  { x: 356, w: 48 },
];
const TRACK_START = 20;
const TRACK_END = 404;
const LABEL_MAX = 26;

export function VariantTrack({
  gene,
  hgvs,
  detail,
  position = 0.22,
  annotated = true,
  className,
}: {
  gene: string;
  hgvs: string;
  detail?: string;
  position?: number;
  annotated?: boolean;
  className?: string;
}) {
  const x = TRACK_START + Math.min(1, Math.max(0, position)) * (TRACK_END - TRACK_START);
  const full = `${gene} ${hgvs}`;
  const label = full.length > LABEL_MAX ? `${full.slice(0, LABEL_MAX - 1)}…` : full;
  const labelLeft = x < 260;
  const textX = labelLeft ? x + 14 : x - 14;
  const anchor = labelLeft ? "start" : "end";

  return (
    <figure className={cn("rounded-[10px] border border-oo-line bg-oo-surface px-4 pb-3 pt-2", className)}>
      <figcaption className="text-[12px] text-oo-ink-3">{gene} · schematic, not to scale</figcaption>
      <svg viewBox="0 0 420 110" className="mt-1 h-auto w-full" role="img" aria-label={`${full}${detail ? `, ${detail}` : ""}, schematic`}>
        <title>{full}</title>
        <rect x="10" y="80" width="400" height="2" rx="1" className="fill-oo-line" />
        {EXONS.map((e) => (
          <rect key={e.x} x={e.x} y="70" width={e.w} height="22" rx="5" className="fill-oo-ink-3" opacity="0.3" />
        ))}
        <rect x={x - 1.5} y="30" width="3" height="50" rx="1.5" className="fill-oo-eosin" />
        <circle cx={x} cy="30" r="6" className="fill-oo-eosin" />
        {annotated ? (
          <>
            <text x={textX} y="28" textAnchor={anchor} fontSize="15" fontWeight="600" className="fill-oo-ink" fontFamily="var(--font-plex)">
              {label}
            </text>
            {detail ? (
              <text x={textX} y="46" textAnchor={anchor} fontSize="12.5" className="fill-oo-ink-3" fontFamily="var(--font-plex)">
                {detail}
              </text>
            ) : null}
          </>
        ) : null}
      </svg>
    </figure>
  );
}
