const LS_KEY = "oo_drug_request_ids";

type OrderMeta = {
  target_gene: string;
  cancer_type: string;
  result_id: string;
};

type StoredOrderMeta = OrderMeta & {
  saved_at: string;
};

export function saveOrderToLocalStorage(requestId: string, meta: OrderMeta): void {
  if (typeof window === "undefined") return;
  const existing: Record<string, StoredOrderMeta> = JSON.parse(localStorage.getItem(LS_KEY) ?? "{}");
  existing[requestId] = { ...meta, saved_at: new Date().toISOString() };
  localStorage.setItem(LS_KEY, JSON.stringify(existing));
}

export function getOrdersFromLocalStorage(): Record<string, StoredOrderMeta> {
  if (typeof window === "undefined") return {};
  return JSON.parse(localStorage.getItem(LS_KEY) ?? "{}");
}
