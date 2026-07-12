"""
services/lulu.py — Lulu Print API (POD) fulfilment for the physical coloring
book, mirroring the public interface of services/printful.py so the orders
router can treat both providers uniformly.

Business rules (decided with the owner):
  * One product: the 54-page perfect-bound coloring book (format id "book").
  * Retail $24.99 with FREE shipping.
  * Drop-ship to 5 countries only: US, GB, ES, DE, AU.
  * Book stays in English (single edition).

Credentials come from the web app .env (added alongside the PayPal etc. keys):
  LULU_CLIENT_KEY, LULU_CLIENT_SECRET, LULU_SANDBOX (0 = production).

IMPORTANT: create_order() POSTs to Lulu's PAID /print-jobs/ endpoint and is the
only place that spends money. It only ever runs after a real PayPal capture
(see routers/orders.py capture_order).
"""

import base64
import logging
import os
import time

import httpx

log = logging.getLogger(__name__)

LULU_CLIENT_KEY    = os.getenv("LULU_CLIENT_KEY", "")
LULU_CLIENT_SECRET = os.getenv("LULU_CLIENT_SECRET", "")
LULU_SANDBOX       = os.getenv("LULU_SANDBOX", "0") == "1"

_HOST = "api.sandbox.lulu.com" if LULU_SANDBOX else "api.lulu.com"
BASE_URL  = f"https://{_HOST}"
TOKEN_URL = f"{BASE_URL}/auth/realms/glasstree/protocol/openid-connect/token"

# ── Product / fulfilment constants ────────────────────────────────────────────
# Lulu prints and ships across Europe from its EU facilities, so we fulfil the
# whole continent EXCEPT Germany. Germany is excluded everywhere (website AND
# Bonanza) until we register in the German packaging register (LUCID / VerpackG).
# Note: DE is intentionally NOT in EUROPE_COUNTRIES nor in the base set.
EUROPE_COUNTRIES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "GR", "HU",
    "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "SE",
    "NO", "IS", "CH", "LI",
}
BOOK_COUNTRIES = {"US", "GB", "ES", "AU"} | EUROPE_COUNTRIES

# SKU: 8.5x11, B&W interior, perfect-bound, 60# uncoated white, matte cover.
BOOK_POD_PACKAGE_ID = "0850X1100.BW.STD.PB.060UW444.MXX"
BOOK_PAGE_COUNT     = 54
BOOK_TITLE          = "Mathematical Tangle Art — A Coloring Book of Curves"

# Stable public URLs Lulu fetches the print files from at fulfilment time.
INTERIOR_URL = "https://mathrelaxing.store/static/downloads/book/interior.pdf"
COVER_URL    = "https://mathrelaxing.store/static/downloads/book/cover.pdf"

# Per-book print files. Every coloring book shares format_id "book" (so they all
# fulfil via Lulu with the same SKU/binding), but each ships its OWN interior +
# cover + printed title. Resolved at order time from order.product_slug.
_BASE = "https://mathrelaxing.store/static/downloads"
BOOK_PRINT_FILES: dict[str, dict] = {
    "mathematical-tangle-art-coloring-book": {
        "interior": f"{_BASE}/book/interior.pdf",
        "cover":    f"{_BASE}/book/cover.pdf",
        "title":    "Mathematical Tangle Art — A Coloring Book of Curves",
    },
    "sacred-harmonics-coloring-book": {
        "interior": f"{_BASE}/Sacred_Harmonics_Book.pdf",
        "cover":    f"{_BASE}/Sacred_Harmonics_Cover_v3.pdf",
        "title":    "Sacred Harmonics — A Chladni Coloring Book",
    },
    "hyperbolic-gardens-coloring-book": {
        "interior": f"{_BASE}/hyperbolic-gardens/interior.pdf",
        "cover":    f"{_BASE}/hyperbolic-gardens/cover.pdf",
        "title":    "Hyperbolic Gardens — A Coloring Book of Infinite Tilings",
    },
}
_DEFAULT_BOOK_SLUG = "mathematical-tangle-art-coloring-book"


