"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # patients
    op.create_table(
        "patients",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("keycloak_id", sa.String, unique=True, nullable=False),
        sa.Column("email_hash", sa.String, nullable=False),
        sa.Column("consent_given", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # pharma_companies
    op.create_table(
        "pharma_companies",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("logo_url", sa.String),
        sa.Column("contact_email", sa.String),
        sa.Column("stripe_account_id", sa.String),
        sa.Column("verified", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # oncologists
    op.create_table(
        "oncologists",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("keycloak_id", sa.String, unique=True, nullable=False),
        sa.Column("name", sa.String),
        sa.Column("institution", sa.String),
        sa.Column("verified", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # submissions
    op.create_table(
        "submissions",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("patient_id", sa.String, sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="queued"),
        sa.Column("biopsy_key", sa.String),
        sa.Column("dna_key", sa.String),
        sa.Column("vcf_key", sa.String),
        sa.Column("report_key", sa.String),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # mutations
    op.create_table(
        "mutations",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("submission_id", sa.String, sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gene", sa.String),
        sa.Column("variant", sa.String),
        sa.Column("hgvs_c", sa.String),
        sa.Column("hgvs_p", sa.String),
        sa.Column("consequence", sa.String),
        sa.Column("alphamissense_score", sa.Float),
        sa.Column("alphamissense_class", sa.String),
        sa.Column("oncokb_level", sa.String),
        sa.Column("is_targetable", sa.Boolean, server_default="false"),
        sa.Column("civic_evidence", postgresql.JSONB),
        sa.Column("clinvar_significance", sa.String),
    )

    # results
    op.create_table(
        "results",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("submission_id", sa.String, sa.ForeignKey("submissions.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("report_url", sa.String),
        sa.Column("oncologist_reviewed", sa.Boolean, server_default="false"),
        sa.Column("oncologist_notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # repurposing_candidates
    op.create_table(
        "repurposing_candidates",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("submission_id", sa.String, sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("drug_name", sa.String, nullable=False),
        sa.Column("chembl_id", sa.String),
        sa.Column("mechanism", sa.String),
        sa.Column("target_gene", sa.String),
        sa.Column("binding_score", sa.Float),
        sa.Column("opentargets_score", sa.Float),
        sa.Column("oncokb_actionable", sa.Boolean, server_default="false"),
        sa.Column("rank_score", sa.Float),
        sa.Column("source", sa.String),
    )

    # campaigns
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("patient_id", sa.String, sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submission_id", sa.String, sa.ForeignKey("submissions.id", ondelete="CASCADE")),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("slug", sa.String, unique=True, nullable=False),
        sa.Column("patient_story", sa.Text),
        sa.Column("goal_usd", sa.Float, nullable=False),
        sa.Column("raised_usd", sa.Float, server_default="0"),
        sa.Column("percent_complete", sa.Float, server_default="0"),
        sa.Column("stripe_product_id", sa.String),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # orders
    op.create_table(
        "orders",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("patient_id", sa.String, sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pharma_id", sa.String, sa.ForeignKey("pharma_companies.id"), nullable=False),
        sa.Column("drug_name", sa.String),
        sa.Column("amount_usd", sa.Float),
        sa.Column("stripe_pi_id", sa.String),
        sa.Column("status", sa.String, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # indexes
    op.create_index("ix_submissions_patient_id", "submissions", ["patient_id"])
    op.create_index("ix_mutations_submission_id", "mutations", ["submission_id"])
    op.create_index("ix_repurposing_submission_id", "repurposing_candidates", ["submission_id"])


def downgrade() -> None:
    for idx in [
        "ix_repurposing_submission_id",
        "ix_mutations_submission_id",
        "ix_submissions_patient_id",
    ]:
        op.drop_index(idx)

    for table in [
        "orders",
        "campaigns",
        "repurposing_candidates",
        "results",
        "mutations",
        "submissions",
        "oncologists",
        "pharma_companies",
        "patients",
    ]:
        op.drop_table(table)
