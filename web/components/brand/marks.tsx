type TrackVariant = "original" | "bold" | "fine";

type MarkProps = {
  size?: number;
  ink?: string;
  accent?: string;
  title?: string;
  variant?: TrackVariant;
};

const TRACKS: Record<TrackVariant, { x: number; y: number; w: number; h: number; spike?: boolean }[]> = {
  original: [
    { x: 2, y: 14, w: 8, h: 4 },
    { x: 12, y: 14, w: 4, h: 4 },
    { x: 18, y: 7, w: 4, h: 18, spike: true },
    { x: 24, y: 14, w: 6, h: 4 },
  ],
  bold: [
    { x: 2, y: 13.5, w: 13, h: 5 },
    { x: 17.5, y: 5, w: 5, h: 22, spike: true },
    { x: 25, y: 13.5, w: 5, h: 5 },
  ],
  fine: [
    { x: 2, y: 14.5, w: 8, h: 3 },
    { x: 12, y: 14.5, w: 3, h: 3 },
    { x: 17.5, y: 5, w: 4.5, h: 22, spike: true },
    { x: 24.5, y: 14.5, w: 5.5, h: 3 },
  ],
};

export function TrackMark({ size = 32, ink = "#1B1626", accent = "#3D2C8D", title, variant = "bold" }: MarkProps) {
  return (
    <svg
      viewBox="0 0 32 32"
      width={size}
      height={size}
      fill="none"
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      {TRACKS[variant].map((r) => (
        <rect
          key={`${r.x}-${r.y}`}
          x={r.x}
          y={r.y}
          width={r.w}
          height={r.h}
          rx={Math.min(r.w, r.h) / 2}
          fill={r.spike ? accent : ink}
        />
      ))}
    </svg>
  );
}

type WordmarkProps = {
  ink?: string;
  accent?: string;
  size?: number;
  lowercase?: boolean;
  split?: boolean;
};

export function Wordmark({ ink = "#1B1626", accent = "#3D2C8D", size = 40, lowercase = false, split = false }: WordmarkProps) {
  const open = lowercase ? "open" : "Open";
  const onco = lowercase ? "onco" : "Onco";
  return (
    <span
      className="inline-flex items-baseline whitespace-nowrap font-sans"
      style={{ color: ink, fontSize: size, letterSpacing: "-0.03em", lineHeight: 1, fontWeight: 600 }}
    >
      <span style={split ? { fontWeight: 400 } : undefined}>{open}</span>
      <span>{onco}</span>
      <span
        style={{
          display: "inline-block",
          width: "0.1em",
          height: "0.96em",
          borderRadius: "0.05em",
          background: accent,
          margin: "0 0.05em 0 0.04em",
        }}
      >
        <span className="sr-only">l</span>
      </span>
      <span>ogy</span>
    </span>
  );
}
