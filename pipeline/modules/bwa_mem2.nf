/*
 * BWA-MEM2 — align reads to GRCh38 reference genome
 *
 * Takes a sample id and one or two read files. Two mates are passed to a single
 * `bwa-mem2 mem` invocation so the aligner can use the insert-size distribution
 * to place reads whose own sequence is ambiguous. That is most of the value of
 * paired-end sequencing, and aligning each mate separately discards it.
 *
 * One BAM per sample either way, so everything downstream is unchanged.
 *
 * The index is an input, not something this process builds. It used to declare
 * only the FASTA, so Nextflow staged the FASTA and none of the index files
 * beside it, and the script then ran `bwa-mem2 index` to recreate what
 * pipeline/scripts/download_references.sh had already built. By that script's
 * own estimate that is about 30 minutes and 12 GB of RAM, per task, thrown away
 * with the work directory. Declaring the index files means they are staged and
 * the work is done once, at setup.
 */
process BWA_MEM2_ALIGN {
    tag "$sample_id"
    publishDir "${params.output_dir}/bam", mode: 'copy'

    label "process_high"
    conda "bioconda::bwa-mem2=2.2.1 bioconda::samtools=1.19"

    input:
    tuple val(sample_id), path(reads)
    path ref_fasta
    path ref_index

    output:
    path "${sample_id}.sorted.bam",     emit: bam
    path "${sample_id}.sorted.bam.bai", emit: bai

    script:
    def read_args = reads instanceof List ? reads.join(' ') : "${reads}"
    """
    bwa-mem2 mem \\
        -t ${task.cpus} \\
        -R "@RG\\tID:openoncology\\tSM:${sample_id}\\tPL:ILLUMINA" \\
        $ref_fasta \\
        ${read_args} | \\
    samtools sort -@ ${task.cpus} -o ${sample_id}.sorted.bam -

    samtools index ${sample_id}.sorted.bam
    """
}
