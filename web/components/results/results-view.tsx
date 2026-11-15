import Link from "next/link";
import { FileText, SearchX } from "lucide-react";
import { Button } from "@/components/oo/button";
import { ReviewState } from "@/components/oo/clinical";
import { Disclaimer, EmptyState } from "@/components/oo/feedback";
import { FindingList, type Finding } from "@/components/oo/finding-list";
import { HighlightProvider } from "@/components/oo/highlight";
import { RevealNoScriptFallback } from "@/components/oo/reveal";
import { StatusPill } from "@/components/oo/status-pill";
import { displaySources, usesClinicalPhaseSignal } from "@/lib/evidence";
import { oncoKbLevel, predictionLabel } from "@/lib/evidence-levels";
import { parseProteinChange } from "@/lib/protein";
import { ProteinLollipop } from "./protein-lollipop";
import { RankLadder } from "./rank-ladder";
import { VariantList } from "./variant-drawer";

const METHODS_URL = "https://github.com/immortal71/openoncology/blob/main/docs/METHODS.md";
const REVIEW_NOTE = "Research prototype. Oncologist review is required before any treatment decision.";

export type ResultsMutation = {
  gene?: string;
  hgvs?: string;
  classification?: string;
  oncokb_level?: string;
  is_targetable?: boolean;
  alphamissense_score?: number | null;
  evidence_lookup_status?: string | null;
};

export type ResultsData = {
  submission_id: string;
  status: string;
  cancer_type: string;
  plain_language_summary: string | null;
  patient_summary: { what_next?: string[] } | null;
  mutations: ResultsMutation[];
  oncologist_reviewed?: boolean;
};

export type RepurposingCandidate = {
  drug_name: string;
  chembl_id: string;
  approval_status: string;
  mechanism: string;
  rank_score: number | null;
  opentargets_score?: number | null;
  evidence_sources: string[];
  drug_tier?: string;
};

const levelLabel = (level?: string) => oncoKbLevel(level)?.label ?? "No OncoKB level";
const predictionNote = (classification?: string, score?: number | null) => {
  const label = predictionLabel(classification, score);
  return label ? `AlphaMissense: ${label.toLowerCase()}` : null;
};

function SectionTitle({ id, children, aside }: { id: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
      <h2 id={id} className="text-[17px] font-semibold tracking-[-0.01em] text-oo-ink">
        {children}
      </h2>
      {aside ? <p className="text-[13px] text-oo-ink-3">{aside}</p> : null}
    </div>
  );
}

