export type OncoKbLevel = { code: string; label: string; short: string; meaning: string; resistance: boolean; recognised: boolean };

const LEVELS: Record<string, { meaning: string; resistance: boolean }> = {
  "1": { meaning: "FDA-recognised biomarker predicting response to an FDA-approved drug in this tumour type.", resistance: false },
  "2": { meaning: "Standard-care biomarker, recommended by NCCN or other expert panels, predicting response to an FDA-approved drug in this tumour type.", resistance: false },
  "3A": { meaning: "Compelling clinical evidence that the biomarker predicts response to a drug in this tumour type.", resistance: false },
  "3B": { meaning: "Standard-care or investigational biomarker predicting response to a drug in another tumour type.", resistance: false },
  "4": { meaning: "Compelling biological evidence that the biomarker predicts response to a drug.", resistance: false },
  R1: { meaning: "Standard-care biomarker predicting resistance to an FDA-approved drug in this tumour type.", resistance: true },
  R2: { meaning: "Compelling clinical evidence that the biomarker predicts resistance to a drug.", resistance: true },
};

const NO_LEVEL = new Set(["", "UNKNOWN", "NONE", "NULL"]);

export function oncoKbLevel(raw: string | null | undefined): OncoKbLevel | null {
  const code = (raw ?? "").trim().toUpperCase().replace(/^LEVEL_/, "");
  if (NO_LEVEL.has(code)) return null;
  const known = LEVELS[code];
  return {
    code,
    label: `OncoKB Level ${code}`,
    short: `OncoKB ${code}`,
    meaning: known?.meaning ?? "This code is not on OncoKB's therapeutic level scale; it is shown as reported.",
    resistance: known?.resistance ?? false,
    recognised: Boolean(known),
  };
}

export type LookupState =
  | { kind: "level"; level: OncoKbLevel; source: string | null }
  | { kind: "checked_none"; source: string }
  | { kind: "not_attempted" }
  | { kind: "unavailable" }
  | { kind: "unrecorded" };

const SOURCES: Record<string, string> = { ok: "OncoKB", static_table: "curated OncoKB table (no live API token)" };

export function evidenceLookup(level: string | null | undefined, status: string | null | undefined): LookupState {
  const parsed = oncoKbLevel(level);
  const source = status ? (SOURCES[status] ?? null) : null;
  if (parsed) return { kind: "level", level: parsed, source };
  if (status === "unavailable") return { kind: "unavailable" };
  if (status === "not_attempted") return { kind: "not_attempted" };
  if (source) return { kind: "checked_none", source };
  return { kind: "unrecorded" };
}

const PREDICTION_LABELS: Record<string, string> = {
  pathogenic: "Likely pathogenic",
  likely_pathogenic: "Likely pathogenic",
  uncertain: "Ambiguous",
  likely_benign: "Likely benign",
  benign: "Likely benign",
};

export function predictionLabel(raw: string | null | undefined, score: number | null | undefined): string | null {
  if (typeof score !== "number" || Number.isNaN(score)) return null;
  const key = (raw ?? "").trim().toLowerCase().replace(/\s+/g, "_");
  if (!key) return null;
  return PREDICTION_LABELS[key] ?? key.replace(/_/g, " ");
}
