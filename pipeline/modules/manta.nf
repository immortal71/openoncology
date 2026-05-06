/*
 * Manta — structural variant and gene fusion detection
 *
 * Manta calls SVs and indels from paired-end sequencing data.  It is the
 * Illumina-supported SV caller and is recommended by GATK Best Practices for
 * somatic SV detection.
 *
 * Inputs:
 *   tumour_bam  — Tumour BAM (indexed)
 *   normal_bam  — Matched normal BAM (indexed); pass NO_NORMAL for tumour-only
 *   ref_fasta   — GRCh38 reference FASTA (indexed)
 *
 * Outputs:
 *   sv_vcf      — Somatic SVs in VCF format (candidateSV + diploidSV merged)
 *   fusions_tsv — Gene fusions extracted from the SV VCF (GENE1--GENE2 format)
 *
 * References:
 *   - Chen et al., Bioinformatics 2016 — Manta paper
 *   - https://github.com/Illumina/manta
 */

process MANTA {
    tag "${tumour_bam.simpleName}"
    label "process_high"
    container "docker.io/szarate/manta:1.6.0"

    input:
    path tumour_bam
    path normal_bam
    path ref_fasta

    output:
    path "*.sv.vcf.gz",      emit: sv_vcf
    path "*.fusions.tsv",    emit: fusions_tsv

    script:
    def normal_arg = normal_bam?.name != "NO_NORMAL" ? "--normalBam ${normal_bam}" : ""
    def prefix = "${tumour_bam.simpleName}"
    def run_mode = normal_bam?.name != "NO_NORMAL" ? "runWorkflow.py -m local" : "runWorkflow.py -m local"
    """
    # Configure Manta
    configManta.py \\
        --tumorBam ${tumour_bam} \\
        ${normal_arg} \\
        --referenceFasta ${ref_fasta} \\
        --runDir manta_output/ \\
        --exome

    # Run Manta
    manta_output/${run_mode} -j ${task.cpus}

    # Copy SV VCF output
    if [ -f manta_output/results/variants/somaticSV.vcf.gz ]; then
        cp manta_output/results/variants/somaticSV.vcf.gz ${prefix}.sv.vcf.gz
    else
        cp manta_output/results/variants/diploidSV.vcf.gz ${prefix}.sv.vcf.gz
    fi

    # Extract fusions (BND pairs that span two genes)
    python3 - <<'EOF'
import gzip, re, sys

fusions = []
with gzip.open("${prefix}.sv.vcf.gz", "rt") as fh:
    for line in fh:
        if line.startswith('#'):
            continue
        cols = line.strip().split('\\t')
        if len(cols) < 8:
            continue
        info = cols[7]
        # BND (breakend) type = potential fusion
        if 'SVTYPE=BND' not in info:
            continue
        # Try to extract gene annotations from ANN or GENE INFO fields
        gene1 = None
        gene2 = None
        ann_match = re.search(r'ANN=([^;]+)', info)
        if ann_match:
            ann_parts = ann_match.group(1).split(',')
            if ann_parts:
                gene1 = ann_parts[0].split('|')[3] if len(ann_parts[0].split('|')) > 3 else None
        gene_match = re.search(r'GENES=([^;]+)', info)
        if gene_match:
            genes = gene_match.group(1).split(',')
            if len(genes) >= 2:
                gene1, gene2 = genes[0], genes[1]
        if gene1 and gene2 and gene1 != gene2:
            fusions.append(f"{gene1}--{gene2}\\t{cols[0]}:{cols[1]}")

with open("${prefix}.fusions.tsv", "w") as out:
    out.write("fusion\\tbreakpoint\\n")
    for f in fusions:
        out.write(f + "\\n")
EOF
    """
}
