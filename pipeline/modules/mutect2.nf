/*
 * GATK Mutect2 — somatic variant calling module
 *
 * Calls somatic SNVs and indels in tumour-only or matched tumour-normal mode.
 * Mutect2 is the GATK Best Practices somatic caller and is required for
 * accurate somatic variant detection in clinical oncology samples.
 *
 * Inputs:
 *   tumour_bam   — Path to tumour BAM (indexed)
 *   normal_bam   — Path to matched normal BAM (indexed); pass empty string for tumour-only
 *   ref_fasta    — Path to GRCh38 reference FASTA (indexed)
 *   germline_vcf — Path to gnomAD / panel-of-normals VCF for filtering (optional)
 *
 * Outputs:
 *   vcf          — Raw somatic VCF (requires FilterMutectCalls step)
 *   stats        — Mutect2 stats file (required for FilterMutectCalls)
 *
 * References:
 *   - GATK Best Practices: https://gatk.broadinstitute.org/hc/en-us/articles/360035531132
 *   - Benjamin et al., bioRxiv 2019 — Mutect2 paper
 */

process MUTECT2 {
    tag "${tumour_bam.simpleName}"
    label "process_high"
    container "broadinstitute/gatk:4.4.0.0"

    input:
    path tumour_bam
    path normal_bam
    path ref_fasta
    path germline_vcf

    output:
    path "*.somatic.vcf.gz",       emit: vcf
    path "*.somatic.vcf.gz.stats", emit: stats

    script:
    def normal_arg = normal_bam?.name != "NO_NORMAL" ? "-I ${normal_bam} --normal-sample ${normal_bam.simpleName}" : ""
    def germline_arg = germline_vcf?.name != "NO_GERMLINE" ? "--germline-resource ${germline_vcf}" : ""
    def prefix = "${tumour_bam.simpleName}"
    """
    # Index BAM if .bai not present
    if [ ! -f "${tumour_bam}.bai" ]; then
        samtools index ${tumour_bam}
    fi

    gatk Mutect2 \\
        -R ${ref_fasta} \\
        -I ${tumour_bam} \\
        --tumor-sample ${tumour_bam.simpleName} \\
        ${normal_arg} \\
        ${germline_arg} \\
        -O ${prefix}.somatic.vcf.gz \\
        --native-pair-hmm-threads ${task.cpus}

    # Apply somatic filters
    gatk FilterMutectCalls \\
        -R ${ref_fasta} \\
        -V ${prefix}.somatic.vcf.gz \\
        --stats ${prefix}.somatic.vcf.gz.stats \\
        -O ${prefix}.somatic.filtered.vcf.gz

    mv ${prefix}.somatic.filtered.vcf.gz ${prefix}.somatic.vcf.gz
    """
}
