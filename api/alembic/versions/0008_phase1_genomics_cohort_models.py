"""Phase 1 + 2: genomics models, cohort models, MAF columns, progress_pct.

Adds:
  - mutations: vaf, depth, allele_depth_ref, allele_depth_alt, strand_bias,
               variant_classification, refseq_transcript_id, protein_position,
               codon_change, hotspot_flag
  - submissions: progress_pct
  - copy_number_alterations table
  - structural_variants table
  - rnaseq_expression table
  - mutation_signatures table
  - studies table
  - cohort_samples table
  - cohort_mutations table  (with gene + protein_change index)

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend mutations table with full MAF fields ──────────────────────────
    with op.batch_alter_table("mutations") as batch_op:
        batch_op.add_column(sa.Column("vaf", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("depth", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("allele_depth_ref", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("allele_depth_alt", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("strand_bias", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("variant_classification", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("refseq_transcript_id", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("protein_position", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("codon_change", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("hotspot_flag", sa.Boolean(), server_default="false", nullable=False))
        batch_op.create_index("ix_mutations_gene", ["gene"])

    # ── Add progress_pct to submissions ──────────────────────────────────────
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.add_column(sa.Column("progress_pct", sa.Integer(), server_default="0", nullable=False))
        batch_op.create_index("ix_submissions_status", ["status"])

    # ── Copy number alterations ───────────────────────────────────────────────
    op.create_table(
        "copy_number_alterations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("submission_id", sa.String(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("gene", sa.String(64), nullable=False),
        sa.Column("chromosome", sa.String(8), nullable=True),
        sa.Column("segment_start", sa.Integer(), nullable=True),
        sa.Column("segment_end", sa.Integer(), nullable=True),
        sa.Column("log2_ratio", sa.Float(), nullable=True),
        sa.Column("copy_number", sa.Integer(), nullable=True),
        sa.Column("gistic_value", sa.String(4), nullable=True),
        sa.Column("cna_status", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_cna_submission_id", "copy_number_alterations", ["submission_id"])
    op.create_index("ix_cna_gene", "copy_number_alterations", ["gene"])

    # ── Structural variants ───────────────────────────────────────────────────
    op.create_table(
        "structural_variants",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("submission_id", sa.String(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("gene1", sa.String(64), nullable=False),
        sa.Column("gene2", sa.String(64), nullable=True),
        sa.Column("chromosome1", sa.String(8), nullable=True),
        sa.Column("breakpoint1", sa.Integer(), nullable=True),
        sa.Column("chromosome2", sa.String(8), nullable=True),
        sa.Column("breakpoint2", sa.Integer(), nullable=True),
        sa.Column("sv_type", sa.String(20), nullable=True),
        sa.Column("frame", sa.String(16), nullable=True),
        sa.Column("support_reads", sa.Integer(), nullable=True),
        sa.Column("is_actionable", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sv_submission_id", "structural_variants", ["submission_id"])
    op.create_index("ix_sv_gene1", "structural_variants", ["gene1"])

    # ── RNA-seq expression ────────────────────────────────────────────────────
    op.create_table(
        "rnaseq_expression",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("submission_id", sa.String(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("gene", sa.String(64), nullable=False),
        sa.Column("tpm", sa.Float(), nullable=True),
        sa.Column("fpkm", sa.Float(), nullable=True),
        sa.Column("z_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_rnaseq_submission_id", "rnaseq_expression", ["submission_id"])
    op.create_index("ix_rnaseq_gene", "rnaseq_expression", ["gene"])

    # ── Mutation signatures ───────────────────────────────────────────────────
    op.create_table(
        "mutation_signatures",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("submission_id", sa.String(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("signature_name", sa.String(16), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("aetiology", sa.String(256), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sig_submission_id", "mutation_signatures", ["submission_id"])

    # ── Studies ───────────────────────────────────────────────────────────────
    op.create_table(
        "studies",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("study_id", sa.String(128), unique=True, nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.String(1024), nullable=True),
        sa.Column("cancer_type", sa.String(64), nullable=True),
        sa.Column("cancer_type_label", sa.String(128), nullable=True),
        sa.Column("sample_count", sa.Integer(), server_default="0"),
        sa.Column("data_types", sa.JSON(), nullable=True),
        sa.Column("reference_genome", sa.String(16), nullable=True),
        sa.Column("pmid", sa.String(32), nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_studies_study_id", "studies", ["study_id"])
    op.create_index("ix_studies_cancer_type", "studies", ["cancer_type"])

    # ── Cohort samples ────────────────────────────────────────────────────────
    op.create_table(
        "cohort_samples",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("study_id", sa.String(), sa.ForeignKey("studies.id"), nullable=False),
        sa.Column("sample_id", sa.String(128), nullable=False),
        sa.Column("patient_sample_id", sa.String(128), nullable=True),
        sa.Column("patient_id", sa.String(), sa.ForeignKey("patients.id"), nullable=True),
        sa.Column("tumor_type", sa.String(128), nullable=True),
        sa.Column("purity", sa.Float(), nullable=True),
        sa.Column("ploidy", sa.Float(), nullable=True),
        sa.Column("msi_status", sa.String(8), nullable=True),
        sa.Column("tmb", sa.Float(), nullable=True),
        sa.Column("os_months", sa.Float(), nullable=True),
        sa.Column("os_status", sa.Integer(), nullable=True),
        sa.Column("dfs_months", sa.Float(), nullable=True),
        sa.Column("dfs_status", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_cohort_samples_study_id", "cohort_samples", ["study_id"])
    op.create_index("ix_cohort_samples_sample_id", "cohort_samples", ["sample_id"])

    # ── Cohort mutations ──────────────────────────────────────────────────────
    op.create_table(
        "cohort_mutations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("study_id", sa.String(), sa.ForeignKey("studies.id"), nullable=False),
        sa.Column("sample_id", sa.String(), sa.ForeignKey("cohort_samples.id"), nullable=False),
        sa.Column("gene", sa.String(64), nullable=False),
        sa.Column("protein_change", sa.String(64), nullable=True),
        sa.Column("hgvs_c", sa.String(256), nullable=True),
        sa.Column("variant_classification", sa.String(64), nullable=True),
        sa.Column("chromosome", sa.String(8), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("ref_allele", sa.String(64), nullable=True),
        sa.Column("alt_allele", sa.String(64), nullable=True),
        sa.Column("vaf", sa.Float(), nullable=True),
        sa.Column("oncokb_level", sa.String(8), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_cohort_mutations_study_id", "cohort_mutations", ["study_id"])
    op.create_index("ix_cohort_mutations_gene", "cohort_mutations", ["gene"])
    op.create_index("ix_cohort_mutations_gene_protein", "cohort_mutations", ["gene", "protein_change"])


def downgrade() -> None:
    for idx in [
        "ix_cohort_mutations_gene_protein",
        "ix_cohort_mutations_gene",
        "ix_cohort_mutations_study_id",
    ]:
        op.drop_index(idx, table_name="cohort_mutations")
    op.drop_table("cohort_mutations")

    for idx in ["ix_cohort_samples_sample_id", "ix_cohort_samples_study_id"]:
        op.drop_index(idx, table_name="cohort_samples")
    op.drop_table("cohort_samples")

    for idx in ["ix_studies_cancer_type", "ix_studies_study_id"]:
        op.drop_index(idx, table_name="studies")
    op.drop_table("studies")

    op.drop_index("ix_sig_submission_id", table_name="mutation_signatures")
    op.drop_table("mutation_signatures")

    for idx in ["ix_rnaseq_gene", "ix_rnaseq_submission_id"]:
        op.drop_index(idx, table_name="rnaseq_expression")
    op.drop_table("rnaseq_expression")

    for idx in ["ix_sv_gene1", "ix_sv_submission_id"]:
        op.drop_index(idx, table_name="structural_variants")
    op.drop_table("structural_variants")

    for idx in ["ix_cna_gene", "ix_cna_submission_id"]:
        op.drop_index(idx, table_name="copy_number_alterations")
    op.drop_table("copy_number_alterations")

    with op.batch_alter_table("submissions") as batch_op:
        batch_op.drop_index("ix_submissions_status")
        batch_op.drop_column("progress_pct")

    with op.batch_alter_table("mutations") as batch_op:
        batch_op.drop_index("ix_mutations_gene")
        for col in [
            "hotspot_flag", "codon_change", "protein_position",
            "refseq_transcript_id", "variant_classification",
            "strand_bias", "allele_depth_alt", "allele_depth_ref",
            "depth", "vaf",
        ]:
            batch_op.drop_column(col)
