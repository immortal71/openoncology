#  Clinical Context: Oncology Workflows & Drug Selection

This document outlines how OpenOncology fits into clinical decision-making, taking patient biopsy data and translating it into actionable therapeutic recommendations.

---

## 1. The Clinical Problem Statement

Every cancer patient's tumour has a unique combination of mutations. Traditional chemotherapy acts like a global system kill signal (`kill -9`), attacking all fast-growing cells indiscriminately. 

**Precision Oncology** aims to identify the specific biological bugs driving a patient's tumour and select targeted drugs that specifically block those mutated pathways while leaving healthy tissue intact.

---

## 2. Biopsy Types: Input Streams

OpenOncology processes data from two primary biopsy sources:

1. **Tissue Biopsy (Solid Tumour DNA):** A physical slice of tumour tissue obtained via surgery or needle biopsy. Provides high-fidelity, localized genomic data.
2. **Liquid Biopsy (ctDNA / Cell-Free DNA):** Blood samples containing fragments of DNA shed by tumour cells into the bloodstream. Think of liquid biopsy as querying a real-time system metric stream without needing direct SSH access to the host server.

---

## 3. The Therapeutic Ranking Engine

Once mutations are extracted and filtered, OpenOncology ranks prospective targeted drugs using a multi-factor score:

$$\text{Rank Score} = f(\text{Actionability}, \text{Evidence Level}, \text{Co-mutational Status}, \text{Drug Toxicity})$$

* **Actionability:** Is there a known FDA-approved drug or clinical trial target for this specific mutation?
* **Evidence Level:** Is the drug supported by Tier 1 clinical trial evidence, or only pre-clinical cell line data?
* **Variant Allele Frequency (VAF):** What percentage of the biopsy sample carries this mutation? High VAF indicates a primary driver mutation; low VAF indicates a minor clone.