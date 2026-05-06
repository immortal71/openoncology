'use client';

import { useState, useEffect, useRef } from 'react';

interface TopMutation {
  protein_change: string;
  count: number;
  is_hotspot: boolean;
}

interface ClassificationCount {
  classification: string;
  count: number;
}

interface GeneSummary {
  gene: string;
  total_mutations: number;
  top_protein_changes: TopMutation[];
  variant_classification_breakdown: ClassificationCount[];
  studies: { study_id: string; name: string; cancer_type_label: string | null; sample_count: number }[];
}

interface LollipopData {
  gene: string;
  lollipops: LollipopPoint[];
  protein_domains: Domain[];
  total_mutations_plotted: number;
}

interface LollipopPoint {
  protein_change: string;
  position: number;
  total_count: number;
  classifications: Record<string, number>;
  is_hotspot: boolean;
  hotspot_n_samples: number | null;
}

interface Domain {
  name: string;
  start: number;
  end: number;
  color: string;
}

const CLASSIFICATION_COLORS: Record<string, string> = {
  Missense_Mutation: '#4dabf7',
  Nonsense_Mutation: '#f03e3e',
  Frame_Shift_Del: '#ff922b',
  Frame_Shift_Ins: '#ffd43b',
  Splice_Site: '#94d82d',
  In_Frame_Del: '#74c0fc',
  In_Frame_Ins: '#a9e34b',
  default: '#adb5bd',
};

function classColor(cls: string): string {
  return CLASSIFICATION_COLORS[cls] ?? CLASSIFICATION_COLORS['default'];
}

export default function GenePage({ params }: { params: { symbol: string } }) {
  const gene = params.symbol.toUpperCase();
  const [summary, setSummary] = useState<GeneSummary | null>(null);
  const [lollipop, setLollipop] = useState<LollipopData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'lollipop' | 'studies'>('overview');

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`/api/cohorts/gene-summary?gene=${gene}`).then((r) => r.json()),
      fetch(`/api/viz/lollipop/${gene}`).then((r) => r.json()),
    ])
      .then(([summaryData, lollipopData]) => {
        setSummary(summaryData);
        setLollipop(lollipopData);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [gene]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <div className="animate-spin h-10 w-10 rounded-full border-4 border-blue-600 border-t-transparent" role="status" aria-label="Loading" />
      </main>
    );
  }

  if (error || !summary) {
    return (
      <main className="p-6">
        <div className="rounded-md bg-red-50 border border-red-200 p-4 text-red-700" role="alert">
          Failed to load gene data: {error ?? 'Unknown error'}
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Hero */}
      <div className="bg-white border-b border-gray-200 px-6 py-6">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 font-mono">{gene}</h1>
              <p className="text-gray-500 text-sm mt-1">
                {summary.total_mutations.toLocaleString()} mutations across {summary.studies.length}{' '}
                {summary.studies.length === 1 ? 'study' : 'studies'}
              </p>
            </div>
            <a
              href={`https://oncokb.org/gene/${gene}`}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto text-sm text-blue-600 hover:underline"
            >
              View on OncoKB ↗
            </a>
          </div>

          {/* Tabs */}
          <nav className="flex gap-1 mt-5" aria-label="Gene data sections">
            {(['overview', 'lollipop', 'studies'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  activeTab === tab
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {tab === 'overview' ? 'Overview' : tab === 'lollipop' ? 'Lollipop Plot' : 'Studies'}
              </button>
            ))}
          </nav>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {activeTab === 'overview' && <OverviewTab summary={summary} />}
        {activeTab === 'lollipop' && lollipop && <LollipopTab data={lollipop} />}
        {activeTab === 'studies' && <StudiesTab studies={summary.studies} />}
      </div>
    </main>
  );
}

