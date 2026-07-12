import os
import json
import httpx

GELATO_API_KEY = os.getenv("GELATO_API_KEY", "")
BASE_URL = "https://order.gelatoapis.com"
PRODUCT_BASE_URL = "https://product.gelatoapis.com"

HEADERS = {
    "X-API-KEY": GELATO_API_KEY,
    "Content-Type": "application/json",
}

# ── Gelato product UIDs ───────────────────────────────────────────────────────
# All formats are 16×20" (400×500 mm), vertical orientation, 4-color print.
# NOTE: Verified against the Gelato catalog and draft-order previews on
#       April 23, 2026.
_CANVAS_16x20   = "canvas_16x20-inch-400x500-mm_canvas_wood-fsc-slim_4-0_ver"
_FRAMED_16x20   = "framed_poster_400x500-mm-16x20-inch_black_wood_w12xt22-mm_plexiglass_400x500-mm-16x20-inch_200-gsm-80lb-uncoated_4-0_ver"
_ACRYLIC_16x20  = "acrylic_400x500-mm-16x20-inch_4-mm_4-0_ver"
# Verified via Gelato Product API on 2026-04-25 — productTypeUid=poster, isPrintable=true
_POSTER_16x20   = "flat_400x500-mm-16x20-inch_200-gsm-80lb-uncoated_4-0_ver"

# NEW: Aluminum and Postcard products (UIDs to be verified with Gelato)
# Aluminum print — 3mm metallic panel, 400×500mm (16×20 inch)
_ALUMINUM_16x20 = "metallic_400x500-mm-16x20-inch_3-mm_4-0_ver"
# Postcard set — A5 size (148×210mm), set of 10 identical prints
_POSTCARD_A5_SET10 = "postcard_148x210-mm-a5_300-gsm-120lb-glossy_set-of-10_4-0"

# Print specs per format for a 16×20" (400×500 mm) product.
# All formats at 300 DPI for premium gallery quality
# Canvas, paper poster, and acrylic all benefit from high resolution
_SPEC_CANVAS  = {"width_px": 4800, "height_px": 6000, "dpi": 300}
_SPEC_PRINT   = {"width_px": 4800, "height_px": 6000, "dpi": 300}

# NEW: Specs for additional formats
_SPEC_ALUMINUM = {"width_px": 4800, "height_px": 6000, "dpi": 300}  # Same as prints
# A5 Postcard: 148×210mm @ 300 DPI = 1748×2480 px per card
_SPEC_POSTCARD = {"width_px": 1748, "height_px": 2480, "dpi": 300, "set_size": 10}

