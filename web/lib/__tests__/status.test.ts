import { describe, expect, it } from "vitest";
import { STATUS_LABEL, normalizeStatus } from "@/lib/status";

describe("normalizeStatus", () => {
  it("collapses the backend's duplicate spellings", () => {
    expect(normalizeStatus("complete")).toBe("complete");
    expect(normalizeStatus("completed")).toBe("complete");
    expect(normalizeStatus("failed")).toBe("failed");
    expect(normalizeStatus("error")).toBe("failed");
  });

  it("maps every in-flight pipeline state to analyzing", () => {
    for (const raw of ["running", "processing", "awaiting_ai"]) {
      expect(normalizeStatus(raw)).toBe("analyzing");
    }
  });

  it("ignores case and surrounding whitespace", () => {
    expect(normalizeStatus("  Completed ")).toBe("complete");
  });

  it("returns unknown for empty or unrecognised values instead of guessing", () => {
    expect(normalizeStatus(null)).toBe("unknown");
    expect(normalizeStatus(undefined)).toBe("unknown");
    expect(normalizeStatus("")).toBe("unknown");
    expect(normalizeStatus("accepted")).toBe("unknown");
  });

  it("has a label for every status", () => {
    expect(STATUS_LABEL[normalizeStatus("queued")]).toBe("Queued");
    expect(STATUS_LABEL.unknown).toBe("Unknown");
  });
});