def book_print_files(slug: str | None) -> dict:
    """Resolve the interior/cover/title for a given book product slug.
    Falls back to the original tangle book if the slug is unknown."""
    return BOOK_PRINT_FILES.get(slug or "", BOOK_PRINT_FILES[_DEFAULT_BOOK_SLUG])

# Lulu's cheapest universal shipping level (economy/ground). We absorb the cost
# (free shipping to the customer); production print cost is ~$4.24/unit.
SHIPPING_LEVEL = "MAIL"

# Total delivery estimate (business days, incl. ~3–5 day production), per market.
DELIVERY_ESTIMATES: dict[str, tuple[int, int]] = {
    "US": (6, 9),
    "GB": (6, 9),
    "ES": (7, 11),
    "DE": (7, 11),
    "AU": (8, 14),
    "DEFAULT": (8, 14),
}
# All other European markets share a single estimate (~7–13 business days).
for _cc in EUROPE_COUNTRIES:
    DELIVERY_ESTIMATES.setdefault(_cc, (7, 13))

# Some countries require a non-empty state_code for Lulu address validation.
# Fallbacks used only when the customer leaves the field blank.
_STATE_FALLBACK = {
    "ES": "Madrid",
    "AU": "NSW",
}


# ── Format (mirrors printful.FORMATS shape) ───────────────────────────────────
FORMATS: list[dict] = [
    {
        "id":                 "book",
        "label":              "Coloring Book (Paperback)",
        "size":               "8.5 × 11 in · 50 designs",
        "material":           "Perfect-bound paperback · 60# (90gsm) uncoated white · matte cover",
        "description":        "A 54-page perfect-bound coloring book of 50 unique "
                              "mathematical line-art designs. Printed on demand and "
                              "shipped from a local Lulu facility.",
        "price_usd":          24.99,
        "base_cost":          4.24,
        "shipping_us":        0.0,
        "shipping_intl":      0.0,
        "ships_worldwide":    False,
        "provider":           "lulu",
        "allowed_countries":  sorted(BOOK_COUNTRIES),
        "excluded_countries": [],
        "pod_package_id":     BOOK_POD_PACKAGE_ID,
        "page_count":         BOOK_PAGE_COUNT,
        "interior_url":       INTERIOR_URL,
        "cover_url":          COVER_URL,
    },
]

FORMATS_BY_ID: dict[str, dict] = {f["id"]: f for f in FORMATS}


# ── Country / shipping helpers ────────────────────────────────────────────────
def can_ship_to_country(country_code: str) -> bool:
    return (country_code or "").upper() in BOOK_COUNTRIES


def delivery_estimate(country_code: str, format_id: str = "book") -> tuple[int, int]:
    return DELIVERY_ESTIMATES.get((country_code or "").upper(),
                                  DELIVERY_ESTIMATES["DEFAULT"])


def shipping_cost(country_code: str, format_id: str = "book") -> float:
    if not can_ship_to_country(country_code):
        raise ValueError(f"We can't ship the book to {country_code or 'this country'} yet")
    return 0.0  # free shipping


async def shipping_quote(shipping_address: dict, format_id: str = "book") -> dict:
    """Return the shipping quote for the book. Shipping is free, so this is a
    pure business rule (no API call): validate the country, return rate 0.0 and
    a delivery estimate. Raises ValueError for unsupported countries."""
    country = (shipping_address.get("country")
               or shipping_address.get("country_code") or "").upper()
    if not can_ship_to_country(country):
        raise ValueError(
            "We currently ship the printed book to the United States, United "
            "Kingdom, most of Europe (except Germany) and Australia."
        )
    lo, hi = delivery_estimate(country, format_id)
    return {
        "rate": 0.0,
        "currency": "USD",
        "minDeliveryDays": lo,
        "maxDeliveryDays": hi,
        "source": "lulu_free_shipping",
    }


# ── Minimal async Lulu API client ─────────────────────────────────────────────
_token_cache: dict = {"value": "", "expiry": 0.0}


