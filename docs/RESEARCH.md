# Research and evaluation

OpenOncology's current product is an evidence-interpretation workflow for labs and oncologists. The repository also contains research from an earlier, broader scope. The records below serve different purposes and should be read separately.

## Current MSK CHORD evaluation

[Research Square preprint](https://www.researchsquare.com/article/rs-11584932/v1) · [doi:10.21203/rs.3.rs-11584932/v1](https://doi.org/10.21203/rs.3.rs-11584932/v1).

[A retrospective benchmark of an open-source oncology drug ranker on 2,505 MSK CHORD patients](../preprints/msk_chord_benchmark.md) describes the saved evidence-lookup experiment. The committed outputs include 2,466 predictions and 2,094 exact top-three hits across 2,505 selected patients.

The experiment selects qualifying alterations using received treatments and applies evidence-level ordering. It does not run the full application ranker. Shared target-map filtering, broad alteration rules and inconsistent baseline descriptions limit what can be concluded. The [benchmark reference](BENCHMARK.md#msk-chord-evidence-lookup-benchmark) gives the protocol details and caveats.

This is retrospective evaluation, not evidence of treatment benefit or prospective deployment. The [case explorer](https://immortal71.github.io/openoncology/) displays saved cases from this work.

## Historical framework preprint

Kharel, A. (2026). *OpenOncology: An Open-Source Framework for Evidence-Based Drug Matching and De Novo Custom Drug Discovery in Precision Oncology.* Research Square. [doi:10.21203/rs.3.rs-9707913/v1](https://doi.org/10.21203/rs.3.rs-9707913/v1).

This preprint describes the broader evidence-matching and discovery agenda. It is not the current product specification or the CHORD report. Its published title and citation remain unchanged.

[PAPER.md](../PAPER.md) retains the publication reference and correction notes. [Paper and repository reconciliation](PAPER_VS_CURRENT_STATE.md) documents differences between published claims and repository evidence. The [oncologist-concordance explanation](ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md) records the retracted circular result.

## Software evaluation records

The frozen 50-case holdout, curated hard regression gate and TCGA coverage studies use different datasets and scoring rules. Their historical results and dated CI observations belong in the [benchmark reference](BENCHMARK.md), rather than in a combined product score.

The [clinical-use roadmap](ROADMAP_TO_CLINICAL_USE.md) describes the work needed for clinical evaluation. Passing a regression gate or producing a research brief does not establish clinical validity.
