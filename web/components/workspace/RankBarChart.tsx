"use client";

import { useState } from "react";

type Bar = { label: string; value: number };

const CHART_HEIGHT = 160;

export default function RankBarChart({ bars, light = false }: { bars: Bar[]; light?: boolean }) {
  const [hovered, setHovered] = useState<string | null>(null);

  const borderClass = light ? "" : "border-white/10";
  const borderStyle = light ? { borderColor: "#E4E2DB" } : undefined;
  const labelColor = light ? "#8A8D86" : undefined;
  const labelClass = light ? "" : "text-neutral-muted";
  const valueColor = light ? "#16181D" : undefined;
  const valueClass = light ? "" : "text-neutral-heading";
  const barIdle = light ? "#C8CBC2" : "#8B8D89";
  const barActive = light ? "#16181D" : "#EDEBE4";

  if (bars.length === 0) {
    return (
      <p className="text-sm" style={{ color: labelColor }}>
        No candidates to chart.
      </p>
    );
  }

  return (
    <div>
      <div
        className={`flex items-end gap-3 border-b pb-0 ${borderClass}`}
        style={{ height: CHART_HEIGHT, ...borderStyle }}
      >
        {bars.map((b) => {
          const barHeight = Math.max(4, b.value * CHART_HEIGHT);
          const isHovered = hovered === b.label;
          return (
            <div
              key={b.label}
              className="flex-1 flex flex-col items-center justify-end h-full relative"
              onMouseEnter={() => setHovered(b.label)}
              onMouseLeave={() => setHovered(null)}
            >
              {isHovered && (
                <span
                  className={`absolute -top-6 font-mono text-[10px] whitespace-nowrap ${valueClass}`}
                  style={valueColor ? { color: valueColor } : undefined}
                >
                  {b.value.toFixed(2)}
                </span>
              )}
              <div
                className="w-full max-w-[24px] rounded-t-[4px] transition-colors"
                style={{
                  height: barHeight,
                  backgroundColor: isHovered ? barActive : barIdle,
                }}
              />
            </div>
          );
        })}
      </div>
      <div className="flex gap-3 mt-2">
        {bars.map((b) => (
          <span
            key={b.label}
            className={`flex-1 text-center font-mono text-[9px] truncate ${labelClass}`}
            style={labelColor ? { color: labelColor } : undefined}
            title={b.label}
          >
            {b.label}
          </span>
        ))}
      </div>
      <p
        className={`text-center font-mono text-[10px] mt-1 ${labelClass}`}
        style={labelColor ? { color: labelColor } : undefined}
      >
        rank_score by drug
      </p>
    </div>
  );
}
