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

def _is_fastq_name(String name) {
    def n = (name ?: '').toLowerCase()
    return n.endsWith('.fastq') || n.endsWith('.fq') || n.endsWith('.fastq.gz') || n.endsWith('.fq.gz')
}

def _is_bam_name(String name) {
    return (name ?: '').toLowerCase().endsWith('.bam')
}

def _is_vcf_name(String name) {
    def n = (name ?: '').toLowerCase()
    return n.endsWith('.vcf') || n.endsWith('.vcf.gz')
}

def _resolve_first_existing_path(String primary, List<String> fallbacks = []) {
    for (candidate in [primary, *fallbacks]) {
        if (candidate && file(candidate).exists()) {
            return candidate
        }
    }
    return primary
}

workflow {
    if (!params.input_file) {
        error "ERROR: --input_file is required"
    }

    def input_name = params.input_file.toString()
    def is_fastq = _is_fastq_name(input_name)
    def is_bam = _is_bam_name(input_name)
    def is_vcf = _is_vcf_name(input_name)

    if (!(is_fastq || is_bam || is_vcf)) {
        error "ERROR: Unsupported --input_file type '${params.input_file}'. Supported: FASTQ/FASTQ.GZ/FQ/FQ.GZ, BAM, VCF/VCF.GZ"
    }

    // Keep defaults compatible with both historical names and download_references.sh output.
    def resolved_ref_fasta = _resolve_first_existing_path(
        params.ref_fasta.toString(),
        ["${projectDir}/references/GRCh38.primary_assembly.fa"]
    )
    def resolved_dbsnp = _resolve_first_existing_path(
        params.dbsnp.toString(),
        ["${projectDir}/references/dbSNP151_GRCh38.vcf.gz"]
    )

    if (is_fastq || is_bam) {
        if (!file(resolved_ref_fasta).exists()) {
            error "ERROR: Missing reference FASTA: ${resolved_ref_fasta}. Run pipeline/scripts/download_references.sh or set --ref_fasta to a valid GRCh38 FASTA."
        }
        if (!file(resolved_dbsnp).exists()) {
            error "ERROR: Missing dbSNP VCF: ${resolved_dbsnp}. Run pipeline/scripts/download_references.sh or set --dbsnp to a valid dbSNP VCF."
        }
    }

    input_ch = Channel.fromPath(params.input_file, checkIfExists: true)

    // VCF-only path does not require alignment/calling references.
    if (is_vcf) {
        OPENCRAVAT(input_ch)
        OPENCRAVAT.out.annotated_vcf
            .collectFile(storeDir: params.output_dir)
        return
    }

    // BAM path: variant calling + annotation.
    if (is_bam) {
        GATK_HAPLOTYPE(input_ch, resolved_ref_fasta, resolved_dbsnp)
        OPENCRAVAT(GATK_HAPLOTYPE.out.vcf)
        OPENCRAVAT.out.annotated_vcf
            .collectFile(storeDir: params.output_dir)
        return
    }

    // FASTQ path: full QC → trim → align → call → annotate flow.
    FASTQC(input_ch)
    TRIMMOMATIC(input_ch)
    BWA_MEM2_ALIGN(TRIMMOMATIC.out.trimmed, resolved_ref_fasta)
    GATK_HAPLOTYPE(BWA_MEM2_ALIGN.out.bam, resolved_ref_fasta, resolved_dbsnp)
    OPENCRAVAT(GATK_HAPLOTYPE.out.vcf)

    OPENCRAVAT.out.annotated_vcf
        .collectFile(storeDir: params.output_dir)
}
