from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="OpenOncology Mock API")

# Allow calls from the frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:(3000|3001|3002)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Mutation(BaseModel):
    gene: str
    hgvs: str
    consequence: str


class Candidate(BaseModel):
    name: str
    source: str
    score: float


# In-memory submission tracker for local demo mode.
SUBMISSIONS: dict[str, dict[str, object]] = {}

# In-memory drug request tracker.
DRUG_REQUESTS: dict[str, dict[str, object]] = {}


def _is_sample2_case(biopsy_name: str, dna_name: str, cancer_type: str) -> bool:
    marker = f"{biopsy_name} {dna_name} {cancer_type}".lower()
    return "sample2" in marker or "no_repurpose" in marker or "no-repurpose" in marker


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mock-api"}


@app.post("/api/submit/")
async def submit_sample(biopsy_file: UploadFile = File(...), dna_file: UploadFile = File(...), cancer_type: str = Form(...)):
    submission_id = f"mock-{uuid4().hex[:10]}"
    scenario = "no_repurpose" if _is_sample2_case(biopsy_file.filename or "", dna_file.filename or "", cancer_type) else "repurpose_ok"
    SUBMISSIONS[submission_id] = {
        "created_at": monotonic(),
        "cancer_type": cancer_type,
        "scenario": scenario,
        "biopsy_filename": biopsy_file.filename or "",
        "dna_filename": dna_file.filename or "",
    }

    return JSONResponse({
        "status": "queued",
        "submission_id": submission_id,
        "job_id": f"mock-job-{submission_id[-6:]}",
        "message": "Sample received. Mutation/actionability checks are starting.",
    }, status_code=202)


