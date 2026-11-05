# Bio Primer: Biology for CS Developers

Welcome to OpenOncology! If you come from a Software Engineering, Computer Science, or AI background, biological concepts can feel overwhelming due to complex jargon. This document maps core biological concepts directly into standard CS, system architecture, and debugging terms.

---

## 1. The Central Dogma (The Execution Pipeline)

In software, source code is compiled into intermediate representation (IR) or bytecode, which is then executed by a runtime engine. Biology follows an almost identical pipeline:

$$\text{DNA (Source Code)} \longrightarrow \text{RNA (Intermediate Compiled Bytecode)} \longrightarrow \text{Protein (Running Executable)}$$

* **DNA (Deoxyribonucleic Acid):** The master source repository stored in the cell nucleus. It is read-only, persistent, and contains all instructions required to build and run the organism.
* **RNA (Ribonucleic Acid / mRNA):** The compiled transcript or temporary executable script created from a specific section of DNA (a gene).
* **Protein:** The active worker instance, microservice, or function that actually performs work inside the cell (e.g., cell signaling, structural transport, enzymatic reactions).

---

## 2. Genomic Data Types: Text Strings & Arrays

At its core, genomic data can be processed as plain text strings built from specific alphabets:

* **DNA Alphabet:** $\{A, C, T, G\}$ (Adenine, Cytosine, Thymine, Guanine). A single human genome contains approximately **3 billion base pairs** ($3 \times 10^9$ characters).
* **RNA Alphabet:** $\{A, C, U, G\}$ (Uracil replaces Thymine).
* **Proteins (Amino Acids):** Built from an alphabet of 20 standard amino acids. A sequence of 3 RNA nucleotides (a **Codon**) translates directly into 1 amino acid. Think of a codon as a **3-byte instruction opcode**.

---

## 3. Mutations: Software Bugs & Typos

Cancer is fundamentally a software bug in the host cell's genetic codebase. Mutations occur when characters in the DNA sequence are altered:

* **SNV (Single Nucleotide Variant):** A 1-character typo (e.g., $A \rightarrow T$). Similar to a typo in a variable name or condition statement.
* **Insertion / Deletion (Indel):** Adding or removing characters from the string. If the length is not a multiple of 3, it causes a **Frameshift Mutation**—the biological equivalent of an off-by-one memory offset error that corrupts all downstream execution.
* **Copy Number Variation (CNV):** A segment of code is duplicated multiple times or deleted entirely (like infinitely looping a resource allocation call).

---

## 4. Oncogenes vs. Tumour Suppressor Genes

When debugging cancer biology, genes usually fall into two major operational categories:

| Biological Term | CS Analogy | Behavior in Cancer |
| :--- | :--- | :--- |
| **Oncogene** | Infinite Loop / Accelerator | A gene that promotes cell growth. When mutated (Gain of Function), it acts like a stuck accelerator pedal or a loop condition that never evaluates to `false`. |
| **Tumour Suppressor Gene** | Crash Handler / Security Guard | A gene that checks for errors and triggers repair or cell shutdown (Apoptosis). When mutated (Loss of Function), the biological error-handling system fails. |

> **Key Example:** `TP53` is known as the "Guardian of the Genome." It acts as the ultimate biological `try/catch` block. If `TP53` is mutated, bad code executes unchecked.