#!/usr/bin/env nextflow
nextflow.enable.dsl=2

/*
 * OpenOncology Genomic Pipeline
 *
 * Supported workflows:
 *   germline  : FastQC → Trimmomatic → BWA-MEM2 → GATK HaplotypeCaller → OpenCRAVAT
 *   somatic   : FastQC → Trimmomatic → BWA-MEM2 → GATK Mutect2 → OpenCRAVAT
 *   full      : germline/somatic + CNVkit (CNA) + Manta (SV)
 *   rnaseq    : STAR + featureCounts → TPM quantification
 *
 * Usage:
 *   nextflow run main.nf \
 *     --input_file patient.vcf \
 *     --output_dir ./results \
 *     --cancer_type "Lung adenocarcinoma" \
 *     --caller somatic
 *
 *   # Full multi-omic (WES tumour/normal pair):
 *   nextflow run main.nf \
 *     --input_file tumour.bam \
 *     --normal_bam normal.bam \
 *     --output_dir ./results \
 *     --caller somatic \
 *     --run_cnv true \
 *     --run_sv true
 */

params.input_file  = null
params.output_dir  = "./results"
params.cancer_type = "unknown"
params.genome      = "GRCh38"
params.ref_fasta   = "${projectDir}/references/GRCh38.fa"
params.dbsnp       = "${projectDir}/references/dbsnp_146.hg38.vcf.gz"

// Somatic calling options
params.caller       = "germline"   // germline | somatic
params.normal_bam   = ""           // matched normal BAM for somatic calling
params.germline_vcf = ""           // gnomAD VCF for Mutect2 germline resource

// Multi-omic flags
params.run_cnv      = false        // Run CNVkit for copy number alterations
params.run_sv       = false        // Run Manta for structural variants
params.run_rnaseq   = false        // Run STAR RNA-seq workflow
params.targets_bed  = ""           // Capture targets BED (for CNVkit / targeted)
params.star_genome  = ""           // Pre-built STAR genome directory
params.gtf          = ""           // GTF annotation (for RNA-seq)

include { FASTQC }           from './modules/fastqc'
include { TRIMMOMATIC }      from './modules/trimmomatic'
include { BWA_MEM2_ALIGN }   from './modules/bwa_mem2'
include { GATK_HAPLOTYPE }   from './modules/gatk'
include { MUTECT2 }          from './modules/mutect2'
include { CNVKIT }           from './modules/cnvkit'
include { MANTA }            from './modules/manta'
include { STAR_ALIGN }       from './modules/star_align'
include { FEATURECOUNTS }    from './modules/star_align'
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
    normal_bam_ch = params.normal_bam ? Channel.fromPath(params.normal_bam) : Channel.value(file("NO_NORMAL"))
    germline_vcf_ch = params.germline_vcf ? Channel.fromPath(params.germline_vcf) : Channel.value(file("NO_GERMLINE"))
    targets_bed_ch = params.targets_bed ? Channel.fromPath(params.targets_bed) : Channel.value(file("FLAT"))

    // ── VCF-only path ────────────────────────────────────────────────────────
    if (is_vcf) {
        OPENCRAVAT(input_ch)
        OPENCRAVAT.out.annotated_vcf.collectFile(storeDir: params.output_dir)
        return
    }

    // ── BAM path ─────────────────────────────────────────────────────────────
    if (is_bam) {
        if (params.caller == "somatic") {
            MUTECT2(input_ch, normal_bam_ch.first(), Channel.value(resolved_ref_fasta), germline_vcf_ch.first())
            OPENCRAVAT(MUTECT2.out.vcf)
            OPENCRAVAT.out.annotated_vcf.collectFile(storeDir: params.output_dir)
        } else {
            GATK_HAPLOTYPE(input_ch, resolved_ref_fasta, resolved_dbsnp)
            OPENCRAVAT(GATK_HAPLOTYPE.out.vcf)
            OPENCRAVAT.out.annotated_vcf.collectFile(storeDir: params.output_dir)
        }

        // Optional CNV calling
        if (params.run_cnv) {
            CNVKIT(input_ch, normal_bam_ch.first(), Channel.value(resolved_ref_fasta), targets_bed_ch.first())
            CNVKIT.out.gene_calls.collectFile(storeDir: "${params.output_dir}/cnv")
        }

        // Optional SV calling
        if (params.run_sv) {
            MANTA(input_ch, normal_bam_ch.first(), Channel.value(resolved_ref_fasta))
            MANTA.out.sv_vcf.collectFile(storeDir: "${params.output_dir}/sv")
            MANTA.out.fusions_tsv.collectFile(storeDir: "${params.output_dir}/sv")
        }
        return
    }

    // ── FASTQ path: full QC → trim → align → call → annotate ────────────────
    FASTQC(input_ch)
    TRIMMOMATIC(input_ch)
    BWA_MEM2_ALIGN(TRIMMOMATIC.out.trimmed, resolved_ref_fasta)

    if (params.caller == "somatic") {
        MUTECT2(BWA_MEM2_ALIGN.out.bam, normal_bam_ch.first(), Channel.value(resolved_ref_fasta), germline_vcf_ch.first())
        OPENCRAVAT(MUTECT2.out.vcf)
    } else {
        GATK_HAPLOTYPE(BWA_MEM2_ALIGN.out.bam, resolved_ref_fasta, resolved_dbsnp)
        OPENCRAVAT(GATK_HAPLOTYPE.out.vcf)
    }

    OPENCRAVAT.out.annotated_vcf.collectFile(storeDir: params.output_dir)

    // Optional CNV calling
    if (params.run_cnv) {
        CNVKIT(BWA_MEM2_ALIGN.out.bam, normal_bam_ch.first(), Channel.value(resolved_ref_fasta), targets_bed_ch.first())
        CNVKIT.out.gene_calls.collectFile(storeDir: "${params.output_dir}/cnv")
    }

    // Optional SV calling
    if (params.run_sv) {
        MANTA(BWA_MEM2_ALIGN.out.bam, normal_bam_ch.first(), Channel.value(resolved_ref_fasta))
        MANTA.out.sv_vcf.collectFile(storeDir: "${params.output_dir}/sv")
        MANTA.out.fusions_tsv.collectFile(storeDir: "${params.output_dir}/sv")
    }
}

// ── RNA-seq sub-workflow ──────────────────────────────────────────────────────
workflow RNASEQ {
    take:
    fastq_r1
    fastq_r2

    main:
    if (!params.star_genome || !params.gtf) {
        error "ERROR: --star_genome and --gtf are required for RNA-seq workflow"
    }
    STAR_ALIGN(fastq_r1, fastq_r2, params.star_genome, params.gtf)
    FEATURECOUNTS(STAR_ALIGN.out.bam, params.gtf)
    FEATURECOUNTS.out.tpm_tsv.collectFile(storeDir: "${params.output_dir}/rnaseq")

    emit:
    bam = STAR_ALIGN.out.bam
    tpm = FEATURECOUNTS.out.tpm_tsv
}
