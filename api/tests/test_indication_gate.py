"""Indication gate (OO-26): a drug is withheld only on positive evidence that
its label does not cover the gene, alteration, cancer or line.

The failing cases are taken from the 69-patient concordance pilot rescored
against HemOncKB (OO-25).
"""
import pytest

from services.indication_gate import evaluate, indication_context, partition_candidates


@pytest.mark.parametrize(
    "drug, gene, alt, cancer",
    [
        ("sonidegib", "SMO", "S699R", "Kidney Renal Clear Cell Carcinoma"),
        ("vismodegib", "PTCH1", "S1008N", "Renal Cell Carcinoma"),
        ("avapritinib", "PDGFRA", "D1026E", "Renal Cell Carcinoma"),
        ("avapritinib", "KIT", "R2I", "Renal Cell Carcinoma"),
        ("alpelisib", "PIK3CA", "E545K", "Renal Cell Carcinoma"),
        ("AFATINIB DIMALEATE", "EGFR", "L838P", "Renal Cell Carcinoma"),
        ("afatinib", "EGFR", "A597P", "Glioblastoma Multiforme"),
        ("belzutifan", "VHL", "L158V", "Glioblastoma"),
    ],
)
def test_gene_to_drug_across_cancer_types_is_withheld(drug, gene, alt, cancer):
    keep, reason, _ = evaluate(drug, gene, alt, cancer)
    assert keep is False
    assert reason


@pytest.mark.parametrize(
    "drug, gene, alt, cancer",
    [
        ("sonidegib", "SMO", "W535L", "Basal Cell Carcinoma"),
        ("osimertinib", "EGFR", "L858R", "Lung Adenocarcinoma"),
        ("alpelisib", "PIK3CA", "H1047R", "Breast Invasive Carcinoma"),
        ("avapritinib", "PDGFRA", "D842V", "Gastrointestinal stromal tumor of stomach"),
        ("imatinib", "KIT", "W557_K558del", "GIST"),
    ],
)
def test_indicated_pairs_are_kept(drug, gene, alt, cancer):
    keep, reason, note = evaluate(drug, gene, alt, cancer)
    assert keep is True
    assert reason is None
    assert note is None


def test_fusion_only_drugs_need_a_fusion():
    assert evaluate("alectinib", "ALK", "H1475Q", "Lung Adenocarcinoma")[0] is False
    assert evaluate("alectinib", "ALK", "EML4-ALK fusion", "Lung Adenocarcinoma")[0] is True
    assert evaluate("larotrectinib", "NTRK3", "R735H", "Renal Cell Carcinoma")[0] is False
    assert evaluate("larotrectinib", "NTRK3", "ETV6::NTRK3", "Infantile Fibrosarcoma")[0] is True


def test_fusions_written_as_gene_pairs_count():
    assert evaluate("alectinib", "ALK", "EML4-ALK", "Non-Small Cell Lung Cancer")[0] is True
    assert evaluate("selpercatinib", "RET", "KIF5B-RET", "Lung Adenocarcinoma")[0] is True
    assert evaluate("larotrectinib", "NTRK3", "ETV6-NTRK3", "Secretory Breast Carcinoma")[0] is True


def test_kinase_domain_resistance_mutations_stand_in_for_the_fusion():
    assert evaluate("lorlatinib", "ALK", "G1202R", "Non-Small Cell Lung Cancer")[0] is True
    assert evaluate("lorlatinib", "ROS1", "G2032R", "Non-Small Cell Lung Cancer")[0] is True
    assert evaluate("alectinib", "ALK", "D282E", "Lung Adenocarcinoma")[0] is False


def test_alk_point_mutation_in_neuroblastoma_is_not_withheld():
    assert evaluate("lorlatinib", "ALK", "F1174L", "Neuroblastoma")[0] is True


def test_g12c_inhibitors_need_g12c():
    assert evaluate("adagrasib", "KRAS", "G12V", "Colon Adenocarcinoma")[0] is False
    assert evaluate("sotorasib", "KRAS", "G12C", "Lung Adenocarcinoma")[0] is True
    assert evaluate("sotorasib", "KRAS", "p.G12C", "Colorectal Cancer")[0] is True


