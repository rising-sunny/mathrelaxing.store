import json
import os

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.product import Order, Certificate, DigitalProduct, Purchase, LowPolyCredit
from services import email, telegram
from services import lemon_squeezy

router = APIRouter()


# ── LemonSqueezy Webhook (legacy — replaced by PayPal) ──────────────────────

@router.post("/webhooks/lemonsqueezy")
async def lemon_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Signature", "")
    payload_str = body.decode("utf-8")

    if not lemon_squeezy.verify_webhook(signature, payload_str):
        raise HTTPException(status_code=401, detail="Invalid LemonSqueezy webhook signature")

    payload = json.loads(payload_str)
    event_name = payload.get("meta", {}).get("event_name", "")

    if event_name == "order_created":
        await _handle_lemon_order_created(payload, db)
    elif event_name == "order_paid":
        await _handle_lemon_order_paid(payload, db)

    return {"status": "ok"}


async def _handle_lemon_order_created(payload: dict, db: Session):
    data = payload.get("data", {})
    attrs = data.get("attributes", {})
    lemon_order_id = str(data.get("id", ""))
    custom = attrs.get("checkout_data", {}).get("custom", {})
    purchase_id = custom.get("purchase_id")

    if not purchase_id:
        return

    purchase = db.query(Purchase).filter(Purchase.id == int(purchase_id)).first()
    if not purchase:
        return

    purchase.lemon_order_id = lemon_order_id
    db.commit()


async def _handle_lemon_order_paid(payload: dict, db: Session):
    data = payload.get("data", {})
    attrs = data.get("attributes", {})
    lemon_order_id = str(data.get("id", ""))
    custom = attrs.get("checkout_data", {}).get("custom", {})

    if custom.get("job_type") == "lowpoly":
        await _handle_lowpoly_order_paid(lemon_order_id, custom, db)
        return

    purchase_id = custom.get("purchase_id")
    if not purchase_id:
        return

    purchase = db.query(Purchase).filter(Purchase.id == int(purchase_id)).first()
    if not purchase:
        return

    if purchase.status == "paid":
        return  # idempotent

    purchase.status = "paid"
    db.commit()

    product = db.query(DigitalProduct).filter(DigitalProduct.id == purchase.product_id).first()
    if product:
        await telegram.notify_new_digital_purchase(purchase, product)


async def _handle_lowpoly_order_paid(lemon_order_id: str, custom: dict, db: Session):
    from models.product import LowPolyJob
    job_id = custom.get("job_id")
    if not job_id:
        return

    job = db.query(LowPolyJob).filter(LowPolyJob.id == int(job_id)).first()
    if not job or job.status == "paid":
        return

    job.lemon_order_id = lemon_order_id
    job.status = "paid"
    db.commit()

    await email.send_lowpoly_download_email(job)


# ── PayPal webhooks ─────────────────────────────────────────────────────────
# Primary capture still happens on /checkout/return (browser). This webhook is
# the safety net when the buyer pays but never lands back on the return URL
# (tab closed, mobile app, network drop). Handles digital Purchase, physical
# Order, and LowPolyJob.

@router.post("/webhooks/paypal")
async def paypal_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()

    from services import paypal
    valid = await paypal.verify_webhook_signature(dict(request.headers), body)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid PayPal webhook signature")

    payload = json.loads(body)
    event_type = payload.get("event_type", "")

    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        await _handle_capture_completed(payload, db)
    elif event_type == "PAYMENT.CAPTURE.DENIED":
        await _handle_capture_denied(payload, db)

    return {"status": "ok"}


def _paypal_order_id_from_capture(resource: dict) -> str:
    related = (resource.get("supplementary_data") or {}).get("related_ids") or {}
    return (
        related.get("order_id")
        or resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
        or ""
    )


def _custom_id_from_capture(resource: dict) -> str:
    # Orders v2 may surface purchase_unit custom_id on the capture resource.
    return (
        resource.get("custom_id")
        or resource.get("invoice_id")
        or resource.get("purchase_unit_reference_id")
        or ""
    )


async def _resolve_refs_from_paypal_order(paypal_order_id: str) -> tuple[str, str]:
    """Return (custom_id, reference_id) from the PayPal order resource."""
    if not paypal_order_id:
        return "", ""
    try:
        from services import paypal
        data = await paypal.get_order(paypal_order_id)
        units = data.get("purchase_units") or []
        if not units:
            return "", ""
        unit = units[0] or {}
        return str(unit.get("custom_id") or ""), str(unit.get("reference_id") or "")
    except Exception:
        return "", ""


