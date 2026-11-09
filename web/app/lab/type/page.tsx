import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { displayFont } from "@/lib/display-font";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";

export const metadata: Metadata = {
  title: "Type lab | OpenOncology",
  robots: { index: false, follow: false },
};

const SEQUENCE = "GTTGGAGCTGGTGGCGTAGGCAAGAGTGCC";
const VARIANT_INDEX = 9;

const candidates = [...DEMO_REPURPOSING.candidates].sort((a, b) => (b.rank_score ?? 0) - (a.rank_score ?? 0));

export default function TypeLabPage() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <main className={`${displayFont.variable} min-h-screen bg-oo-paper px-5 py-12 text-oo-ink md:px-12`}>
      <div className="mx-auto max-w-5xl space-y-14">
        <header className="space-y-3">
          <p className="font-mono text-xs uppercase tracking-[0.12em] text-oo-muted">Internal · not shipped</p>
          <h1 className="text-4xl font-semibold tracking-tight">Type lab</h1>
          <p className="max-w-2xl leading-relaxed text-oo-ink-2">
            Locked on 2026-11-09: Source Serif 4 Display for marketing headlines, IBM Plex Sans for the app, IBM Plex
            Mono for sequences, IDs and scores.
          </p>
        </header>

        <section className="space-y-5 border-t border-oo-line pt-10">
          <p className="font-mono text-xs uppercase tracking-[0.12em] text-oo-muted">Display · Source Serif 4 Display Semibold</p>
          <h2 className="font-display text-[52px] font-semibold leading-[1.08] tracking-[-0.015em] md:text-[64px]">
            From tumor sequencing data to a <span className="text-oo-hema">ranked</span>, evidence-linked report.
          </h2>
          <p className="max-w-xl text-lg leading-relaxed text-oo-ink-2">
            Upload a VCF. OpenOncology ranks approved drugs and repurposing candidates against the mutation profile and
            names the source behind every ranking. Oncologist review is required before any treatment decision.
          </p>
        </section>

        <section className="space-y-5 border-t border-oo-line pt-10">
          <p className="font-mono text-xs uppercase tracking-[0.12em] text-oo-muted">UI · IBM Plex Sans 400 / 500 / 600</p>
          <div className="rounded-xl border border-oo-line bg-oo-surface p-6">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <div>
                <div className="text-xs font-medium text-oo-muted">Submission</div>
                <div className="mt-1 text-[22px] font-semibold tracking-[-0.01em]">{DEMO_RESULTS.cancer_type}</div>
              </div>
              <span className="rounded-full bg-oo-status-complete-bg px-2.5 py-1 text-xs font-semibold text-oo-status-complete-fg">
                Complete
              </span>
            </div>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-oo-ink-2">{DEMO_RESULTS.plain_language_summary}</p>
            <div className="mt-5 grid grid-cols-3 gap-3">
              {[
                { label: "Variants found", value: DEMO_RESULTS.mutations.length },
                { label: "Ranked candidates", value: candidates.length },
                { label: "Top rank score", value: (candidates[0].rank_score ?? 0).toFixed(3) },
              ].map((s) => (
                <div key={s.label} className="rounded-lg border border-oo-line-soft p-4">
                  <div className="text-xs font-medium text-oo-muted">{s.label}</div>
                  <div className="mt-2 text-[28px] font-semibold tabular-nums tracking-[-0.02em]">{s.value}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="space-y-5 border-t border-oo-line pt-10">
          <p className="font-mono text-xs uppercase tracking-[0.12em] text-oo-muted">Mono · IBM Plex Mono</p>
          <div className="rounded-xl border border-oo-line bg-oo-surface p-6">
            <div className="text-xs font-medium text-oo-muted">
              KRAS coding sequence, codons 9–18 (reference) · highlighted base is c.34, which is G&gt;T in G12C
            </div>
            <div className="mt-3 overflow-x-auto font-mono text-[22px] tracking-[0.12em]" aria-label="KRAS reference sequence, codons 9 to 18, with position c.34 highlighted">
              {SEQUENCE.split("").map((base, i) => (
                <span
                  key={i}
                  className={i === VARIANT_INDEX ? "rounded bg-oo-eosin-tint px-0.5 font-semibold text-oo-ink underline decoration-oo-eosin decoration-2 underline-offset-4" : "text-oo-ink-3"}
                >
                  {base}
                </span>
              ))}
            </div>
            <div className="mt-6 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-[0.06em] text-oo-muted">
                    <th className="py-2 pr-4 font-medium">Drug</th>
                    <th className="py-2 pr-4 font-medium">ChEMBL</th>
                    <th className="py-2 text-right font-medium">Rank score</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c) => (
                    <tr key={c.chembl_id} className="border-t border-oo-line-soft">
                      <td className="py-2.5 pr-4 font-medium">{c.drug_name}</td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-oo-ink-3">{c.chembl_id}</td>
                      <td className="py-2.5 text-right font-mono tabular-nums">{(c.rank_score ?? 0).toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
