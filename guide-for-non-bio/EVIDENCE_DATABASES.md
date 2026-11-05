#  Evidence Databases: The "StackOverflow" for Mutations

When our pipeline finds a mutation in a patient's VCF file, we cross-reference it against global clinical databases to evaluate its clinical significance.

---

## 1. ClinVar (The Global Issue Tracker)
* **Provider:** NIH / NCBI
* **CS Analogy:** A public GitHub Issues repository for genetic variants.
* **Purpose:** Classifies variants into categories: *Pathogenic*, *Likely Pathogenic*, *Benign*, or *Uncertain Significance (VUS)*.

---

## 2. COSMIC (The Crash Report Log)
* **Provider:** Sanger Institute
* **CS Analogy:** A dedicated crash log database for somatic mutations in cancer.
* **Purpose:** Tracks how frequently specific mutations appear across thousands of distinct cancer types.

---

## 3. CIViC (The Developer Forum / Solution Database)
* **Provider:** Open-source community
* **CS Analogy:** StackOverflow for targeted cancer therapies.
* **Purpose:** Links specific variants to drug responses, clinical trial outcomes, and evidence levels.

---

## 4. Annotation Pipeline Integration
Our backend queries these databases to annotate raw VCF records, providing enriched metadata for the ranking engine and frontend UI.