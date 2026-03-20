/*
 * Trimmomatic — adapter trimming and quality filtering
 */
process TRIMMOMATIC {
    tag "$reads"
    publishDir "${params.output_dir}/trimmed", mode: 'copy'

    conda 'bioconda::trimmomatic=0.39'

    input:
    path reads

    output:
    path "*_trimmed.fastq.gz", emit: trimmed

    script:
    def base = reads.baseName.replaceAll(/\.fastq(\.gz)?$/, "")
    """
    trimmomatic SE -threads ${task.cpus} \
        $reads \
        ${base}_trimmed.fastq.gz \
        ILLUMINACLIP:/opt/conda/share/trimmomatic/adapters/TruSeq3-SE.fa:2:30:10 \
        LEADING:3 \
        TRAILING:3 \
        SLIDINGWINDOW:4:15 \
        MINLEN:36
    """
}
