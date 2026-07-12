import logging
import os
from html import escape

import httpx

logger = logging.getLogger("telegram_notify")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[telegram] %(levelname)s %(message)s"))
    logger.addHandler(_h)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


async def _send(payload: dict, label: str) -> bool:
    """Send a sendMessage payload, logging any failure. Returns True on success."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("%s skipped — TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set", label)
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json={"chat_id": TELEGRAM_CHAT_ID, **payload}, timeout=10)
    except Exception:
        logger.exception("%s network/timeout failure", label)
        return False
    if r.status_code != 200:
        logger.error("%s HTTP %s: %s", label, r.status_code, r.text[:500])
        return False
    try:
        body = r.json()
        if not body.get("ok"):
            logger.error("%s API not-ok: %s", label, str(body)[:500])
            return False
    except Exception:
        logger.exception("%s could not parse response: %s", label, r.text[:200])
        return False
    return True

FORMAT_LABELS = {
    "canvas":        "Gallery Canvas",
    "framed-poster": "Framed Poster",
    "acrylic":       "Metal Print",
    "poster":        "Art Print",
    "postcard-set":  "Postcard",
}

SOURCE_LABELS = {
    "bonanza": "Bonanza",
    "gumroad": "Gumroad",
    "lemon": "Lemon Squeezy",
    "direct": "MathRelaxing.store",
}


from typing import Optional

async def send_message(text: str, parse_mode: Optional[str] = None) -> None:
    payload = {"text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    await _send(payload, "send_message")


async def notify_new_order(order, params: dict, edition: int):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        from services.printful import FORMATS_BY_ID
        fmt_id = getattr(order, "format_id", "canvas") or "canvas"
        fmt = FORMATS_BY_ID.get(fmt_id, {})
        fmt_label = FORMAT_LABELS.get(fmt_id, fmt_id)
        price = fmt.get("price_usd")
        price_str = f"${price:.0f}" if price else "—"

        shipping = {}
        try:
            import json
            shipping = json.loads(order.shipping_address or "{}")
        except Exception:
            pass
        country = shipping.get("country", "—")
        city = shipping.get("city", "")
        location = f"{city}, {country}".strip(", ") if city else country

        param_lines = "\n".join(
            f"  • {escape(str(key))}: {escape(str(value['value'] if isinstance(value, dict) else value))}"
            for key, value in params.items()
            if key not in ("color_start", "color_end", "background_color")
        )
        color_lines = "\n".join(
            f"  • {escape(str(key))}: {escape(str(value['value'] if isinstance(value, dict) else value))}"
            for key, value in params.items()
            if key in ("color_start", "color_end", "background_color")
        )

        text = (
            f"🎨 <b>Nueva venta — MathRelaxing.store</b>\n\n"
            f"📦 <code>{escape(str(order.product_slug))}</code>\n"
            f"🖼 {escape(str(fmt_label))}  ·  {price_str}\n"
            f"📍 {escape(str(location))}\n"
            f"📧 {escape(str(order.customer_email))}\n"
            f"🔢 Pedido #{order.id}  ·  Edición #{edition}\n"
        )
        if param_lines:
            text += f"\n<b>Parámetros:</b>\n{param_lines}\n"
        if color_lines:
            text += f"\n<b>Colores:</b>\n{color_lines}\n"
        text += f"\n🔗 https://mathrelaxing.store/certificate/{order.id}"
    except Exception:
        logger.exception("notify_new_order failed building message for order=%s", getattr(order, "id", "?"))
        return

    await _send({"text": text, "parse_mode": "HTML"}, f"notify_new_order(order={order.id})")

    try:
        from services import live_events
        live_events.record_purchase(
            label="paypal_legacy", uniq_key=f"order_{order.id}",
            value=price if isinstance(price, (int, float)) else None,
            product_slug=order.product_slug,
            customer_email=order.customer_email,
            extra={"order_id": order.id, "edition": edition},
        )
    except Exception:
        logger.exception("record_purchase (paypal_legacy) failed for order=%s", order.id)


def _country_flag(cc: Optional[str]) -> str:
    """Two-letter ISO country code → flag emoji (regional indicators)."""
    if not cc or len(cc) != 2 or not cc.isalpha():
        return "🌍"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in cc.upper())


async def notify_new_digital_purchase(purchase, product, country: Optional[str] = None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        price_str = f"${product.price_usd:.0f}" if product.price_usd else "—"
        ref = purchase.ref_source or "direct"
        source = SOURCE_LABELS.get(ref, ref.title())
        customer_name = getattr(purchase, "customer_name", "") or ""
        name_line = f"👤 {escape(str(customer_name))}\n" if customer_name else ""
        country_line = f"{_country_flag(country)} {escape(str(country).upper())}\n" if country else ""
        token_preview = escape(str(purchase.download_token[:8]))
        download_token = escape(str(purchase.download_token))

        text = (
            f"💰 <b>Nueva venta digital — {escape(source)}</b>\n\n"
            f"📦 <code>{escape(str(product.slug))}</code>\n"
            f"🗂 {escape(str(product.product_type))}  ·  {price_str}\n"
            f"{name_line}"
            f"{country_line}"
            f"📧 {escape(str(purchase.customer_email))}\n"
            f"🔢 Purchase #{purchase.id}\n"
            f"🏷 Canal: {escape(source)}\n"
            f"⬇️ Download token: <code>{token_preview}…</code>\n"
            f"\n🔗 https://mathrelaxing.store/download/{download_token}"
        )
    except Exception:
        logger.exception("notify_new_digital_purchase failed building message for purchase=%s", getattr(purchase, "id", "?"))
        return

    await _send({"text": text, "parse_mode": "HTML"}, f"notify_new_digital_purchase(purchase={purchase.id})")

    try:
        from services import live_events
        live_events.record_purchase(
            label=(purchase.ref_source or "direct"),
            uniq_key=f"purchase_{purchase.id}",
            value=float(product.price_usd) if product and product.price_usd else None,
            product_slug=product.slug if product else None,
            customer_email=getattr(purchase, "customer_email", None),
            extra={"purchase_id": purchase.id, "type": "digital"},
        )
    except Exception:
        logger.exception("record_purchase (digital) failed for purchase=%s", purchase.id)


async def notify_new_physical_order(order):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    fmt_id = getattr(order, "format_id", "poster") or "poster"
    # Resolve the print format from the right provider: coloring books ship via
    # Lulu (format "book"); posters / apparel / notebooks / desk-mats via
    # Printful. Fall back to the poster format only as a last resort.
    fmt = None
    price = None
    try:
        from services import lulu, printful
        fmt = lulu.FORMATS_BY_ID.get(fmt_id) or printful.FORMATS_BY_ID.get(fmt_id) or printful.FORMATS_BY_ID["poster"]
        price = fmt.get("price_usd")
        # Mirror the checkout pricing (routers/orders.py): sticker packs and
        # coloring books are priced on the Product, not on the shared format.
        from database import SessionLocal
        from models.product import Product
        _db = SessionLocal()
        try:
            product = _db.query(Product).filter(Product.id == getattr(order, "product_id", 0)).first()
            if product and product.collection in ("sticker-packs", "coloring-book", "coloring-books"):
                price = product.price_usd
        finally:
            _db.close()
    except Exception:
        logger.exception("notify_new_physical_order failed resolving format for order=%s", getattr(order, "id", "?"))

    try:
        import json as _json
        addr = _json.loads(order.shipping_address or "{}")
        country = addr.get("country", "?")
        city    = addr.get("city", "?")
        source = "Bonanza" if (getattr(order, "lemon_order_id", "") or "").startswith("bonanza_pod_") else "MathRelaxing.store"
        fmt = fmt or {"label": fmt_id, "size": ""}
        price_str = ("$%.2f" % price).rstrip("0").rstrip(".") if isinstance(price, (int, float)) else "—"
        text = (
            f"🖨 <b>Nueva venta física — {escape(source)}</b>\n\n"
            f"📦 <code>{escape(str(order.product_slug))}</code>  ·  {escape(str(fmt.get('label', fmt_id)))} {escape(str(fmt.get('size', '')))}\n"
            f"👤 {escape(str(order.customer_name or ''))}\n"
            f"📧 {escape(str(order.customer_email or ''))}\n"
            f"📍 {escape(str(city))}, {escape(str(country))}\n"
            f"🔢 Order #{order.id}\n"
            f"💰 {price_str} + shipping/marketplace fees\n"
        )
    except Exception:
        logger.exception("notify_new_physical_order failed building message for order=%s", getattr(order, "id", "?"))
        return

    await _send({"text": text, "parse_mode": "HTML"}, f"notify_new_physical_order(order={order.id})")

    try:
        from services import live_events
        # Channel attribution: Bonanza POD orders are tagged with a
        # "bonanza_pod_" external id; everything else is a direct web sale.
        is_bonanza = (getattr(order, "lemon_order_id", "") or "").startswith("bonanza_pod_")
        live_events.record_purchase(
            label="bonanza" if is_bonanza else "direct",
            uniq_key=f"order_{order.id}",
            value=float(price) if isinstance(price, (int, float)) else None,
            product_slug=order.product_slug,
            customer_email=getattr(order, "customer_email", None),
            extra={"order_id": order.id, "type": "physical", "format": fmt_id,
                   "channel": "bonanza" if is_bonanza else "direct"},
        )
    except Exception:
        logger.exception("record_purchase (physical) failed for order=%s", order.id)


async def notify_new_lowpoly_purchase(job):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        import json
        params = json.loads(job.params_json)
        text = (
            f"🖍 <b>Nueva venta Low Poly — MathRelaxing.store</b>\n\n"
            f"📧 {escape(str(job.customer_email))}\n"
            f"🎨 {escape(str(params.get('num_colors', '?')))} colores  ·  densidad {escape(str(params.get('polygon_size', '?')))}px  ·  {escape(str(params.get('polygon_type', '?')))}\n"
            f"📄 Formato: {escape(str(params.get('page_format', '?')))}\n"
            f"💵 $2.99\n"
            f"🔢 Job #{job.id}  ·  token <code>{escape(str(job.token[:8]))}…</code>\n"
        )
    except Exception:
        logger.exception("notify_new_lowpoly_purchase failed building message for job=%s", getattr(job, "id", "?"))
        return

    await _send({"text": text, "parse_mode": "HTML"}, f"notify_new_lowpoly_purchase(job={job.id})")

    try:
        from services import live_events
        live_events.record_purchase(
            label="lowpoly",
            uniq_key=f"job_{job.id}",
            value=2.99,
            product_slug="lowpoly-coloring-page",
            customer_email=getattr(job, "customer_email", None),
            extra={"job_id": job.id, "type": "tool"},
        )
    except Exception:
        logger.exception("record_purchase (lowpoly) failed for job=%s", job.id)
