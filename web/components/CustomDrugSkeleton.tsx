"use client";

export default function CustomDrugSkeleton() {
  return (
    <main className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-5xl mx-auto space-y-8 animate-pulse">

        {/* Header skeleton */}
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div className="space-y-2">
            <div className="h-4 w-20 bg-slate-200 rounded" />
            <div className="h-8 w-72 bg-slate-200 rounded-lg" />
            <div className="h-4 w-96 bg-slate-200 rounded" />
          </div>
          <div className="h-10 w-48 bg-slate-200 rounded-xl" />
        </div>

        {/* Stage tracker skeleton */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="h-5 w-40 bg-slate-200 rounded mb-1" />
          <div className="h-4 w-64 bg-slate-200 rounded" />
          <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="rounded-xl border border-gray-200 p-4 space-y-2">
                <div className="h-4 w-24 bg-slate-200 rounded" />
                <div className="h-3 w-full bg-slate-100 rounded" />
              </div>
            ))}
          </div>
        </section>

        {/* Lead Compounds skeleton */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="h-6 w-40 bg-slate-200 rounded mb-4" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="border border-gray-200 rounded-xl p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="h-5 w-28 bg-slate-200 rounded" />
                  <div className="h-5 w-20 bg-slate-200 rounded-full" />
                </div>
                <div className="h-3 w-24 bg-slate-100 rounded" />
                <div className="h-3 w-full bg-slate-100 rounded" />
                <div className="grid grid-cols-2 gap-x-3 gap-y-1 mt-2">
                  {[1, 2, 3, 4, 5, 6].map((j) => (
                    <div key={j} className="h-3 w-full bg-slate-100 rounded" />
                  ))}
                </div>
                <div className="flex flex-wrap gap-2 mt-3">
                  {[1, 2].map((j) => (
                    <div key={j} className="h-5 w-16 bg-slate-100 rounded-full" />
                  ))}
                </div>
                <div className="h-4 w-full bg-slate-100 rounded mt-2" />
              </div>
            ))}
          </div>
        </section>

        {/* De Novo Candidates skeleton */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="h-6 w-56 bg-slate-200 rounded mb-4" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1, 2].map((i) => (
              <div key={i} className="rounded-xl border border-gray-200 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="h-5 w-32 bg-slate-200 rounded" />
                  <div className="h-5 w-16 bg-slate-200 rounded-full" />
                </div>
                <div className="h-3 w-40 bg-slate-100 rounded" />
                <div className="h-3 w-full bg-slate-100 rounded" />
                <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                  {[1, 2, 3, 4, 5].map((j) => (
                    <div key={j} className="h-3 w-full bg-slate-100 rounded" />
                  ))}
                </div>
                <div className="h-4 w-full bg-slate-100 rounded mt-2" />
              </div>
            ))}
          </div>
        </section>

        {/* Scaffold & ADMET skeleton */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="h-6 w-48 bg-slate-200 rounded mb-3" />
          <div className="grid md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <div className="h-4 w-28 bg-slate-200 rounded" />
              {[1, 2, 3].map((j) => (
                <div key={j} className="h-4 w-full bg-slate-100 rounded" />
              ))}
            </div>
            <div className="space-y-2">
              <div className="h-4 w-24 bg-slate-200 rounded" />
              {[1, 2, 3].map((j) => (
                <div key={j} className="h-4 w-full bg-slate-100 rounded" />
              ))}
            </div>
          </div>
          <div className="mt-4 h-16 w-full bg-amber-50 rounded-xl border border-amber-100" />
        </section>

        {/* Timeline skeleton */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="h-6 w-44 bg-slate-200 rounded mb-4" />
          <div className="space-y-4 ml-8">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-1">
                <div className="h-4 w-32 bg-slate-200 rounded" />
                <div className="h-3 w-20 bg-slate-100 rounded" />
              </div>
            ))}
          </div>
        </section>

        {/* Next Steps skeleton */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="h-6 w-48 bg-slate-200 rounded mb-3" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-4 w-full bg-slate-100 rounded" />
            ))}
          </div>
        </section>

      </div>
    </main>
  );
}
