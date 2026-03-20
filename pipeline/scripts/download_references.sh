#!/usr/bin/env bash
# Download reference genome and variant databases required by the pipeline.
# GRCh38 (hg38) from Ensembl + dbSNP 151 from NCBI.
#
# Usage:
#   bash pipeline/scripts/download_references.sh [OUTPUT_DIR]
#
# Default output: pipeline/references/
# Approx. disk space needed: ~25 GB (genome + index + dbSNP)

set -euo pipefail

OUTDIR="${1:-$(dirname "$0")/../references}"
mkdir -p "$OUTDIR"

echo "==> Reference output directory: $OUTDIR"

# ─── GRCh38 genome (primary assembly, no ALT contigs) ─────────────────────────
GENOME_URL="https://ftp.ensembl.org/pub/release-111/fasta/homo_sapiens/dna/Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz"
GENOME_GZ="$OUTDIR/GRCh38.primary_assembly.fa.gz"
GENOME_FA="$OUTDIR/GRCh38.primary_assembly.fa"

if [[ ! -f "$GENOME_FA" ]]; then
  echo "==> Downloading GRCh38 primary assembly..."
  curl -C - -L "$GENOME_URL" -o "$GENOME_GZ"
  echo "==> Decompressing..."
  bgzip -d "$GENOME_GZ" -o "$GENOME_FA" 2>/dev/null || gunzip -k "$GENOME_GZ"
  [[ -f "$GENOME_FA" ]] || mv "${GENOME_GZ%.gz}" "$GENOME_FA"
else
  echo "==> GRCh38 FASTA already present, skipping."
fi

# ─── BWA-MEM2 index ───────────────────────────────────────────────────────────
if [[ ! -f "${GENOME_FA}.bwt.2bit.64" ]]; then
  echo "==> Building BWA-MEM2 index (this takes ~30 min and requires ~12 GB RAM)..."
  bwa-mem2 index "$GENOME_FA"
else
  echo "==> BWA-MEM2 index already present, skipping."
fi

# ─── samtools FASTA index (needed by GATK) ────────────────────────────────────
if [[ ! -f "${GENOME_FA}.fai" ]]; then
  echo "==> Building samtools .fai index..."
  samtools faidx "$GENOME_FA"
fi

# ─── GATK sequence dictionary ─────────────────────────────────────────────────
DICT="${GENOME_FA%.fa}.dict"
if [[ ! -f "$DICT" ]]; then
  echo "==> Creating GATK sequence dictionary..."
  gatk CreateSequenceDictionary -R "$GENOME_FA" -O "$DICT"
fi

# ─── dbSNP 151 (GRCh38) ───────────────────────────────────────────────────────
DBSNP_URL="https://ftp.ncbi.nlm.nih.gov/snp/organisms/human_9606_b151_GRCh38p7/VCF/GATK/00-All.vcf.gz"
DBSNP_VCF="$OUTDIR/dbSNP151_GRCh38.vcf.gz"

if [[ ! -f "$DBSNP_VCF" ]]; then
  echo "==> Downloading dbSNP 151..."
  curl -C - -L "$DBSNP_URL" -o "$DBSNP_VCF"
  curl -C - -L "${DBSNP_URL}.tbi" -o "${DBSNP_VCF}.tbi"
else
  echo "==> dbSNP VCF already present, skipping."
fi

echo ""
echo "==> All references ready in $OUTDIR"
echo ""
echo "Set these values in your .env / nextflow.config:"
echo "  REF_FASTA=$GENOME_FA"
echo "  DBSNP_VCF=$DBSNP_VCF"
