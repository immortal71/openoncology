import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { TrackMark, Wordmark } from "@/components/brand/marks";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";

export const metadata: Metadata = {
  title: "Palette lab | OpenOncology",
  robots: { index: false, follow: false },
};

type Palette = {
  id: string;
  name: string;
  idea: string;
  conflict: string;
  paper: string;
  surface: string;
  line: string;
  lineSoft: string;
  ink: string;
  ink2: string;
  ink3: string;
  muted: string;
  accent: string;
  accentTint: string;
  highlight: string;
  highlightTint: string;
};

const PALETTES: Palette[] = [
  {
    id: "A",
    name: "A · H&E on paper",
    idea: "Hematoxylin violet for actions, eosin pink only inside visualizations. The two stains on every tumor slide.",
    conflict: "Eosin pink sits close to the Failed red. Rule: eosin appears only inside visualizations, never next to status pills.",
    paper: "#FAF7F2",
    surface: "#FFFFFF",
    line: "#E8E1D6",
    lineSoft: "#F2ECE3",
    ink: "#1B1626",
    ink2: "#3F3A4B",
    ink3: "#5E586B",
    muted: "#6F6A7B",
    accent: "#3D2C8D",
    accentTint: "#ECE9F8",
    highlight: "#D9669A",
    highlightTint: "#FBE8F0",
  },
];

const STATUS = [
  { label: "Queued", bg: "#F2ECE3", fg: "#5E586B" },
  { label: "Analyzing", bg: "#FDF4E3", fg: "#8A4B08" },
  { label: "Complete", bg: "#E8F6EE", fg: "#0F6B3E" },
  { label: "Failed", bg: "#FDECEC", fg: "#A61B1B", alert: true },
];

