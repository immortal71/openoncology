'use client';

import { useState, useEffect, useCallback } from 'react';
import api from '@/lib/api';

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

export default function ExplorePage() {
  const [studies, setStudies] = useState<Study[]>([]);
  const [filtered, setFiltered] = useState<Study[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [cancerTypeFilter, setCancerTypeFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');

  const loadStudies = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .getStudies({
        cancer_type: cancerTypeFilter || undefined,
        source: sourceFilter || undefined,
      })
      .then((data) => {
        setStudies(data.studies ?? []);
        setFiltered(data.studies ?? []);
      })
      .catch((err: Error) => {
        setError(err.message ?? 'Failed to load studies');
      })
      .finally(() => setLoading(false));
  }, [cancerTypeFilter, sourceFilter]);

  useEffect(() => {
    loadStudies();
  }, [loadStudies]);

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
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="animate-pulse rounded-xl border border-gray-200 bg-white p-5 h-44">
              <div className="flex justify-between mb-3">
                <div className="h-5 w-16 rounded-full bg-gray-200" />
                <div className="h-4 w-20 rounded bg-gray-100" />
              </div>
              <div className="h-4 w-3/4 rounded bg-gray-200 mb-2" />
              <div className="h-3 w-1/2 rounded bg-gray-100 mb-4" />
              <div className="flex gap-2">
                <div className="h-5 w-20 rounded-full bg-gray-100" />
                <div className="h-5 w-14 rounded-full bg-blue-50" />
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 flex flex-col sm:flex-row items-start sm:items-center gap-4" role="alert">
          <div className="flex-1">
            <p className="font-semibold text-red-800 mb-1">Failed to load studies</p>
            <p className="text-sm text-red-700">{error}</p>
          </div>
          <button
            onClick={loadStudies}
            className="shrink-0 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <svg className="mb-4 h-12 w-12 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
          </svg>
          <p className="text-base font-medium text-gray-500">No studies found</p>
          {(search || cancerTypeFilter || sourceFilter) && (
            <p className="mt-1 text-sm text-gray-400">
              Try clearing your filters or search term.
            </p>
          )}
          {(cancerTypeFilter || sourceFilter) && (
            <button
              onClick={() => { setCancerTypeFilter(''); setSourceFilter(''); setSearch(''); }}
              className="mt-4 rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
            >
              Clear filters
            </button>
          )}
        </div>
      )}

      {!loading && !error && filtered.length > 0 && (
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
