"""
Server-side ingestion of `purchase` events into the /admin/live dashboard.

Frontend tracking (templates/base.html) covers pageviews and funnel signals
from the browser. But the `purchase` confirmation happens server-side in
webhooks (PayPal, Lemon, Whop, Printful, Bonanza, Gumroad…), so we record
it here so the dashboard counts every real sale — even when the buyer
closes the tab before /checkout/success loads.
"""
import logging
from datetime import datetime
from typing import Optional

from database import SessionLocal
from models.live import LiveEvent

logger = logging.getLogger("live_events")


def record_purchase(
    *,
    label: str,
    uniq_key,
    value: Optional[float] = None,
    product_slug: Optional[str] = None,
    customer_email: Optional[str] = None,
    extra: Optional[dict] = None,
) -> None:
    """Insert a `purchase` event server-side. Idempotent per (label, uniq_key).

    `label` is the channel ("paypal", "lemon", "whop", "bonanza", "gumroad", "lowpoly").
    `uniq_key` should be the order_id / purchase_id / job_id — used to dedupe webhook retries.
    Server-side events are flagged with ua_class="server" so they don't inflate
    active_visitors / today_sessions on the dashboard.
    """
    import json as _json

    sid = f"srv_{label}_{uniq_key}"[:64]
    db = SessionLocal()
    try:
        already = db.query(LiveEvent.id).filter(
            LiveEvent.session_id == sid,
            LiveEvent.event_type == "purchase",
        ).first()
        if already:
            return
        payload_blob = None
        if extra is not None or customer_email:
            payload_blob = _json.dumps({
                **(extra or {}),
                **({"email": customer_email} if customer_email else {}),
            })[:2000]
        ev = LiveEvent(
            ts=datetime.utcnow(),
            session_id=sid,
            event_type="purchase",
            path=f"/srv/{label}",
            ua_class="server",
            source=label.lower(),
            medium="server",
            product_slug=(product_slug or "")[:120] or None,
            value_usd=float(value) if value is not None else None,
            payload=payload_blob,
        )
        db.add(ev)
        db.commit()
    except Exception:
        logger.exception("record_purchase failed label=%s uniq=%s", label, uniq_key)
        db.rollback()
    finally:
        db.close()
