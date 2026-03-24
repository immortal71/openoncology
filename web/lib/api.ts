/**
 * API client for the OpenOncology FastAPI backend.
 * All calls include the Keycloak Bearer token from session storage.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("kc_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    ...(options.headers as Record<string, string>),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed: ${res.status}`);
  }

  return res.json() as Promise<T>;
}

export const api = {
  /** Submit a patient sample for genomic analysis */
  submitSample: (form: FormData) =>
    request<{ submission_id: string; status: string; job_id: string }>("/api/submit/", {
      method: "POST",
      body: form,
    }),

  /** Get submission status + mutation results */
  getResults: (submissionId: string) =>
    request<{
      submission_id: string;
      status: string;
      cancer_type: string;
      has_targetable_mutation: boolean;
      target_gene: string | null;
      summary: string | null;
      plain_language_summary: string | null;
      cbioportal_data: { study_id: string; cancer_type: string; mutation_count: number }[] | null;
      cosmic_sample_count: string | null;
      oncologist_reviewed: boolean;
      oncologist_notes: string | null;
      mutations: Record<string, unknown>[];
      result_id: string | null;
      message?: string;
    }>(`/api/results/${submissionId}`),

  /** Get all submissions for the current patient */
  getAllSubmissions: () =>
    request<
      {
        submission_id: string;
        cancer_type: string;
        status: string;
        submitted_at: string;
        completed_at: string | null;
      }[]
    >("/api/results/dashboard/all"),

  /** Get drug repurposing candidates for a result */
  getRepurposing: (resultId: string) =>
    request<{
      result_id: string;
      target_gene: string | null;
      has_targetable_mutation: boolean;
      message?: string;
      candidates: {
        drug_name: string;
        chembl_id: string;
        approval_status: string;
        mechanism: string;
        binding_score: number | null;
        opentargets_score: number | null;
        rank_score: number | null;
      }[];
    }>(`/api/repurposing/${resultId}`),

  /** List verified pharma companies */
  getPharmaCompanies: () =>
    request<
      {
        id: string;
        name: string;
        country: string;
        description: string;
        min_order_usd: number | null;
      }[]
    >("/api/marketplace/pharma"),

  /** Get a public crowdfunding campaign */
  getCampaign: (slug: string) =>
    request<{
      campaign_id: string;
      slug: string;
      title: string;
      patient_story: string;
      goal_usd: number;
      raised_usd: number;
      percent_complete: number;
    }>(`/api/crowdfund/${slug}`),

  /** Get the authenticated user's profile */
  getMe: () =>
    request<{
      id: string;
      email: string;
      name: string;
      roles: string[];
    }>("/api/auth/me"),

  // ── DRUG REQUESTS & BIDDING ──────────────────────────────────────────────

  /** Create a new drug synthesis request (patient) */
  createDrugRequest: (body: {
    drug_spec: string;
    target_gene?: string;
    max_budget_usd?: number;
    result_id?: string;
  }) =>
    request<{ drug_request_id: string; status: string }>("/api/marketplace/drug-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  /** List all open drug synthesis requests (public — pharma view) */
  getDrugRequests: () =>
    request<
      {
        id: string;
        target_gene: string | null;
        drug_spec: string;
        max_budget_usd: number | null;
        bid_count: number;
        created_at: string;
      }[]
    >("/api/marketplace/drug-requests"),

  /** List bids on a specific request (patient only) */
  getBids: (requestId: string) =>
    request<
      {
        id: string;
        pharma_id: string;
        price_usd: number;
        estimated_weeks: string;
        notes: string | null;
        status: string;
        created_at: string;
      }[]
    >(`/api/marketplace/drug-requests/${requestId}/bids`),

  /** Submit a bid on a drug request (pharma) */
  submitBid: (
    requestId: string,
    body: { price_usd: number; estimated_weeks: number; notes?: string }
  ) =>
    request<{ bid_id: string; status: string; price_usd: number }>(
      `/api/marketplace/drug-requests/${requestId}/bids`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    ),

  /** Accept a bid and get Stripe client_secret (patient) */
  acceptBid: (requestId: string, bidId: string) =>
    request<{
      bid_id: string;
      price_usd: number;
      estimated_weeks: string;
      client_secret: string;
      status: string;
    }>(`/api/marketplace/drug-requests/${requestId}/bids/${bidId}/accept`, {
      method: "POST",
    }),
};
