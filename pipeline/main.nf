#!/usr/bin/env nextflow
nextflow.enable.dsl=2

/*
 * OpenOncology Genomic Pipeline
 * FastQC → Trimmomatic → BWA-MEM2 → GATK HaplotypeCaller → OpenCRAVAT
 *
 * Usage:
 *   nextflow run main.nf \
 *     --input_file patient.vcf \
 *     --output_dir ./results \
 *     --cancer_type "Lung adenocarcinoma"
 */

params.input_file  = null
params.output_dir  = "./results"
params.cancer_type = "unknown"
params.genome      = "GRCh38"
params.ref_fasta   = "${projectDir}/references/GRCh38.fa"
params.dbsnp       = "${projectDir}/references/dbsnp_146.hg38.vcf.gz"

include { FASTQC }           from './modules/fastqc'
include { TRIMMOMATIC }      from './modules/trimmomatic'
include { BWA_MEM2_ALIGN }   from './modules/bwa_mem2'
include { GATK_HAPLOTYPE }   from './modules/gatk'
include { OPENCRAVAT }       from './modules/opencravat'

workflow {
    if (!params.input_file) {
        error "ERROR: --input_file is required"
    }

    input_ch = Channel.fromPath(params.input_file)

    // Step 1: Quality control
    FASTQC(input_ch)

    // Step 2: Adapter trimming (skip for VCF input, apply for FASTQ)
    trimmed_ch = input_ch.filter { it.name.endsWith('.fastq') || it.name.endsWith('.fq') || it.name.endsWith('.fastq.gz') }
    TRIMMOMATIC(trimmed_ch)

    // Step 3: Alignment to GRCh38 (FASTQ → BAM)
    fastq_input  = TRIMMOMATIC.out.trimmed.mix(
        input_ch.filter { it.name.endsWith('.fastq') || it.name.endsWith('.fastq.gz') }
    )
    BWA_MEM2_ALIGN(fastq_input, params.ref_fasta)

    // Step 4: Variant calling (BAM → VCF)
    bam_input = BWA_MEM2_ALIGN.out.bam.mix(
        input_ch.filter { it.name.endsWith('.bam') }
    )
    GATK_HAPLOTYPE(bam_input, params.ref_fasta, params.dbsnp)

    // Step 5: Variant annotation (VCF → annotated VCF)
    vcf_input = GATK_HAPLOTYPE.out.vcf.mix(
        input_ch.filter { it.name.endsWith('.vcf') || it.name.endsWith('.vcf.gz') }
    )
    OPENCRAVAT(vcf_input)

    OPENCRAVAT.out.annotated_vcf
        .collectFile(storeDir: params.output_dir)
}
