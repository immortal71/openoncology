/**
 * Demo data for ?demo=true mode on all pages.
 * Source: demo_output.json (KRAS G12C, Non-Small Cell Lung Cancer)
 */

export const DEMO_ID = "demo-nsclc-kras-g12c";

export const DEMO_RESULTS = {
  submission_id: DEMO_ID,
  status: "completed",
  cancer_type: "Non-Small Cell Lung Cancer",
  has_targetable_mutation: true,
  target_gene: "KRAS",
  summary:
    "Analysis identified 2 variant(s) in KRAS, TP53. Top repurposing candidate: Sotorasib (OncoKB Level 1). Cancer type: Non-Small Cell Lung Cancer.",
  plain_language_summary:
    "Your tumour carries a KRAS G12C mutation — a well-characterised actionable driver in lung cancer. Two FDA-approved targeted therapies (Sotorasib and Adagrasib) are ranked as top candidates. Oncologist review is required before any treatment decision.",
  patient_summary: {
    explanation:
      "Your tumour carries a KRAS G12C mutation. Two approved drugs are known to target this specific mutation in non-small cell lung cancer.",
    top_drugs: [
      {
        drug_name: "Sotorasib (Lumakras)",
        approval_status: "FDA Approved — NSCLC KRAS G12C",
        patient_note: "First FDA-approved drug specifically for KRAS G12C mutations in lung cancer.",
      },
      {
        drug_name: "Adagrasib (Krazati)",
        approval_status: "FDA Approved — NSCLC KRAS G12C",
        patient_note: "Second-generation KRAS G12C inhibitor, also FDA approved.",
      },
    ],
    what_next: [
      "Share this report with your oncologist or molecular tumour board",
      "Ask about clinical trials combining KRAS inhibitors with SHP2 or mTOR inhibitors",
      "Request full genomic profiling if only partial VCF available",
    ],
  },
  mutations: [
    {
      gene: "KRAS",
      hgvs: "p.Gly12Cys",
      classification: "Pathogenic",
      oncokb_level: "LEVEL_1",
      is_targetable: true,
    },
    {
      gene: "TP53",
      hgvs: "p.Arg175His",
      classification: "Pathogenic",
      oncokb_level: "LEVEL_3B",
      is_targetable: false,
    },
  ],
  cbioportal_data: null,
  cosmic_sample_count: null,
  result_id: DEMO_ID,
};

export const DEMO_REPURPOSING = {
  has_targetable_mutation: true,
  target_gene: "KRAS",
  candidates: [
    {
      drug_name: "Sotorasib",
      chembl_id: "CHEMBL4523582",
      approval_status: "FDA Approved",
      mechanism: "Covalent KRAS G12C inhibitor — locks the protein in inactive GDP-bound state",
      opentargets_score: 0.9,
      rank_score: 0.9827,
      evidence_sources: ["OncoKB", "OpenTargets", "DiffDock", "ClinicalPhase"],
      matched_terms: ["KRAS G12C", "NSCLC", "AMG-510"],
    },
    {
      drug_name: "Adagrasib",
      chembl_id: "CHEMBL4741767",
      approval_status: "FDA Approved",
      mechanism: "Irreversible KRAS G12C inhibitor with CNS penetration",
      opentargets_score: 0.88,
      rank_score: 0.9731,
      evidence_sources: ["OncoKB", "OpenTargets", "DiffDock", "ClinicalPhase"],
      matched_terms: ["KRAS G12C", "NSCLC", "MRTX849"],
    },
    {
      drug_name: "Osimertinib",
      chembl_id: "CHEMBL3353410",
      approval_status: "FDA Approved",
      mechanism: "EGFR T790M inhibitor — included as combination therapy candidate",
      opentargets_score: 0.61,
      rank_score: 0.71,
      evidence_sources: ["OncoKB", "ClinVar"],
      matched_terms: ["EGFR", "NSCLC", "combination"],
    },
  ],
};

