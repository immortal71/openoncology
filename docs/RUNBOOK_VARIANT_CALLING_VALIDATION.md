# Runbook: closing the variant-calling accuracy gate

**What this closes.** `REGULATORY_FRAMEWORK.md` section 3.1, variant calling
accuracy against an orthogonal truth set, sensitivity >= 99% and PPV >= 95%. It
is open action 1 in [risk_analysis.md](risk_analysis.md), F6 there, and item 2.1
in [ROADMAP_TO_CLINICAL_USE.md](ROADMAP_TO_CLINICAL_USE.md), which calls it the
single cheapest remaining item on the critical path. It is the only blocking gate
that needs no partner institution, no IRB and no regulator. It needs a machine.

**Why it is still open.** Everything needed exists. `scripts/validate_variant_calling.py`
is the measuring instrument, the GIAB truth set downloads itself, and
`pipeline/main.nf` is the thing to be measured. Nobody has run the second through
the first, because doing so needs a host with `bwa-mem2`, `gatk`, `samtools` and
a GRCh38 reference, and that is not a developer workstation.

**What it does not close.** Analytical validation of one stage. Sections 3.2 and
3.3, prospective clinical validation and benchmarking against commercial
platforms, are untouched by this and need an institution.

---

## The flag that decides whether the run counts

```
--from-repo-pipeline
```

Without it the harness records `query_from_repo_pipeline: false` and the run
cannot satisfy the gate no matter how good the numbers are. Pass it only when
`--query` really is output from `pipeline/main.nf` on this repository's code.

This exists because it has already been got wrong once in the safe direction.
`validation_results/variant_calling_reference_gatk4.json` holds a real, careful
measurement of a *published NIST call set* made with GATK HaplotypeCaller
4.1.4.1. It is a useful reference figure and it is not this pipeline, so it is
recorded with `satisfies_regulatory_gate_3_1: false`. Do not let a run of this
runbook end up mislabelled in either direction.

---

## Scope: chr20, confident regions

`--chrom` defaults to `chr20`, and the reference measurement used chr20 inside
the NIST high-confidence regions. Keep that scope. Two reasons:

- It is the conventional held-out evaluation chromosome in GIAB benchmarking, so
  the number is comparable to published work.
- It is what the existing reference figure used, so the comparison below is
  like for like. Changing the scope makes that comparison meaningless.

`--chrom all` runs the genome. It is not needed to answer the gate and multiplies
the compute.

---

## Host

The reference download script states its own requirements: about 25 GB for
genome, index and dbSNP, and roughly 30 minutes and 12 GB of RAM to build the
BWA-MEM2 index.

Beyond that, size from the pipeline's own resource labels rather than from
guesswork. `pipeline/nextflow.config` gives `process_high` 12 CPUs and 72 GB,
capped by `params.max_cpus` and `params.max_memory`. Alignment and calling both
carry that label.

A practical starting point, to be confirmed on the day rather than trusted from
this document:

| | chr20 only | whole genome |
|---|---|---|
| vCPU | 8 to 16 | 16 to 32 |
| RAM | 32 GB, set `--max_memory 32.GB` | 72 GB or more |
| Disk | 150 GB | 500 GB or more |
| Wall clock | a few hours | a day or more |

A spot or preemptible instance is fine; Nextflow resumes with `-resume`. The
chr20 column is the one this runbook is built around.

---

## Step 1: references

```bash
bash pipeline/scripts/download_references.sh
```

Writes to `pipeline/references/` by default. `main.nf` resolves the filenames
this script produces, `GRCh38.primary_assembly.fa` and `dbSNP151_GRCh38.vcf.gz`,
through a fallback list, so the defaults in `nextflow.config` naming
`GRCh38.fa` and `dbsnp_146.hg38.vcf.gz` do not need editing. Confirm with a run
that reaches alignment rather than assuming.

The script needs `bwa-mem2`, `samtools` and `gatk` on `PATH` to build the index,
the `.fai` and the sequence dictionary. Those are needed whether or not you run
the pipeline itself in containers.

---

## Two known pipeline limitations that shape this measurement

Both were found while writing this runbook, by reading the modules rather than
running them. Neither is documented elsewhere and both change what a FASTQ run
would mean.

