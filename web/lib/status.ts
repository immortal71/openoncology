export type SubmissionStatus = "queued" | "analyzing" | "complete" | "failed" | "unknown";

const ALIASES: Record<string, SubmissionStatus> = {
  queued: "queued",
  pending: "queued",
  running: "analyzing",
  processing: "analyzing",
  awaiting_ai: "analyzing",
  analyzing: "analyzing",
  complete: "complete",
  completed: "complete",
  failed: "failed",
  error: "failed",
};

export const STATUS_LABEL: Record<SubmissionStatus, string> = {
  queued: "Queued",
  analyzing: "Analyzing",
  complete: "Complete",
  failed: "Failed",
  unknown: "Unknown",
};

export function normalizeStatus(raw: string | null | undefined): SubmissionStatus {
  if (!raw) return "unknown";
  return ALIASES[raw.trim().toLowerCase()] ?? "unknown";
}
