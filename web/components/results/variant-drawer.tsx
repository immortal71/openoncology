"use client";

import { useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowUpRight, ChevronRight, X } from "lucide-react";
import { evidenceLookup, oncoKbLevel, predictionLabel, type LookupState } from "@/lib/evidence-levels";
import { PROTEIN_REFERENCE, domainAt, parseProteinChange } from "@/lib/protein";
import { cn } from "@/lib/utils";

export type DrawerVariant = {
  gene: string;
  hgvs: string;
  classification?: string | null;
  alphamissense_score?: number | null;
  oncokb_level?: string | null;
  evidence_lookup_status?: string | null;
  is_targetable?: boolean | null;
};

const NOT_IN_RESULT = ["allele fraction (VAF)", "read depth", "ClinVar review status", "COSMIC count"];

function Field({ label, children, muted = false }: { label: string; children: React.ReactNode; muted?: boolean }) {
  return (
    <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3 py-2.5 sm:grid-cols-[8.5rem_minmax(0,1fr)]">
      <dt className="text-[13px] text-oo-ink-3">{label}</dt>
      <dd className={cn("min-w-0 text-[13.5px]", muted ? "text-oo-ink-3" : "text-oo-ink")}>{children}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-oo-line pt-4 first:border-t-0">
      <h3 className="text-[12px] font-medium text-oo-ink-3">{title}</h3>
      <dl className="mt-1 divide-y divide-oo-line-soft">{children}</dl>
    </section>
  );
}

function LevelBadge({ level, className }: { level: string | null | undefined; className?: string }) {
  const info = oncoKbLevel(level);
  if (!info) return <span className={cn("whitespace-nowrap text-[12px] text-oo-ink-3", className)}>No OncoKB level</span>;
  return (
    <span
      className={cn(
        "inline-flex whitespace-nowrap rounded-md border px-1.5 py-0.5 font-mono text-[11.5px]",
        info.resistance ? "border-oo-status-failed-fg/30 text-oo-status-failed-fg" : "border-oo-line text-oo-ink-2",
        className
      )}
    >
      {info.short}
    </span>
  );
}

function LookupValue({ state, cancerType }: { state: LookupState; cancerType?: string }) {
  if (state.kind === "level") {
    return (
      <span className="block space-y-1">
        <span className="block font-medium">{state.level.label}</span>
        <span className="block text-[12.5px] leading-relaxed text-oo-ink-2">{state.level.meaning}</span>
        <span className="block text-[12px] text-oo-ink-3">
          {cancerType ? `Tumour type in this result: ${cancerType}. ` : null}
          {state.source ? `Source: ${state.source}.` : "Lookup source not recorded for this result."}
        </span>
      </span>
    );
  }
  if (state.kind === "checked_none") return <>Checked, no OncoKB level (source: {state.source})</>;
  if (state.kind === "not_attempted") return <>Not checked: no protein change to look up</>;
  if (state.kind === "unavailable") return <span className="font-medium text-oo-status-failed-fg">Lookup failed. Absence of a level here means nothing.</span>;
  return <>No level, and the lookup status was not recorded</>;
}

export function VariantDetail({ variant, cancerType }: { variant: DrawerVariant; cancerType?: string }) {
  const change = parseProteinChange(variant.hgvs);
  const ref = PROTEIN_REFERENCE[variant.gene.toUpperCase()];
  const domain = change ? domainAt(variant.gene, change.position) : null;
  const prediction = predictionLabel(variant.classification, variant.alphamissense_score);
  const lookup = evidenceLookup(variant.oncokb_level, variant.evidence_lookup_status);
  const oncokbUrl = change ? `https://www.oncokb.org/gene/${encodeURIComponent(variant.gene)}/${encodeURIComponent(change.short)}` : null;
  const clinvarUrl = `https://www.ncbi.nlm.nih.gov/clinvar/?term=${encodeURIComponent(`${variant.gene}[gene] ${variant.hgvs}`)}`;

  return (
    <div className="space-y-5">
      <Section title="Actionability">
        <Field label="Evidence level" muted={lookup.kind !== "level" && lookup.kind !== "unavailable"}>
          <LookupValue state={lookup} cancerType={cancerType} />
        </Field>
        <Field label="Targetable" muted={typeof variant.is_targetable !== "boolean"}>
          {typeof variant.is_targetable === "boolean" ? (variant.is_targetable ? "Yes, as reported" : "No, as reported") : "Not reported"}
        </Field>
      </Section>

      <Section title="Pathogenicity">
        <Field label="AlphaMissense" muted={!prediction}>
          {prediction ? (
            <span className="block space-y-0.5">
              <span className="block">
                {prediction}
                {typeof variant.alphamissense_score === "number" ? (
                  <span className="font-mono text-[12.5px] text-oo-ink-2"> · score {variant.alphamissense_score.toFixed(2)}</span>
                ) : null}
              </span>
              <span className="block text-[12px] text-oo-ink-3">Computational prediction, not a curated classification.</span>
            </span>
          ) : (
            "Not scored in this result"
          )}
        </Field>
      </Section>

      <Section title="Protein">
        <Field label="Protein change">
          <span className="font-mono text-[12.5px]">{variant.hgvs}</span>
        </Field>
        <Field label="Position" muted={!change}>
          {change ? `Residue ${change.position}${ref ? ` of ${ref.length}` : ""}` : "Not parsed"}
        </Field>
        <Field label="Domain" muted={!domain}>
          {domain ?? (ref ? "Outside annotated domains" : "No domain reference")}
        </Field>
        {ref ? (
          <Field label="Reference">
            <span className="font-mono text-[12.5px]">{ref.source}</span>
          </Field>
        ) : null}
      </Section>

      <p className="border-t border-oo-line pt-4 text-[12.5px] leading-relaxed text-oo-ink-3">
        Not in this result: {NOT_IN_RESULT.join(", ")}.
      </p>

      <section className="border-t border-oo-line pt-4">
        <h3 className="text-[12px] font-medium text-oo-ink-3">Look it up</h3>
        <ul className="mt-2 flex flex-wrap gap-2">
          {oncokbUrl ? (
            <li>
              <a href={oncokbUrl} target="_blank" rel="noreferrer" className={linkClass}>
                OncoKB <ArrowUpRight size={13} aria-hidden="true" />
                <span className="sr-only">(opens in a new tab)</span>
              </a>
            </li>
          ) : null}
          <li>
            <a href={clinvarUrl} target="_blank" rel="noreferrer" className={linkClass}>
              ClinVar <ArrowUpRight size={13} aria-hidden="true" />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          </li>
        </ul>
      </section>
    </div>
  );
}

