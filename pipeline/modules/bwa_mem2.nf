/*
 * BWA-MEM2 — align reads to GRCh38 reference genome
 */
process BWA_MEM2_ALIGN {
    tag "$reads"
    publishDir "${params.output_dir}/bam", mode: 'copy'

    conda 'bioconda::bwa-mem2=2.2.1 bioconda::samtools=1.19'

    input:
    path reads
    path ref_fasta

    output:
    path "*.sorted.bam",     emit: bam
    path "*.sorted.bam.bai", emit: bai

    script:
    def base = reads.baseName
    """
    bwa-mem2 index $ref_fasta

    bwa-mem2 mem \
        -t ${task.cpus} \
        -R "@RG\\tID:openoncology\\tSM:patient\\tPL:ILLUMINA" \
        $ref_fasta \
        $reads | \
    samtools sort -@ ${task.cpus} -o ${base}.sorted.bam -

    samtools index ${base}.sorted.bam
    """
}
