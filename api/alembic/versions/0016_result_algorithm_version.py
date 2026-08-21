"""Add results.algorithm_version so a recommendation names the rules that made it.

REGULATORY_FRAMEWORK.md section 2.3 requires a locked algorithm version with a
change-control procedure before a De Novo or CE IVD-R submission. A regulator's
question is not what the system recommends, it is what exactly produced a given
recommendation and whether that has changed since.

results.evidence_provenance (0013) already records which evidence snapshot
answered, and mutations.evidence_lookup_status (0014) records whether a
variant's lookup succeeded. Neither says which scoring behaviour ran. Two
recommendations built from identical evidence can differ because a weight moved
or a pool policy flipped, and until now nothing recorded that.

The column holds the declared semantic version, a fingerprint over every input
that can reorder drugs for fixed evidence, and the components that went into it.
The fingerprint deliberately excludes the evidence table's contents: that
identity belongs to evidence_provenance, and folding it in would make the
algorithm version churn every time a dump refreshed.

Stamped at production time rather than read at request time, for the same reason
evidence provenance is: settings can change between producing a recommendation
and reading it, and the question a reader has is which rules produced this one.

Nullable, so results written before this column read as "algorithm not
recorded" rather than being retroactively claimed to have run under the current
rules. Absence of a version and a known version must not render alike, the same
asymmetry used by 0011, 0013 and 0014.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("results", sa.Column("algorithm_version", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("results", "algorithm_version")
