/*
 * BWA-MEM2 — align reads to GRCh38 reference genome
 *
 * Takes a sample id and one or two read files. Two mates are passed to a single
 * `bwa-mem2 mem` invocation so the aligner can use the insert-size distribution
 * to place reads whose own sequence is ambiguous. That is most of the value of
 * paired-end sequencing, and aligning each mate separately discards it.
 *
 * One BAM per sample either way, so everything downstream is unchanged.
 */
process BWA_MEM2_ALIGN {
    tag "$sample_id"
    publishDir "${params.output_dir}/bam", mode: 'copy'

    label "process_high"
    conda "bioconda::bwa-mem2=2.2.1 bioconda::samtools=1.19"

    input:
    tuple val(sample_id), path(reads)
    path ref_fasta

    output:
    path "${sample_id}.sorted.bam",     emit: bam
    path "${sample_id}.sorted.bam.bai", emit: bai

    script:
    def read_args = reads instanceof List ? reads.join(' ') : "${reads}"
    """
    bwa-mem2 index $ref_fasta

    bwa-mem2 mem \\
        -t ${task.cpus} \\
        -R "@RG\\tID:openoncology\\tSM:${sample_id}\\tPL:ILLUMINA" \\
        $ref_fasta \\
        ${read_args} | \\
    samtools sort -@ ${task.cpus} -o ${sample_id}.sorted.bam -

    samtools index ${sample_id}.sorted.bam
    """
}
