/*
 * CNVkit — copy number alteration calling from WES / WGS BAMs
 *
 * CNVkit infers copy number changes from read depth in target and off-target
 * regions of whole-exome or targeted sequencing data.  It produces:
 *   - Per-gene CNA calls (amplification, deletion, neutral)
 *   - Log2 ratio and discrete GISTIC-style calls per gene
 *   - Scatter plots and genome-wide visualisation files
 *
 * Inputs:
 *   tumour_bam  — Path to tumour BAM (indexed)
 *   normal_bam  — Reference / panel-of-normals BAM (optional)
 *   ref_fasta   — GRCh38 reference FASTA
 *   targets_bed — Target capture BED file; pass "flat" for WGS
 *
 * Outputs:
 *   cns         — Segment-level copy number calls (.cns)
 *   gene_calls  — Gene-level discrete calls with GISTIC value (.csv)
 *
 * References:
 *   - Talevich et al., PLOS Comput. Biol. 2016 — CNVkit paper
 *   - https://cnvkit.readthedocs.io/
 */

process CNVKIT {
    tag "${tumour_bam.simpleName}"
    label "process_medium"
    container "etal/cnvkit:0.9.10"

    input:
    path tumour_bam
    path normal_bam
    path ref_fasta
    path targets_bed

    output:
    path "*.cns",       emit: cns
    path "*.gene.csv",  emit: gene_calls

    script:
    def normal_arg = normal_bam?.name != "NO_NORMAL" ? "-n ${normal_bam}" : "-n"
    def targets_arg = targets_bed?.name != "FLAT" ? "--targets ${targets_bed}" : "--method wgs"
    def prefix = "${tumour_bam.simpleName}"
    """
    cnvkit.py batch \\
        ${tumour_bam} \\
        ${normal_arg} \\
        -f ${ref_fasta} \\
        ${targets_arg} \\
        --output-dir cnvkit_output/ \\
        -p ${task.cpus}

    # Export gene-level calls with GISTIC values
    cnvkit.py genemetrics \\
        cnvkit_output/${prefix}.cns \\
        --segment cnvkit_output/${prefix}.cns \\
        --threshold 0.2 \\
        -o ${prefix}.gene.csv

    cp cnvkit_output/${prefix}.cns .
    """
}