def _parse_kind_id(custom_id: str, reference_id: str) -> tuple[str | None, int | None]:
    """Map PayPal custom_id/reference_id → ('purchase'|'order'|'lowpoly', id)."""
    cid = (custom_id or "").strip()
    if ":" in cid:
        kind, _, raw = cid.partition(":")
        kind = kind.lower().strip()
        try:
            return kind, int(raw)
        except (TypeError, ValueError):
            pass
    if reference_id:
        try:
            return None, int(str(reference_id).strip())
        except (TypeError, ValueError):
            pass
    return None, None


async def _fulfill_digital_purchase(purchase: Purchase, paypal_order_id: str, db: Session, payer: dict | None = None):
    """Mark a digital Purchase paid and send email/telegram. Idempotent."""
    if purchase.status == "paid":
        if paypal_order_id and not purchase.paypal_order_id:
            purchase.paypal_order_id = paypal_order_id
            db.commit()
        return

    purchase.status = "paid"
    if paypal_order_id:
        purchase.paypal_order_id = paypal_order_id

    payer = payer or {}
    if not purchase.customer_email or not purchase.customer_name:
        payer_email = (payer.get("email_address") or "").strip().lower()
        name_obj = payer.get("name") or {}
        payer_name = " ".join(
            filter(None, [name_obj.get("given_name"), name_obj.get("surname")])
        ).strip()
        if payer_email and not purchase.customer_email:
            purchase.customer_email = payer_email
        if payer_name and not purchase.customer_name:
            purchase.customer_name = payer_name

    db.commit()

    product = db.query(DigitalProduct).filter(DigitalProduct.id == purchase.product_id).first()
    country = ((payer.get("address") or {}).get("country_code")) if payer else None
    if purchase.customer_email and product:
        await email.send_digital_purchase_email(purchase, product)
    if product:
        await telegram.notify_new_digital_purchase(purchase, product, country=country)


async def _fulfill_physical_order(order: Order, paypal_order_id: str, db: Session):
    """Mark a physical Order paid, issue certificate, notify. Idempotent."""
    if order.status in {"paid", "processing", "printed", "shipped", "fulfillment_failed"}:
        if paypal_order_id and not order.paypal_order_id:
            order.paypal_order_id = paypal_order_id
            db.commit()
        return

    if paypal_order_id:
        order.paypal_order_id = paypal_order_id
    order.status = "paid"
    db.commit()

    edition = db.query(Certificate).count() + 1
    cert = Certificate(
        order_id=order.id,
        edition_number=edition,
        params_json=order.params_json,
        qr_url=f"https://mathrelaxing.store/certificate/{order.id}",
    )
    db.add(cert)
    db.commit()

    params = json.loads(order.params_json or "{}")
    await email.send_order_confirmation(order, edition)
    await telegram.notify_new_order(order, params, edition)


async def _fulfill_lowpoly_job(job, paypal_order_id: str, db: Session):
    """Mark LowPolyJob paid and email files. Idempotent."""
    if job.status == "paid":
        return
    if paypal_order_id and not job.lemon_order_id:
        job.lemon_order_id = paypal_order_id
    job.status = "paid"
    db.commit()
    await email.send_lowpoly_download_email(job)
    await telegram.notify_new_lowpoly_purchase(job)


