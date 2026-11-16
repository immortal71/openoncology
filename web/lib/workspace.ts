import { parseApproval, type Approval } from "@/lib/approval";
import { DERIVED_SIGNALS, SOURCES_PENDING_REVIEW, displaySources } from "@/lib/evidence";
import { evidenceLookup, oncoKbLevel, predictionLabel, type LookupState, type OncoKbLevel } from "@/lib/evidence-levels";
import { parseProteinChange } from "@/lib/protein";
import { groupByTier, tierInfo, type TherapyGroup, type TierInfo } from "@/lib/therapy-groups";

export const NEAR_TIE = 0.02;

export type CaseMutation = {
  gene?: string;
  hgvs?: string;
  classification?: string | null;
  oncokb_level?: string | null;
  is_targetable?: boolean | null;
  alphamissense_score?: number | null;
  evidence_lookup_status?: string | null;
};

export type CaseResult = {
  submission_id: string;
  status?: string;
  cancer_type: string;
  plain_language_summary?: string | null;
  patient_summary?: { what_next?: string[] } | null;
  mutations: CaseMutation[];
  oncologist_reviewed?: boolean;
  cosmic_sample_count?: number | null;
  cbioportal_data?: unknown;
};

export type CaseCandidate = {
  drug_name: string;
  chembl_id?: string | null;
  approval_status?: string | null;
  mechanism?: string | null;
  rank_score?: number | null;
  opentargets_score?: number | null;
  evidence_sources?: string[];
  matched_terms?: string[];
  drug_tier?: string | null;
};

export type WsCandidate = {
  id: string;
  name: string;
  rank: number;
  tier: string;
  tierInfo: TierInfo;
  approval: Approval;
  mechanism: string | null;
  chembl: string | null;
  matched: string[];
  sources: string[];
  hidden: { name: string; reason: string }[];
  score: number | null;
  opentargets: number | null;
};

export type WsVariant = {
  key: string;
  gene: string;
  hgvs: string;
  short: string;
  name: string;
  level: OncoKbLevel | null;
  lookup: LookupState;
  targetable: boolean | null;
  prediction: string | null;
  classification: string | null;
  alphamissense: number | null;
  lookupStatus: string | null;
};

export type GapState = "not_supplied" | "not_assessed" | "not_recorded" | "lookup_failed";

export type WsGap = { item: string; scope: string | null; state: GapState; note: string };

export type WsCase = {
  id: string;
  title: string;
  tumor: string;
  tumorShort: string | null;
  demo: boolean;
  status: string | null;
  reviewed: boolean | null;
  variants: WsVariant[];
  lead: WsVariant | null;
  candidates: WsCandidate[];
  groups: TherapyGroup<WsCandidate>[];
  nearTies: { name: string; above: string }[];
  gaps: WsGap[];
  summary: string | null;
  nextSteps: string[];
};

export const GAP_LABELS: Record<GapState, string> = {
  not_supplied: "Not supplied",
  not_assessed: "Not assessed",
  not_recorded: "Not recorded",
  lookup_failed: "Lookup failed",
};

const TUMOR_SHORT: Record<string, string> = { "non-small cell lung cancer": "NSCLC" };

function toVariant(m: CaseMutation): WsVariant | null {
  if (!m.gene || !m.hgvs) return null;
  const change = parseProteinChange(m.hgvs);
  const short = change?.short ?? m.hgvs;
  return {
    key: `${m.gene}-${m.hgvs}`,
    gene: m.gene,
    hgvs: m.hgvs,
    short,
    name: `${m.gene} ${short}`,
    level: oncoKbLevel(m.oncokb_level),
    lookup: evidenceLookup(m.oncokb_level, m.evidence_lookup_status),
    targetable: typeof m.is_targetable === "boolean" ? m.is_targetable : null,
    prediction: predictionLabel(m.classification, m.alphamissense_score),
    classification: m.classification ?? null,
    alphamissense: typeof m.alphamissense_score === "number" ? m.alphamissense_score : null,
    lookupStatus: m.evidence_lookup_status ?? null,
  };
}

function toCandidate(c: CaseCandidate, rank: number): WsCandidate {
  const raw = c.evidence_sources ?? [];
  return {
    id: c.chembl_id || c.drug_name,
    name: c.drug_name,
    rank,
    tier: tierInfo(c.drug_tier).key,
    tierInfo: tierInfo(c.drug_tier),
    approval: parseApproval(c.approval_status),
    mechanism: c.mechanism?.trim() || null,
    chembl: c.chembl_id || null,
    matched: c.matched_terms ?? [],
    sources: displaySources({ evidence_sources: raw, opentargets_score: c.opentargets_score }),
    hidden: raw
      .filter((s) => SOURCES_PENDING_REVIEW.has(s) || DERIVED_SIGNALS.has(s))
      .map((s) => ({ name: s, reason: SOURCES_PENDING_REVIEW.has(s) ? "pending review" : "derived signal" })),
    score: typeof c.rank_score === "number" ? c.rank_score : null,
    opentargets: typeof c.opentargets_score === "number" ? c.opentargets_score : null,
  };
}

