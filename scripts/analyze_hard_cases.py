"""Manual hard-case analysis script — identifies top failure modes."""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from api.ai.ranking import rank_candidates
from api.services.oncokb_evidence import get_all_drugs_for_variant, annotate_compound_resistance

HARD_CASES = [
    {"id": "EGFR_T790M+C797S",     "gene": "EGFR",   "alts": ["T790M","C797S"],  "cancer": "NSCLC",        "expected_drug": "(none)", "expect_empty": True},
    {"id": "EGFR_T790M",           "gene": "EGFR",   "alts": ["T790M"],          "cancer": "NSCLC",        "expected_drug": "Osimertinib"},
    {"id": "EGFR_T790M_erlotinib", "gene": "EGFR",   "alts": ["T790M"],          "cancer": "NSCLC",        "expected_drug": "Erlotinib", "expect_resistance": True},
    {"id": "EGFR_L858R",           "gene": "EGFR",   "alts": ["L858R"],          "cancer": "NSCLC",        "expected_drug": "Osimertinib"},
    {"id": "KRAS_G12C",            "gene": "KRAS",   "alts": ["G12C"],           "cancer": "NSCLC",        "expected_drug": "Sotorasib"},
    {"id": "ABL1_T315I",           "gene": "ABL1",   "alts": ["T315I"],          "cancer": "CML",          "expected_drug": "Ponatinib"},
    {"id": "ABL1_T315I+E255K",     "gene": "ABL1",   "alts": ["T315I","E255K"],  "cancer": "CML",          "expected_drug": "Ponatinib", "expect_reduced": True},
    {"id": "BRAF_V600E_MEL",       "gene": "BRAF",   "alts": ["V600E"],          "cancer": "Melanoma",     "expected_drug": "Vemurafenib"},
    {"id": "PIK3CA_E545K",         "gene": "PIK3CA", "alts": ["E545K"],          "cancer": "Breast Cancer","expected_drug": "Alpelisib"},
    {"id": "TP53_R248W",           "gene": "TP53",   "alts": ["R248W"],          "cancer": "NSCLC",        "expected_drug": "(none)", "expect_empty": True},
    {"id": "FLT3_ITD",             "gene": "FLT3",   "alts": ["ITD"],            "cancer": "AML",          "expected_drug": "Midostaurin"},
    {"id": "IDH1_R132H",           "gene": "IDH1",   "alts": ["R132H"],          "cancer": "AML",          "expected_drug": "Ivosidenib"},
    {"id": "BRCA2_OVARIAN",        "gene": "BRCA2",  "alts": ["Pathogenic"],     "cancer": "Ovarian",      "expected_drug": "Olaparib"},
    {"id": "ERBB2_AMP_BREAST",     "gene": "ERBB2",  "alts": ["Amplification"],  "cancer": "Breast Cancer","expected_drug": "Trastuzumab"},
    {"id": "RET_M918T_THYROID",    "gene": "RET",    "alts": ["M918T"],          "cancer": "Thyroid",      "expected_drug": "Selpercatinib"},
    {"id": "NRAS_Q61R_MEL",        "gene": "NRAS",   "alts": ["Q61R"],           "cancer": "Melanoma",     "expected_drug": "Binimetinib"},
    {"id": "FGFR3_S249C_BLADDER",  "gene": "FGFR3",  "alts": ["S249C"],          "cancer": "Bladder",      "expected_drug": "Erdafitinib"},
    {"id": "KIT_EX11_GIST",        "gene": "KIT",    "alts": ["exon11_del"],     "cancer": "GIST",         "expected_drug": "Imatinib"},
    {"id": "MET_EX14_NSCLC",       "gene": "MET",    "alts": ["exon14_skip"],    "cancer": "NSCLC",        "expected_drug": "Capmatinib"},
    {"id": "PDGFRA_D842V_GIST",    "gene": "PDGFRA", "alts": ["D842V"],          "cancer": "GIST",         "expected_drug": "Avapritinib"},
]

print("=" * 72)
print("  HARD CASE ANALYSIS — 20 Scenarios")
print("=" * 72)
print()

