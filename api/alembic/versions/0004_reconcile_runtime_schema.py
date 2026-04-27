"""Reconcile runtime schema with current SQLAlchemy models.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    if not _has_table(inspector, table):
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def _add_column_if_missing(
    inspector: sa.Inspector,
    table: str,
    column: sa.Column,
) -> None:
    if _has_table(inspector, table) and not _has_column(inspector, table, column.name):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(column)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # patients
    _add_column_if_missing(inspector, "patients", sa.Column("country", sa.String(length=64), nullable=True))
    _add_column_if_missing(inspector, "patients", sa.Column("consent_research_sharing", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    _add_column_if_missing(inspector, "patients", sa.Column("consent_date", sa.DateTime(), nullable=True))
    _add_column_if_missing(inspector, "patients", sa.Column("data_retention_days", sa.Integer(), nullable=True, server_default=sa.text("365")))

    # submissions
    _add_column_if_missing(inspector, "submissions", sa.Column("cancer_type", sa.String(length=128), nullable=True))
    _add_column_if_missing(inspector, "submissions", sa.Column("biopsy_s3_key", sa.String(length=512), nullable=True))
    _add_column_if_missing(inspector, "submissions", sa.Column("dna_s3_key", sa.String(length=512), nullable=True))
    _add_column_if_missing(inspector, "submissions", sa.Column("vcf_s3_key", sa.String(length=512), nullable=True))
    _add_column_if_missing(inspector, "submissions", sa.Column("pipeline_job_id", sa.String(length=128), nullable=True))
    _add_column_if_missing(inspector, "submissions", sa.Column("ai_job_id", sa.String(length=128), nullable=True))
    _add_column_if_missing(inspector, "submissions", sa.Column("submitted_at", sa.DateTime(), nullable=True))
    _add_column_if_missing(inspector, "submissions", sa.Column("completed_at", sa.DateTime(), nullable=True))

    # mutations
    _add_column_if_missing(inspector, "mutations", sa.Column("hgvs_notation", sa.String(length=256), nullable=True))
    _add_column_if_missing(inspector, "mutations", sa.Column("mutation_type", sa.String(length=64), nullable=True))
    _add_column_if_missing(inspector, "mutations", sa.Column("chromosome", sa.String(length=8), nullable=True))
    _add_column_if_missing(inspector, "mutations", sa.Column("position", sa.Integer(), nullable=True))
    _add_column_if_missing(inspector, "mutations", sa.Column("ref_allele", sa.String(length=64), nullable=True))
    _add_column_if_missing(inspector, "mutations", sa.Column("alt_allele", sa.String(length=64), nullable=True))
    _add_column_if_missing(inspector, "mutations", sa.Column("created_at", sa.DateTime(), nullable=True))

    # results
    _add_column_if_missing(inspector, "results", sa.Column("has_targetable_mutation", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    _add_column_if_missing(inspector, "results", sa.Column("target_gene", sa.String(length=64), nullable=True))
    _add_column_if_missing(inspector, "results", sa.Column("summary_text", sa.Text(), nullable=True))
    _add_column_if_missing(inspector, "results", sa.Column("report_pdf_s3_key", sa.String(length=512), nullable=True))

    # campaigns
    _add_column_if_missing(inspector, "campaigns", sa.Column("result_id", sa.String(), nullable=True))
    _add_column_if_missing(inspector, "campaigns", sa.Column("order_id", sa.String(), nullable=True))
    _add_column_if_missing(inspector, "campaigns", sa.Column("is_public", sa.Boolean(), nullable=True, server_default=sa.text("true")))
    _add_column_if_missing(inspector, "campaigns", sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")))
    _add_column_if_missing(inspector, "campaigns", sa.Column("stripe_account_id", sa.String(length=128), nullable=True))

    # orders
    _add_column_if_missing(inspector, "orders", sa.Column("drug_spec", sa.Text(), nullable=True))
    _add_column_if_missing(inspector, "orders", sa.Column("stripe_payment_intent_id", sa.String(length=128), nullable=True))

    # pharma_companies
    _add_column_if_missing(inspector, "pharma_companies", sa.Column("country", sa.String(length=64), nullable=True))
    _add_column_if_missing(inspector, "pharma_companies", sa.Column("min_order_usd", sa.Float(), nullable=True))

    # repurposing table currently used by ORM (legacy migration created repurposing_candidates)
    if not _has_table(inspector, "repurposing"):
        op.create_table(
            "repurposing",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("result_id", sa.String(), sa.ForeignKey("results.id"), nullable=False),
            sa.Column("drug_name", sa.String(length=256), nullable=False),
            sa.Column("chembl_id", sa.String(length=64), nullable=True),
            sa.Column("binding_score", sa.Float(), nullable=True),
            sa.Column("opentargets_score", sa.Float(), nullable=True),
            sa.Column("rank_score", sa.Float(), nullable=True),
            sa.Column("approval_status", sa.String(length=128), nullable=True),
            sa.Column("mechanism", sa.String(length=512), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    # deletion request table used by GDPR route/worker
    if not _has_table(inspector, "deletion_requests"):
        op.create_table(
            "deletion_requests",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("patient_id", sa.Uuid(), nullable=True),
            sa.Column("keycloak_id", sa.String(length=256), nullable=False),
            sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        )


def downgrade() -> None:
    # Non-destructive reconciliation migration: keep downgrade as no-op.
    pass