function gapsFor(result: CaseResult, variants: WsVariant[]): WsGap[] {
  const gaps: WsGap[] = [
    { item: "Allele fraction (VAF)", scope: null, state: "not_supplied", note: "Not part of this result" },
    { item: "Read depth", scope: null, state: "not_supplied", note: "Not part of this result" },
    { item: "ClinVar review status", scope: null, state: "not_supplied", note: "Not part of this result" },
  ];
  if (result.cosmic_sample_count == null) gaps.push({ item: "COSMIC count", scope: null, state: "not_supplied", note: "No value in this result" });
  if (result.cbioportal_data == null) gaps.push({ item: "cBioPortal cohort data", scope: null, state: "not_supplied", note: "No value in this result" });
  for (const v of variants) {
    if (!v.prediction) gaps.push({ item: "AlphaMissense class", scope: v.name, state: "not_assessed", note: "Not scored in this result" });
    const l = v.lookup;
    if (l.kind === "level" && !l.source) gaps.push({ item: "Evidence lookup source", scope: v.name, state: "not_recorded", note: "Level present; where it came from was not stored" });
    if (l.kind === "unrecorded") gaps.push({ item: "Evidence lookup", scope: v.name, state: "not_recorded", note: "No level, and the lookup status was not stored" });
    if (l.kind === "not_attempted") gaps.push({ item: "Evidence lookup", scope: v.name, state: "not_assessed", note: "No protein change to look up" });
    if (l.kind === "unavailable") gaps.push({ item: "Evidence lookup", scope: v.name, state: "lookup_failed", note: "Absence of a level here means nothing" });
  }
  gaps.push({ item: "Exact source records", scope: null, state: "not_recorded", note: "The citation behind each evidence level is not stored" });
  return gaps;
}

export function buildCase(result: CaseResult, candidates: CaseCandidate[], opts: { demo?: boolean } = {}): WsCase {
  const variants = result.mutations.map(toVariant).filter((v): v is WsVariant => v !== null);
  const lead = variants.find((v) => v.targetable) ?? variants[0] ?? null;
  const ranked = [...candidates]
    .sort((a, b) => (b.rank_score ?? -1) - (a.rank_score ?? -1))
    .map((c, i) => toCandidate(c, i + 1));
  const scored = ranked.filter((c): c is WsCandidate & { score: number } => c.score !== null);
  const nearTies = scored.slice(1).flatMap((c, i) => (scored[i].score - c.score < NEAR_TIE ? [{ name: c.name, above: scored[i].name }] : []));
  return {
    id: result.submission_id,
    title: lead ? lead.name : result.cancer_type,
    tumor: result.cancer_type,
    tumorShort: TUMOR_SHORT[result.cancer_type.trim().toLowerCase()] ?? null,
    demo: Boolean(opts.demo),
    status: result.status ?? null,
    reviewed: typeof result.oncologist_reviewed === "boolean" ? result.oncologist_reviewed : null,
    variants,
    lead,
    candidates: ranked,
    groups: groupByTier(ranked),
    nearTies,
    gaps: gapsFor(result, variants),
    summary: result.plain_language_summary?.trim() || null,
    nextSteps: result.patient_summary?.what_next ?? [],
  };
}

export function levelApplies(c: WsCandidate, lead: WsVariant | null): boolean {
  return Boolean(lead?.level) && c.tier === "fda_approved";
}

export function sourceRow(source: string, c: WsCandidate, lead: WsVariant | null) {
  if (source.startsWith("OpenTargets"))
    return {
      name: "OpenTargets",
      provides: "Target–disease association",
      value: c.opentargets !== null ? c.opentargets.toFixed(2) : "Listed",
      lookup: c.chembl ? { href: `https://platform.opentargets.org/drug/${encodeURIComponent(c.chembl)}`, label: "Search OpenTargets" } : null,
    };
  if (source === "OncoKB")
    return {
      name: "OncoKB",
      provides: "Curated evidence level",
      value: levelApplies(c, lead) && lead?.level ? `${lead.level.label} · ${lead.name}` : "Listed",
      lookup: lead ? { href: `https://www.oncokb.org/gene/${encodeURIComponent(lead.gene)}/${encodeURIComponent(lead.short)}`, label: "Search OncoKB" } : null,
    };
  if (source === "ChEMBL") return { name: "ChEMBL", provides: "Bioactivity and mechanism", value: "Listed", lookup: null };
  if (source === "ClinVar") return { name: "ClinVar", provides: "Variant clinical significance", value: "Listed", lookup: null };
  return { name: source, provides: "Evidence provider", value: "Listed", lookup: null };
}
