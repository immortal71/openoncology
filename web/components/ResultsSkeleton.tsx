"use client";

export default function ResultsSkeleton() {
  return (
    <main className="min-h-screen py-8 px-4">
      <div className="max-w-5xl mx-auto space-y-6 animate-pulse">

        {/* Patient Summary skeleton */}
        <section className="clinical-surface p-6 border-t-4 border-cyan-200">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="space-y-2">
              <div className="h-7 w-48 bg-slate-200 dark:bg-slate-700 rounded-lg" />
              <div className="h-4 w-64 bg-slate-200 dark:bg-slate-700 rounded" />
              <div className="h-4 w-56 bg-slate-200 dark:bg-slate-700 rounded" />
            </div>
            <div className="flex gap-3">
              <div className="h-9 w-52 bg-slate-200 dark:bg-slate-700 rounded-xl" />
              <div className="h-9 w-44 bg-slate-200 dark:bg-slate-700 rounded-xl" />
            </div>
          </div>
          <div className="mt-4 space-y-2">
            <div className="h-4 w-full bg-slate-200 dark:bg-slate-700 rounded" />
            <div className="h-4 w-5/6 bg-slate-200 dark:bg-slate-700 rounded" />
            <div className="h-4 w-4/6 bg-slate-200 dark:bg-slate-700 rounded" />
          </div>
          <div className="mt-4 space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 w-full bg-slate-100 dark:bg-slate-800 rounded-lg" />
            ))}
          </div>
        </section>

        {/* Mutations table skeleton */}
        <section className="clinical-surface p-6">
          <div className="h-6 w-28 bg-slate-200 dark:bg-slate-700 rounded mb-4" />
          <div className="space-y-2">
            <div className="h-4 w-full bg-slate-200 dark:bg-slate-700 rounded" />
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-10 w-full bg-slate-100 dark:bg-slate-800 rounded" />
            ))}
          </div>
        </section>

        {/* Drug candidates skeleton */}
        <section className="clinical-surface p-6">
          <div className="h-6 w-52 bg-slate-200 dark:bg-slate-700 rounded mb-4" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="border border-slate-200 dark:border-slate-700 rounded-lg p-3 space-y-2">
                <div className="h-5 w-40 bg-slate-200 dark:bg-slate-700 rounded" />
                <div className="h-4 w-72 bg-slate-200 dark:bg-slate-700 rounded" />
                <div className="h-4 w-56 bg-slate-200 dark:bg-slate-700 rounded" />
                <div className="flex gap-2 mt-1">
                  <div className="h-5 w-20 bg-slate-200 dark:bg-slate-700 rounded-full" />
                  <div className="h-5 w-24 bg-slate-200 dark:bg-slate-700 rounded-full" />
                </div>
              </div>
            ))}
          </div>
        </section>

      </div>
    </main>
  );
}
