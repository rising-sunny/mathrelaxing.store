"""
eBay Sell API service — token management, listings, orders, fulfillment.
"""
import base64
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

CLIENT_ID     = os.getenv("EBAY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET", "")
REFRESH_TOKEN = os.getenv("EBAY_REFRESH_TOKEN", "")

API_BASE      = "https://api.ebay.com"
TOKEN_FILE    = "/var/www/mathrelaxing.store/.ebay_token.json"
FULFILLED_FILE = "/var/www/mathrelaxing.store/.ebay_fulfilled.json"
PUBLIC_BASE   = os.getenv("PUBLIC_BASE_URL", "https://mathrelaxing.store").rstrip("/")
STORE_ROOT    = os.getenv("STORE_ROOT", "/var/www/mathrelaxing.store")

MARKETPLACE_ID = "EBAY_US"
CURRENCY       = "USD"

# eBay category: Art > Art Prints (leaf; works for digital wall-art packs)
DIGITAL_CATEGORY_ID = "360"

# eBay selling-limit quantity is SHARED across the whole account (e.g. 70).
# Always keep per-SKU qty at 1 so we can list many digital products without
# burning the quota. Do NOT raise this without checking
# GET /sell/account/v1/privilege → sellingLimit.quantity first.
# After a sale, restock carefully (still 1) only if headroom remains.
LISTING_QUANTITY = max(1, min(int(os.getenv("EBAY_LISTING_QUANTITY", "1")), 1))

# US managed-payments FVF for most categories (no eBay Store discount assumed).
# Final value fee is a % of the total sale + a flat per-order fee.
# Ref: ebay.com/help selling fees — most categories 13.6% + $0.30 (≤$10) / $0.40 (>$10).
FEE_RATE = float(os.getenv("EBAY_FEE_RATE", "0.136"))
ORDER_FEE_LOW = float(os.getenv("EBAY_ORDER_FEE_LOW", "0.30"))
ORDER_FEE_HIGH = float(os.getenv("EBAY_ORDER_FEE_HIGH", "0.40"))

SCOPES = " ".join([
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.marketing",
])


# ── Token management ─────────────────────────────────────────────────────────

def _load_cached_token() -> dict | None:
    try:
        with open(TOKEN_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def _save_token(data: dict) -> None:
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)


async def get_access_token() -> str:
    cached = _load_cached_token()
    if cached and cached.get("expires_at", 0) > time.time() + 60:
        return cached["access_token"]

    creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{API_BASE}/identity/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": REFRESH_TOKEN,
                "scope": SCOPES,
            },
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"eBay token refresh failed: {resp.text}")

    data = resp.json()
    data["expires_at"] = time.time() + data.get("expires_in", 7200) - 120
    _save_token(data)
    return data["access_token"]


def is_configured() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN)


# ── Generic REST helpers ──────────────────────────────────────────────────────

async def _get(path: str, params: dict | None = None) -> Any:
    token = await get_access_token()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            params=params or {},
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"eBay GET {path} failed ({resp.status_code}): {resp.text}")
    return resp.json() if resp.text else {}


async def _post(path: str, body: dict) -> Any:
    token = await get_access_token()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Content-Language": "en-US",
            },
            json=body,
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"eBay POST {path} failed ({resp.status_code}): {resp.text}")
    return resp.json() if resp.text else {}


async def _put(path: str, body: dict) -> Any:
    token = await get_access_token()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(
            f"{API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Content-Language": "en-US",
            },
            json=body,
        )
    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(f"eBay PUT {path} failed ({resp.status_code}): {resp.text}")
    return resp.json() if resp.text else {}


