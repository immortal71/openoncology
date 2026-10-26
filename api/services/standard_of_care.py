"""Standard-of-care options by cancer type (OO-28).

WHY THIS EXISTS
---------------
The ranker answers one question: which drugs does this tumour's mutation make
relevant? For most patients the honest answer is "none". A molecular tumour
board still recommends something in that case: the standard treatment for the
cancer type. In the 2026-07-28 concordance pilot, 45 of 69 patients had clear
cell kidney cancer and received sunitinib, sorafenib, pazopanib, temsirolimus,
everolimus or bevacizumab. None of those is chosen by a mutation, so a
mutation-only ranker could not match a single one of them (0 of 38).

This module lists, per cancer context, therapies whose FDA label covers that
cancer without requiring a tumour biomarker. It is reported SEPARATELY from the
mutation-matched ranking and must never be merged into it: "standard care for
renal cell carcinoma" and "matched to your VHL mutation" are different claims,
and a reader has to be able to tell them apart.

WHAT IT IS NOT
--------------
- Not a treatment recommendation. Choice between these depends on stage, line
  of therapy, prior treatment, performance status, comorbidity and access,
  none of which a variant file contains. The list is a menu for the treating
  oncologist, in no clinical order beyond the ``line`` field.
- Not exhaustive and not current to the week. Each entry names its basis; the
  table needs review by an oncologist before clinical use (``REVIEW_STATUS``).
- Biomarker-conditional standard care (HER2-positive breast, RAS wild-type
  colorectal, PD-L1 high lung) is listed with ``requires`` set, so callers can
  show the condition instead of implying it was met.

Sources: FDA prescribing information, indications and usage section. On
2026-10-26 every drug-cancer pair was checked against openFDA label text.
Results:
- A regimen counts as labelled when the label of at least one of its drugs
  names that cancer and the combination. Partners named in another drug's
  label (leucovorin, prednisone and interferon alfa, for example) fail a
  per-drug check, as expected.
- Three regimens are guideline standard with a component used off label.
  These are carboplatin + paclitaxel in NSCLC, and fluorouracil or
  capecitabine + oxaliplatin in gastric cancer. They carry
  basis="guideline", so a reader is not told they are on label.
- openFDA had no label for abemaciclib, atezolizumab, avelumab, belzutifan,
  darolutamide, lenvatinib, tivozanib or relugolix (Orgovyx). Those
  indications are not machine-verified and need a manual check.
Contexts use the names from services.indication_gate.indication_context.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

REVIEW_STATUS = "draft: FDA-label based, not yet reviewed by an oncologist"

FIRST_LINE = "first-line"
LATER_LINE = "later-line"
ANY_LINE = "any line"


@dataclass(frozen=True)
class Regimen:
    drugs: tuple[str, ...]
    line: str
    requires: Optional[str] = None
    note: str = ""
    basis: str = "FDA label"

    @property
    def name(self) -> str:
        return " + ".join(self.drugs)


def _r(drugs: str, line: str, requires: Optional[str] = None, note: str = "",
       basis: str = "FDA label") -> Regimen:
    return Regimen(tuple(d.strip() for d in drugs.split("+")), line, requires, note, basis)


_TABLE: dict[str, tuple[Regimen, ...]] = {
    "RCC": (
        _r("pembrolizumab + axitinib", FIRST_LINE, note="advanced RCC"),
        _r("nivolumab + cabozantinib", FIRST_LINE, note="advanced RCC"),
        _r("lenvatinib + pembrolizumab", FIRST_LINE, note="advanced RCC"),
        _r("nivolumab + ipilimumab", FIRST_LINE, note="intermediate or poor risk advanced RCC"),
        _r("sunitinib", FIRST_LINE, note="advanced RCC"),
        _r("pazopanib", FIRST_LINE, note="advanced RCC"),
        _r("cabozantinib", ANY_LINE, note="advanced RCC"),
        _r("temsirolimus", FIRST_LINE, note="advanced RCC, label studied poor-risk first line"),
        _r("bevacizumab + interferon alfa", FIRST_LINE, note="metastatic RCC"),
        _r("sorafenib", ANY_LINE, note="advanced RCC"),
        _r("aldesleukin", ANY_LINE, note="metastatic RCC"),
        _r("axitinib", LATER_LINE, note="after one prior systemic therapy"),
        _r("everolimus", LATER_LINE, note="after sunitinib or sorafenib"),
        _r("lenvatinib + everolimus", LATER_LINE, note="after one prior anti-angiogenic therapy"),
        _r("nivolumab", LATER_LINE, note="after prior anti-angiogenic therapy"),
        _r("tivozanib", LATER_LINE, note="after two or more prior systemic therapies"),
        _r("belzutifan", LATER_LINE, note="after a PD-1/PD-L1 inhibitor and a VEGF-TKI"),
    ),
    "PROSTATE": (
        _r("leuprolide", ANY_LINE, note="advanced prostate cancer, androgen deprivation"),
        _r("goserelin", ANY_LINE, note="advanced prostate cancer, androgen deprivation"),
        _r("degarelix", ANY_LINE, note="advanced prostate cancer"),
        _r("relugolix", ANY_LINE, note="advanced prostate cancer"),
        _r("bicalutamide", ANY_LINE, note="with LHRH analogue, metastatic"),
        _r("abiraterone + prednisone", ANY_LINE, note="metastatic CRPC and high-risk castration-sensitive"),
        _r("enzalutamide", ANY_LINE, note="CRPC and castration-sensitive"),
        _r("apalutamide", ANY_LINE, note="non-metastatic CRPC and metastatic castration-sensitive"),
        _r("darolutamide", ANY_LINE, note="non-metastatic CRPC and metastatic castration-sensitive"),
        _r("docetaxel + prednisone", ANY_LINE, note="metastatic CRPC"),
        _r("cabazitaxel + prednisone", LATER_LINE, note="metastatic CRPC after docetaxel"),
        _r("radium-223", LATER_LINE, note="CRPC with symptomatic bone metastases"),
        _r("sipuleucel-T", ANY_LINE, note="asymptomatic or minimally symptomatic metastatic CRPC"),
        _r("lutetium Lu 177 vipivotide tetraxetan", LATER_LINE, requires="PSMA-positive",
           note="PSMA-positive metastatic CRPC"),
    ),
    "COLORECTAL": (
        _r("fluorouracil + leucovorin + oxaliplatin", FIRST_LINE, note="FOLFOX, metastatic"),
        _r("fluorouracil + leucovorin + irinotecan", ANY_LINE, note="FOLFIRI, metastatic"),
        _r("capecitabine", ANY_LINE, note="metastatic, and adjuvant colon"),
        _r("bevacizumab", ANY_LINE, note="with fluoropyrimidine chemotherapy, metastatic"),
        _r("cetuximab", ANY_LINE, requires="RAS wild-type", note="metastatic"),
        _r("panitumumab", ANY_LINE, requires="RAS wild-type", note="metastatic"),
        _r("ramucirumab", LATER_LINE, note="with FOLFIRI after bevacizumab, oxaliplatin and fluoropyrimidine"),
        _r("ziv-aflibercept", LATER_LINE, note="with FOLFIRI after an oxaliplatin regimen"),
        _r("regorafenib", LATER_LINE, note="previously treated metastatic"),
        _r("trifluridine + tipiracil", LATER_LINE, note="previously treated metastatic"),
        _r("fruquintinib", LATER_LINE, note="previously treated metastatic"),
    ),
    "BREAST": (
        _r("doxorubicin + cyclophosphamide", ANY_LINE, note="adjuvant chemotherapy"),
        _r("paclitaxel", ANY_LINE, note="adjuvant and metastatic"),
        _r("docetaxel", ANY_LINE, note="adjuvant and metastatic"),
        _r("capecitabine", LATER_LINE, note="metastatic"),
        _r("trastuzumab", ANY_LINE, requires="HER2-positive"),
        _r("pertuzumab", ANY_LINE, requires="HER2-positive"),
        _r("ado-trastuzumab emtansine", ANY_LINE, requires="HER2-positive"),
        _r("fam-trastuzumab deruxtecan", LATER_LINE, requires="HER2-positive or HER2-low"),
        _r("lapatinib", LATER_LINE, requires="HER2-positive"),
        _r("tamoxifen", ANY_LINE, requires="hormone receptor-positive"),
        _r("letrozole", ANY_LINE, requires="hormone receptor-positive"),
        _r("anastrozole", ANY_LINE, requires="hormone receptor-positive"),
        _r("exemestane", ANY_LINE, requires="hormone receptor-positive"),
        _r("fulvestrant", ANY_LINE, requires="hormone receptor-positive"),
        _r("palbociclib", ANY_LINE, requires="HR-positive, HER2-negative"),
        _r("ribociclib", ANY_LINE, requires="HR-positive, HER2-negative"),
        _r("abemaciclib", ANY_LINE, requires="HR-positive, HER2-negative"),
        _r("pembrolizumab", ANY_LINE, requires="triple-negative", note="with chemotherapy"),
        _r("sacituzumab govitecan", LATER_LINE, requires="triple-negative or HR-positive HER2-negative"),
    ),
    "NSCLC": (
        _r("pembrolizumab", FIRST_LINE, requires="PD-L1 expression", note="alone or with chemotherapy"),
        _r("carboplatin + pemetrexed + pembrolizumab", FIRST_LINE, note="non-squamous, no EGFR/ALK driver"),
        _r("carboplatin + paclitaxel", FIRST_LINE, basis="guideline"),
        _r("cisplatin + pemetrexed", FIRST_LINE, note="non-squamous"),
        _r("bevacizumab", FIRST_LINE, note="non-squamous, with carboplatin and paclitaxel"),
        _r("nivolumab + ipilimumab", FIRST_LINE, note="no EGFR/ALK driver"),
        _r("atezolizumab", ANY_LINE),
        _r("docetaxel", LATER_LINE),
        _r("ramucirumab + docetaxel", LATER_LINE),
        _r("nivolumab", LATER_LINE),
    ),
    "GLIOMA": (
        _r("temozolomide", FIRST_LINE, note="newly diagnosed glioblastoma, with radiotherapy"),
        _r("bevacizumab", LATER_LINE, note="recurrent glioblastoma"),
        _r("lomustine", LATER_LINE, note="brain tumours"),
        _r("carmustine", ANY_LINE, note="brain tumours; implant for glioblastoma"),
    ),
    "MELANOMA": (
        _r("nivolumab", ANY_LINE),
        _r("pembrolizumab", ANY_LINE),
        _r("nivolumab + ipilimumab", FIRST_LINE),
        _r("nivolumab + relatlimab", FIRST_LINE),
        _r("ipilimumab", ANY_LINE),
    ),
    "PANCREATIC": (
        _r("irinotecan liposome + fluorouracil + leucovorin + oxaliplatin", FIRST_LINE, note="NALIRIFOX, metastatic"),
        _r("gemcitabine + nab-paclitaxel", FIRST_LINE, note="metastatic"),
        _r("gemcitabine", ANY_LINE),
        _r("gemcitabine + erlotinib", FIRST_LINE, note="advanced"),
        _r("irinotecan liposome + fluorouracil + leucovorin", LATER_LINE, note="after gemcitabine"),
    ),
    "GASTRIC": (
        _r("nivolumab", FIRST_LINE, note="with fluoropyrimidine and platinum chemotherapy"),
        _r("fluorouracil + oxaliplatin", FIRST_LINE, basis="guideline"),
        _r("capecitabine + oxaliplatin", FIRST_LINE, basis="guideline"),
        _r("trastuzumab", FIRST_LINE, requires="HER2-positive", note="with chemotherapy"),
        _r("ramucirumab", LATER_LINE, note="alone or with paclitaxel"),
        _r("trifluridine + tipiracil", LATER_LINE),
    ),
    "OVARIAN": (
        _r("carboplatin + paclitaxel", FIRST_LINE),
        _r("bevacizumab", ANY_LINE, note="with chemotherapy"),
        _r("niraparib", FIRST_LINE, note="maintenance after response to platinum"),
    ),
    "BLADDER": (
        _r("enfortumab vedotin + pembrolizumab", FIRST_LINE, note="locally advanced or metastatic urothelial"),
        _r("gemcitabine + cisplatin", FIRST_LINE),
        _r("avelumab", FIRST_LINE, note="maintenance after platinum chemotherapy"),
        _r("pembrolizumab", ANY_LINE),
    ),
    "HCC": (
        _r("atezolizumab + bevacizumab", FIRST_LINE, note="unresectable"),
        _r("durvalumab + tremelimumab", FIRST_LINE, note="unresectable"),
        _r("sorafenib", FIRST_LINE),
        _r("lenvatinib", FIRST_LINE),
        _r("regorafenib", LATER_LINE, note="after sorafenib"),
        _r("cabozantinib", LATER_LINE, note="after sorafenib"),
    ),
    "THYROID": (
        _r("lenvatinib", ANY_LINE, note="radioactive iodine-refractory differentiated"),
        _r("sorafenib", ANY_LINE, note="radioactive iodine-refractory differentiated"),
    ),
}


def _canon(name: str) -> str:
    from services.oncology_atc import parent_name

    return parent_name(name)


def options_for(cancer_type: Optional[str]) -> list[Regimen]:
    """Standard-care regimens for a cancer type, or [] when the type is unknown."""
    from services.indication_gate import indication_context

    context = indication_context(cancer_type)
    return list(_TABLE.get(context or "", ()))


def report(cancer_type: Optional[str]) -> dict:
    """Serializable standard-of-care section for a case report."""
    from services.indication_gate import indication_context

    context = indication_context(cancer_type)
    regimens = _TABLE.get(context or "", ())
    return {
        "cancer_context": context,
        "basis": "standard treatment for this cancer type (FDA label unless marked guideline); not selected by the tumour's mutations",
        "review_status": REVIEW_STATUS,
        "options": [
            {
                "regimen": r.name,
                "drugs": list(r.drugs),
                "line": r.line,
                "requires": r.requires,
                "note": r.note,
                "basis": r.basis,
            }
            for r in regimens
        ],
    }


def drug_names(cancer_type: Optional[str], *, include_conditional: bool = True) -> set[str]:
    """Every component drug named in this cancer's standard-care regimens."""
    names: set[str] = set()
    for r in options_for(cancer_type):
        if r.requires and not include_conditional:
            continue
        names.update(_canon(d) for d in r.drugs)
    return names