failure_modes = []
for case in HARD_CASES:
    gene = case["gene"]
    alts = case["alts"]

    all_drugs = {}
    for alt in alts:
        drugs = get_all_drugs_for_variant(gene, alt, alphamissense_score=1.0)
        for drug, level in drugs.items():
            if drug not in all_drugs:
                all_drugs[drug] = level

    if not all_drugs:
        top3 = []
        result = "(no candidates in OncoKB table)"
        ranked = []
    else:
        candidates = [
            {
                "drug_name": d.title(),
                "oncokb_level": lv,
                "opentargets_score": 0.7 if lv == "LEVEL_1" else (0.5 if lv == "LEVEL_2" else 0.3),
                "is_approved": lv == "LEVEL_1",
                "max_phase": 4 if lv == "LEVEL_1" else (3 if lv == "LEVEL_2" else 2),
            }
            for d, lv in all_drugs.items()
        ]
        if len(alts) > 1:
            candidates = annotate_compound_resistance(candidates, gene, alts)
        ranked = rank_candidates(candidates)
        top3 = [
            f"{c['drug_name']}({c.get('oncokb_level','?')})={c['rank_score']:.3f}"
            for c in ranked[:4]
        ]
        result = ", ".join(top3[:3])

    exp = case["expected_drug"]
    passed = True
    issue = None

    if case.get("expect_empty"):
        if ranked:
            top_score = ranked[0]["rank_score"]
            if top_score > 0.22:
                passed = False
                issue = f"Should have no strong candidate but top score={top_score:.3f} ({ranked[0]['drug_name']})"
        else:
            passed = True  # correctly empty

    elif case.get("expect_resistance"):
        if ranked:
            drug_score = next(
                (c["rank_score"] for c in ranked if exp.lower() in c["drug_name"].lower()),
                None
            )
            drug_level = next(
                (c.get("oncokb_level","") for c in ranked if exp.lower() in c["drug_name"].lower()),
                None
            )
            # Pass if the drug is correctly R-flagged (score ≤ resistance cap 0.08)
            # regardless of absolute rank position (with few total drugs, rank#2 may be "bottom")
            if drug_score is not None and drug_score > 0.12:
                passed = False
                issue = f"{exp} score={drug_score:.3f} (level={drug_level}) still above resistance threshold 0.12"
            elif drug_score is not None and drug_level and "R" not in drug_level:
                passed = False
                issue = f"{exp} not R-flagged (level={drug_level}) — should be LEVEL_R1 or LEVEL_R2"

    else:
        if not ranked:
            passed = False
            issue = f"No candidates found, expected {exp}"
        else:
            names_lower = [c["drug_name"].lower() for c in ranked[:3]]
            found = any(
                exp.lower().replace(" deruxtecan","").replace(" ","").strip() in n.replace(" ","")
                for n in names_lower
            )
            if not found:
                all_names = [c["drug_name"] for c in ranked[:5]]
                passed = False
                issue = f"MISS: '{exp}' not in top3. Top5={all_names}"

    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {case['id']}")
    print(f"         Expected: {exp}")
    print(f"         Got:      {result}")
    if issue:
        print(f"         >> {issue}")
        failure_modes.append({"case": case["id"], "issue": issue})
    print()

print("=" * 72)
print(f"  RESULTS: {len(HARD_CASES)-len(failure_modes)}/{len(HARD_CASES)} PASSED  |  {len(failure_modes)} FAILURES")
print("=" * 72)
print()

# Categorize failure modes
categories = {"empty_should_have_no_drug": [], "resistance_not_flagged": [], "missing_in_top3": [], "wrong_score": []}
for fm in failure_modes:
    if "no strong" in fm["issue"] or "no candidates" in fm["issue"].lower():
        categories["empty_should_have_no_drug"].append(fm)
    elif "R-flagged" in fm["issue"] or "resistance" in fm["issue"].lower():
        categories["resistance_not_flagged"].append(fm)
    elif "MISS" in fm["issue"]:
        categories["missing_in_top3"].append(fm)
    else:
        categories["wrong_score"].append(fm)

print("  TOP FAILURE MODE CATEGORIES:")
for cat, items in categories.items():
    if items:
        print(f"    [{len(items)}x] {cat}:")
        for item in items:
            print(f"         - {item['case']}: {item['issue']}")
