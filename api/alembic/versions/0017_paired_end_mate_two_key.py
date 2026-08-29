"""Carry mate 2 of a paired-end FASTQ submission.

BACKLOG.md OO-10. `POST /api/submit` accepted a single `dna_file` described as
"VCF, FASTQ, or BAM". Every sequencer emits paired-end reads as two files, so a
clinician holding both could upload one, nothing said so, and the pipeline then
aligned it single-end with half the sample's reads absent.

Nullable, and it stays nullable. Null means one of three things and the column
deliberately does not try to distinguish them, because only the application
knows which applies: the submission is a VCF or a BAM and has no mate; the reads
were genuinely single-end; or the submission predates this column. A NOT NULL
with a sentinel would assert a fact about the first two that nothing measured.

No backfill. Existing rows have no second mate stored anywhere to point at, and
inventing a value would be worse than the absence.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-29
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "submissions",
        sa.Column("dna_r2_s3_key", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("submissions", "dna_r2_s3_key")