export const DEMO_CUSTOM_DRUG = {
  drug_request_id: DEMO_ID,
  result_id: DEMO_ID,
  status: "complete",
  stage: 3,
  target_gene: "KRAS",
  cancer_type: "Non-Small Cell Lung Cancer",
  mutation_profile: ["KRAS p.Gly12Cys", "TP53 p.Arg175His"],
  rationale:
    "KRAS G12C is a well-validated oncology target. The mutation locks KRAS in an active GTP-bound state driving uncontrolled cell proliferation. Covalent inhibitors targeting the mutant cysteine represent the primary mechanistic approach, with two approved agents already in clinical use. De novo design focuses on improving CNS penetration and overcoming acquired resistance via SOS1/SHP2 co-inhibition.",
  live_data_used: true,
  integration_issues: [],
  lead_compounds: [
    {
      name: "Sotorasib",
      smiles: "CN1CC[NH+](C1)c2cc3c(F)cc(cc3[nH]2)C(=O)N[C@H]4CCOC4",
      binding_score: 0.85,
      design_priority_score: 0.94,
      oral_exposure_score: 0.91,
      synthesis_feasibility_score: 0.88,
      toxicity_risk: 0.12,
      toxicity_flag: false,
      mechanism: "Covalent KRAS G12C inhibitor (GDP-locked)",
      phase: "Phase 4 / Approved",
      evidence_sources: ["OncoKB", "OpenTargets", "ChEMBL"],
      matched_terms: ["KRAS G12C", "NSCLC"],
      ensemble_score: 0.9827,
    },
    {
      name: "Adagrasib",
      smiles: "CC1COCCN1c2cc3cc(F)cc(c3[nH]2)C(=O)N[C@@H]4CCOC4",
      binding_score: 0.82,
      design_priority_score: 0.91,
      oral_exposure_score: 0.88,
      synthesis_feasibility_score: 0.85,
      toxicity_risk: 0.14,
      toxicity_flag: false,
      mechanism: "Irreversible KRAS G12C inhibitor with CNS penetration",
      phase: "Phase 4 / Approved",
      evidence_sources: ["OncoKB", "OpenTargets", "ChEMBL"],
      matched_terms: ["KRAS G12C", "NSCLC", "CNS"],
      ensemble_score: 0.9731,
    },
  ],
  de_novo_candidates: [
    {
      candidate_id: "OO-DN-001",
      parent_lead: "Sotorasib",
      design_strategy: "Add SOS1 interaction loop binder to overcome acquired resistance",
      proposed_smiles: null,
      selected_scaffold: "Piperidine-linked pyrimidine",
      selected_fragment: "Covalent warhead (acrylamide)",
      docking_binding_score: 0.79,
      target_fit_score: 0.86,
      novelty_score: 0.72,
      feasibility_score: 0.81,
      overall_score: 0.8,
      evidence_sources: ["ChEMBL", "OpenTargets"],
      matched_terms: ["KRAS G12C", "SOS1"],
      disclaimer:
        "De novo design requires experimental validation. This candidate has not been synthesised or tested.",
    },
  ],
  scaffold_summary: {
    core_scaffolds: ["Piperidine-pyrimidine", "Indazole"],
    fragment_hits: ["Acrylamide warhead", "Fluorobenzene"],
    admet_notes: "Strong oral exposure (Ro5 compliant). Low BBB permeability predicted for lead scaffolds.",
  },
  next_steps: [
    "Synthesise OO-DN-001 and test binding affinity via SPR",
    "Run DiffDock against KRAS G12C crystal structure (PDB 6OIM)",
    "Test combination with SHP2 inhibitor (TNO155) in KRAS-mutant cell lines",
  ],
  docking_summary: {
    runs_attempted: 2,
    used_mutation_specific_structure: true,
    structure_path: "alphafold/KRAS_G12C.pdb",
  },
};

export const DEMO_DRUG_REQUESTS = [
  {
    id: DEMO_ID,
    target_gene: "KRAS",
    drug_spec:
      "Seeking manufacturers capable of synthesising KRAS G12C covalent inhibitor scaffold. Target: KRAS G12C (PDB 6OIM). Lead compound: Sotorasib analogue with improved CNS penetration and resistance profile. Full discovery brief available. GMP synthesis required for IND-enabling studies.",
    max_budget_usd: 250000,
    bid_count: 3,
    created_at: new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString(),
  },
];

export const DEMO_CROWDFUND = {
  id: DEMO_ID,
  slug: DEMO_ID,
  title: "Custom KRAS G12C inhibitor for María — NSCLC patient",
  description:
    "María has a KRAS G12C mutation driving her non-small cell lung cancer. Her oncologist has identified a novel KRAS inhibitor candidate from OpenOncology's discovery pipeline that could work where existing drugs have failed. Help fund the synthesis and early-stage testing.",
  goal_usd: 180000,
  raised_usd: 121400,
  backer_count: 847,
  created_at: new Date(Date.now() - 18 * 24 * 3600 * 1000).toISOString(),
  end_date: new Date(Date.now() + 12 * 24 * 3600 * 1000).toISOString(),
  patient_name: "María",
  cancer_type: "Non-Small Cell Lung Cancer",
  target_gene: "KRAS G12C",
};
