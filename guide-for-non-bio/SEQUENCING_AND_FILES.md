# Sequencing & Files: The Data Pipeline

If you are a developer touching the `pipeline/` or `scripts/` directories, you will be handling raw genomic data. This document explains the file formats and the biological processes that generate them, translated into standard CS concepts.

---

## 1. Next-Generation Sequencing (NGS)
Think of NGS as a massive, parallel data-read operation. A sequencing machine takes physical DNA, breaks it into millions of tiny fragments, and reads the characters (A, C, T, G). It outputs massive raw text files containing these overlapping fragments.

---

## 2. The File Journey (Raw Data to Output)
When a biopsy is taken, the data moves through a strict pipeline:

* **FASTQ (Raw Server Logs):** Raw reads coming straight from the machine containing base calls and quality scores. Massive, unstructured, and noisy.
* **BAM (The Indexed Database):** Aligned reads matched against a Reference Genome (e.g., GRCh38—the master branch). Indexed and binary-compressed for fast range queries.
* **VCF - Variant Call Format (The `git diff`):** The primary input for our AI ranking system. It filters out normal DNA and lists only the mutations (diffs) present in the patient sample.

---

## 3. Reading a VCF File
When parsing a VCF file, the key fields are:
* `CHROM` & `POS`: Chromosome and position index (the file path and line number).
* `REF`: Expected reference character (e.g., `G`).
* `ALT`: Mutated variant character observed (e.g., `T`).
* `VAF` (Variant Allele Frequency): Percentage of reads supporting the mutation.

---

## 4. Variant Callers (Parsers)
* **HaplotypeCaller (Germline):** Detects inherited mutations (present at system setup).
* **Mutect2 (Somatic):** Detects acquired mutations (runtime mutations specific to the tumour).

---

## 5. Advanced Biomarkers
* **TMB (Tumour Mutational Burden):** Mutation count per megabase. High TMB indicates high visibility to the immune system.
* **MSI (Microsatellite Instability):** Measures DNA mismatch repair failure.