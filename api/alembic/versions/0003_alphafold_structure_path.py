"""Add alphafold_structure_path to mutations table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mutations") as batch_op:
        batch_op.add_column(
            sa.Column("alphafold_structure_path", sa.String(512), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("mutations") as batch_op:
        batch_op.drop_column("alphafold_structure_path")