const linkClass =
  "inline-flex items-center gap-1 rounded-md border border-oo-line bg-oo-surface px-2.5 py-1 text-[13px] font-medium text-oo-ink transition-colors duration-150 hover:bg-oo-paper focus-visible:outline focus-visible:outline-2 focus-visible:outline-oo-hema";

export function VariantList({ variants, cancerType, className }: { variants: DrawerVariant[]; cancerType?: string; className?: string }) {
  const [selected, setSelected] = useState<DrawerVariant | null>(null);
  const opener = useRef<HTMLButtonElement | null>(null);
  if (variants.length === 0) return null;

  const nameOf = (v: DrawerVariant) => `${v.gene} ${parseProteinChange(v.hgvs)?.short ?? v.hgvs}`;

  return (
    <section aria-labelledby="variants-title" className={className}>
      <h2 id="variants-title" className="text-[13px] font-medium text-oo-ink-3">
        Variants in this case
      </h2>
      <ul className="mt-3 divide-y divide-oo-line-soft border-y border-oo-line-soft">
        {variants.map((v) => {
          const level = oncoKbLevel(v.oncokb_level);
          return (
            <li key={`${v.gene}-${v.hgvs}`}>
              <button
                type="button"
                onClick={(e) => {
                  opener.current = e.currentTarget;
                  setSelected(v);
                }}
                aria-haspopup="dialog"
                aria-label={`${nameOf(v)}, ${v.hgvs}, ${level ? level.label : "no OncoKB level"}. Open variant details`}
                className="-mx-2 flex w-[calc(100%+1rem)] items-center gap-3 rounded-md px-2 py-2.5 text-left transition-colors duration-150 hover:bg-oo-paper focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-oo-hema"
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-[14px] font-semibold text-oo-ink">{nameOf(v)}</span>
                  <span className="block truncate font-mono text-[11.5px] text-oo-ink-3">{v.hgvs}</span>
                </span>
                <LevelBadge level={v.oncokb_level} />
                <ChevronRight size={15} className="shrink-0 text-oo-ink-3" aria-hidden="true" />
              </button>
            </li>
          );
        })}
      </ul>

      <Dialog.Root open={selected !== null} onOpenChange={(open) => (open ? null : setSelected(null))}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-oo-ink/20" />
          <Dialog.Content
            onCloseAutoFocus={(e) => {
              e.preventDefault();
              opener.current?.focus();
            }}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[440px] flex-col border-oo-line sm:border-l bg-oo-surface shadow-[-24px_0_48px_-24px_rgb(27_22_38/0.3)] focus:outline-none"
          >
            {selected ? (
              <>
                <div className="flex items-start justify-between gap-3 border-b border-oo-line px-5 py-4">
                  <div className="min-w-0">
                    <Dialog.Title className="text-[20px] font-semibold tracking-[-0.01em] text-oo-ink">{nameOf(selected)}</Dialog.Title>
                    <Dialog.Description className="mt-0.5 text-[12.5px] text-oo-ink-3">
                      {[selected.hgvs, oncoKbLevel(selected.oncokb_level)?.label ?? "No OncoKB level", cancerType].filter(Boolean).join(" · ")}
                    </Dialog.Description>
                  </div>
                  <Dialog.Close
                    aria-label="Close variant details"
                    className="inline-grid h-9 w-9 shrink-0 place-items-center rounded-md text-oo-ink-2 hover:bg-oo-paper hover:text-oo-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-oo-hema"
                  >
                    <X size={17} aria-hidden="true" />
                  </Dialog.Close>
                </div>
                <div className="flex-1 overflow-y-auto px-5 pb-8 pt-4">
                  <VariantDetail variant={selected} cancerType={cancerType} />
                </div>
              </>
            ) : null}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