function luminance(hex: string) {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function checks(p: Palette) {
  return [
    { label: "Body text on page", fg: p.ink, bg: p.paper, min: 4.5 },
    { label: "Secondary text on card", fg: p.ink3, bg: p.surface, min: 4.5 },
    { label: "Muted label on page", fg: p.muted, bg: p.paper, min: 4.5 },
    { label: "White text on accent button", fg: "#FFFFFF", bg: p.accent, min: 4.5 },
    { label: "Accent link on page", fg: p.accent, bg: p.paper, min: 4.5 },
    { label: "Accent text on accent tint", fg: p.accent, bg: p.accentTint, min: 4.5 },
    { label: "Highlight mark on card (graphic, 3:1)", fg: p.highlight, bg: p.surface, min: 3 },
    ...STATUS.map((s) => ({ label: `${s.label} pill text`, fg: s.fg, bg: s.bg, min: 4.5 })),
  ];
}

const mutations = DEMO_RESULTS.mutations;
const candidates = [...DEMO_REPURPOSING.candidates].sort((a, b) => (b.rank_score ?? 0) - (a.rank_score ?? 0));
const top = candidates[0];
const tierLabel: Record<string, string> = { fda_approved: "FDA approved", repurposed: "Repurposed" };

function VariantTrack({ p }: { p: Palette }) {
  const exons = [
    { x: 40, w: 46 },
    { x: 130, w: 70 },
    { x: 250, w: 38 },
    { x: 340, w: 90 },
    { x: 480, w: 60 },
  ];
  return (
    <svg viewBox="0 0 600 96" className="h-auto w-full" role="img" aria-label="Variant track: KRAS p.Gly12Cys highlighted">
      <rect x="20" y="58" width="560" height="2" rx="1" fill={p.line} />
      {exons.map((e) => (
        <rect key={e.x} x={e.x} y="50" width={e.w} height="18" rx="4" fill={p.ink} opacity="0.85" />
      ))}
      <rect x="146" y="22" width="6" height="56" rx="3" fill={p.highlight} />
      <circle cx="149" cy="22" r="11" fill={p.highlightTint} />
      <circle cx="149" cy="22" r="5" fill={p.highlight} />
      <text x="166" y="26" fontSize="13" fontWeight="600" fill={p.ink} fontFamily="var(--font-plex)">
        KRAS p.Gly12Cys
      </text>
      <text x="166" y="42" fontSize="11" fill={p.ink3} fontFamily="var(--font-mono)">
        OncoKB LEVEL_1 · targetable
      </text>
      <rect x="361" y="44" width="4" height="30" rx="2" fill={p.ink3} />
      <text x="372" y="40" fontSize="11" fill={p.ink3} fontFamily="var(--font-mono)">
        TP53 p.Arg175His · LEVEL_3B
      </text>
    </svg>
  );
}

function Pill({ bg, fg, children }: { bg: string; fg: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold" style={{ background: bg, color: fg }}>
      {children}
    </span>
  );
}

function PaletteScreen({ p }: { p: Palette }) {
  const card = { background: p.surface, borderColor: p.line };
  return (
    <section className="overflow-hidden rounded-2xl border" style={{ background: p.paper, borderColor: p.line, color: p.ink }}>
      <div className="flex flex-wrap items-center justify-between gap-4 border-b px-6 py-4" style={{ borderColor: p.line }}>
        <span className="flex items-center gap-2">
          <TrackMark variant="bold" size={22} ink={p.ink} accent={p.accent} />
          <Wordmark size={17} ink={p.ink} accent={p.accent} />
        </span>
        <span className="flex items-center gap-6 text-sm" style={{ color: p.ink2 }}>
          <span>Product</span>
          <span>Docs</span>
          <span>Community</span>
          <span className="rounded-full px-4 py-2 text-sm font-semibold text-white" style={{ background: p.accent }}>
            Request access
          </span>
        </span>
      </div>

      <div className="grid gap-8 px-6 py-10 lg:grid-cols-[1.1fr_1fr]">
        <div className="space-y-5">
          <span className="inline-flex rounded-full border px-3 py-1 text-xs font-medium" style={{ borderColor: p.line, color: p.ink3, background: p.surface }}>
            Research prototype · Open source
          </span>
          <h2 className="text-4xl font-semibold leading-tight tracking-tight">
            From tumor sequencing data to a <span style={{ color: p.accent }}>ranked</span>, evidence-linked report.
          </h2>
          <p className="max-w-md text-base leading-relaxed" style={{ color: p.ink2 }}>
            Upload a VCF. OpenOncology ranks approved drugs and repurposing candidates against the mutation profile and
            names the source behind every ranking. Oncologist review is required before any treatment decision.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full px-5 py-2.5 text-sm font-semibold text-white" style={{ background: p.accent }}>
              View the demo case
            </span>
            <span className="rounded-full border px-5 py-2.5 text-sm font-semibold" style={{ borderColor: p.line, color: p.ink, background: p.surface }}>
              Read the methods
            </span>
          </div>
          <div className="flex flex-wrap gap-2 pt-2">
            {STATUS.map((s) => (
              <Pill key={s.label} bg={s.bg} fg={s.fg}>
                {s.alert ? <AlertTriangle size={12} aria-hidden="true" /> : <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.fg }} />}
                {s.label}
              </Pill>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "Variants found", value: mutations.length },
              { label: "Ranked candidates", value: candidates.length },
              { label: "FDA-approved matches", value: candidates.filter((c) => c.drug_tier === "fda_approved").length },
            ].map((s) => (
              <div key={s.label} className="rounded-xl border p-4" style={card}>
                <div className="text-xs font-medium" style={{ color: p.muted }}>
                  {s.label}
                </div>
                <div className="mt-2 text-3xl font-semibold tabular-nums tracking-tight">{s.value}</div>
              </div>
            ))}
          </div>

          <div className="rounded-xl border p-4" style={card}>
            <div className="mb-1 flex items-center justify-between text-xs" style={{ color: p.muted }}>
              <span>Variant track</span>
              <span className="font-mono">Demo case · {DEMO_RESULTS.cancer_type}</span>
            </div>
            <VariantTrack p={p} />
          </div>

          <div className="rounded-xl border p-5" style={card}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs font-medium" style={{ color: p.muted }}>
                  Top ranked
                </div>
                <div className="mt-1 text-xl font-semibold tracking-tight">{top.drug_name}</div>
              </div>
              <Pill bg={p.accentTint} fg={p.accent}>
                {tierLabel[top.drug_tier ?? ""] ?? top.drug_tier}
              </Pill>
            </div>
            <p className="mt-2 text-sm leading-relaxed" style={{ color: p.ink2 }}>
              {top.mechanism}
            </p>
            <div className="mt-3 flex items-center gap-3">
              <div className="h-1.5 flex-1 rounded-full" style={{ background: p.lineSoft }}>
                <div className="h-1.5 rounded-full" style={{ width: `${(top.rank_score ?? 0) * 100}%`, background: p.accent }} />
              </div>
              <span className="font-mono text-xs tabular-nums" style={{ color: p.ink3 }}>
                {(top.rank_score ?? 0).toFixed(3)}
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {top.evidence_sources.map((s) => (
                <span key={s} className="rounded-md border px-2 py-0.5 font-mono text-[11px]" style={{ borderColor: p.line, color: p.ink3 }}>
                  {s}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="px-6 pb-8">
        <div className="overflow-x-auto rounded-xl border" style={card}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-[0.06em]" style={{ color: p.muted }}>
                <th className="px-4 py-3 font-medium">Drug</th>
                <th className="px-4 py-3 font-medium">ChEMBL</th>
                <th className="px-4 py-3 font-medium">Tier</th>
                <th className="px-4 py-3 font-medium">Sources</th>
                <th className="px-4 py-3 text-right font-medium">Rank score</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c) => (
                <tr key={c.chembl_id} className="border-t" style={{ borderColor: p.lineSoft }}>
                  <td className="px-4 py-3 font-medium">{c.drug_name}</td>
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: p.ink3 }}>
                    {c.chembl_id}
                  </td>
                  <td className="px-4 py-3">
                    <Pill bg={c.drug_tier === "fda_approved" ? p.accentTint : p.lineSoft} fg={c.drug_tier === "fda_approved" ? p.accent : p.ink2}>
                      {tierLabel[c.drug_tier] ?? c.drug_tier}
                    </Pill>
                  </td>
                  <td className="px-4 py-3" style={{ color: p.ink2 }}>
                    {c.evidence_sources.length}
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums">{(c.rank_score ?? 0).toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export default function PaletteLabPage() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <main className="min-h-screen bg-[#F4F2EE] px-5 py-12 text-[#16181D] md:px-12">
      <div className="mx-auto max-w-6xl space-y-14">
        <header className="space-y-3">
          <p className="font-mono text-xs uppercase tracking-[0.12em] text-[#5E5A54]">Internal · not shipped</p>
          <h1 className="text-4xl font-semibold tracking-tight">Palette lab</h1>
          <p className="max-w-2xl leading-relaxed text-[#3F3C37]">
            Palette A, H&amp;E on paper, locked on 2026-11-09. Built from the real KRAS G12C demo case, with its contrast
            checks and its one known color conflict. The tokens live in globals.css as --oo-*.
          </p>
        </header>

        {PALETTES.map((p) => (
          <div key={p.id} className="space-y-5">
            <div className="space-y-1">
              <h2 className="text-2xl font-semibold tracking-tight">{p.name}</h2>
              <p className="text-[#3F3C37]">{p.idea}</p>
            </div>

            <PaletteScreen p={p} />

            <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
              <div className="rounded-xl border border-[#E6E3DE] bg-white p-5">
                <div className="text-sm font-semibold">Known conflict</div>
                <p className="mt-1 text-sm leading-relaxed text-[#3F3C37]">{p.conflict}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {[p.paper, p.surface, p.line, p.ink, p.ink3, p.muted, p.accent, p.accentTint, p.highlight].map((c, i) => (
                    <span key={`${c}-${i}`} className="flex items-center gap-1.5 font-mono text-[11px] text-[#5E5A54]">
                      <span className="h-5 w-5 rounded border border-[#00000014]" style={{ background: c }} />
                      {c}
                    </span>
                  ))}
                </div>
              </div>

              <div className="overflow-x-auto rounded-xl border border-[#E6E3DE] bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-[0.06em] text-[#5E5A54]">
                      <th className="px-4 py-2.5 font-medium">Contrast check</th>
                      <th className="px-4 py-2.5 font-medium">Sample</th>
                      <th className="px-4 py-2.5 text-right font-medium">Ratio</th>
                      <th className="px-4 py-2.5 text-right font-medium">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {checks(p).map((c) => {
                      const r = contrast(c.fg, c.bg);
                      const pass = r >= c.min;
                      return (
                        <tr key={c.label} className="border-t border-[#F1EFEB]">
                          <td className="px-4 py-2">{c.label}</td>
                          <td className="px-4 py-2">
                            <span className="rounded px-2 py-0.5 text-xs font-semibold" style={{ color: c.fg, background: c.bg }}>
                              Aa
                            </span>
                          </td>
                          <td className="px-4 py-2 text-right font-mono tabular-nums">{r.toFixed(2)}</td>
                          <td className={`px-4 py-2 text-right text-xs font-semibold ${pass ? "text-[#0F6B3E]" : "text-[#A61B1B]"}`}>
                            {pass ? `Pass ≥${c.min}` : `Fail <${c.min}`}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
