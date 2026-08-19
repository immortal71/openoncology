"""Add mutations.evidence_lookup_status so a failed lookup is visible per variant.

risk_analysis.md F3: when the OncoKB lookup returned nothing because the token
was missing, the network failed, or the API rate limited, the variant was
skipped and the report was assembled without it. Nothing in the output
distinguished "this variant has no actionable evidence" from "we could not
determine whether it does". Those are clinically opposite statements: the first
supports moving on, the second does not.

Migration 0013 answered the question per result, via results.evidence_provenance.
That says the evidence base was degraded when the report was produced, but not
which gene's lookup was the one that failed. A report naming four variants where
one lookup failed should not read as four negatives.

Nullable on purpose. Every mutation written before this column existed reads as
NULL, which the API and the report render as "not assessed" rather than as a
completed check that found nothing. Absence of a verdict and a successful lookup
must not render alike, the same asymmetry used by results.evidence_provenance
(0013) and submissions.sample_qc (0011).

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

_STATUS = sa.Enum(
    "ok",
    "not_attempted",
    "unavailable",
    name="evidencelookupstatus",
)


def upgrade() -> None:
    bind = op.get_bind()
    _STATUS.create(bind, checkfirst=True)
    op.add_column(
        "mutations",
        sa.Column("evidence_lookup_status", _STATUS, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mutations", "evidence_lookup_status")
    _STATUS.drop(op.get_bind(), checkfirst=True)
