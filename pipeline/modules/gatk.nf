/*
 * GATK HaplotypeCaller — call somatic variants, produce VCF
 */
process GATK_HAPLOTYPE {
    tag "$bam"
    publishDir "${params.output_dir}/vcf", mode: 'copy'

    conda 'bioconda::gatk4=4.5.0.0'

    input:
    path bam
    path ref_fasta
    path dbsnp

    output:
    path "*.g.vcf.gz",      emit: gvcf
    path "*.filtered.vcf",  emit: vcf

    script:
    def base = bam.baseName.replaceAll(/\.sorted\.bam$/, "")
    """
    # Index reference if not present
    samtools faidx $ref_fasta || true

    # HaplotypeCaller
    gatk HaplotypeCaller \
        -R $ref_fasta \
        -I $bam \
        -O ${base}.g.vcf.gz \
        --dbsnp $dbsnp \
        -ERC GVCF \
        --native-pair-hmm-threads ${task.cpus}

    # Genotype GVCFs
    gatk GenotypeGVCFs \
        -R $ref_fasta \
        -V ${base}.g.vcf.gz \
        -O ${base}.raw.vcf

    # Filter variants
    gatk VariantFiltration \
        -R $ref_fasta \
        -V ${base}.raw.vcf \
        --filter-expression "QD < 2.0" --filter-name "QD2" \
        --filter-expression "FS > 60.0" --filter-name "FS60" \
        --filter-expression "MQ < 40.0" --filter-name "MQ40" \
        -O ${base}.filtered.vcf
    """
}
