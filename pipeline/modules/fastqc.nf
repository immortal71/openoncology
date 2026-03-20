/*
 * FastQC — DNA read quality control
 */
process FASTQC {
    tag "$reads"
    publishDir "${params.output_dir}/fastqc", mode: 'copy'

    conda 'bioconda::fastqc=0.12.1'

    input:
    path reads

    output:
    path "*.html", emit: report
    path "*.zip",  emit: data

    script:
    """
    fastqc --threads ${task.cpus} --outdir . $reads
    """
}
