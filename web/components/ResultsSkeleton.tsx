"use client";

import { atlasSans } from "@/lib/atlas-font";
import { line } from "@/components/workspace/parts";

export default function ResultsSkeleton() {
  return (
    <main className={`${atlasSans.variable} min-h-screen bg-[#F7F5F0] py-8 px-4 font-[family-name:var(--font-atlas)]`}>
      <div className="mx-auto max-w-5xl animate-pulse space-y-6">

        {/* Patient Summary skeleton */}
        <section className={`rounded-[12px] border ${line} bg-white p-6`}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="h-7 w-48 rounded-[8px] bg-[#ECEAEF]" />
              <div className="h-4 w-64 rounded bg-[#ECEAEF]" />
              <div className="h-4 w-56 rounded bg-[#ECEAEF]" />
            </div>
            <div className="flex gap-3">
              <div className="h-9 w-52 rounded-[8px] bg-[#ECEAEF]" />
              <div className="h-9 w-44 rounded-[8px] bg-[#ECEAEF]" />
            </div>
          </div>
          <div className="mt-4 space-y-2">
            <div className="h-4 w-full rounded bg-[#ECEAEF]" />
            <div className="h-4 w-5/6 rounded bg-[#ECEAEF]" />
            <div className="h-4 w-4/6 rounded bg-[#ECEAEF]" />
          </div>
          <div className="mt-4 space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 w-full rounded-[8px] bg-[#FAF9F7]" />
            ))}
          </div>
        </section>

        {/* Mutations table skeleton */}
        <section className={`rounded-[12px] border ${line} bg-white p-6`}>
          <div className="mb-4 h-6 w-28 rounded bg-[#ECEAEF]" />
          <div className="space-y-2">
            <div className="h-4 w-full rounded bg-[#ECEAEF]" />
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-10 w-full rounded bg-[#FAF9F7]" />
            ))}
          </div>
        </section>

        {/* Drug candidates skeleton */}
        <section className={`rounded-[12px] border ${line} bg-white p-6`}>
          <div className="mb-4 h-6 w-52 rounded bg-[#ECEAEF]" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className={`space-y-2 rounded-[10px] border ${line} p-3`}>
                <div className="h-5 w-40 rounded bg-[#ECEAEF]" />
                <div className="h-4 w-72 rounded bg-[#ECEAEF]" />
                <div className="h-4 w-56 rounded bg-[#ECEAEF]" />
                <div className="mt-1 flex gap-2">
                  <div className="h-5 w-20 rounded-full bg-[#ECEAEF]" />
                  <div className="h-5 w-24 rounded-full bg-[#ECEAEF]" />
                </div>
              </div>
            ))}
          </div>
        </section>

      </div>
    </main>
  );
}
