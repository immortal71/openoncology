"""Add stripe_webhook_events so a redelivered Stripe event is processed once.

Stripe redelivers a webhook on any non-2xx response, on a timeout, and at its
own discretion; at-least-once delivery is documented, expected behaviour rather
than an error condition. The donation branch of the handler did

    campaign.raised_usd = (campaign.raised_usd or 0) + amount_usd

so each redelivery of a single succeeded payment added the amount again. The
figure only ever moved upward, nothing recorded which events had been seen, and
an inflated campaign total is indistinguishable from a successful campaign.

The event id is the primary key rather than a unique column so that two
concurrent redeliveries resolve in the database instead of in a check-then-act
race in application code.

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
    op.create_table(
        "stripe_webhook_events",
        sa.Column("event_id", sa.String(255), primary_key=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("stripe_webhook_events")
