"""Add results.excluded_candidates for the oncology-relevance gate audit trail.

Tier 2 repurposing now drops candidates that WHO ATC classifies as something
other than a cancer therapy (see api/services/oncology_atc.py). Those drugs
were previously only written to the application log, which means a filter that
removes treatment options from a patient's report left no record in the report
itself. This column stores what was withheld and why.

Revision ID: 0010
Revises: a8bf7eb4833c
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "a8bf7eb4833c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("results", sa.Column("excluded_candidates", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("results", "excluded_candidates")
