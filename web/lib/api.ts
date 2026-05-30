/**
 * API client for the OpenOncology FastAPI backend.
 * All calls include the Keycloak Bearer token from session storage.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 15000;

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  const token = sessionStorage.getItem("kc_token");
  if (token) return token;

  // Local development fallback when Keycloak is not running.
  const isLocalApi = API_URL.includes("localhost") || API_URL.includes("127.0.0.1");
  const isLocalHost = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
  if (isLocalApi && isLocalHost) {
    sessionStorage.setItem("kc_token", "demo-local-token");
    return "demo-local-token";
  }

  return null;
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

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`Request timed out after ${REQUEST_TIMEOUT_MS / 1000}s`);
    }
    throw new Error("Network error: unable to reach API");
  } finally {
    clearTimeout(timeoutId);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed: ${res.status}`);
  }

  return res.json() as Promise<T>;
}

function normalizeDrugRequests<T extends { requests?: unknown }>(payload: T | unknown[]): unknown[] {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && typeof payload === "object" && Array.isArray((payload as { requests?: unknown[] }).requests)) {
    return (payload as { requests: unknown[] }).requests;
  }
  return [];
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
      patient_summary: {
        explanation?: string;
        top_drugs?: {
          drug_name?: string;
          approval_status?: string;
          patient_note?: string;
        }[];
        what_next?: string[];
      } | null;
      cbioportal_data: { study_id: string; cancer_type: string; mutation_count: number }[] | null;
      cosmic_sample_count: string | null;
      oncologist_reviewed: boolean;
      oncologist_notes: string | null;
      custom_drug_possible: boolean;
      custom_drug_reason: string;
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
        evidence_sources: string[];
        matched_terms: string[];
      }[];
    }>(`/api/repurposing/${resultId}`),

  /** Get live ClinicalTrials.gov matches for a result */
  getClinicalTrials: (resultId: string) =>
    request<{
      result_id: string;
      cancer_type: string;
      target_gene: string | null;
      message?: string;
      trials: {
        trial_id: string;
        title: string;
        phase: string;
        status: string;
        cancer_type: string;
        drugs: string[];
        basket_trial: boolean;
        expanded_access_hint: boolean;
        trial_url: string | null;
        source: string;
      }[];
    }>(`/api/repurposing/${resultId}/trials`),

  /** Get immunotherapy biomarker profile (TMB, MSI-H, HRD, POLE) for a result */
  getImmunotherapyProfile: (resultId: string) =>
    request<{
      result_id: string;
      available: boolean;
      message?: string;
      profile: {
        tmb_per_mb: number;
        tmb_high: boolean;
        msi_high: boolean;
        hrd: boolean;
        pole_mutation: boolean;
        mmr_gene_hits: string[];
        hrd_gene_hits: string[];
        candidates: {
          drug_name: string;
          drug_class: string;
          oncokb_level: string;
          indication?: string;
          evidence_note?: string;
          rank_score_estimate: number;
        }[];
      } | null;
    }>(`/api/repurposing/${resultId}/immunotherapy`),

  /** Get dominant SBS mutational signature + treatment implication for a result */
  getMutationalSignature: (resultId: string) =>
    request<{
      result_id: string;
      available: boolean;
      message?: string;
      signature: {
        dominant_signature: string | null;
        signature_fraction: number;
        confidence: string;
        mutation_count: number;
        all_fractions: Record<string, number>;
        implication: {
          signature_name: string;
          drug_class: string;
          drug_recommendations: string[];
          oncokb_level: string;
          evidence_note?: string;
        } | null;
      } | null;
    }>(`/api/repurposing/${resultId}/signatures`),

  /** Get combination therapy suggestions for a result */
  getCombinationTherapy: (resultId: string) =>
    request<{
      result_id: string;
      count: number;
      message: string;
      combinations: {
        drugs: string[];
        synergy_type: string;
        rationale: string;
        combination_score: number;
        evidence_level: string;
        evidence_note: string;
        cancer_type_context?: string | null;
        trial_ids: string[];
      }[];
    }>(`/api/repurposing/${resultId}/combinations`),

  /** Generate custom discovery brief for a result */
  getDiscoveryBrief: (resultId: string) =>
    request<{
      mode: string;
      reason: string;
      target_gene: string;
      cancer_type: string;
      mutation_profile: string[];
      lead_candidates: Record<string, unknown>[];
      component_library: { scaffolds: string[]; fragments: string[] };
    }>(`/api/marketplace/discovery-brief/${resultId}`),

  /** Auto-create marketplace request from result context */
  createDrugRequestFromResult: (resultId: string, maxBudgetUsd?: number) =>
    request<{
      drug_request_id: string;
      status: string;
      mode: string;
      target_gene: string;
      cancer_type: string;
      brief_preview: {
        reason: string;
        lead_count: number;
        scaffold_count: number;
        fragment_count: number;
      };
    }>(`/api/marketplace/drug-requests/from-result/${resultId}${maxBudgetUsd ? `?max_budget_usd=${maxBudgetUsd}` : ""}`, {
      method: "POST",
    }),

  /** Get a single drug request with staged status and full brief when complete */
  getDrugRequest: (requestId: string) =>
    request<{
      drug_request_id: string;
      result_id: string;
      status: string;
      target_gene: string;
      cancer_type: string;
      message?: string;
      stage: number;
      mutation_profile?: string[];
      rationale?: string;
      live_data_used?: boolean;
      integration_issues?: string[];
      lead_compounds?: {
        name: string;
        smiles: string;
        binding_score: number | null;
        design_priority_score: number | null;
        oral_exposure_score: number | null;
        synthesis_feasibility_score: number | null;
        toxicity_risk: number | null;
        toxicity_flag: boolean;
        mechanism: string;
        phase: string;
        evidence_sources: string[];
        matched_terms: string[];
        ensemble_score?: number;
        ensemble_breakdown?: Record<string, number | null>;
      }[];
      de_novo_candidates?: {
        candidate_id: string;
        parent_lead: string;
        design_strategy: string;
        proposed_smiles: string | null;
        selected_scaffold: string | null;
        selected_fragment: string | null;
        docking_binding_score: number | null;
        target_fit_score: number;
        novelty_score: number;
        feasibility_score: number;
        overall_score: number;
        evidence_sources: string[];
        matched_terms: string[];
        ensemble_score?: number;
        ensemble_breakdown?: Record<string, number | null>;
        disclaimer: string;
      }[];
      docking_summary?: {
        runs_attempted: number;
        used_mutation_specific_structure: boolean;
        structure_path: string | null;
      };
      computational_synthesis_plan?: {
        mode?: string;
        status?: string;
        summary?: string;
        synthesis_readiness_score?: number;
        selected_candidates?: {
          candidate_id?: string;
          parent_lead?: string;
          proposed_smiles?: string | null;
          precursor_count_estimate?: number;
          route_confidence_score?: number;
          route_outline?: string[];
        }[];
        execution_stages?: {
          stage?: string;
          duration?: string;
          deliverable?: string;
        }[];
        constraints?: string[];
        disclaimer?: string;
      };
      scaffold_summary?: {
        core_scaffolds: string[];
        fragment_hits: string[];
        admet_notes: string;
      };
      timeline_weeks?: Record<string, string>;
      next_steps?: string[];
      attributions?: string[];
      scoring_engines_used?: string[];
    }>(`/api/marketplace/drug-requests/${requestId}`),

  /** List all submitted drug requests (in demo: server-side; also augmented from localStorage) */
  listDrugRequests: () =>
    request<
      | {
          requests: {
            drug_request_id: string;
            result_id: string;
            target_gene: string;
            cancer_type: string;
            status: string;
          }[];
        }
      | {
          drug_request_id: string;
          result_id: string;
          target_gene: string;
          cancer_type: string;
          status: string;
        }[]
    >("/api/marketplace/drug-requests").then((payload) => ({
      requests: normalizeDrugRequests(payload) as {
        drug_request_id: string;
        result_id: string;
        target_gene: string;
        cancer_type: string;
        status: string;
      }[],
    })),

  /** Download-ready custom drug report text */
  getCustomDrugReport: (resultId: string) =>
    request<{
      result_id: string;
      filename: string;
      report_text: string;
      brief: Record<string, unknown>;
    }>(`/api/marketplace/custom-drug-report/${resultId}`),

  /** Nearby pharmacy placeholder list */
  getNearbyPharmacies: () =>
    request<{
      pharmacies: {
        name: string;
        distance_km: number;
        phone: string;
        address: string;
      }[];
    }>("/api/marketplace/nearby-pharmacies"),

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
      | {
          requests: {
            id: string;
            target_gene: string | null;
            drug_spec: string;
            max_budget_usd: number | null;
            bid_count: number;
            created_at: string;
          }[];
        }
      | {
          id: string;
          target_gene: string | null;
          drug_spec: string;
          max_budget_usd: number | null;
          bid_count: number;
          created_at: string;
        }[]
    >("/api/marketplace/drug-requests").then((payload) =>
      normalizeDrugRequests(payload) as {
        id: string;
        target_gene: string | null;
        drug_spec: string;
        max_budget_usd: number | null;
        bid_count: number;
        created_at: string;
      }[]
    ),

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

  // ── COHORT / STUDY EXPLORER ──────────────────────────────────────────────

  /** List all public genomic studies, with optional cancer_type / source filters */
  getStudies: (filters?: { cancer_type?: string; source?: string }) => {
    const params = new URLSearchParams();
    if (filters?.cancer_type) params.set("cancer_type", filters.cancer_type);
    if (filters?.source) params.set("source", filters.source);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{
      total: number;
      studies: {
        id: string;
        study_id: string;
        name: string;
        description: string | null;
        cancer_type: string | null;
        cancer_type_label: string | null;
        sample_count: number;
        data_types: string[] | null;
        reference_genome: string | null;
        pmid: string | null;
        source: string | null;
      }[];
    }>(`/api/cohorts/studies${qs}`);
  },

  /** Get details for a single study including live sample + gene counts */
  getStudyDetail: (studyId: string) =>
    request<{
      id: string;
      study_id: string;
      name: string;
      description: string | null;
      cancer_type: string | null;
      cancer_type_label: string | null;
      sample_count: number;
      data_types: string[] | null;
      reference_genome: string | null;
      pmid: string | null;
      source: string | null;
      sample_count_live: number;
      distinct_genes_mutated: number;
    }>(`/api/cohorts/studies/${studyId}`),

  /** Paginated mutation list for a study, with optional gene/classification filters */
  getCohortMutations: (
    studyId: string,
    params?: { gene?: string; classification?: string; page?: number; per_page?: number }
  ) => {
    const qs = new URLSearchParams();
    if (params?.gene) qs.set("gene", params.gene);
    if (params?.classification) qs.set("classification", params.classification);
    if (params?.page) qs.set("page", String(params.page));
    if (params?.per_page) qs.set("per_page", String(params.per_page));
    const q = qs.toString() ? `?${qs.toString()}` : "";
    return request<{
      study_id: string;
      gene_filter: string | null;
      total: number;
      page: number;
      per_page: number;
      mutations: {
        id: string;
        gene: string;
        sample_id: string;
        variant_classification: string | null;
        variant_type: string | null;
        protein_change: string | null;
        hgvsc: string | null;
        chromosome: string | null;
        start_position: number | null;
        end_position: number | null;
      }[];
    }>(`/api/cohorts/${studyId}/mutations${q}`);
  },

  /** Alteration frequency for a gene (and optional specific variant) across all studies */
  getCrossStudyFrequency: (gene: string, alteration?: string) => {
    const qs = new URLSearchParams({ gene });
    if (alteration) qs.set("alteration", alteration);
    return request<{
      gene: string;
      alteration: string | null;
      total_studies_with_alteration: number;
      frequency_by_study: {
        study_id: string;
        study_name: string;
        cancer_type: string | null;
        cancer_type_label: string | null;
        mutation_count: number;
        sample_count: number;
        frequency: number | null;
        frequency_pct: number | null;
      }[];
    }>(`/api/cohorts/cross-study?${qs.toString()}`);
  },

  /** OncoPrint alteration matrix for a gene panel in a study */
  getOncoprint: (studyId: string, genes: string[], maxSamples?: number) => {
    const qs = new URLSearchParams({ study_id: studyId, genes: genes.join(",") });
    if (maxSamples) qs.set("max_samples", String(maxSamples));
    return request<{
      study_id: string;
      genes: string[];
      samples: string[];
      sample_count: number;
      gene_frequencies: Record<string, number>;
      alterations: Record<string, Record<string, string[]>>;
    }>(`/api/cohorts/oncoprint?${qs.toString()}`);
  },

  /** Per-gene summary (top protein changes, variant classes, study list) */
  getGeneSummary: (gene: string) =>
    request<{
      gene: string;
      total_mutations: number;
      top_protein_changes: {
        protein_change: string;
        count: number;
        is_hotspot: boolean;
      }[];
      variant_classification_breakdown: {
        classification: string;
        count: number;
      }[];
      studies: {
        study_id: string;
        name: string;
        cancer_type: string | null;
        source: string | null;
      }[];
    }>(`/api/cohorts/gene-summary?gene=${encodeURIComponent(gene)}`),
};
