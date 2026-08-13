"""Add results.evidence_provenance so a recommendation states its evidence source.

risk_analysis.md F4: the actionability table resolves through one of three paths
— a fresh cache, a live download, or the hardcoded static table — and which one
answered was recorded only as a log line. Nothing stored it and nothing returned
it, so a recommendation built from the undated built-in table was
indistinguishable from one built against a current OncoKB dump.

That is not hypothetical. During benchmark runs on 2026-08-13 every OncoKB
public dump URL returned 401 Unauthorized, the service fell back to the static
table on every invocation, and recommendations were produced normally.

Stamped on results rather than read at request time: the table can be refreshed
between producing a result and reading it, and the question a reader is asking
is which snapshot produced *this* recommendation.

Nullable, so results predating this read as "provenance not recorded" rather
than being retroactively claimed to have used current evidence.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("results", sa.Column("evidence_provenance", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("results", "evidence_provenance")