@app.get("/api/results/{result_id}")
async def get_result(result_id: str):
    submission = SUBMISSIONS.get(result_id)
    created_at = submission.get("created_at") if submission else None
    elapsed = monotonic() - float(created_at) if created_at else 999.0
    scenario = str(submission.get("scenario", "repurpose_ok")) if submission else "repurpose_ok"
    is_sample2 = scenario == "no_repurpose"

    # Local demo progression: queued -> analyzing -> complete
    if elapsed < 6:
        return {
            "submission_id": result_id,
            "result_id": result_id,
            "status": "queued",
            "cancer_type": str(submission.get("cancer_type", "Unknown")) if submission else "Unknown",
            "has_targetable_mutation": False,
            "target_gene": None,
            "custom_drug_possible": False,
            "custom_drug_reason": "Mutation analysis is still running.",
            "mutations": [],
            "message": "Step 1/3: parsing upload and checking mutation calls.",
            "summary": None,
            "plain_language_summary": None,
            "oncologist_reviewed": False,
            "oncologist_notes": None,
            "cbioportal_data": None,
            "cosmic_sample_count": None,
        }

    if elapsed < 12:
        return {
            "submission_id": result_id,
            "result_id": result_id,
            "status": "analyzing",
            "cancer_type": str(submission.get("cancer_type", "Unknown")) if submission else "Unknown",
            "has_targetable_mutation": True,
            "target_gene": "KRAS" if is_sample2 else "EGFR",
            "custom_drug_possible": True,
            "custom_drug_reason": "Target signal detected. Preparing repurposing search.",
            "mutations": [
                {"gene": "TP53", "hgvs": "p.R175H", "classification": "likely_pathogenic", "oncokb_level": "N/A", "is_targetable": False},
                {"gene": "KRAS", "hgvs": "p.G12D", "classification": "likely_pathogenic", "oncokb_level": "4", "is_targetable": True}
                if is_sample2
                else {"gene": "EGFR", "hgvs": "p.L858R", "classification": "likely_pathogenic", "oncokb_level": "1", "is_targetable": True},
            ],
            "message": "Step 2/3: mutation actionability confirmed. Running repurposing ranking.",
            "summary": "Targetable mutation detected. Repurposing search in progress.",
            "plain_language_summary": "We found a mutation we may be able to treat. Looking for repurposed options now.",
            "oncologist_reviewed": False,
            "oncologist_notes": None,
            "cbioportal_data": None,
            "cosmic_sample_count": None,
        }

    if is_sample2:
        return {
            "submission_id": result_id,
            "result_id": result_id,
            "status": "complete",
            "cancer_type": str(submission.get("cancer_type", "Pancreatic adenocarcinoma")) if submission else "Pancreatic adenocarcinoma",
            "has_targetable_mutation": True,
            "target_gene": "KRAS",
            "summary": "Actionable mutation found, but no strong repurposed candidates were identified.",
            "plain_language_summary": "We found a mutation, but existing repurposed medicines were not suitable in this simulated case. Custom-drug generation is recommended.",
            "custom_drug_possible": True,
            "custom_drug_reason": "No repurposing hit above threshold. Custom medicinal chemistry path is available.",
            "oncologist_reviewed": False,
            "oncologist_notes": None,
            "cbioportal_data": [
                {"study_id": "paad_tcga", "cancer_type": "Pancreatic adenocarcinoma", "mutation_count": 2}
            ],
            "cosmic_sample_count": "812",
            "mutations": [
                {"gene": "TP53", "hgvs": "p.R175H", "classification": "likely_pathogenic", "oncokb_level": "N/A", "is_targetable": False},
                {"gene": "KRAS", "hgvs": "p.G12D", "classification": "likely_pathogenic", "oncokb_level": "4", "is_targetable": True},
            ],
            "message": "Step 3/3 complete: no repurposing hit. Custom-drug path is ready.",
        }

    return {
        "submission_id": result_id,
        "result_id": result_id,
        "status": "complete",
        "cancer_type": str(submission.get("cancer_type", "Lung adenocarcinoma")) if submission else "Lung adenocarcinoma",
        "has_targetable_mutation": True,
        "target_gene": "EGFR",
        "summary": "Actionable mutation found. Repurposed options are available.",
        "plain_language_summary": "Good news: we found a mutation that may be treatable. We already ranked repurposed medicines for you.",
        "custom_drug_possible": True,
        "custom_drug_reason": "If repurposed options are not suitable, custom design is feasible.",
        "oncologist_reviewed": False,
        "oncologist_notes": None,
        "cbioportal_data": [
            {"study_id": "luad_tcga", "cancer_type": "Lung adenocarcinoma", "mutation_count": 2}
        ],
        "cosmic_sample_count": "1243",
        "mutations": [
            {"gene": "TP53", "hgvs": "p.R175H", "classification": "likely_pathogenic", "oncokb_level": "N/A", "is_targetable": False},
            {"gene": "EGFR", "hgvs": "p.L858R", "classification": "likely_pathogenic", "oncokb_level": "1", "is_targetable": True},
        ],
        "message": "Step 3/3 complete: repurposing ranking is ready.",
    }


@app.get("/api/repurposing/{result_id}")
async def get_repurposing(result_id: str):
    submission = SUBMISSIONS.get(result_id)
    scenario = str(submission.get("scenario", "repurpose_ok")) if submission else "repurpose_ok"

    if scenario == "no_repurpose":
        return {
            "result_id": result_id,
            "target_gene": "KRAS",
            "has_targetable_mutation": True,
            "message": "Repurposing run completed, but no candidate passed threshold.",
            "candidates": [],
        }

    return {
        "result_id": result_id,
        "target_gene": "EGFR",
        "has_targetable_mutation": True,
        "message": "Repurposing candidates generated automatically from mutation profile.",
        "candidates": [
            {
                "drug_name": "Osimertinib",
                "chembl_id": "CHEMBL3353410",
                "approval_status": "FDA-approved",
                "mechanism": "EGFR inhibitor",
                "binding_score": 0.87,
                "opentargets_score": 0.81,
                "rank_score": 0.86,
            },
            {
                "drug_name": "Erlotinib",
                "chembl_id": "CHEMBL553",
                "approval_status": "FDA-approved",
                "mechanism": "EGFR inhibitor",
                "binding_score": 0.74,
                "opentargets_score": 0.69,
                "rank_score": 0.72,
            },
        ],
    }


