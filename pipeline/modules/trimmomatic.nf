/*
 * Trimmomatic — adapter trimming and quality filtering
 *
 * Takes a sample id and one or two read files. Two means paired-end, and the
 * pair is trimmed together: Trimmomatic PE decides jointly whether both mates
 * survive, which is what keeps them in step for the aligner. Trimming each mate
 * as a separate SE run desynchronises them and the pairing is then unusable.
 *
 * The unpaired outputs are the reads whose mate was dropped. They are written
 * out so the loss is visible and countable, and they are deliberately not
 * emitted to the aligner: adding them back means a second single-end alignment
 * pass with different error characteristics mixed into one BAM. Discarding them
 * is the conventional choice and it is a choice, not an oversight.
 */
process TRIMMOMATIC {
    tag "$sample_id"
    publishDir "${params.output_dir}/trimmed", mode: 'copy'

    label "process_low"
    conda "bioconda::trimmomatic=0.39"

    input:
    tuple val(sample_id), path(reads)

    output:
    tuple val(sample_id), path("*_trimmed_{1,2}P.fastq.gz"), emit: trimmed,   optional: true
    tuple val(sample_id), path("*_trimmed.fastq.gz"),        emit: trimmed_se, optional: true
    path "*_trimmed_{1,2}U.fastq.gz",                        emit: unpaired,   optional: true

    script:
    def paired = reads instanceof List && reads.size() == 2
    if (paired)
        """
        trimmomatic PE -threads ${task.cpus} \\
            ${reads[0]} ${reads[1]} \\
            ${sample_id}_trimmed_1P.fastq.gz ${sample_id}_trimmed_1U.fastq.gz \\
            ${sample_id}_trimmed_2P.fastq.gz ${sample_id}_trimmed_2U.fastq.gz \\
            ILLUMINACLIP:${params.adapters_pe}:2:30:10 \\
            LEADING:3 \\
            TRAILING:3 \\
            SLIDINGWINDOW:4:15 \\
            MINLEN:36
        """
    else
        """
        trimmomatic SE -threads ${task.cpus} \\
            ${reads instanceof List ? reads[0] : reads} \\
            ${sample_id}_trimmed.fastq.gz \\
            ILLUMINACLIP:${params.adapters_se}:2:30:10 \\
            LEADING:3 \\
            TRAILING:3 \\
            SLIDINGWINDOW:4:15 \\
            MINLEN:36
        """
}
