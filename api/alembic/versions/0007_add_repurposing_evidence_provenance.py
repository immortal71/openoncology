"""Add provenance fields to repurposing candidates.

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("repurposing") as batch_op:
        batch_op.add_column(sa.Column("evidence_sources", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("matched_terms", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("repurposing") as batch_op:
        batch_op.drop_column("matched_terms")
        batch_op.drop_column("evidence_sources")
