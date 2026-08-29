/*
 * FastQC — DNA read quality control
 *
 * Both mates are reported when the sample is paired. FastQC writes one report
 * per input file, which is what you want: mate 2 is routinely worse than mate 1
 * and averaging them would hide it.
 */
process FASTQC {
    tag "$sample_id"
    publishDir "${params.output_dir}/fastqc", mode: 'copy'

    label "process_low"
    conda "bioconda::fastqc=0.12.1"

    input:
    tuple val(sample_id), path(reads)

    output:
    path "*.html", emit: report
    path "*.zip",  emit: data

    script:
    """
    fastqc --threads ${task.cpus} --outdir . $reads
    """
}
