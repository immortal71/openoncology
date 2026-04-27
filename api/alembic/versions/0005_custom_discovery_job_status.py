"""Add persisted discovery job fields to drug_requests.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


discovery_status = sa.Enum(
    "queued",
    "running",
    "complete",
    "failed",
    name="discoverystatus",
)


def upgrade() -> None:
    discovery_status.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("drug_requests") as batch_op:
        batch_op.add_column(sa.Column("discovery_status", discovery_status, nullable=False, server_default="queued"))
        batch_op.add_column(sa.Column("discovery_brief", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("discovery_error", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("discovery_started_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("discovery_completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("drug_requests") as batch_op:
        batch_op.drop_column("discovery_completed_at")
        batch_op.drop_column("discovery_started_at")
        batch_op.drop_column("discovery_error")
        batch_op.drop_column("discovery_brief")
        batch_op.drop_column("discovery_status")
    discovery_status.drop(op.get_bind(), checkfirst=True)