def test_anti_egfr_with_a_g12c_inhibitor_in_colorectal_is_kept():
    assert evaluate("cetuximab", "KRAS", "G12C", "Colorectal Cancer")[0] is True
    assert evaluate("panitumumab", "KRAS", "G12C", "Lung Adenocarcinoma")[0] is False


def test_avapritinib_in_mastocytosis_is_kept():
    assert evaluate("avapritinib", "KIT", "D816V", "Systemic Mastocytosis")[0] is True


@pytest.mark.parametrize("drug", ["cetuximab", "panitumumab"])
@pytest.mark.parametrize("gene", ["KRAS", "NRAS"])
def test_anti_egfr_antibodies_are_withheld_for_ras_mutations(drug, gene):
    keep, reason, _ = evaluate(drug, gene, "G12V", "Colon Adenocarcinoma")
    assert keep is False
    assert "wild-type" in reason or "G12C" in reason


def test_belzutifan_in_rcc_depends_on_line():
    first_line = evaluate("belzutifan", "VHL", "L158V", "Renal Cell Carcinoma", line_of_therapy=1)
    assert first_line[0] is False
    assert evaluate("belzutifan", "VHL", "L158V", "Renal Cell Carcinoma", line_of_therapy=3)[0] is True


def test_belzutifan_with_unknown_line_is_kept_with_a_note():
    keep, reason, note = evaluate("belzutifan", "VHL", "L158V", "Renal Cell Carcinoma")
    assert keep is True
    assert reason is None
    assert "line of therapy not supplied" in note


def test_belzutifan_adjuvant_is_kept_with_a_note():
    keep, _, note = evaluate(
        "belzutifan", "VHL", "L158V", "Renal Cell Carcinoma", line_of_therapy=1, intent="adjuvant"
    )
    assert keep is True
    assert "combination" in note


def test_unknown_cancer_type_keeps_the_drug_and_says_so():
    keep, reason, note = evaluate("sonidegib", "SMO", "S699R", None)
    assert keep is True
    assert reason is None
    assert "BCC" in note


def test_alteration_requirement_applies_even_without_a_cancer_type():
    assert evaluate("alectinib", "ALK", "H1475Q", None)[0] is False


def test_pairs_without_a_rule_are_untouched():
    assert evaluate("dabrafenib", "BRAF", "V600E", "Glioblastoma") == (True, None, None)
    assert evaluate("everolimus", "MTOR", "S2215Y", "Renal Cell Carcinoma") == (True, None, None)
    assert evaluate("cisplatin", "TP53", "R175G", "Glioblastoma") == (True, None, None)


def test_gist_is_not_read_as_gastric_cancer():
    assert indication_context("Gastrointestinal stromal tumor of stomach") == "GIST"
    assert indication_context("Stomach Adenocarcinoma") == "GASTRIC"


def test_partition_returns_withheld_candidates_with_reasons():
    candidates = [
        {"drug_name": "AVAPRITINIB"},
        {"drug_name": "DASATINIB ANHYDROUS"},
        {"drug_name": "IMATINIB"},
        {"drug_name": "pembrolizumab"},
    ]
    kept, dropped = partition_candidates(candidates, "KIT", "R2I", "Renal Cell Carcinoma")
    assert [d["drug_name"] for d in kept] == ["pembrolizumab"]
    assert {d["drug_name"] for d in dropped} == {"AVAPRITINIB", "DASATINIB ANHYDROUS", "IMATINIB"}
    assert all(d["indication_exclusion"] for d in dropped)


def test_partition_keeps_order_and_adds_notes():
    kept, dropped = partition_candidates(
        [{"drug_name": "belzutifan"}, {"drug_name": "pembrolizumab"}],
        "VHL", "L158V", "Renal Cell Carcinoma",
    )
    assert dropped == []
    assert [d["drug_name"] for d in kept] == ["belzutifan", "pembrolizumab"]
    assert "indication_note" in kept[0]
    assert "indication_note" not in kept[1]
