'use client';

import { useState, useEffect } from 'react';

interface Study {
  study_id: string;
  name: string;
  cancer_type: string | null;
  cancer_type_label: string | null;
  sample_count: number;
  data_types: string[] | null;
  reference_genome: string | null;
  pmid: string | null;
  source: string | null;
}

interface StudiesResponse {
  total: number;
  studies: Study[];
}

export default function ExplorePage() {
  const [studies, setStudies] = useState<Study[]>([]);
  const [filtered, setFiltered] = useState<Study[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [cancerTypeFilter, setCancerTypeFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');

  useEffect(() => {
    const params = new URLSearchParams();
    if (cancerTypeFilter) params.append('cancer_type', cancerTypeFilter);
    if (sourceFilter) params.append('source', sourceFilter);

    setLoading(true);
    fetch(`/api/cohorts/studies?${params.toString()}`)
      .then((r) => r.json())
      .then((data: StudiesResponse) => {
        setStudies(data.studies ?? []);
        setFiltered(data.studies ?? []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [cancerTypeFilter, sourceFilter]);

  useEffect(() => {
    if (!search.trim()) {
      setFiltered(studies);
    } else {
      const q = search.toLowerCase();
      setFiltered(
        studies.filter(
          (s) =>
            s.name.toLowerCase().includes(q) ||
            (s.cancer_type_label ?? '').toLowerCase().includes(q) ||
            s.study_id.toLowerCase().includes(q),
        ),
      );
    }
  }, [search, studies]);

  const uniqueSources = Array.from(new Set(studies.map((s) => s.source).filter(Boolean)));
  const uniqueCancerTypes = Array.from(
    new Set(studies.map((s) => s.cancer_type).filter(Boolean)),
  ).sort();

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Study Explorer</h1>
        <p className="mt-2 text-gray-600">
          Browse public cancer genomics cohorts. Click a study to explore mutations, OncoPrint,
          and survival data.
        </p>
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap gap-4">
        <input
          type="text"
          placeholder="Search studies…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-md border border-gray-300 px-4 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-64"
          aria-label="Search studies"
        />

        <select
          value={cancerTypeFilter}
          onChange={(e) => setCancerTypeFilter(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          aria-label="Filter by cancer type"
        >
          <option value="">All cancer types</option>
          {uniqueCancerTypes.map((ct) => (
            <option key={ct!} value={ct!}>
              {ct}
            </option>
          ))}
        </select>

        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          aria-label="Filter by data source"
        >
          <option value="">All sources</option>
          {uniqueSources.map((src) => (
            <option key={src!} value={src!}>
              {src}
            </option>
          ))}
        </select>

        <span className="self-center text-sm text-gray-500">
          {filtered.length} {filtered.length === 1 ? 'study' : 'studies'}
        </span>
      </div>

      {/* Content */}
      {loading && (
        <div className="flex justify-center py-20">
          <div className="animate-spin h-10 w-10 rounded-full border-4 border-blue-600 border-t-transparent" role="status" aria-label="Loading" />
        </div>
      )}

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-4 text-red-700" role="alert">
          Failed to load studies: {error}
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="text-center py-20 text-gray-500">No studies match your filters.</div>
      )}

      {!loading && !error && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {filtered.map((study) => (
            <StudyCard key={study.study_id} study={study} />
          ))}
        </div>
      )}
    </main>
  );
}

function StudyCard({ study }: { study: Study }) {
  return (
    <a
      href={`/explore/${study.study_id}`}
      className="block rounded-xl border border-gray-200 bg-white p-5 shadow-sm hover:shadow-md hover:border-blue-400 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500"
      aria-label={`Open study: ${study.name}`}
    >
      {/* Source badge */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <span
          className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${badgeColors(study.source)}`}
        >
          {study.source ?? 'Unknown'}
        </span>
        {study.pmid && (
          <a
            href={`https://pubmed.ncbi.nlm.nih.gov/${study.pmid}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-xs text-blue-600 hover:underline"
            aria-label={`PubMed ID ${study.pmid}`}
          >
            PMID: {study.pmid}
          </a>
        )}
      </div>

      <h2 className="text-base font-semibold text-gray-900 mb-1 line-clamp-2">{study.name}</h2>
      <p className="text-sm text-gray-500 mb-3">{study.cancer_type_label ?? study.cancer_type ?? '—'}</p>

      <div className="flex flex-wrap gap-2 text-xs text-gray-600">
        <span className="rounded bg-gray-100 px-2 py-0.5">
          {study.sample_count.toLocaleString()} samples
        </span>
        {(study.data_types ?? []).map((dt) => (
          <span key={dt} className="rounded bg-blue-50 text-blue-700 px-2 py-0.5">
            {dt}
          </span>
        ))}
        {study.reference_genome && (
          <span className="rounded bg-gray-100 px-2 py-0.5">{study.reference_genome}</span>
        )}
      </div>
    </a>
  );
}

function badgeColors(source: string | null): string {
  switch (source?.toUpperCase()) {
    case 'TCGA':
      return 'bg-blue-100 text-blue-800';
    case 'ICGC':
      return 'bg-purple-100 text-purple-800';
    case 'CCLE':
      return 'bg-green-100 text-green-800';
    default:
      return 'bg-gray-100 text-gray-700';
  }
}
