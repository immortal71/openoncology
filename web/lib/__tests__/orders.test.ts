import { describe, it, expect, beforeEach } from "vitest";
import { saveOrderToLocalStorage, getOrdersFromLocalStorage } from "@/lib/orders";

const meta = {
  target_gene: "KRAS",
  cancer_type: "NSCLC",
  result_id: "res-1",
};

describe("orders localStorage helpers", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("returns an empty object when nothing is stored", () => {
    expect(getOrdersFromLocalStorage()).toEqual({});
  });

  it("saves and reads back an order, stamping saved_at", () => {
    saveOrderToLocalStorage("req-1", meta);
    const stored = getOrdersFromLocalStorage();
    expect(stored["req-1"]).toMatchObject(meta);
    expect(typeof stored["req-1"].saved_at).toBe("string");
    // saved_at should be a valid ISO timestamp.
    expect(Number.isNaN(Date.parse(stored["req-1"].saved_at))).toBe(false);
  });

  it("accumulates multiple orders without clobbering", () => {
    saveOrderToLocalStorage("req-1", meta);
    saveOrderToLocalStorage("req-2", { ...meta, target_gene: "EGFR" });
    const stored = getOrdersFromLocalStorage();
    expect(Object.keys(stored).sort()).toEqual(["req-1", "req-2"]);
    expect(stored["req-2"].target_gene).toBe("EGFR");
  });

  it("overwrites an existing order with the same id", () => {
    saveOrderToLocalStorage("req-1", meta);
    saveOrderToLocalStorage("req-1", { ...meta, cancer_type: "Colorectal" });
    const stored = getOrdersFromLocalStorage();
    expect(Object.keys(stored)).toHaveLength(1);
    expect(stored["req-1"].cancer_type).toBe("Colorectal");
  });
});
