"""Add 'static_table' to evidencelookupstatus.

BACKLOG.md OO-27. With no OncoKB token, the worker's targetability step asked
nobody, stamped every variant not_attempted, and every submission ended in
no_targetable_mutation. The curated static table now answers in that case, and
the variant has to say which source answered: "the built-in table matched this"
and "live OncoKB matched this" are different claims about how current it is.

Postgres only. SQLite stores the enum as a plain string, so there is nothing to
alter. ADD VALUE is allowed inside a transaction from Postgres 12 as long as the
new value is not used in the same transaction; every deployment here runs 16.

The downgrade cannot drop an enum value without recreating the type, so it moves
static_table rows back to not_attempted and leaves the value in place, unused.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-23
"""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TYPE evidencelookupstatus ADD VALUE IF NOT EXISTS 'static_table'")


def downgrade() -> None:
    op.execute(
        "UPDATE mutations SET evidence_lookup_status = 'not_attempted' "
        "WHERE evidence_lookup_status = 'static_table'"
    )
