"""Add COSMIC/cBioPortal fields to results, LLM summary, bidding tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- results table: new columns ---
    with op.batch_alter_table("results") as batch_op:
        batch_op.add_column(
            sa.Column("plain_language_summary", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("cbioportal_data", sa.JSON(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("cosmic_sample_count", sa.String(32), nullable=True)
        )

    # --- drug_requests table ---
    op.create_table(
        "drug_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("patient_id", sa.String(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("result_id", sa.String(), sa.ForeignKey("results.id"), nullable=True),
        sa.Column("target_gene", sa.String(64), nullable=True),
        sa.Column("drug_spec", sa.Text(), nullable=False),
        sa.Column("max_budget_usd", sa.Float(), nullable=True),
        sa.Column("is_open", sa.String(8), nullable=True, server_default="True"),
        sa.Column("accepted_bid_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
    )

    # --- pharma_bids table ---
    op.create_table(
        "pharma_bids",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "drug_request_id",
            sa.String(),
            sa.ForeignKey("drug_requests.id"),
            nullable=False,
        ),
        sa.Column(
            "pharma_id",
            sa.String(),
            sa.ForeignKey("pharma_companies.id"),
            nullable=False,
        ),
        sa.Column("price_usd", sa.Float(), nullable=False),
        sa.Column("estimated_weeks", sa.String(8), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "accepted", "rejected", "expired", name="bidstatus"),
            nullable=True,
            server_default="open",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("pharma_bids")
    op.drop_table("drug_requests")

    with op.batch_alter_table("results") as batch_op:
        batch_op.drop_column("cosmic_sample_count")
        batch_op.drop_column("cbioportal_data")
        batch_op.drop_column("plain_language_summary")
