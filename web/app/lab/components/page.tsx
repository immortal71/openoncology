import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FileUp } from "lucide-react";
import { Button } from "@/components/oo/button";
import { Card, Skeleton, StatCard } from "@/components/oo/card";
import { ApprovalLine, ReviewState, SourceBadges, TierPill } from "@/components/oo/clinical";
import { DataTable, type Column } from "@/components/oo/data-table";
import { Disclaimer, EmptyState } from "@/components/oo/feedback";
import { FindingList, type Finding } from "@/components/oo/finding-list";
import { ScoreBar } from "@/components/oo/score-bar";
import { StatusPill } from "@/components/oo/status-pill";
import { VariantTrack } from "@/components/oo/variant-track";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { displaySources } from "@/lib/evidence";

export const metadata: Metadata = {
  title: "Components lab | OpenOncology",
  robots: { index: false, follow: false },
};

type Candidate = (typeof DEMO_REPURPOSING.candidates)[number];

const ranked = [...DEMO_REPURPOSING.candidates].sort((a, b) => (b.rank_score ?? 0) - (a.rank_score ?? 0));
const kras = DEMO_RESULTS.mutations[0];

const findings: Finding[] = ranked.map((c) => ({
  id: c.chembl_id,
  name: c.drug_name,
  tier: c.drug_tier,
  score: c.rank_score,
  approvalStatus: c.approval_status,
  mechanism: c.mechanism,
  sources: displaySources(c),
}));

const COLUMNS: Column<Candidate>[] = [
  { key: "drug", header: "Drug", cell: (c) => <span className="font-medium">{c.drug_name}</span> },
  { key: "chembl", header: "ChEMBL", cell: (c) => <span className="text-oo-ink-3">{c.chembl_id}</span>, mono: true },
  { key: "tier", header: "Tier", cell: (c) => <TierPill tier={c.drug_tier} /> },
  { key: "sources", header: "Evidence sources", cell: (c) => <span className="text-oo-ink-2">{displaySources(c).join(", ")}</span> },
  { key: "score", header: "Rank score", cell: (c) => <ScoreBar score={c.rank_score} />, align: "right" },
];

const SUBMISSION_STATES = ["queued", "running", "awaiting_ai", "completed", "complete", "error", "failed", "accepted", null];

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-5 border-t border-oo-line pt-10">
      <div className="space-y-1">
        <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
        {note ? <p className="max-w-3xl text-oo-ink-2">{note}</p> : null}
      </div>
      {children}
    </section>
  );
}

export default function ComponentsLabPage() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <main className="min-h-screen bg-oo-paper px-5 py-12 text-oo-ink md:px-12">
      <div className="mx-auto max-w-6xl space-y-14">
        <header className="space-y-3">
          <p className="font-mono text-xs uppercase tracking-[0.12em] text-oo-muted">Internal · not shipped</p>
          <h1 className="text-4xl font-semibold tracking-tight">Components lab</h1>
          <p className="max-w-2xl leading-relaxed text-oo-ink-2">
            The phase 1 component set in <code className="font-mono text-[14px]">components/oo</code>, revised after its
            devil&apos;s-advocate review, shown with the KRAS G12C demo case. Tab through the page to check focus.
          </p>
        </header>

        <Section title="Findings" note="The Results page's core list. Each row is one button that expands in place to show approval status, mechanism and the drug's own named evidence sources. Violet is reserved for actions, so tiers and scores are neutral.">
          <FindingList
            findings={findings}
            caption="Ranked candidates for the KRAS G12C demo case"
            defaultOpenFirst
            empty={<EmptyState icon={FileUp} title="No ranked candidates" description="This analysis found no drugs to rank." />}
          />
        </Section>

        <Section title="Clinical pieces">
          <div className="flex flex-wrap items-center gap-4">
            <TierPill tier="fda_approved" />
            <TierPill tier="repurposed" />
            <TierPill tier={null} />
            <ReviewState reviewed={false} />
            <ReviewState reviewed />
          </div>
          <div className="space-y-2">
            {ranked.map((c) => (
              <div key={c.chembl_id}>
                <ApprovalLine status={c.approval_status} />
              </div>
            ))}
            <ApprovalLine status={null} />
          </div>
          <SourceBadges sources={displaySources(ranked[0])} />
        </Section>

        <Section title="Buttons" note="Rounded for the app, pill for marketing CTAs. Disabled, loading, and a link styled as a button.">
          <div className="flex flex-wrap items-center gap-3">
            <Button>Submit a case</Button>
            <Button variant="secondary">Read the methods</Button>
            <Button variant="ghost">Cancel</Button>
            <Button variant="danger">Delete submission</Button>
            <Button disabled>Disabled</Button>
            <Button loading>Uploading</Button>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button shape="pill" size="lg">
              View the demo case
            </Button>
            <Button shape="pill" size="lg" variant="secondary">
              Read the methods
            </Button>
            <Button size="sm" variant="secondary">
              Export
            </Button>
            <Button asChild variant="ghost">
              <Link href="/lab/hero">Link styled as button</Link>
            </Button>
          </div>
        </Section>

        <Section title="Status" note="Shape glyphs, not tinted pills: dashed ring, half-filled, check, alert. Raw backend values are shown beside each, including duplicates and unknowns.">
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            {SUBMISSION_STATES.map((raw) => (
              <span key={String(raw)} className="flex items-center gap-2">
                <code className="font-mono text-[12px] text-oo-ink-3">{String(raw)}</code>
                <StatusPill status={raw} />
              </span>
            ))}
          </div>
        </Section>

        <Section title="Variant track" note="The pin position is a prop. The label flips side near the right edge.">
          <div className="grid gap-4 md:grid-cols-2">
            <VariantTrack gene="KRAS" hgvs={kras.hgvs} detail={`OncoKB Level ${kras.oncokb_level.replace("LEVEL_", "")} · ${kras.classification}`} />
            <VariantTrack gene="TP53" hgvs={DEMO_RESULTS.mutations[1].hgvs} detail="OncoKB Level 3B" position={0.82} />
          </div>
        </Section>

        <Section title="Data table" note="For simple lists, such as submissions. Table from md up, stacked cards below. An empty state is required.">
          <DataTable
            columns={COLUMNS}
            rows={ranked}
            rowKey={(c) => c.chembl_id}
            caption="Ranked candidates for the KRAS G12C demo case"
            empty={<EmptyState icon={FileUp} title="No candidates" description="Nothing to show yet." />}
          />
        </Section>

        <Section title="Stat cards, disclaimer, empty and loading" note="Stat cards are for the dashboard only. The Results page uses a one-line summary instead.">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Submissions" value={1} />
            <StatCard label="Complete" value={1} />
            <StatCard label="Analyzing" value={0} />
            <StatCard label="Failed" value={0} loading />
          </div>
          <Disclaimer variant="banner">Research prototype. Oncologist review is required before any treatment decision.</Disclaimer>
          <Disclaimer>Research prototype. Oncologist review is required before any treatment decision.</Disclaimer>
          <div className="grid gap-4 md:grid-cols-2">
            <EmptyState
              icon={FileUp}
              title="No submissions yet"
              description="Upload a VCF to rank approved drugs and repurposing candidates against its mutation profile."
              action={<Button shape="pill">Submit a case</Button>}
            />
            <Card className="space-y-3 p-5" aria-busy="true">
              <span className="sr-only">Loading results</span>
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </Card>
          </div>
        </Section>
      </div>
    </main>
  );
}
