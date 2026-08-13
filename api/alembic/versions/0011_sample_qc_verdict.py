"""Add submissions.sample_qc so the QC verdict reaches the report.

api/services/sample_qc.py detects FFPE artefacts, estimates tumour purity and
summarises coverage, and until now none of that reached anybody. Nothing called
it, and once it was called there was nowhere to put the answer, so the
oncologist report printed "QC report not provided" as its normal state rather
than as an exception. A sample carrying a high-confidence deamination signal
produced drug recommendations indistinguishable from a clean one.

The column lives on submissions rather than results because QC is a property of
the submitted sample, and because it is computed in the genomic worker, which
runs before any Result row exists.

Nullable, so every existing submission keeps reading as "not assessed" rather
than being retroactively claimed to have passed. Absence of a verdict and a
passing verdict must not look alike.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("sample_qc", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "sample_qc")
