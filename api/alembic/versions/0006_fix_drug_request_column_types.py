"""Fix incorrect drug request and bid column types.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("pharma_bids") as batch_op:
        batch_op.alter_column(
            "estimated_weeks",
            existing_type=sa.String(length=8),
            type_=sa.Integer(),
            postgresql_using="estimated_weeks::integer",
            existing_nullable=False,
        )

    with op.batch_alter_table("drug_requests") as batch_op:
        batch_op.alter_column(
            "is_open",
            existing_type=sa.String(length=8),
            type_=sa.Boolean(),
            postgresql_using=(
                "CASE WHEN lower(coalesce(is_open, 'true')) IN ('true', 't', '1', 'yes') "
                "THEN true ELSE false END"
            ),
            existing_nullable=True,
            nullable=False,
            existing_server_default=sa.text("true"),
            server_default=sa.text("true"),
        )


def downgrade() -> None:
    with op.batch_alter_table("drug_requests") as batch_op:
        batch_op.alter_column(
            "is_open",
            existing_type=sa.Boolean(),
            type_=sa.String(length=8),
            postgresql_using="CASE WHEN is_open THEN 'true' ELSE 'false' END",
            existing_nullable=False,
            nullable=True,
            existing_server_default=sa.text("true"),
            server_default=None,
        )

    with op.batch_alter_table("pharma_bids") as batch_op:
        batch_op.alter_column(
            "estimated_weeks",
            existing_type=sa.Integer(),
            type_=sa.String(length=8),
            postgresql_using="estimated_weeks::text",
            existing_nullable=False,
        )