**The FASTQ path is single-end only.** `main.nf` channels the input with
`Channel.fromPath`, not `fromFilePairs`. `trimmomatic.nf` runs `trimmomatic SE`
against `TruSeq3-SE.fa` adapters. `bwa_mem2.nf` passes one read file to
`bwa-mem2 mem`. There is no point at which a mate file is paired up.

GIAB HG002 is paired-end 2x150, and so is essentially all clinical sequencing.
Aligning paired reads as single-end discards the mate-pair information that
resolves repetitive and low-complexity regions, which is where variants are
missed. A FASTQ run therefore measures a single-end pipeline against a truth set
built from paired-end data, and would understate what the caller can do while
also not reflecting how real samples would be processed.

**BWA-MEM2 rebuilds the reference index on every alignment task.**
`BWA_MEM2_ALIGN` declares `path ref_fasta` as its only reference input, so
Nextflow stages the FASTA into the task work directory and none of the index
files beside it. The script then runs `bwa-mem2 index $ref_fasta`, which by the
download script's own estimate is about 30 minutes and 12 GB of RAM, and the
result is thrown away with the work directory. Step 1 builds the index; the
pipeline never sees it.

Both are filed in `BACKLOG.md`. Neither blocks this measurement, but they decide
which of the two routes below is worth running first.

---

## Step 2 and 3, route A: BAM in, caller measured

**Use this one first.** GIAB publishes HG002 aligned to GRCh38. Feeding that
alignment straight in exercises `GATK_HAPLOTYPE` with this repository's
configuration, on properly paired alignments, and sidesteps both limitations
above. What it measures is the caller and its filters, which is the substance of
the 3.1 gate.

Source data is under the GIAB release the harness already points at:

```
https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/
```

The truth set itself is fetched automatically into `validation_results/cache/`,
so this step is only about the alignment.

```bash
samtools view -b -h <HG002_GRCh38.bam> chr20 > HG002.chr20.bam
samtools index HG002.chr20.bam
```

```bash
cd pipeline
nextflow run main.nf \
  -profile docker \
  --input_file /data/HG002.chr20.bam \
  --output_dir /data/hg002_results \
  --caller germline \
  --max_cpus 16 --max_memory 32.GB \
  -resume
```

`main.nf` routes a `.bam` input directly to `GATK_HAPLOTYPE`, then OpenCRAVAT.
FastQC, Trimmomatic and BWA-MEM2 do not run, which is the point.

**What this cannot claim.** It measures calling, not the whole pipeline. Say so
in `--query-label` and do not describe the result as end-to-end accuracy.
`--from-repo-pipeline` is still correct: the calls did come from
`pipeline/main.nf`.

---

## Step 2 and 3, route B: FASTQ in, whole pipeline measured

Run this second, and read it against route A rather than on its own. The gap
between them is the cost of trimming and alignment as currently configured, and
given the single-end limitation that gap is the more interesting number here.

FASTQ cannot be subset by region, so take the published alignment, pull chr20,
and convert back:

```bash
samtools view -b -h <HG002_GRCh38.bam> chr20 > HG002.chr20.bam
samtools sort -n -o HG002.chr20.qsorted.bam HG002.chr20.bam
samtools fastq -1 HG002.chr20_R1.fastq.gz -2 HG002.chr20_R2.fastq.gz \
  -0 /dev/null -s /dev/null -n HG002.chr20.qsorted.bam
```

The pipeline will consume **one** of those files. Passing a `{1,2}` glob to
`--input_file` does not pair them: `Channel.fromPath` emits two independent
items and the workflow runs twice, once per mate. Pass `R1` alone and record
that only R1 was used.

```bash
cd pipeline
nextflow run main.nf \
  -profile docker \
  --input_file /data/HG002.chr20_R1.fastq.gz \
  --output_dir /data/hg002_results_fastq \
  --caller germline \
  --max_cpus 16 --max_memory 32.GB \
  -resume
```

Budget for the index rebuild described above on top of alignment itself.

---

## Both routes

