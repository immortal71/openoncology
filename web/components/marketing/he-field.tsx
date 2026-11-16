type Nucleus = { x: number; y: number; rx: number; ry: number; rot: number; tone: number };
type Lumen = { x: number; y: number; rx: number; ry: number; rot: number };
type Fiber = { d: string; w: number; a: number };

function rng(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function buildField() {
  const r = rng(20261115);
  const lumens: Lumen[] = [];
  const nuclei: Nucleus[] = [];
  const fibers: Fiber[] = [];

  const centers = [
    [230, 260], [520, 190], [790, 300], [330, 560], [640, 520], [860, 650], [210, 820], [520, 820], [790, 900],
  ];
  for (const [cx, cy] of centers) {
    const l = { x: cx + (r() - 0.5) * 50, y: cy + (r() - 0.5) * 50, rx: 48 + r() * 46, ry: 30 + r() * 34, rot: r() * 180 };
    lumens.push(l);
    const rad = (l.rot * Math.PI) / 180;
    for (const ring of [1, 1.38]) {
      const per = Math.PI * (l.rx + l.ry) * ring;
      const count = Math.floor(per / (ring === 1 ? 11 : 16));
      for (let i = 0; i < count; i++) {
        if (ring > 1 && r() < 0.35) continue;
        const t = (i / count) * Math.PI * 2 + r() * 0.08;
        const ex = Math.cos(t) * (l.rx * ring + 9);
        const ey = Math.sin(t) * (l.ry * ring + 9);
        const x = l.x + ex * Math.cos(rad) - ey * Math.sin(rad);
        const y = l.y + ex * Math.sin(rad) + ey * Math.cos(rad);
        const tangent = (Math.atan2(ey, ex) * 180) / Math.PI + l.rot + 90;
        nuclei.push({ x, y, rx: 5.4 + r() * 2.2, ry: 3.1 + r() * 1.2, rot: tangent + (r() - 0.5) * 20, tone: r() });
      }
    }
  }

  for (let i = 0; i < 170; i++) {
    const cx = 640 + (r() - 0.5) * 330;
    const cy = 760 + (r() - 0.5) * 230;
    nuclei.push({ x: cx, y: cy, rx: 6.5 + r() * 4, ry: 5 + r() * 3, rot: r() * 180, tone: 0.75 + r() * 0.25 });
  }

  for (let i = 0; i < 520; i++) {
    nuclei.push({ x: r() * 1000, y: r() * 1000, rx: 4.5 + r() * 3, ry: 1.4 + r() * 0.9, rot: r() * 180, tone: r() * 0.6 });
  }

  for (let i = 0; i < 150; i++) {
    const x = r() * 1000;
    const y = r() * 1000;
    const len = 60 + r() * 140;
    const a = r() * Math.PI;
    const x2 = x + Math.cos(a) * len;
    const y2 = y + Math.sin(a) * len;
    const bend = (r() - 0.5) * 60;
    fibers.push({
      d: `M${x.toFixed(1)} ${y.toFixed(1)} Q${((x + x2) / 2 + bend).toFixed(1)} ${((y + y2) / 2 - bend).toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`,
      w: 0.8 + r() * 2.2,
      a: 0.12 + r() * 0.22,
    });
  }

  return { lumens, nuclei, fibers };
}

const FIELD = buildField();
const HEMA = ["#5B4A9E", "#4A3A8A", "#3B2C78", "#2E2163"];

export function HEField({ id = "he", className }: { id?: string; className?: string }) {
  return (
    <svg viewBox="0 0 1000 1000" className={className} role="img" aria-label="Illustrative H&E-style tissue texture, not patient tissue">
      <defs>
        <radialGradient id={`${id}-vignette`} cx="50%" cy="50%" r="50%">
          <stop offset="70%" stopColor="#FFFFFF" stopOpacity="0" />
          <stop offset="100%" stopColor="#2B1D3D" stopOpacity="0.28" />
        </radialGradient>
        <filter id={`${id}-soft`}>
          <feGaussianBlur stdDeviation="0.7" />
        </filter>
      </defs>
      <rect width="1000" height="1000" fill="#F3CFDD" />
      <g filter={`url(#${id}-soft)`}>
        {FIELD.fibers.map((f, i) => (
          <path key={i} d={f.d} stroke="#D9799F" strokeOpacity={f.a} strokeWidth={f.w} fill="none" strokeLinecap="round" />
        ))}
        {FIELD.lumens.map((l, i) => (
          <ellipse
            key={`epi-${i}`}
            cx={l.x}
            cy={l.y}
            rx={l.rx + 16}
            ry={l.ry + 16}
            transform={`rotate(${l.rot} ${l.x} ${l.y})`}
            fill="none"
            stroke="#E9B3CB"
            strokeWidth="26"
            strokeOpacity="0.85"
          />
        ))}
        {FIELD.lumens.map((l, i) => (
          <ellipse key={i} cx={l.x} cy={l.y} rx={l.rx} ry={l.ry} transform={`rotate(${l.rot} ${l.x} ${l.y})`} fill="#FBF3F6" stroke="#DE97B6" strokeWidth="2.5" />
        ))}
        {FIELD.nuclei.map((n, i) => (
          <ellipse
            key={i}
            cx={n.x}
            cy={n.y}
            rx={n.rx}
            ry={n.ry}
            transform={`rotate(${n.rot.toFixed(1)} ${n.x.toFixed(1)} ${n.y.toFixed(1)})`}
            fill={HEMA[Math.min(3, Math.floor(n.tone * 4))]}
            fillOpacity={0.78}
          />
        ))}
      </g>
      <rect width="1000" height="1000" fill={`url(#${id}-vignette)`} />
    </svg>
  );
}
