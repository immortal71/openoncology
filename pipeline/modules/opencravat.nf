/*
 * OpenCRAVAT — variant annotation against ClinVar, COSMIC, OncoKB, dbSNP
 */
process OPENCRAVAT {
    tag "$vcf"
    publishDir "${params.output_dir}/annotated", mode: 'copy'

    conda 'bioconda::open-cravat=2.4.2'

    input:
    path vcf

    output:
    path "*.annotated.vcf", emit: annotated_vcf
    path "*.sqlite",        emit: db

    script:
    def base = vcf.baseName.replaceAll(/\.filtered\.vcf$/, "")
    """
    # Install required annotators on first run
    oc module install-base || true
    oc module install clinvar cosmic oncokb dbsnp -y || true

    # Run annotation
    oc run $vcf \
        -a clinvar cosmic oncokb dbsnp \
        -t vcf \
        -l hg38 \
        --output-dir . \
        --noconvert

    # Rename output
    mv ${vcf}.vcf ${base}.annotated.vcf || \
    mv *.vcf ${base}.annotated.vcf || true
    """
}
