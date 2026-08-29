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
 *   # Paired-end FASTQ. Both mates, because that is what a sequencer produces,
 *   # and aligning one alone throws away the insert-size information that
 *   # places reads in repetitive regions:
 *   nextflow run main.nf \
 *     --input_file sample_R1.fastq.gz \
 *     --reads_r2 sample_R2.fastq.gz \
 *     --output_dir ./results \
 *     --caller germline
 *
 *   # A {1,2} glob on --input_file does NOT pair the mates. It runs the
 *   # workflow twice, once per file. Use --reads_r2.
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
// Mate 2 of a paired-end FASTQ sample. Empty means single-end.
//
// Paired-end is what every sequencer emits and what all of the reference data
// this pipeline is validated against uses. Until this existed the FASTQ path
// ran `trimmomatic SE` and handed one file to `bwa-mem2 mem`, so a paired
// sample could only be submitted one mate at a time and was aligned without the
// insert-size information that resolves ambiguous placements.
params.reads_r2    = ""
params.output_dir  = "./results"
params.cancer_type = "unknown"
params.genome      = "GRCh38"
params.ref_fasta   = "${projectDir}/references/GRCh38.fa"
params.dbsnp       = "${projectDir}/references/dbsnp_146.hg38.vcf.gz"

// Somatic calling options
params.caller       = "germline"   // germline | somatic
params.normal_bam   = ""           // matched normal BAM for somatic calling
params.germline_vcf = ""           // gnomAD VCF for Mutect2 germline resource

// Trimmomatic adapter files. Parameters rather than literals because the paths
// differ by execution profile: these defaults are where the bioconda package
// puts them, and a container image will not agree.
params.adapters_se  = "/opt/conda/share/trimmomatic/adapters/TruSeq3-SE.fa"
params.adapters_pe  = "/opt/conda/share/trimmomatic/adapters/TruSeq3-PE.fa"

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

/*
 * Sample id from a read filename, with the mate marker removed so R1 and R2 of
 * one sample agree. Without stripping it the pair would be named after mate 1
 * and every output would read as though mate 2 belonged to a different sample.
 */
def _sample_id_from_reads(String name) {
    def base = (name ?: '')
        .replaceAll(/\.(fastq|fq)(\.gz)?$/, '')
        .replaceAll(/[._-](R?[12])$/, '')
    return base ?: 'sample'
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

    // Reads travel as (sample_id, [mates]) so one sample stays one item through
    // QC, trimming and alignment. Passing a {1,2} glob to --input_file does not
    // do this: fromPath emits two independent items and the workflow would run
    // twice, once per mate, which is what used to happen.
    def r2_given = params.reads_r2 ? params.reads_r2.toString().trim() : ""
    if (r2_given && !is_fastq) {
        error "ERROR: --reads_r2 is only meaningful with FASTQ input; --input_file is ${params.input_file}"
    }
    if (r2_given && !file(r2_given).exists()) {
        error "ERROR: Missing mate 2 file: ${r2_given}"
    }

    reads_ch = r2_given
        ? Channel.of(tuple(
              _sample_id_from_reads(file(params.input_file).name),
              [file(params.input_file), file(r2_given)]
          ))
        : input_ch.map { r -> tuple(_sample_id_from_reads(r.name), [r]) }

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
    FASTQC(reads_ch)
    TRIMMOMATIC(reads_ch)

    // Trimmomatic emits the paired channel for a pair and the single-end one
    // otherwise, exactly one of which carries an item for any given sample.
    trimmed_ch = TRIMMOMATIC.out.trimmed.mix(TRIMMOMATIC.out.trimmed_se)

    BWA_MEM2_ALIGN(trimmed_ch, resolved_ref_fasta)

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
