/*
 * STAR + featureCounts RNA-seq alignment and quantification module
 *
 * Aligns RNA-seq FASTQ reads to the GRCh38 genome with STAR and quantifies
 * gene expression with featureCounts (Subread package).  Outputs per-gene
 * count matrices and TPM / FPKM estimates.
 *
 * Inputs:
 *   fastq_r1      — Path to R1 FASTQ (gzipped)
 *   fastq_r2      — Path to R2 FASTQ (gzipped); pass empty for single-end
 *   star_genome   — Path to pre-built STAR genome directory
 *   gtf           — Path to Ensembl / GENCODE GTF annotation
 *
 * Outputs:
 *   bam           — STAR-aligned BAM sorted by coordinate
 *   counts        — featureCounts count matrix (genes × samples)
 *   tpm_tsv       — Per-gene TPM values (computed from length-normalised counts)
 *
 * References:
 *   - Dobin et al., Bioinformatics 2013 — STAR aligner
 *   - Liao et al., Bioinformatics 2014 — featureCounts
 */

process STAR_ALIGN {
    tag "${fastq_r1.simpleName}"
    label "process_high"
    container "quay.io/biocontainers/star:2.7.11b--h43eeafb_0"

    input:
    path fastq_r1
    path fastq_r2
    path star_genome
    path gtf

    output:
    path "*Aligned.sortedByCoord.out.bam", emit: bam
    path "*Log.final.out",                 emit: log

    script:
    def r2_arg = fastq_r2?.name != "NO_R2" ? "${fastq_r2}" : ""
    def prefix = "${fastq_r1.simpleName.replaceAll(/_R1.*/, '')}_"
    """
    STAR \\
        --runThreadN ${task.cpus} \\
        --genomeDir ${star_genome} \\
        --readFilesIn ${fastq_r1} ${r2_arg} \\
        --readFilesCommand zcat \\
        --outSAMtype BAM SortedByCoordinate \\
        --outSAMattributes NH HI AS NM \\
        --outFileNamePrefix ${prefix} \\
        --outSAMstrandField intronMotif \\
        --outFilterIntronMotifs RemoveNoncanonical \\
        --runMode alignReads
    """
}


process FEATURECOUNTS {
    tag "${bam.simpleName}"
    label "process_medium"
    container "quay.io/biocontainers/subread:2.0.6--h6fdf29a_0"

    input:
    path bam
    path gtf

    output:
    path "*.counts.txt",   emit: counts
    path "*.tpm.tsv",      emit: tpm_tsv

    script:
    def prefix = "${bam.simpleName}"
    """
    # featureCounts for raw counts
    featureCounts \\
        -T ${task.cpus} \\
        -a ${gtf} \\
        -o ${prefix}.counts.txt \\
        -g gene_name \\
        -p \\
        ${bam}

    # Compute TPM from counts + gene lengths
    python3 - <<'EOF'
import csv, math

counts = {}
lengths = {}
with open("${prefix}.counts.txt") as fh:
    for line in fh:
        if line.startswith('#') or line.startswith('Geneid'):
            continue
        cols = line.strip().split('\\t')
        gene = cols[0]
        length = int(cols[5])
        count = int(cols[-1])
        counts[gene] = count
        lengths[gene] = length

# RPK = reads per kilobase
rpk = {g: counts[g] / (lengths[g] / 1000) for g in counts if lengths[g] > 0}
scale = sum(rpk.values()) / 1e6
tpm = {g: v / scale for g, v in rpk.items() if scale > 0}

with open("${prefix}.tpm.tsv", "w") as out:
    out.write("gene\\ttpm\\n")
    for g, t in sorted(tpm.items(), key=lambda x: -x[1]):
        out.write(f"{g}\\t{round(t, 4)}\\n")
EOF
    """
}