/* ── Overview tab ─────────────────────────────────────────────────────────── */
function OverviewTab({ summary }: { summary: GeneSummary }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Top protein changes */}
      <section aria-labelledby="top-mutations-heading">
        <h2 id="top-mutations-heading" className="text-lg font-semibold text-gray-800 mb-3">
          Top Mutations
        </h2>
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <table className="min-w-full text-sm" role="table">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-4 py-2 text-left text-gray-600 font-medium">Change</th>
                <th scope="col" className="px-4 py-2 text-right text-gray-600 font-medium">Count</th>
                <th scope="col" className="px-4 py-2 text-center text-gray-600 font-medium">Hotspot</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {summary.top_protein_changes.slice(0, 15).map((m) => (
                <tr key={m.protein_change} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-gray-900">{m.protein_change}</td>
                  <td className="px-4 py-2 text-right text-gray-700">{m.count.toLocaleString()}</td>
                  <td className="px-4 py-2 text-center">
                    {m.is_hotspot ? (
                      <span className="inline-block rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                        🔥 Hotspot
                      </span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Variant classification breakdown */}
      <section aria-labelledby="classifications-heading">
        <h2 id="classifications-heading" className="text-lg font-semibold text-gray-800 mb-3">
          Variant Classifications
        </h2>
        <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm space-y-3">
          {summary.variant_classification_breakdown.map((c) => {
            const pct = summary.total_mutations
              ? Math.round((c.count / summary.total_mutations) * 100)
              : 0;
            return (
              <div key={c.classification}>
                <div className="flex justify-between text-sm mb-0.5">
                  <span className="text-gray-700">{c.classification}</span>
                  <span className="text-gray-500">
                    {c.count.toLocaleString()} ({pct}%)
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-gray-100" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
                  <div
                    className="h-2 rounded-full transition-all"
                    style={{ width: `${pct}%`, backgroundColor: classColor(c.classification) }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

/* ── Lollipop tab ─────────────────────────────────────────────────────────── */
function LollipopTab({ data }: { data: LollipopData }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const WIDTH = 900;
  const HEIGHT = 260;
  const PAD = { top: 20, right: 20, bottom: 60, left: 50 };

  const lollipops = data.lollipops.filter((l) => l.position !== null);
  const maxPos = Math.max(...lollipops.map((l) => l.position), 500);
  const maxCount = Math.max(...lollipops.map((l) => l.total_count), 1);
  const domainY = HEIGHT - PAD.bottom + 10;
  const lineY = domainY - 5;
  const plotW = WIDTH - PAD.left - PAD.right;
  const plotH = lineY - PAD.top;

  const toX = (pos: number) => PAD.left + (pos / maxPos) * plotW;
  const toY = (count: number) => PAD.top + plotH - (count / maxCount) * plotH;

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-800 mb-4">
        Mutation Lollipop — {data.gene}
        <span className="ml-2 text-sm text-gray-500 font-normal">
          {data.total_mutations_plotted.toLocaleString()} mutations
        </span>
      </h2>

      <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm overflow-x-auto">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="w-full"
          aria-label={`Lollipop plot for ${data.gene}`}
          role="img"
        >
          {/* Protein backbone */}
          <line x1={PAD.left} y1={lineY} x2={PAD.left + plotW} y2={lineY} stroke="#adb5bd" strokeWidth={3} />

          {/* Protein domains */}
          {data.protein_domains.map((d) => (
            <g key={d.name}>
              <rect
                x={toX(d.start)}
                y={domainY - 10}
                width={toX(d.end) - toX(d.start)}
                height={20}
                fill={d.color}
                rx={3}
                opacity={0.8}
              />
              <text
                x={(toX(d.start) + toX(d.end)) / 2}
                y={domainY + 4}
                textAnchor="middle"
                fontSize={9}
                fill="white"
                fontWeight="bold"
              >
                {d.name.length > 12 ? d.name.slice(0, 12) + '…' : d.name}
              </text>
            </g>
          ))}

          {/* Lollipops */}
          {lollipops.map((l) => {
            const x = toX(l.position);
            const y = toY(l.total_count);
            const topClass = Object.entries(l.classifications).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'default';
            const fill = classColor(topClass);
            const radius = Math.max(4, Math.min(14, 3 + Math.log2(l.total_count + 1) * 2));
            return (
              <g key={l.protein_change}>
                <line x1={x} y1={lineY} x2={x} y2={y + radius} stroke="#ced4da" strokeWidth={1} />
                <circle
                  cx={x}
                  cy={y}
                  r={radius}
                  fill={fill}
                  stroke={l.is_hotspot ? '#f03e3e' : 'white'}
                  strokeWidth={l.is_hotspot ? 2.5 : 1}
                  role="img"
                  aria-label={`${l.protein_change}: ${l.total_count} samples${l.is_hotspot ? ' (hotspot)' : ''}`}
                >
                  <title>{`${l.protein_change}\n${l.total_count} samples${l.is_hotspot ? '\n🔥 Cancer Hotspot' : ''}`}</title>
                </circle>
              </g>
            );
          })}

          {/* Y-axis label */}
          <text x={PAD.left - 10} y={PAD.top + plotH / 2} textAnchor="middle" fontSize={11} fill="#6c757d" transform={`rotate(-90, ${PAD.left - 35}, ${PAD.top + plotH / 2})`}>
            # Samples
          </text>

          {/* X-axis label */}
          <text x={PAD.left + plotW / 2} y={HEIGHT - 5} textAnchor="middle" fontSize={11} fill="#6c757d">
            Protein Position (aa)
          </text>
        </svg>

        {/* Legend */}
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-gray-600">
          {Object.entries(CLASSIFICATION_COLORS)
            .filter(([k]) => k !== 'default')
            .map(([cls, color]) => (
              <span key={cls} className="flex items-center gap-1">
                <span className="inline-block w-3 h-3 rounded-full" style={{ background: color }} />
                {cls.replace(/_/g, ' ')}
              </span>
            ))}
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 rounded-full bg-transparent border-2 border-red-500" />
            Cancer Hotspot
          </span>
        </div>
      </div>
    </div>
  );
}

/* ── Studies tab ──────────────────────────────────────────────────────────── */
function StudiesTab({ studies }: { studies: GeneSummary['studies'] }) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-800 mb-4">
        Studies Containing {studies[0] ? 'this Gene' : 'Gene'}
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {studies.map((s) => (
          <a
            key={s.study_id}
            href={`/explore/${s.study_id}`}
            className="block rounded-xl border border-gray-200 bg-white p-4 shadow-sm hover:shadow-md hover:border-blue-400 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label={`Open study: ${s.name}`}
          >
            <p className="font-medium text-gray-900 text-sm line-clamp-2">{s.name}</p>
            <p className="text-gray-500 text-xs mt-1">{s.cancer_type_label ?? '—'}</p>
            <p className="text-gray-400 text-xs mt-2">{s.sample_count.toLocaleString()} samples</p>
          </a>
        ))}
        {studies.length === 0 && (
          <p className="text-gray-500 col-span-3">No studies found for this gene.</p>
        )}
      </div>
    </div>
  );
}