export function ResultsView({
  results,
  candidates,
  demo = false,
  reportAvailable = false,
}: {
  results: ResultsData;
  candidates: RepurposingCandidate[];
  demo?: boolean;
  reportAvailable?: boolean;
}) {
  const ranked = [...candidates].sort((a, b) => (b.rank_score ?? 0) - (a.rank_score ?? 0));
  const findings: Finding[] = ranked.map((c) => ({
    id: c.chembl_id,
    name: c.drug_name,
    tier: c.drug_tier,
    score: c.rank_score,
    approvalStatus: c.approval_status,
    mechanism: c.mechanism,
    sources: displaySources(c),
    phaseSignal: usesClinicalPhaseSignal(c),
  }));
  const variants = results.mutations.filter((m) => m.gene && m.hgvs);
  const targetable = variants.filter((m) => m.is_targetable);
  const lead = targetable[0] ?? variants[0];
  const leadChange = parseProteinChange(lead?.hgvs);
  const title = lead && leadChange ? `${lead.gene} ${leadChange.short}` : results.cancer_type;
  const nextSteps = results.patient_summary?.what_next ?? [];

  return (
    <div className="min-h-screen bg-oo-paper text-oo-ink">
      <RevealNoScriptFallback />
      <Disclaimer variant="banner" className="justify-center">
        {REVIEW_NOTE}
      </Disclaimer>

      <div className="mx-auto max-w-[1160px] px-5 pb-20 pt-8 md:px-8">
        <nav aria-label="Breadcrumb" className="text-[13px] text-oo-ink-3">
          <ol className="flex flex-wrap items-center gap-1.5">
            <li>
              <Link
                href={demo ? "/" : "/dashboard"}
                className="rounded hover:text-oo-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-oo-hema"
              >
                {demo ? "Home" : "Submissions"}
              </Link>
            </li>
            <li aria-hidden="true">/</li>
            <li aria-current="page" className={demo ? "text-oo-ink-2" : "font-mono text-[12px] text-oo-ink-2"}>
              {demo ? "Demo case" : results.submission_id}
            </li>
          </ol>
        </nav>

        <header className="mt-5 flex flex-wrap items-end justify-between gap-x-8 gap-y-5 border-b border-oo-line pb-7">
          <div className="min-w-0">
            <h1 className="text-[34px] font-semibold leading-none tracking-[-0.025em]">{title}</h1>
            <p className="mt-2 text-[16px] text-oo-ink-2">{results.cancer_type}</p>
            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2">
              <span role="status" aria-live="polite">
                <StatusPill status={results.status} />
              </span>
              {typeof results.oncologist_reviewed === "boolean" ? <ReviewState reviewed={results.oncologist_reviewed} /> : null}
              {demo ? (
                <span className="rounded-full border border-oo-ink-3/50 px-2.5 py-0.5 text-[12px] font-medium text-oo-ink-2">
                  Demo case, not a real patient
                </span>
              ) : null}
            </div>
          </div>
          <div className="hidden gap-2 sm:flex">
            {reportAvailable ? (
              <Button variant="secondary">
                <FileText aria-hidden="true" />
                Oncologist report
              </Button>
            ) : null}
            <Button variant="secondary" asChild>
              <a href={METHODS_URL} target="_blank" rel="noreferrer">
                Read the methods
              </a>
            </Button>
          </div>
        </header>

        <div className="mt-8 grid gap-x-12 gap-y-10 lg:grid-cols-[minmax(0,1fr)_320px]">
          {variants.length > 0 ? (
            <ProteinLollipop
              className="order-2 lg:order-none lg:col-span-2"
              variants={variants.map((m) => ({
                gene: m.gene as string,
                hgvs: m.hgvs as string,
                emphasis: m === lead,
                note: [predictionNote(m.classification, m.alphamissense_score), levelLabel(m.oncokb_level), m.is_targetable ? "targetable" : "not targetable"].filter(Boolean).join(" · "),
              }))}
            />
          ) : null}

          <HighlightProvider>
          <div className="order-1 min-w-0 space-y-10 lg:order-none">
            {results.plain_language_summary ? (
              <section aria-labelledby="summary-title">
                <h2 id="summary-title" className="sr-only">
                  Summary
                </h2>
                <p className="max-w-[62ch] text-[16px] leading-[1.6] text-oo-ink sm:text-[18px]">{results.plain_language_summary}</p>
              </section>
            ) : null}

            <RankLadder
              items={ranked.map((c) => ({ id: c.chembl_id, name: c.drug_name, score: c.rank_score, tier: c.drug_tier }))}
              context={lead && leadChange ? `for ${lead.gene} ${leadChange.short}` : undefined}
            />

            <section aria-labelledby="candidates-title">
              <SectionTitle id="candidates-title" aside="Grouped by clinical context. Numbers are the overall rank.">
                All ranked candidates
              </SectionTitle>
              <FindingList
                className="mt-4"
                findings={findings}
                caption="All ranked candidates"
                showHeader
                grouped
                defaultOpenFirst
                footer={
                  <>
                    Evidence score is a weighted composite of the sources named on each row, from 0 to 1. Sources still being verified are
                    hidden.{" "}
                    <a
                      href={METHODS_URL}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-oo-hema underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-oo-hema"
                    >
                      Methods
                    </a>
                  </>
                }
                empty={
                  <EmptyState
                    className="mt-4"
                    icon={SearchX}
                    title="No ranked candidates"
                    description="No approved or repurposing candidates matched this mutation profile."
                  />
                }
              />
            </section>
          </div>
          </HighlightProvider>

          <aside className="order-3 space-y-8 lg:sticky lg:top-24 lg:order-none lg:self-start" aria-label="Variants and next steps">
            <VariantList
              cancerType={results.cancer_type}
              variants={variants.map((m) => ({
                gene: m.gene as string,
                hgvs: m.hgvs as string,
                classification: m.classification,
                alphamissense_score: m.alphamissense_score,
                oncokb_level: m.oncokb_level,
                evidence_lookup_status: m.evidence_lookup_status,
                is_targetable: m.is_targetable,
              }))}
            />
            {nextSteps.length > 0 ? (
              <section aria-labelledby="next-title">
                <h2 id="next-title" className="text-[13px] font-medium text-oo-ink-3">
                  Suggested next steps
                </h2>
                <ol className="mt-3 divide-y divide-oo-line-soft border-y border-oo-line-soft">
                  {nextSteps.map((step, i) => (
                    <li key={step} className="flex gap-3 py-3 text-[14px] leading-relaxed text-oo-ink-2">
                      <span className="w-4 shrink-0 font-mono text-[12px] leading-[1.7] text-oo-ink-3">{i + 1}</span>
                      {step}
                    </li>
                  ))}
                </ol>
              </section>
            ) : null}
          </aside>
        </div>
      </div>
    </div>
  );
}