async def _get_token(client: httpx.AsyncClient) -> str:
    now = time.time()
    if _token_cache["value"] and now < _token_cache["expiry"] - 30:
        return _token_cache["value"]
    basic = base64.b64encode(
        f"{LULU_CLIENT_KEY}:{LULU_CLIENT_SECRET}".encode()
    ).decode()
    resp = await client.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials"},
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Lulu token request failed {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    _token_cache["value"] = data["access_token"]
    _token_cache["expiry"] = now + int(data.get("expires_in", 3600))
    return _token_cache["value"]


def _build_recipient(shipping_address: dict, contact_email: str) -> dict:
    country = (shipping_address.get("country")
               or shipping_address.get("country_code") or "US").upper()
    name = " ".join(filter(None, [
        shipping_address.get("first_name", ""),
        shipping_address.get("last_name", ""),
    ])).strip() or shipping_address.get("name", "Customer")
    state = (shipping_address.get("state")
             or shipping_address.get("state_code") or "").strip()
    if not state and country in _STATE_FALLBACK:
        state = _STATE_FALLBACK[country]
    phone = (shipping_address.get("phone")
             or shipping_address.get("phone_number") or "").strip()
    if not phone:
        phone = "+1 202 555 0100"  # Lulu requires a value; courier fallback
    addr = {
        "name":         name,
        "street1":      shipping_address.get("address1", ""),
        "city":         shipping_address.get("city", ""),
        "state_code":   state,
        "postcode":     shipping_address.get("zip", "") or shipping_address.get("postcode", ""),
        "country_code": country,
        "phone_number": phone,
        "email":        contact_email or "",
    }
    street2 = shipping_address.get("address2", "")
    if street2:
        addr["street2"] = street2
    return addr


# ── Order creation (PAID — runs only after a real PayPal capture) ─────────────
async def create_order(order, shipping_address: dict):
    if not LULU_CLIENT_KEY or not LULU_CLIENT_SECRET:
        await _mark_order_failed(order.id, "Lulu credentials are not configured")
        return None

    fmt = FORMATS_BY_ID["book"]
    country = (shipping_address.get("country")
               or shipping_address.get("country_code") or "").upper()
    if not can_ship_to_country(country):
        await _mark_order_failed(order.id, f"Lulu does not ship the book to {country}")
        return None

    recipient = _build_recipient(shipping_address, order.customer_email or "")
    files = book_print_files(getattr(order, "product_slug", None))
    payload = {
        "contact_email": order.customer_email or "support@mathrelaxing.store",
        "external_id": f"mathrelaxing-{order.id}",
        "line_items": [{
            "external_id": f"mathrelaxing-{order.id}-book",
            "title": files["title"],
            "printable_normalization": {
                "cover":    {"source_url": files["cover"]},
                "interior": {"source_url": files["interior"]},
            },
            "pod_package_id": fmt["pod_package_id"],
            "quantity": 1,
        }],
        "shipping_address": recipient,
        "shipping_level": SHIPPING_LEVEL,
    }

    try:
        async with httpx.AsyncClient() as client:
            token = await _get_token(client)
            resp = await client.post(
                f"{BASE_URL}/print-jobs/",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Cache-Control": "no-cache",
                },
                json=payload,
                timeout=60,
            )
    except Exception as exc:
        await _mark_order_failed(order.id, f"Lulu request error: {exc}")
        return None

    if resp.status_code in (200, 201):
        data = resp.json()
        job_id = str(data.get("id", ""))
        if job_id:
            from database import SessionLocal
            db = SessionLocal()
            try:
                o = db.query(type(order)).filter(type(order).id == order.id).first()
                if o:
                    o.printful_order_id = f"lulu:{job_id}"  # reuse column; prefix marks provider
                    o.status = "processing"
                    db.commit()
            finally:
                db.close()
        log.info("[lulu] order %s -> print-job %s", order.id, job_id)
        return job_id

    await _mark_order_failed(
        order.id, f"Lulu create print-job failed {resp.status_code}: {resp.text[:500]}")
    return None


async def _mark_order_failed(order_id: int, reason: str) -> None:
    log.error("[lulu] order %s fulfillment failed: %s", order_id, reason)
    from database import SessionLocal
    from models.product import Order

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order and order.status not in ("shipped", "printed", "cancelled"):
            order.status = "fulfillment_failed"
            db.commit()
    finally:
        db.close()