`-profile docker` matters. Modules mix `conda` and `container` directives, and
with no profile selected Nextflow uses neither and runs whatever is on `PATH`,
with no record of the version that produced the calls. Use `docker`,
`singularity` or `conda` deliberately and write the choice into
`--query-label`. On a shared HPC node `singularity` is usually the only option.

**OpenCRAVAT is not on the measurement path.** It annotates; it does not call.
It needs its own annotation modules installed, which is a separate download and
a common place for a first run to fail. `GATK_HAPLOTYPE` publishes to
`${output_dir}/vcf` before OpenCRAVAT runs, so if the run dies at annotation the
VCF you need already exists. Do not let an OpenCRAVAT failure read as a pipeline
failure for this purpose.

The file to carry forward is:

```
/data/hg002_results/vcf/*.filtered.vcf
```

**Region extraction caveat, for both routes.** Read pairs whose mate maps off
chr20 are cut, and reads originating elsewhere that would misalign onto chr20
are never presented. This perturbs results near boundaries and in repetitive
regions. It is standard practice and it is still a deviation from a whole-genome
run. Put it in `--query-label`.

---

## Step 4: measure

```bash
cd <repo root>
PYTHONPATH=. python scripts/validate_variant_calling.py \
  --query /data/hg002_results/vcf/HG002.chr20.filtered.vcf \
  --from-repo-pipeline \
  --query-label "HG002 chr20 reads extracted from GIAB GRCh38 alignment; pipeline/main.nf <git sha>, -profile docker, GATK <version from params.gatk_version>" \
  --chrom chr20 \
  --gate
```

`--gate` exits non-zero unless both targets are met, which is what makes this
usable in CI later. Drop it for an exploratory run.

Defaults worth knowing rather than overriding blindly:

- `--query-include-filtered` is **off**. Calls the caller rejected are not
  counted, because the production parser drops them (F7). Turning it on scores
  the caller on variants the pipeline never ingests.
- `--match-genotype` is **off**. The reference measurement also compared alleles
  without genotypes. Turning it on makes the comparison stricter and no longer
  like for like.
- `--out` defaults to `validation_results/variant_calling_accuracy.json`, which
  currently holds the ingestion-fidelity run. Decide deliberately whether to
  overwrite it or write beside it; that file is the record of what has been
  measured, and the mode field is what distinguishes the two.

`validation_results/**` is covered by the `PreToolUse` guard, so an agent cannot
write the result. A human running this locally can.

---

## What the number will be compared against

`validation_results/variant_calling_reference_gatk4.json`, chr20, confident
regions, alleles not genotypes, caller-rejected calls excluded. Same scope as
above:

| | sensitivity | PPV | target |
|---|---|---|---|
| overall | 95.82% | 98.87% | 99% / 95% |
| SNV | 95.69% | 99.98% | |
| indel | 96.60% | 92.81% | |

That is a published NIST call set from GATK Best Practices, **not** this
pipeline. It fails the sensitivity target.

---

## Read the result before celebrating or despairing

Two things to hold in mind when the number arrives, both already flagged in
`ROADMAP_TO_CLINICAL_USE.md` under what would falsify the plan.

**A stock GATK4 pipeline lands near 96% sensitivity against a 99% gate.** If
this pipeline lands there too, that is not necessarily this pipeline being bad.
It may mean the gate expects better than stock tuning, or that the target needs
revisiting against what the field actually achieves. Do not respond by lowering
the threshold; `CLAUDE.md` is explicit that thresholds are never lowered to make
a gate pass. Respond by writing down which of the three explanations the evidence
supports.

**The comparison is allele-identity, not haplotype-aware.** `hap.py` and
`rtg vcfeval` compare by haplotype, and typically score indels higher because
representationally different but biologically equivalent indels match. The
reference figures above are consistent with that being a factor: SNV PPV is
99.98% with 17 false positives, while indel PPV is 92.81% with 894. A comparison
method that penalises representation differences would show exactly that shape.

This is a question about the measuring instrument, and it is worth answering
before spending money on compute a second time. `scripts/` is guard-protected,
so changing the harness is a human edit made deliberately, not an incidental one.

---

## If the run cannot be done

Record why, and where it stopped. An open action that has been attempted and
blocked is different information from one nobody has started, and
`risk_analysis.md` open action 1 currently reads as the second.
