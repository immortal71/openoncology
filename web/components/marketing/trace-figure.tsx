export type TraceRow = { name: string; score: number; group: string; sources: string[] };
export type TraceVariant = { gene: string; short: string; hgvs: string; position: number; length: number; domain: { label: string; start: number; end: number } | null; context: string };

const INK = "#1B1626";
const INK2 = "#5B5566";
const INK3 = "#8A8494";
const RULE = "#D9D4DE";
const HEMA = "#3D2C8D";
const EOSIN = "#D9669A";
const SANS = "var(--font-plex), IBM Plex Sans, system-ui, sans-serif";
const MONO = "var(--font-mono), IBM Plex Mono, monospace";

function chipWidth(text: string) {
  return text.length * 7.3 + 18;
}

export function TraceFigureWide({ variant, rows }: { variant: TraceVariant; rows: TraceRow[] }) {
  const trackX0 = 24;
  const trackX1 = 330;
  const trackY = 236;
  const px = (n: number) => trackX0 + ((trackX1 - trackX0) * n) / variant.length;
  const node = { x: 372, y: trackY };
  const rowX = 470;
  const rowY = [118, 196, 296];
  const srcX = 910;
  const labels = rows.map((r, i) => ({ ...r, y: rowY[i] ?? rowY[rowY.length - 1] + 80 * (i - rowY.length + 1) }));

  return (
    <svg viewBox="0 0 1200 370" role="img" aria-labelledby="trace-title trace-desc" className="block h-auto w-full">
      <title id="trace-title">How the demo case is traced</title>
      <desc id="trace-desc">
        {`${variant.gene} ${variant.short} leads to ${rows.length} ranked candidates: ${rows.map((r) => `${r.name} ${r.score.toFixed(2)}, sources ${r.sources.join(" and ")}`).join("; ")}.`}
      </desc>

      <g fontFamily={MONO} fontSize="11" letterSpacing="1.4" fill={INK3}>
        <text x={trackX0} y="34">01 · VARIANT</text>
        <text x={rowX} y="34">02 · RANKED CANDIDATES</text>
        <text x={srcX} y="34">03 · NAMED SOURCES</text>
      </g>
      <line x1={trackX0} y1="48" x2="1176" y2="48" stroke={RULE} strokeWidth="1" />

      <text x={trackX0} y="128" fontFamily={SANS} fontSize="40" fontWeight="600" letterSpacing="-1" fill={INK}>
        {variant.gene} <tspan fill={EOSIN}>{variant.short}</tspan>
      </text>
      <text x={trackX0} y="156" fontFamily={MONO} fontSize="13" fill={INK2}>
        {variant.hgvs} · {variant.context}
      </text>

      {variant.domain ? (
        <g>
          <rect x={px(variant.domain.start)} y={trackY - 8} width={Math.max(px(variant.domain.end) - px(variant.domain.start), 6)} height="16" fill={HEMA} fillOpacity="0.12" stroke={HEMA} strokeOpacity="0.35" />
          <text x={px(variant.domain.start)} y={trackY + 36} fontFamily={MONO} fontSize="11" fill={INK3}>
            {variant.domain.label} {variant.domain.start}–{variant.domain.end}
          </text>
        </g>
      ) : null}
      <line x1={trackX0} y1={trackY} x2={node.x} y2={trackY} stroke={INK} strokeWidth="1.5" />
      {[1, 50, 100, 150, variant.length].map((t) => (
        <g key={t}>
          <line x1={px(t)} y1={trackY - 4} x2={px(t)} y2={trackY + 4} stroke={INK3} />
          <text x={px(t)} y={trackY + 20} fontFamily={MONO} fontSize="10" fill={INK3} textAnchor="middle">
            {t}
          </text>
        </g>
      ))}
      <line x1={px(variant.position)} y1={trackY - 34} x2={px(variant.position)} y2={trackY} stroke={EOSIN} strokeWidth="2" />
      <circle cx={px(variant.position)} cy={trackY - 40} r="7" fill={EOSIN} />
      <circle cx={px(variant.position)} cy={trackY - 40} r="13" fill={EOSIN} fillOpacity="0.18" />
      <text x={px(variant.position) + 20} y={trackY - 36} fontFamily={MONO} fontSize="12" fill={INK}>
        residue {variant.position} of {variant.length}
      </text>
      <circle cx={node.x} cy={node.y} r="5" fill={HEMA} />

      {labels.map((r) => (
        <path
          key={`in-${r.name}`}
          d={`M${node.x} ${node.y} C ${node.x + 50} ${node.y}, ${rowX - 70} ${r.y - 6}, ${rowX - 14} ${r.y - 6}`}
          fill="none"
          stroke={HEMA}
          strokeWidth={0.8 + r.score * 1.2}
          strokeOpacity={0.25 + r.score * 0.6}
        />
      ))}

      {labels.map((r, i) => {
        const prevGroup = i > 0 ? labels[i - 1].group : null;
        return (
          <g key={r.name}>
            {r.group !== prevGroup ? (
              <text x={rowX} y={r.y - 34} fontFamily={SANS} fontSize="12" fontWeight="600" fill={HEMA}>
                {r.group}
              </text>
            ) : null}
            <text x={rowX} y={r.y} fontFamily={MONO} fontSize="12" fill={INK3}>
              {i + 1}
            </text>
            <text x={rowX + 24} y={r.y} fontFamily={SANS} fontSize="22" fontWeight="600" letterSpacing="-0.4" fill={INK}>
              {r.name}
            </text>
            <rect x={rowX + 220} y={r.y - 9} width="110" height="4" rx="2" fill={RULE} />
            <rect x={rowX + 220} y={r.y - 9} width={110 * r.score} height="4" rx="2" fill={INK} />
            <text x={rowX + 344} y={r.y} fontFamily={MONO} fontSize="15" fill={INK}>
              {r.score.toFixed(2)}
            </text>
            {(() => {
              let x = srcX;
              return r.sources.map((s, j) => {
                const w = chipWidth(s);
                const cx = x;
                x += w + 8;
                return (
                  <g key={s}>
                    {j === 0 ? <line x1={rowX + 392} y1={r.y - 6} x2={srcX - 10} y2={r.y - 6} stroke={HEMA} strokeOpacity="0.45" strokeDasharray="2 3" /> : null}
                    <rect x={cx} y={r.y - 20} width={w} height="26" rx="4" fill="#FFFFFF" stroke={RULE} />
                    <text x={cx + 9} y={r.y - 2.5} fontFamily={MONO} fontSize="12" fill={INK2}>
                      {s}
                    </text>
                  </g>
                );
              });
            })()}
          </g>
        );
      })}
    </svg>
  );
}