async def _handle_capture_completed(payload: dict, db: Session):
    resource = payload.get("resource", {}) or {}
    paypal_order_id = _paypal_order_id_from_capture(resource)
    custom_id = _custom_id_from_capture(resource)
    reference_id = ""

    # Prefer explicit custom_id; otherwise resolve from the PayPal order.
    if not custom_id or ":" not in custom_id:
        cid2, ref2 = await _resolve_refs_from_paypal_order(paypal_order_id)
        if cid2:
            custom_id = cid2
        if ref2:
            reference_id = ref2

    kind, ref_int = _parse_kind_id(custom_id, reference_id or custom_id)

    # 1) Match by stored paypal_order_id (set at checkout creation)
    purchase = None
    order = None
    lowpoly = None
    if paypal_order_id:
        purchase = db.query(Purchase).filter(Purchase.paypal_order_id == paypal_order_id).first()
        order = db.query(Order).filter(Order.paypal_order_id == paypal_order_id).first()
        from models.product import LowPolyJob
        lowpoly = db.query(LowPolyJob).filter(LowPolyJob.lemon_order_id == paypal_order_id).first()

    # 2) Match by kind:id / bare reference_id
    if not purchase and not order and not lowpoly and ref_int is not None:
        if kind == "purchase" or kind is None:
            purchase = db.query(Purchase).filter(Purchase.id == ref_int).first()
            # Only accept bare-id match for still-pending rows to avoid
            # clobbering an unrelated paid record when tables share int space.
            if purchase and purchase.status not in (None, "pending", "failed") and kind is None:
                purchase = None
        if not purchase and (kind == "order" or kind is None):
            order = db.query(Order).filter(Order.id == ref_int).first()
            if order and order.status not in (None, "pending", "failed") and kind is None:
                order = None
        if not purchase and not order and (kind == "lowpoly" or kind is None):
            from models.product import LowPolyJob
            lowpoly = db.query(LowPolyJob).filter(LowPolyJob.id == ref_int).first()
            if lowpoly and lowpoly.status not in (None, "pending") and kind is None:
                lowpoly = None

    if purchase:
        # Capture payload has no payer block; optional GET for email fill-in.
        payer = {}
        if not purchase.customer_email and paypal_order_id:
            try:
                from services import paypal
                odata = await paypal.get_order(paypal_order_id)
                payer = odata.get("payer") or {}
            except Exception:
                payer = {}
        await _fulfill_digital_purchase(purchase, paypal_order_id, db, payer=payer)
        return

    if order:
        await _fulfill_physical_order(order, paypal_order_id, db)
        return

    if lowpoly:
        await _fulfill_lowpoly_job(lowpoly, paypal_order_id, db)
        return


async def _handle_capture_denied(payload: dict, db: Session):
    resource = payload.get("resource", {}) or {}
    paypal_order_id = _paypal_order_id_from_capture(resource) or resource.get("id", "")
    if not paypal_order_id:
        return

    order = db.query(Order).filter(Order.paypal_order_id == paypal_order_id).first()
    if order and order.status == "pending":
        order.status = "failed"
        db.commit()

    purchase = db.query(Purchase).filter(Purchase.paypal_order_id == paypal_order_id).first()
    if purchase and purchase.status == "pending":
        purchase.status = "failed"
        db.commit()

    from models.product import LowPolyJob
    job = db.query(LowPolyJob).filter(LowPolyJob.lemon_order_id == paypal_order_id).first()
    if job and job.status == "pending":
        # leave as pending so buyer can retry; no status field for "failed"
        pass


@router.post("/webhooks/printful")
async def printful_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Printful-Signature", "")

    from services import printful
    if not printful.verify_webhook(body, signature):
        raise HTTPException(status_code=401, detail="Invalid Printful webhook signature")

    payload_data = json.loads(body)
    event_type = payload_data.get("type", "")
    data = payload_data.get("data", {})

    pf_order = data.get("order", {})
    pf_order_id = str(pf_order.get("id", ""))

    if not pf_order_id:
        return {"status": "ok"}

    order = db.query(Order).filter(Order.printful_order_id == pf_order_id).first()

    if not order:
        ext_id = pf_order.get("external_id", "")
        if ext_id.startswith("mathrelaxing-"):
            try:
                internal_id = int(ext_id.split("-", 1)[1])
                order = db.query(Order).filter(Order.id == internal_id).first()
            except (ValueError, IndexError):
                pass

    if not order:
        return {"status": "ok"}

    if event_type == "package_shipped":
        order.status = "shipped"
        db.commit()
        if (order.lemon_order_id or "").startswith("bonanza_pod_"):
            try:
                from services import bonanza
                await bonanza.mark_physical_order_shipped(order, data.get("shipment", {}))
            except Exception:
                pass
    elif event_type == "order_updated":
        pf_status = pf_order.get("status", "")
        new_status = printful.PRINTFUL_STATUS_MAP.get(pf_status)
        if new_status:
            order.status = new_status
            db.commit()

    return {"status": "ok"}


# ── Whop Webhook ─────────────────────────────────────────────────────────────

def _whop_client():
    import base64
    import whop_sdk
    secret = os.getenv("WHOP_WEBHOOK_SECRET", "")
    webhook_key = base64.b64encode(secret.encode()).decode() if secret else None
    return whop_sdk.Whop(
        api_key=os.getenv("WHOP_API_KEY", ""),
        webhook_key=webhook_key,
    )


@router.post("/webhooks/whop")
async def whop_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        event = _whop_client().webhooks.unwrap(body_str, headers=dict(request.headers))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Whop webhook signature")

    if event.type == "payment.succeeded":
        await _handle_whop_payment_succeeded(event.data, db)
    elif event.type == "membership.activated":
        await _handle_whop_membership_activated(event.data, db)
    elif event.type == "refund.created":
        await _handle_whop_refund(event.data, db)
    elif event.type in ("dispute.created", "dispute.updated"):
        await _handle_whop_dispute(event.data)

    return {"status": "ok"}