@app.post("/api/marketplace/drug-requests/from-result/{result_id}")
async def create_drug_request_from_result(result_id: str):
    submission = SUBMISSIONS.get(result_id) or {}
    scenario = str(submission.get("scenario", "repurpose_ok"))
    cancer_type = str(submission.get("cancer_type", "Unknown"))
    target_gene = "KRAS" if scenario == "no_repurpose" else "EGFR"
    request_id = f"drq-{result_id[-8:]}"

    DRUG_REQUESTS[request_id] = {
        "created_at": monotonic(),
        "result_id": result_id,
        "scenario": scenario,
        "cancer_type": cancer_type,
        "target_gene": target_gene,
    }

    return {
        "drug_request_id": request_id,
        "status": "queued",
        "mode": "custom_design",
        "target_gene": target_gene,
        "cancer_type": cancer_type,
        "brief_preview": {
            "reason": "No repurposing hit above rank threshold." if scenario == "no_repurpose" else "Alternative strategy requested.",
            "lead_count": 3,
            "scaffold_count": 2,
            "fragment_count": 4,
        },
    }


@app.get("/api/marketplace/drug-requests/{request_id}")
async def get_drug_request(request_id: str):
    req = DRUG_REQUESTS.get(request_id)
    if not req:
        # Return a completed demo brief even for unknown IDs so old links still work
        req = {
            "created_at": monotonic() - 999,
            "result_id": request_id,
            "scenario": "no_repurpose",
            "cancer_type": "Unknown",
            "target_gene": "KRAS",
        }

    created_at = float(req["created_at"])  # type: ignore[arg-type]
    elapsed = monotonic() - created_at
    target_gene = str(req.get("target_gene", "KRAS"))
    cancer_type = str(req.get("cancer_type", "Unknown"))
    result_id = str(req.get("result_id", request_id))

    # Stage timing: queued 0-8s → synthesizing 8-18s → complete 18s+
    if elapsed < 8:
        return {
            "drug_request_id": request_id,
            "result_id": result_id,
            "status": "queued",
            "target_gene": target_gene,
            "cancer_type": cancer_type,
            "message": "Request received. Preparing target protein data.",
            "stage": 0,
        }

    if elapsed < 18:
        return {
            "drug_request_id": request_id,
            "result_id": result_id,
            "status": "synthesizing",
            "target_gene": target_gene,
            "cancer_type": cancer_type,
            "message": "Running AlphaFold structure prediction and DiffDock binding simulation.",
            "stage": 1,
        }

    # Complete — return rich brief
    if target_gene == "KRAS":
        lead_compounds = [
            {
                "name": "OO-KRS-001",
                "smiles": "CC(=O)Nc1ccc(cc1)S(=O)(=O)N",
                "binding_score": 0.86,
                "design_priority_score": 82.0,
                "oral_exposure_score": 62.0,
                "synthesis_feasibility_score": 71.0,
                "toxicity_risk": 18.0,
                "toxicity_flag": False,
                "mechanism": "Covalent inhibitor targeting KRAS G12D switch-II pocket",
                "phase": "In silico lead",
                "evidence_sources": ["AlphaFold Server", "DiffDock", "ChEMBL"],
                "matched_terms": ["KRAS G12D", "switch-II pocket"],
            },
            {
                "name": "OO-KRS-002",
                "smiles": "COc1ccc2c(c1)nc(N)n2",
                "binding_score": 0.79,
                "design_priority_score": 74.0,
                "oral_exposure_score": 55.0,
                "synthesis_feasibility_score": 68.0,
                "toxicity_risk": 21.0,
                "toxicity_flag": False,
                "mechanism": "Non-covalent allosteric binder, disrupts SOS1 interaction",
                "phase": "In silico lead",
                "evidence_sources": ["DiffDock", "OpenTargets"],
                "matched_terms": ["KRAS", "SOS1 interaction"],
            },
            {
                "name": "OO-KRS-003",
                "smiles": "Cc1cc(NC(=O)c2ccccc2)ccc1F",
                "binding_score": 0.71,
                "design_priority_score": 63.0,
                "oral_exposure_score": 48.0,
                "synthesis_feasibility_score": 66.0,
                "toxicity_risk": 27.0,
                "toxicity_flag": False,
                "mechanism": "Small molecule GDP-state stabilizer",
                "phase": "In silico screening hit",
                "evidence_sources": ["Fragment screen"],
                "matched_terms": ["GDP state", "KRAS"],
            },
        ]
        de_novo_candidates = [
            {
                "candidate_id": "DNV-KRAS-01",
                "parent_lead": "OO-KRS-001",
                "design_strategy": "Scaffold hopping + fragment recombination",
                "proposed_smiles": "CC(=O)Nc1ccc(cc1)S(=O)(=O)NCC2=NC=CC(=N2)N",
                "selected_scaffold": "Pyrimidine-sulfonamide",
                "selected_fragment": "F-001 (covalent warhead)",
                "docking_binding_score": 0.83,
                "target_fit_score": 86.0,
                "novelty_score": 69.0,
                "feasibility_score": 73.0,
                "overall_score": 80.4,
                "evidence_sources": ["AlphaFold Server", "DiffDock"],
                "matched_terms": ["KRAS G12D", "covalent warhead"],
                "disclaimer": "Computational design proposal for medicinal-chemistry triage only; requires synthesis and wet-lab validation.",
            },
            {
                "candidate_id": "DNV-KRAS-02",
                "parent_lead": "OO-KRS-002",
                "design_strategy": "Pocket-focused linker exploration",
                "proposed_smiles": "COc1ccc2c(c1)nc(N)n2CC(=O)Nc3ccc(F)cc3",
                "selected_scaffold": "Quinazoline-amine",
                "selected_fragment": "F-003 (hinge binder)",
                "docking_binding_score": 0.78,
                "target_fit_score": 79.0,
                "novelty_score": 74.0,
                "feasibility_score": 70.0,
                "overall_score": 76.8,
                "evidence_sources": ["DiffDock", "Fragment screen"],
                "matched_terms": ["allosteric binder", "hinge binder"],
                "disclaimer": "Computational design proposal for medicinal-chemistry triage only; requires synthesis and wet-lab validation.",
            },
        ]
        scaffold_summary = {
            "core_scaffolds": ["Pyrimidine-sulfonamide", "Quinazoline-amine"],
            "fragment_hits": ["F-001 (covalent warhead)", "F-002 (linker)", "F-003 (hinge binder)", "F-004 (selectivity tail)"],
            "admet_notes": "Predicted hepatic clearance moderate. CYP3A4 interaction low. No hERG flag.",
        }
        docking_summary = {
            "runs_attempted": 2,
            "used_mutation_specific_structure": True,
            "structure_path": "mock://structures/KRAS_G12D_model.pdb",
        }
    else:
        lead_compounds = [
            {
                "name": "OO-EGF-001",
                "smiles": "Clc1cc2c(cc1)ncnc2Nc1ccccc1",
                "binding_score": 0.91,
                "design_priority_score": 88.0,
                "oral_exposure_score": 71.0,
                "synthesis_feasibility_score": 75.0,
                "toxicity_risk": 16.0,
                "toxicity_flag": False,
                "mechanism": "4th-generation EGFR inhibitor with mutant selectivity over WT",
                "phase": "In silico lead",
                "evidence_sources": ["AlphaFold Server", "DiffDock", "OpenTargets"],
                "matched_terms": ["EGFR L858R", "mutant selectivity"],
            },
            {
                "name": "OO-EGF-002",
                "smiles": "FC(F)(F)c1ccc(NC(=O)Nc2ccc(cc2)Cl)cc1",
                "binding_score": 0.84,
                "design_priority_score": 79.0,
                "oral_exposure_score": 64.0,
                "synthesis_feasibility_score": 72.0,
                "toxicity_risk": 19.0,
                "toxicity_flag": False,
                "mechanism": "Irreversible EGFR C797S bypass compound",
                "phase": "In silico lead",
                "evidence_sources": ["DiffDock", "ChEMBL"],
                "matched_terms": ["EGFR", "C797S bypass"],
            },
        ]
        de_novo_candidates = [
            {
                "candidate_id": "DNV-EGFR-01",
                "parent_lead": "OO-EGF-001",
                "design_strategy": "Selectivity-pocket expansion",
                "proposed_smiles": "Clc1cc2c(cc1)ncnc2Nc1ccc(CC(=O)N3CCOCC3)cc1",
                "selected_scaffold": "Anilinoquinazoline",
                "selected_fragment": "F-102 (selectivity filter)",
                "docking_binding_score": 0.87,
                "target_fit_score": 89.0,
                "novelty_score": 66.0,
                "feasibility_score": 76.0,
                "overall_score": 82.7,
                "evidence_sources": ["AlphaFold Server", "DiffDock"],
                "matched_terms": ["EGFR L858R", "selectivity filter"],
                "disclaimer": "Computational design proposal for medicinal-chemistry triage only; requires synthesis and wet-lab validation.",
            },
            {
                "candidate_id": "DNV-EGFR-02",
                "parent_lead": "OO-EGF-002",
                "design_strategy": "Warhead replacement for resistance bypass",
                "proposed_smiles": "FC(F)(F)c1ccc(NC(=O)Nc2ccc(cc2)Cl)cc1OCCN",
                "selected_scaffold": "Trifluoromethyl-urea",
                "selected_fragment": "F-104 (linker)",
                "docking_binding_score": 0.8,
                "target_fit_score": 81.0,
                "novelty_score": 72.0,
                "feasibility_score": 74.0,
                "overall_score": 77.9,
                "evidence_sources": ["DiffDock", "OpenTargets"],
                "matched_terms": ["C797S bypass", "resistance"],
                "disclaimer": "Computational design proposal for medicinal-chemistry triage only; requires synthesis and wet-lab validation.",
            },
        ]
        scaffold_summary = {
            "core_scaffolds": ["Anilinoquinazoline", "Trifluoromethyl-urea"],
            "fragment_hits": ["F-101 (warhead)", "F-102 (selectivity filter)", "F-103 (solubilising group)", "F-104 (linker)"],
            "admet_notes": "Predicted high intestinal absorption. Low CYP1A2 liability. BBB penetration unlikely.",
        }
        docking_summary = {
            "runs_attempted": 2,
            "used_mutation_specific_structure": True,
            "structure_path": "mock://structures/EGFR_L858R_model.pdb",
        }

    return {
        "drug_request_id": request_id,
        "result_id": result_id,
        "status": "complete",
        "target_gene": target_gene,
        "cancer_type": cancer_type,
        "mutation_profile": [
            f"{target_gene} p.G12D — likely pathogenic, OncoKB level 4" if target_gene == "KRAS"
            else f"{target_gene} p.L858R — likely pathogenic, OncoKB level 1",
            "TP53 p.R175H — likely pathogenic, non-targetable",
        ],
        "rationale": (
            f"No approved or repurposed drug exceeded the actionability threshold for {target_gene} in this cancer context. "
            "A de novo medicinal chemistry programme is warranted. "
            "AlphaFold v3 was used to predict the mutant protein structure; DiffDock was used for blind docking across 50,000 fragment hits."
        ),
        "lead_compounds": lead_compounds,
        "de_novo_candidates": de_novo_candidates,
        "docking_summary": docking_summary,
        "scaffold_summary": scaffold_summary,
        "computational_synthesis_plan": {
            "mode": "computational_synthesis_planning",
            "status": "ready_for_medicinal_chemistry_review",
            "summary": "Top de novo candidates include in-silico retrosynthesis route hypotheses for chemist triage.",
            "synthesis_readiness_score": 72.5,
            "selected_candidates": [
                {
                    "candidate_id": de_novo_candidates[0]["candidate_id"] if de_novo_candidates else None,
                    "parent_lead": de_novo_candidates[0]["parent_lead"] if de_novo_candidates else None,
                    "proposed_smiles": de_novo_candidates[0]["proposed_smiles"] if de_novo_candidates else None,
                    "precursor_count_estimate": 3,
                    "route_confidence_score": 78.0,
                    "route_outline": [
                        "Retrosynthetic split around core scaffold bonds.",
                        "Map available analog fragments and prioritise low-step assembly.",
                        "Rank alternate routes by confidence and synthetic complexity.",
                    ],
                }
            ],
            "execution_stages": [
                {
                    "stage": "retrosynthesis_enumeration",
                    "duration": "5-15 min",
                    "deliverable": "Alternative route trees with precursor sets",
                },
                {
                    "stage": "route_ranking",
                    "duration": "2-5 min",
                    "deliverable": "Ranked route shortlist",
                },
                {
                    "stage": "handoff_package",
                    "duration": "<1 min",
                    "deliverable": "Medicinal chemistry route memo",
                },
            ],
            "constraints": [
                "In-silico confidence does not guarantee wet-lab success.",
                "Final synthesis decisions require licensed chemist review.",
            ],
            "disclaimer": "Computational synthesis planning only; no physical synthesis is performed by the platform.",
        },
        "timeline_weeks": {
            "target_structure_compute": "1-3 min",
            "docking_and_ranking": "2-5 min",
            "de_novo_candidate_assembly": "<1 min",
        },
        "next_steps": [
            "Review the ranked leads and de novo proposals with medicinal chemistry and oncology teams.",
            "Select the top compounds for synthesis and assay planning.",
            "Request manufacturer bids only after scientific review.",
        ],
        "attributions": [
            "Structure prediction: AlphaFold v3 (DeepMind / Google)",
            "Blind docking: DiffDock (MIT CSAIL)",
            "Fragment library: ZINC22 (500k drug-like compounds)",
            "Toxicity: pkCSM ADMET server",
        ],
        "message": "Custom drug discovery brief is complete.",
        "stage": 2,
    }


@app.get("/api/marketplace/drug-requests")
async def list_drug_requests():
    results = []
    for req_id, req in DRUG_REQUESTS.items():
        created_at = float(req["created_at"])  # type: ignore[arg-type]
        elapsed = monotonic() - created_at
        status = "complete" if elapsed >= 18 else "synthesizing" if elapsed >= 8 else "queued"
        results.append({
            "drug_request_id": req_id,
            "result_id": str(req.get("result_id", "")),
            "target_gene": str(req.get("target_gene", "")),
            "cancer_type": str(req.get("cancer_type", "")),
            "status": status,
        })
    return {"requests": results}


@app.get("/api/marketplace/nearby-pharmacies")
async def nearby_pharmacies():
    return {
        "pharmacies": [
            {
                "name": "Metro Specialty Pharmacy",
                "distance_km": 2.3,
                "phone": "+1-555-0101",
                "address": "12 Research Ave",
            },
            {
                "name": "City Oncology Pharmacy",
                "distance_km": 4.1,
                "phone": "+1-555-0109",
                "address": "88 Care Street",
            },
        ]
    }