export function TraceFigureTall({ variant, rows }: { variant: TraceVariant; rows: TraceRow[] }) {
  const x0 = 16;
  const x1 = 300;
  const trackY = 120;
  const px = (n: number) => x0 + ((x1 - x0) * n) / variant.length;
  const top = 200;
  const step = 112;
  return (
    <svg viewBox="0 0 340 560" role="img" aria-labelledby="trace-m-title" className="block h-auto w-full">
      <title id="trace-m-title">{`${variant.gene} ${variant.short} traced to ${rows.map((r) => r.name).join(", ")} and their sources`}</title>
      <text x={x0} y="24" fontFamily={MONO} fontSize="10" letterSpacing="1.3" fill={INK3}>
        01 · VARIANT
      </text>
      <text x={x0} y="62" fontFamily={SANS} fontSize="30" fontWeight="600" letterSpacing="-0.8" fill={INK}>
        {variant.gene} <tspan fill={EOSIN}>{variant.short}</tspan>
      </text>
      <text x={x0} y="84" fontFamily={MONO} fontSize="11" fill={INK2}>
        {variant.hgvs} · {variant.context}
      </text>
      <line x1={x0} y1={trackY} x2={x1} y2={trackY} stroke={INK} strokeWidth="1.5" />
      <line x1={px(variant.position)} y1={trackY - 18} x2={px(variant.position)} y2={trackY} stroke={EOSIN} strokeWidth="2" />
      <circle cx={px(variant.position)} cy={trackY - 22} r="5.5" fill={EOSIN} />
      <text x={x0} y={trackY + 18} fontFamily={MONO} fontSize="9.5" fill={INK3}>
        1
      </text>
      <text x={x1} y={trackY + 18} fontFamily={MONO} fontSize="9.5" fill={INK3} textAnchor="end">
        {variant.length}
      </text>
      <text x={x0} y={top - 24} fontFamily={MONO} fontSize="10" letterSpacing="1.3" fill={INK3}>
        02 · RANKED · 03 · SOURCES
      </text>
      <line x1={x0 + 4} y1={top - 12} x2={x0 + 4} y2={top + step * (rows.length - 1)} stroke={HEMA} strokeOpacity="0.4" />
      {rows.map((r, i) => {
        const y = top + i * step;
        let cx = x0 + 22;
        return (
          <g key={r.name}>
            <circle cx={x0 + 4} cy={y - 6} r="3.5" fill={HEMA} fillOpacity={0.35 + r.score * 0.6} />
            <text x={x0 + 22} y={y} fontFamily={SANS} fontSize="19" fontWeight="600" fill={INK}>
              {r.name}
            </text>
            <text x={324} y={y} fontFamily={MONO} fontSize="14" fill={INK} textAnchor="end">
              {r.score.toFixed(2)}
            </text>
            <text x={x0 + 22} y={y + 20} fontFamily={SANS} fontSize="11.5" fill={HEMA}>
              {r.group}
            </text>
            {r.sources.map((s) => {
              const w = s.length * 6.4 + 14;
              const gx = cx;
              cx += w + 6;
              return (
                <g key={s}>
                  <rect x={gx} y={y + 32} width={w} height="22" rx="4" fill="#FFFFFF" stroke={RULE} />
                  <text x={gx + 7} y={y + 47} fontFamily={MONO} fontSize="10.5" fill={INK2}>
                    {s}
                  </text>
                </g>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}