async def _delete(path: str) -> None:
    token = await get_access_token()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(
            f"{API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"eBay DELETE {path} failed ({resp.status_code}): {resp.text}")


# ── Seller policies ───────────────────────────────────────────────────────────

async def get_or_create_policies() -> dict[str, str]:
    """Return fulfillment, payment, and return policy IDs, creating them if missing."""

    # Fulfillment policy — digital delivery, free
    try:
        fp = await _get("/sell/account/v1/fulfillment_policy", {"marketplace_id": MARKETPLACE_ID})
        fulfillment_id = next(
            (p["fulfillmentPolicyId"] for p in fp.get("fulfillmentPolicies", [])
             if "digital" in p.get("name", "").lower() or p.get("freightShipping") or
             all(s.get("shippingCostType") == "NOT_SPECIFIED" for s in p.get("shippingOptions", []))),
            None,
        )
    except Exception:
        fulfillment_id = None

    if not fulfillment_id:
        try:
            r = await _post("/sell/account/v1/fulfillment_policy", {
                "name": "Digital Delivery - Free",
                "description": "Instant digital delivery via email",
                "marketplaceId": MARKETPLACE_ID,
                "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                "handlingTime": {"value": 1, "unit": "DAY"},
                "shippingOptions": [],
                "globalShipping": False,
                "freightShipping": False,
                "pickupDropOff": False,
                "localPickup": False,
            })
            fulfillment_id = r.get("fulfillmentPolicyId")
        except Exception as e:
            # Use first available policy
            fp = await _get("/sell/account/v1/fulfillment_policy", {"marketplace_id": MARKETPLACE_ID})
            policies = fp.get("fulfillmentPolicies", [])
            fulfillment_id = policies[0]["fulfillmentPolicyId"] if policies else None

    # Payment policy
    try:
        pp = await _get("/sell/account/v1/payment_policy", {"marketplace_id": MARKETPLACE_ID})
        payment_id = next(
            (p["paymentPolicyId"] for p in pp.get("paymentPolicies", [])), None
        )
    except Exception:
        payment_id = None

    if not payment_id:
        r = await _post("/sell/account/v1/payment_policy", {
            "name": "Immediate Payment",
            "marketplaceId": MARKETPLACE_ID,
            "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
            "immediatePay": True,
            "paymentMethods": [{"paymentMethodType": "PAYPAL",
                                "recipientAccountReference": {"referenceType": "PAYPAL_EMAIL",
                                                               "referenceId": "orders@mathrelaxing.store"}}],
        })
        payment_id = r.get("paymentPolicyId")

    # Return policy — no returns for digital
    try:
        rp = await _get("/sell/account/v1/return_policy", {"marketplace_id": MARKETPLACE_ID})
        return_id = next(
            (p["returnPolicyId"] for p in rp.get("returnPolicies", [])), None
        )
    except Exception:
        return_id = None

    if not return_id:
        r = await _post("/sell/account/v1/return_policy", {
            "name": "No Returns - Digital",
            "marketplaceId": MARKETPLACE_ID,
            "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
            "returnsAccepted": False,
        })
        return_id = r.get("returnPolicyId")

    return {
        "fulfillment_policy_id": fulfillment_id,
        "payment_policy_id": payment_id,
        "return_policy_id": return_id,
    }


# ── Inventory & listings ──────────────────────────────────────────────────────

def _product_description(product) -> str:
    ptype = getattr(product, "product_type", "image_pack") or "image_pack"
    is_loop = "loop" in ptype or "animation" in ptype
    kind = "HD loop animations" if is_loop else "high-resolution digital images"
    return f"""<div>
<h2>{product.name}</h2>
<p>{product.description or ''}</p>
<h3>What you get</h3>
<ul>
<li>Instant digital download delivered to your email</li>
<li>Pack of {kind}</li>
<li>Commercial license included — use in videos, prints, reels, and more</li>
<li>No watermark · No DRM</li>
</ul>
<h3>Delivery</h3>
<p>After payment, you will receive a download link by eBay message within minutes.
All files are delivered digitally — no physical item ships.</p>
<p>Questions? Contact us via eBay message — we respond within a few hours.</p>
<p style="font-size:0.85em;color:#666;">⚠ DIGITAL DOWNLOAD — No physical item. Files delivered by email.</p>
</div>"""


def price_for_product(product) -> float:
    """
    Gross up DigitalProduct.price_usd so that after eBay final-value fee
    (+ per-order fee) we still net approximately the catalog price.

        list ≈ (base + order_fee) / (1 - fee_rate)
    """
    import math

    base = float(getattr(product, "price_usd", 0) or 0)
    if base <= 0:
        return 0.0
    rate = min(max(FEE_RATE, 0.0), 0.95)
    p = (base + ORDER_FEE_LOW) / (1.0 - rate)
    p = math.ceil(p * 100 - 1e-9) / 100
    order_fee = ORDER_FEE_LOW if p <= 10 else ORDER_FEE_HIGH
    if order_fee != ORDER_FEE_LOW:
        p = (base + order_fee) / (1.0 - rate)
        p = math.ceil(p * 100 - 1e-9) / 100
    # Prefer a clean .99 retail ending when we're within ~20¢ of one
    if p < 10:
        dollars = int(p)
        candidate = dollars + 0.99
        if candidate >= p and candidate - p <= 0.20:
            p = candidate
        elif candidate < p:
            candidate = dollars + 1.99
            if candidate - p <= 0.20:
                p = candidate
    return round(p, 2)


def net_after_fees(list_price: float) -> float:
    of = ORDER_FEE_LOW if list_price <= 10 else ORDER_FEE_HIGH
    return round(float(list_price) - float(list_price) * FEE_RATE - of, 2)


def _listing_image_urls(product) -> list[str]:
    """
    Collect multiple gallery images for eBay (hero + cover + per-design previews).
    eBay inventory accepts several imageUrls; more previews convert better than a single tile.
    """
    from pathlib import Path

    root = Path(STORE_ROOT)
    urls: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        if url and url not in seen:
            seen.add(url)
            urls.append(url)

    def add_file(path: Path) -> None:
        if path.is_file() and path.stat().st_size > 2000:
            rel = path.relative_to(root).as_posix()
            add(f"{PUBLIC_BASE}/{rel}")

    # Heroes / composites first
    for rel in (
        f"static/bonanza/{product.slug}.jpg",
        f"static/previews/{product.slug}.jpg",
        f"static/img/{product.slug}_cover.jpg",
        f"static/previews/{product.slug}_clean.jpg",
    ):
        add_file(root / rel)

    for attr in ("cover_image", "thumbnail_url"):
        val = (getattr(product, attr, None) or "").split("?", 1)[0]
        if val.startswith("/static/"):
            add_file(root / val.lstrip("/"))
        elif val.startswith(PUBLIC_BASE):
            add(val)

    # Numbered page previews: static/previews/{slug}_0.jpg, _0_clean.jpg, _1.jpg, …
    prev_dir = root / "static" / "previews"
    if prev_dir.is_dir():
        numbered: dict[str, Path] = {}
        for p in sorted(prev_dir.glob(f"{product.slug}_*")):
            if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            stem = p.stem
            if stem in (product.slug, f"{product.slug}_clean"):
                continue
            key = stem.replace("_clean", "")
            # prefer *_clean variants
            if key not in numbered or "_clean" in stem:
                numbered[key] = p
        for key in sorted(numbered.keys()):
            add_file(numbered[key])
            if len(urls) >= 12:
                break

    # Extracted / rendered gallery (static/ebay/{slug}/)
    gallery = root / "static" / "ebay" / product.slug
    if gallery.is_dir():
        for p in sorted(gallery.glob("*.jpg")) + sorted(gallery.glob("*.png")):
            add_file(p)
            if len(urls) >= 12:
                break

    if not urls:
        add(f"{PUBLIC_BASE}/api/render/preview?product={product.slug}")
    return urls[:12]


def _listing_image_url(product) -> str:
    """Back-compat single image (first gallery URL)."""
    return _listing_image_urls(product)[0]


def _safe_title(product) -> str:
    title = f"{product.name} — Digital Download | Math Art"
    return title[:80]


async def upsert_inventory_item(product, policies: dict) -> None:
    sku = f"mr-{product.slug}"
    ptype = getattr(product, "product_type", "image_pack") or "image_pack"
    is_loop = "loop" in ptype or "animation" in ptype
    condition = "NEW"
    aspects = {
        "Format": ["Digital Download"],
        "File Type": ["JPG/MP4"] if is_loop else ["PDF/ZIP/JPG"],
        "Subject": ["Mathematical Art", "Abstract"],
        "Style": ["Abstract", "Digital Art"],
    }
    qty = _sku_quantity()  # always 1 under selling-limit protection
    images = _listing_image_urls(product)

    await _put(f"/sell/inventory/v1/inventory_item/{sku}", {
        "product": {
            "title": _safe_title(product),
            "description": _product_description(product),
            "aspects": aspects,
            "imageUrls": images,
        },
        "condition": condition,
        "availability": {
            "shipToLocationAvailability": {
                "quantity": qty,
            }
        },
    })


def _sku_quantity() -> int:
    """Per-SKU available quantity — hard-capped at 1 for selling-limit safety."""
    return 1


async def get_selling_limits() -> dict:
    """Account-level selling limits (quantity + GMV)."""
    try:
        priv = await _get("/sell/account/v1/privilege")
        lim = priv.get("sellingLimit") or {}
        amt = lim.get("amount") or {}
        return {
            "max_quantity": lim.get("quantity"),
            "max_amount": amt.get("value"),
            "currency": amt.get("currency"),
            "registration_completed": priv.get("sellerRegistrationCompleted"),
        }
    except Exception as e:
        return {"error": str(e)[:200]}


async def create_offer(product, policies: dict) -> str:
    sku = f"mr-{product.slug}"
    price_str = f"{price_for_product(product):.2f}"
    qty = _sku_quantity()
    body = {
        "sku": sku,
        "marketplaceId": MARKETPLACE_ID,
        "format": "FIXED_PRICE",
        "availableQuantity": qty,
        "categoryId": DIGITAL_CATEGORY_ID,
        "listingDescription": _product_description(product),
        "listingPolicies": {
            "fulfillmentPolicyId": policies["fulfillment_policy_id"],
            "paymentPolicyId": policies["payment_policy_id"],
            "returnPolicyId": policies["return_policy_id"],
        },
        "pricingSummary": {
            "price": {"value": price_str, "currency": CURRENCY},
        },
        "merchantLocationKey": os.getenv("EBAY_MERCHANT_LOCATION_KEY", "default_location"),
        "includeCatalogProductDetails": False,
    }
    r = await _post("/sell/inventory/v1/offer", body)
    return r.get("offerId", "")


async def get_offers_for_sku(sku: str) -> list[dict]:
    try:
        r = await _get("/sell/inventory/v1/offer", {"sku": sku})
        return r.get("offers", [])
    except Exception:
        return []


async def publish_offer(offer_id: str) -> str:
    r = await _post(f"/sell/inventory/v1/offer/{offer_id}/publish", {})
    return r.get("listingId", "")


async def withdraw_offer(offer_id: str) -> None:
    await _post(f"/sell/inventory/v1/offer/{offer_id}/withdraw", {})


async def publish_product(product) -> dict:
    """Full flow: upsert inventory item → create/find offer → publish. Returns status dict."""
    policies = await get_or_create_policies()
    await upsert_inventory_item(product, policies)

    sku = f"mr-{product.slug}"
    list_price = price_for_product(product)
    price_str = f"{list_price:.2f}"
    qty = _sku_quantity()
    offers = await get_offers_for_sku(sku)

    if offers:
        offer_id = offers[0]["offerId"]
        listing_id = offers[0].get("listingId") or offers[0].get("listing", {}).get("listingId")
        status = offers[0].get("status", "")
        # Keep price/qty/policies in sync with catalog (fee-aware list price)
        try:
            await _put(
                f"/sell/inventory/v1/offer/{offer_id}",
                {
                    "availableQuantity": qty,
                    "categoryId": DIGITAL_CATEGORY_ID,
                    "listingDescription": _product_description(product),
                    "listingPolicies": {
                        "fulfillmentPolicyId": policies["fulfillment_policy_id"],
                        "paymentPolicyId": policies["payment_policy_id"],
                        "returnPolicyId": policies["return_policy_id"],
                    },
                    "pricingSummary": {
                        "price": {"value": price_str, "currency": CURRENCY},
                    },
                    "merchantLocationKey": os.getenv(
                        "EBAY_MERCHANT_LOCATION_KEY", "default_location"
                    ),
                    "marketplaceId": MARKETPLACE_ID,
                    "format": "FIXED_PRICE",
                },
            )
        except Exception as e:
            print(f"[ebay] offer update warn for {sku}: {e}", flush=True)
        if status != "PUBLISHED":
            listing_id = await publish_offer(offer_id)
    else:
        offer_id = await create_offer(product, policies)
        listing_id = await publish_offer(offer_id)

    return {
        "offer_id": offer_id,
        "listing_id": listing_id,
        "list_price": list_price,
        "base_price": float(getattr(product, "price_usd", 0) or 0),
        "est_net": net_after_fees(list_price),
        "images": len(_listing_image_urls(product)),
    }


async def unpublish_product(product) -> None:
    sku = f"mr-{product.slug}"
    offers = await get_offers_for_sku(sku)
    for offer in offers:
        if offer.get("status") == "PUBLISHED":
            await withdraw_offer(offer["offerId"])


async def get_listing_status(product) -> dict:
    sku = f"mr-{product.slug}"
    offers = await get_offers_for_sku(sku)
    if not offers:
        return {"status": "not_listed", "offer_id": None, "listing_id": None}
    offer = offers[0]
    return {
        "status": offer.get("status", "UNKNOWN").lower(),
        "offer_id": offer.get("offerId"),
        "listing_id": offer.get("listingId") or offer.get("listing", {}).get("listingId"),
        "price": offer.get("pricingSummary", {}).get("price", {}).get("value"),
    }


# ── Orders & fulfillment ──────────────────────────────────────────────────────

def _load_fulfilled() -> set[str]:
    try:
        with open(FULFILLED_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_fulfilled(ids: set[str]) -> None:
    with open(FULFILLED_FILE, "w") as f:
        json.dump(list(ids), f)


async def get_orders(limit: int = 20) -> list[dict]:
    try:
        r = await _get("/sell/fulfillment/v1/order", {
            "limit": limit,
            "filter": "orderfulfillmentstatus:{NOT_STARTED|IN_PROGRESS}",
        })
        return r.get("orders", [])
    except Exception:
        return []


async def get_recent_orders(limit: int = 20) -> list[dict]:
    try:
        r = await _get("/sell/fulfillment/v1/order", {"limit": limit})
        return r.get("orders", [])
    except Exception:
        return []


async def mark_order_shipped(order_id: str, line_item_ids: list[str]) -> bool:
    try:
        fulfillment_id = str(uuid.uuid4())[:8].upper()
        await _post(
            f"/sell/fulfillment/v1/order/{order_id}/shipping_fulfillment",
            {
                "lineItems": [{"lineItemId": lid, "quantity": 1} for lid in line_item_ids],
                "shippedDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "shippingCarrierCode": "OTHER",
                "trackingNumber": f"DIGITAL-{fulfillment_id}",
            },
        )
        return True
    except Exception as e:
        print(f"[ebay] mark_shipped failed for {order_id}: {e}", flush=True)
        return False


async def fulfill_new_orders(db) -> list[dict]:
    """
    Poll unfulfilled eBay orders, send download emails, mark shipped.
    Returns list of fulfilled order summaries.
    """
    from models.product import DigitalProduct, Purchase
    from services import email as email_svc
    from services import telegram

    fulfilled_ids = _load_fulfilled()
    orders = await get_orders(limit=50)
    results = []

    for order in orders:
        order_id = order.get("orderId", "")
        if order_id in fulfilled_ids:
            continue

        buyer_email = order.get("buyer", {}).get("username", "") + "@members.ebay.com"
        buyer_name = order.get("buyer", {}).get("username", "eBay Customer")

        line_items = order.get("lineItems", [])
        line_item_ids = []

        for item in line_items:
            line_item_ids.append(item.get("lineItemId", ""))
            sku = item.get("sku", "")
            slug = sku.replace("mr-", "") if sku.startswith("mr-") else sku

            product = db.query(DigitalProduct).filter(DigitalProduct.slug == slug).first()
            if not product:
                continue

            # Create purchase record
            purchase = Purchase(
                lemon_order_id=f"ebay_{order_id}_{item.get('lineItemId','')}",
                product_id=product.id,
                customer_email=buyer_email,
                customer_name=buyer_name,
                status="paid",
                ref_source="ebay",
                max_downloads=5,
            )
            db.add(purchase)
            db.commit()
            db.refresh(purchase)

            # Send download email
            try:
                await email_svc.send_digital_purchase_email(purchase, product)
            except Exception as e:
                print(f"[ebay] email failed for {order_id}: {e}", flush=True)

        # Mark shipped on eBay
        if line_item_ids:
            await mark_order_shipped(order_id, line_item_ids)

        fulfilled_ids.add(order_id)
        results.append({
            "order_id": order_id,
            "buyer": buyer_name,
            "items": len(line_items),
        })

        try:
            await telegram.send_message(
                f"🛒 eBay sale fulfilled!\n"
                f"Order: {order_id}\nBuyer: {buyer_name}\nItems: {len(line_items)}"
            )
        except Exception:
            pass

    _save_fulfilled(fulfilled_ids)
    return results