LOWPOLY_PLANS = {
    os.getenv("WHOP_LOWPOLY_PLAN_1", ""): 1,
    os.getenv("WHOP_LOWPOLY_PLAN_5", ""): 5,
}


async def _handle_whop_payment_succeeded(payment, db: Session):
    """Fulfill a payment.succeeded event (one-time purchase)."""
    plan_id     = (payment.plan.id if payment.plan else "")
    whop_id     = payment.id
    buyer_email = (payment.user.email if payment.user else "") or ""
    buyer_name  = (payment.user.name  if payment.user else "") or ""

    if plan_id in LOWPOLY_PLANS:
        await _handle_whop_lowpoly_credit(whop_id, buyer_email, buyer_name, plan_id, LOWPOLY_PLANS[plan_id], db)
        return

    await _fulfill_digital_product(plan_id, whop_id, buyer_email, buyer_name, db)


async def _handle_whop_membership_activated(membership, db: Session):
    """Fulfill a membership.activated event (subscription or one-time that creates a membership)."""
    plan_id     = (membership.plan.id if membership.plan else "")
    whop_id     = membership.id
    buyer_email = (membership.user.email if membership.user else "") or ""
    buyer_name  = (membership.user.name  if membership.user else "") or ""

    if plan_id in LOWPOLY_PLANS:
        await _handle_whop_lowpoly_credit(whop_id, buyer_email, buyer_name, plan_id, LOWPOLY_PLANS[plan_id], db)
        return

    await _fulfill_digital_product(plan_id, whop_id, buyer_email, buyer_name, db)


async def _fulfill_digital_product(plan_id: str, whop_id: str, buyer_email: str, buyer_name: str, db: Session):
    if not buyer_email:
        return

    product = db.query(DigitalProduct).filter(
        DigitalProduct.whop_plan_id == plan_id,
        DigitalProduct.active == True,
    ).first()
    if not product:
        return

    existing = db.query(Purchase).filter(
        Purchase.paypal_order_id == f"whop:{whop_id}"
    ).first()
    if existing:
        return  # idempotent

    from datetime import datetime, timedelta
    purchase = Purchase(
        product_id      = product.id,
        customer_email  = buyer_email,
        customer_name   = buyer_name or "Unknown",
        ref_source      = "whop",
        status          = "paid",
        paypal_order_id = f"whop:{whop_id}",
        expires_at      = datetime.utcnow() + timedelta(days=14),
        download_count  = 0,
        max_downloads   = 3,
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    await email.send_digital_purchase_email(purchase, product)
    await telegram.notify_new_digital_purchase(purchase, product)


async def _handle_whop_lowpoly_credit(whop_id: str, buyer_email: str, buyer_name: str, plan_id: str, pack_size: int, db: Session):
    """Create a LowPolyCredit and email the redemption link to the buyer."""
    if not buyer_email:
        return

    if db.query(LowPolyCredit).filter(LowPolyCredit.whop_id == whop_id).first():
        return  # idempotent

    credit = LowPolyCredit(
        whop_id        = whop_id,
        customer_email = buyer_email,
        customer_name  = buyer_name,
        pack_size      = pack_size,
        used_count     = 0,
        status         = "unused",
    )
    db.add(credit)
    db.commit()
    db.refresh(credit)

    await email.send_lowpoly_credit_email(credit)
    await telegram.send_message(
        f"🖍 Low Poly credit sold ({pack_size}×) — {buyer_email} — whop:{whop_id}"
    )


async def _handle_whop_refund(refund_data, db: Session):
    """Mark the related purchase as refunded."""
    payment = refund_data.payment if hasattr(refund_data, "payment") else None
    whop_id = (payment.id if payment else "") or ""
    if not whop_id:
        return
    purchase = db.query(Purchase).filter(
        Purchase.paypal_order_id == f"whop:{whop_id}"
    ).first()
    if purchase and purchase.status == "paid":
        purchase.status = "refunded"
        purchase.max_downloads = 0
        db.commit()


async def _handle_whop_dispute(dispute_data):
    """Alert on Telegram when a dispute is opened or updated."""
    user    = getattr(dispute_data, "user", None)
    buyer   = (user.email if user and user.email else "unknown")
    amount  = getattr(dispute_data, "amount", "?")
    whop_id = getattr(dispute_data, "id", "")
    await telegram.send_message(
        f"⚠️ Whop dispute\nID: {whop_id}\nBuyer: {buyer}\nAmount: ${amount}"
    )
