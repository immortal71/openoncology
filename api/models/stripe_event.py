from datetime import datetime, UTC

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class StripeWebhookEvent(Base):
    """One row per Stripe event id this service has already processed.

    Stripe redelivers a webhook on any non-2xx response, a timeout, or at its
    own discretion, and documents at-least-once delivery as normal behaviour.
    The donation branch of the handler did

        campaign.raised_usd = (campaign.raised_usd or 0) + amount_usd

    so every redelivery of one succeeded payment added the amount again. The
    total only ever moved up, nothing recorded which events had been seen, and
    a campaign page showing an inflated figure looks exactly like a campaign
    that raised more money.

    Inserting the event id first, and letting the primary key reject a repeat,
    makes the handler idempotent for every branch at once rather than requiring
    each one to be individually safe to replay.
    """

    __tablename__ = "stripe_webhook_events"

    # Stripe's own event id (evt_...). Primary key, so a concurrent redelivery
    # loses the race at the database rather than in application logic.
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    event_type: Mapped[str] = mapped_column(String(128), nullable=False)

    processed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False
    )
