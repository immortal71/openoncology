"""Restore the query indexes a8bf7eb4833c dropped.

risk_analysis.md open action 8. The schema-drift reconciliation migration
a8bf7eb4833c dropped 19 indexes. Nothing replaced them, and because the models
never declared them either, `alembic check` had nothing to compare against and
stayed green. The absence was invisible to CI for the same reason F11's missing
audit prefix was: every check asserted a positive about something present.

These are the lookups the application actually performs: every mutation for a
submission, every submission for a patient, the work queue by status, and the
cohort browser's gene and study filters. Without them each is a sequential scan,
which is survivable on a demo database and not on a real one. Filed as
non-blocking for clinical use because it is a performance property, not a safety
one, though a report that takes minutes is its own kind of clinical problem.

TWO OF THE NINETEEN ARE NOT RESTORED
------------------------------------
* ix_repurposing_submission_id, on repurposing_candidates.submission_id. Neither
  the table nor the column exists any more: the model is `repurposing`, keyed on
  `result_id`. The index was dropped because the schema moved on, and recreating
  it would fail. Recorded here rather than silently omitted.

* ix_studies_study_id, on studies.study_id. That column is already
  `unique=True`, and a unique constraint is backed by an index. A second index
  on the same column would cost writes and serve no read.

So seventeen are restored, and the count in open action 8 was itself slightly
wrong.

The columns now carry `index=True` in the models, so this migration and
autogenerate agree and `alembic check` will notice if one is dropped again.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-19
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

# (index name, table, [columns])
_INDEXES = [
    ("ix_mutations_submission_id", "mutations", ["submission_id"]),
    ("ix_mutations_gene", "mutations", ["gene"]),
    ("ix_submissions_patient_id", "submissions", ["patient_id"]),
    ("ix_submissions_status", "submissions", ["status"]),
    ("ix_cohort_mutations_study_id", "cohort_mutations", ["study_id"]),
    ("ix_cohort_mutations_gene", "cohort_mutations", ["gene"]),
    (
        "ix_cohort_mutations_gene_protein",
        "cohort_mutations",
        ["gene", "protein_change"],
    ),
    ("ix_cohort_samples_study_id", "cohort_samples", ["study_id"]),
    ("ix_cohort_samples_sample_id", "cohort_samples", ["sample_id"]),
    # These four groups are recreated under the names SQLAlchemy derives from
    # index=True, ix_<tablename>_<column>, not the abbreviated names
    # a8bf7eb4833c dropped. A migration that creates ix_cna_gene while the model
    # declares ix_copy_number_alterations_gene leaves `alembic check` reporting
    # drift forever, which is the check this migration exists to satisfy.
    ("ix_copy_number_alterations_submission_id", "copy_number_alterations", ["submission_id"]),
    ("ix_copy_number_alterations_gene", "copy_number_alterations", ["gene"]),
    ("ix_mutation_signatures_submission_id", "mutation_signatures", ["submission_id"]),
    ("ix_rnaseq_expression_submission_id", "rnaseq_expression", ["submission_id"]),
    ("ix_rnaseq_expression_gene", "rnaseq_expression", ["gene"]),
    ("ix_structural_variants_submission_id", "structural_variants", ["submission_id"]),
    ("ix_structural_variants_gene1", "structural_variants", ["gene1"]),
    ("ix_studies_cancer_type", "studies", ["cancer_type"]),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector_indexes: dict[str, set[str]] = {}
    try:
        from sqlalchemy import inspect

        inspector = inspect(bind)
        for _name, table, _cols in _INDEXES:
            if table not in inspector_indexes:
                inspector_indexes[table] = {
                    ix["name"] for ix in inspector.get_indexes(table)
                }
    except Exception:
        # If the dialect cannot be inspected, fall through and let the create
        # calls decide. Better to attempt than to skip silently.
        inspector_indexes = {}

    for name, table, cols in _INDEXES:
        if name in inspector_indexes.get(table, set()):
            continue
        op.create_index(name, table, cols)


def downgrade() -> None:
    for name, table, _cols in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