# Formats shown on every product page as a selector.
FORMATS: list[dict] = [
    {
        "id":          "canvas",
        "label":       "Gallery Canvas",
        "size":        "16 × 20 in",
        "material":    "Stretched canvas · FSC slim wood frame",
        "price_usd":   90.0,   # prod $28.19 + ship $12.29 (US) / $19.46 (FR worst) · PayPal 2.9%+$0.30 → 30.1% margin worst-case
        "gelato_uid":  _CANVAS_16x20,
        "print_specs": _SPEC_CANVAS,
    },
    {
        "id":          "framed-poster",
        "label":       "Framed Poster",
        "size":        "16 × 20 in",
        "material":    "200gsm premium matte paper · black wood frame",
        "price_usd":   105.0,  # prod $44.15 + ship $18.99 (US) / $22.29 (EU worst) · PayPal 2.9%+$0.30 → 33.5% margin worst-case
        "gelato_uid":  _FRAMED_16x20,
        "print_specs": _SPEC_PRINT,
    },
    {
        "id":          "acrylic",
        "label":       "Acrylic Print",
        "size":        "16 × 20 in",
        "material":    "4mm crystal-clear acrylic · direct reverse print",
        "price_usd":   115.0,  # prod $42.43 + ship $21.02 (US) / $26.65 (FR worst) · PayPal 2.9%+$0.30 → 36.8% margin worst-case
        "gelato_uid":  _ACRYLIC_16x20,
        "print_specs": _SPEC_PRINT,
    },
    {
        "id":          "poster",
        "label":       "Art Print",
        "size":        "16 × 20 in",
        "material":    "200gsm premium matte paper · unframed",
        "price_usd":   35.0,   # prod $9.33 + ship $6.49 (US) / $10.51 (FR worst) · PayPal 2.9%+$0.30 → 39.6% margin worst-case
        "gelato_uid":  _POSTER_16x20,
        "print_specs": _SPEC_PRINT,
    },
    {
        "id":          "aluminum",
        "label":       "Aluminum Print",
        "size":        "16 × 20 in",
        "material":    "Metallic aluminum panel · 3mm thickness · brushed finish",
        "price_usd":   98.0,   # prod ~$38 + ship ~$15 (est.) → ~35% margin
        "gelato_uid":  _ALUMINUM_16x20,
        "print_specs": _SPEC_ALUMINUM,
    },
    {
        "id":          "postcard-set",
        "label":       "Postcard Set",
        "size":        "A5 (148 × 210 mm) · Set of 10",
        "material":    "300gsm glossy cardstock · 10 identical art cards",
        "price_usd":   32.0,   # prod ~$12 + ship ~$4 (est.) → ~45% margin
        "gelato_uid":  _POSTCARD_A5_SET10,
        "print_specs": _SPEC_POSTCARD,
    },
]

FORMATS_BY_ID: dict[str, dict] = {f["id"]: f for f in FORMATS}

# Legacy — kept for backwards compat with order creation
PRINT_SPECS: dict[str, dict] = {
    _CANVAS_16x20:    _SPEC_CANVAS,
    _FRAMED_16x20:    _SPEC_PRINT,
    _ACRYLIC_16x20:   _SPEC_PRINT,
    _POSTER_16x20:    _SPEC_PRINT,
    _ALUMINUM_16x20:  _SPEC_ALUMINUM,
    _POSTCARD_A5_SET10: _SPEC_POSTCARD,
}
PRODUCT_UIDS: dict[str, str] = {}  # not used directly anymore


async def create_order(order, shipping_address: dict):
    if not GELATO_API_KEY:
        return None

    from models.product import Product
    from database import SessionLocal
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == order.product_id).first()
        if not product:
            return None
        format_id   = getattr(order, "format_id", None) or "canvas"
        product_uid = FORMATS_BY_ID.get(format_id, FORMATS[0])["gelato_uid"]
        image_url   = f"https://mathrelaxing.store/api/render/print?product={product.slug}&format={format_id}"
    finally:
        db.close()

    payload = {
        "orderReferenceId": f"mathrelaxing-{order.id}",
        "customerReferenceId": order.customer_email or f"order-{order.id}",
        "currency": "USD",
        "items": [
            {
                "itemReferenceId": f"item-{order.id}",
                "productUid": product_uid,
                "files": [{"type": "default", "url": image_url}],
                "quantity": 1,
            }
        ],
        "shipmentMethodUid": "express",
        "shippingAddress": {
            "firstName": shipping_address.get("first_name", ""),
            "lastName":  shipping_address.get("last_name", ""),
            "addressLine1": shipping_address.get("address1", ""),
            "city":    shipping_address.get("city", ""),
            "postCode": shipping_address.get("zip", ""),
            "country": shipping_address.get("country", "US"),
            "email":   order.customer_email or "",
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/v3/orders",
            headers=HEADERS,
            json=payload,
            timeout=20,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            gelato_id = data.get("id", "")
            from database import SessionLocal
            db2 = SessionLocal()
            try:
                from sqlalchemy.orm import Session
                o = db2.query(type(order)).filter(type(order).id == order.id).first()
                if o:
                    o.gelato_order_id = gelato_id
                    o.status = "processing"
                    db2.commit()
            finally:
                db2.close()
            return gelato_id
    return None
