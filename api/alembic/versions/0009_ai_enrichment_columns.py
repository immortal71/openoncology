"""Add immunotherapy_profile, mutational_signature, combination_therapy to results.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("results", sa.Column("immunotherapy_profile", sa.JSON(), nullable=True))
    op.add_column("results", sa.Column("mutational_signature", sa.JSON(), nullable=True))
    op.add_column("results", sa.Column("combination_therapy", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("results", "combination_therapy")
    op.drop_column("results", "mutational_signature")
    op.drop_column("results", "immunotherapy_profile")
