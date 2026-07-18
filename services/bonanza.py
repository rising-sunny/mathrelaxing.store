import json
import os
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any
from urllib.parse import urljoin

import httpx

DEV_ID = os.getenv("BONANZA_DEV_ID", "")
CERT_ID = os.getenv("BONANZA_CERT_ID", "")
TOKEN = os.getenv("BONANZA_TOKEN", "")
DIGITAL_ART_CATEGORY_ID = int(os.getenv("BONANZA_DIGITAL_ART_CATEGORY_ID", "999011"))
POD_MOUSE_PAD_CATEGORY_ID = int(os.getenv("BONANZA_POD_MOUSE_PAD_CATEGORY_ID", "23895"))
# Bonanza leaf category "Books & Magazines >> Books" (verified via getCategoriesRequest).
BOOK_CATEGORY_ID = int(os.getenv("BONANZA_BOOK_CATEGORY_ID", "261186"))
FEE_RATE = float(os.getenv("BONANZA_FEE_RATE", "0.11"))
TRANSACTION_FEE = float(os.getenv("BONANZA_TRANSACTION_FEE", "0.25"))

API_BASE = "https://api.bonanza.com/api_requests"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://mathrelaxing.store").rstrip("/")
PRODUCTS_FILE = "/var/www/mathrelaxing.store/.bonanza_products.json"
POD_PRODUCTS_FILE = "/var/www/mathrelaxing.store/.bonanza_pod_products.json"
FULFILLED_FILE = "/var/www/mathrelaxing.store/.bonanza_fulfilled.json"
STATIC_IMAGE_DIR = "/var/www/mathrelaxing.store/static/bonanza"


def is_configured() -> bool:
    return bool(DEV_ID and CERT_ID and TOKEN)


def _headers(secure: bool = True) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "MathRelaxingBonanza/1.0",
        "X-BONANZLE-API-DEV-NAME": DEV_ID,
    }
    if secure:
        headers["X-BONANZLE-API-CERT-NAME"] = CERT_ID
    return headers


def _credentials() -> dict[str, str]:
    return {"bonanzleAuthToken": TOKEN}


async def _request(name: str, payload: dict | None = None, secure: bool = True) -> dict[str, Any]:
    url = f"{API_BASE}/{'secure_request' if secure else 'standard_request'}"
    body = json.dumps({name: payload or {}})
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, content=body, headers=_headers(secure))
    if resp.status_code >= 400:
        raise RuntimeError(f"Bonanza HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    if data.get("ack") != "Success":
        raise RuntimeError(_error_text(data))
    return data


def _error_text(data: dict) -> str:
    err = data.get("errorMessage") or data
    try:
        return json.dumps(err)[:500]
    except Exception:
        return str(err)[:500]


def _load_map() -> dict[str, dict]:
    try:
        with open(PRODUCTS_FILE) as f:
            data = json.load(f)
    except Exception:
        return {}
    normalized = {}
    for slug, value in data.items():
        if isinstance(value, dict):
            normalized[slug] = value
        else:
            normalized[slug] = {"item_id": value}
    return normalized


def _save_map(data: dict[str, dict]) -> None:
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def _load_pod_map() -> dict[str, dict]:
    try:
        with open(POD_PRODUCTS_FILE) as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_pod_map(data: dict[str, dict]) -> None:
    with open(POD_PRODUCTS_FILE, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def _load_fulfilled() -> set[str]:
    try:
        with open(FULFILLED_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_fulfilled(ids: set[str]) -> None:
    with open(FULFILLED_FILE, "w") as f:
        json.dump(sorted(ids), f, indent=2)


def _absolute_url(path_or_url: str | None) -> str:
    if not path_or_url:
        return f"{PUBLIC_BASE_URL}/api/render/preview?product=lorenz-dream"
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return urljoin(f"{PUBLIC_BASE_URL}/", path_or_url.lstrip("/"))


def _listing_image_url(product) -> str:
    static_path = os.path.join(STATIC_IMAGE_DIR, f"{product.slug}.jpg")
    if os.path.exists(static_path):
        return f"{PUBLIC_BASE_URL}/static/bonanza/{product.slug}.jpg"
    return _absolute_url(getattr(product, "thumbnail_url", "") or getattr(product, "cover_image", ""))


def _safe_title(product) -> str:
    # Avoid "download" / "PDF" — Bonanza auto-mod flags those in listing text.
    base = _scrub_bonanza_text(product.name or "MathRelaxing Art")
    title = f"{base} | Digital Mathematical Art"
    return title[:80]


def price_for_product(product) -> float:
    base_price = float(product.price_usd)
    fee_rate = min(max(FEE_RATE, 0.0), 0.95)
    if fee_rate >= 0.95:
        return round(base_price, 2)
    gross_price = (base_price + max(TRANSACTION_FEE, 0.0)) / (1.0 - fee_rate)
    return int(gross_price * 100 + 0.9999) / 100


def _gross_up(amount: float, include_transaction_fee: bool = False) -> float:
    fee_rate = min(max(FEE_RATE, 0.0), 0.95)
    if fee_rate >= 0.95:
        return round(amount, 2)
    fee = max(TRANSACTION_FEE, 0.0) if include_transaction_fee else 0.0
    gross_price = (float(amount) + fee) / (1.0 - fee_rate)
    return int(gross_price * 100 + 0.9999) / 100


def price_for_pod_format(fmt: dict) -> float:
    # price_usd already includes US shipping (free-shipping model), so don't add
    # shipping again — just gross up for Bonanza fees. US ships free; the
    # international shipping option charges only the extra above US.
    base_price = float(fmt["price_usd"])
    return _gross_up(base_price, include_transaction_fee=True)


def international_shipping_for_pod_format(fmt: dict) -> float:
    diff = max(0.0, float(fmt.get("shipping_intl", 0.0)) - float(fmt.get("shipping_us", 0.0)))
    return _gross_up(diff, include_transaction_fee=False)


def _shipping_cost_for_pod(fmt: dict, country_code: str) -> float:
    from services.printful import shipping_cost
    return shipping_cost(country_code, fmt["id"])


def _bonanza_shipping_option(ship_to_location: str, extra_cost: float) -> dict[str, Any]:
    if extra_cost <= 0:
        return {
            "shippingType": "Free",
            "shipToLocation": ship_to_location,
        }
    return {
        "shippingType": "Fixed",
        "shippingServiceCost": _gross_up(extra_cost, include_transaction_fee=False),
        "shipToLocation": ship_to_location,
        "shippingService": "Other",
    }


def _pod_international_shipping_options(fmt: dict) -> list[dict[str, Any]]:
    us_cost = _shipping_cost_for_pod(fmt, "US")
    region_rates = [
        ("Canada", _shipping_cost_for_pod(fmt, "CA")),
        ("United Kingdom", _shipping_cost_for_pod(fmt, "GB")),
        ("Europe", max(_shipping_cost_for_pod(fmt, code) for code in ("DE", "FR", "ES", "NO", "CH"))),
        ("Australia", _shipping_cost_for_pod(fmt, "AU")),
        ("Japan", _shipping_cost_for_pod(fmt, "JP")),
        ("Mexico", _shipping_cost_for_pod(fmt, "MX")),
    ]
    return [
        _bonanza_shipping_option(location, max(0.0, cost - us_cost))
        for location, cost in region_rates
    ]


def fee_settings() -> dict[str, float]:
    return {
        "fee_rate": FEE_RATE,
        "transaction_fee": TRANSACTION_FEE,
    }


def _scrub_bonanza_text(text: str) -> str:
    """Remove phrases Bonanza's auto-mod flags as prohibited digital wording.

    Support (Kel, 2026-07): items flagged for the words "download link" and "pdf"
    in the description. We scrub those (case-insensitive) from titles/body copy
    sent to Bonanza only — site copy and fulfillment messages are unchanged.
    """
    import re

    if not text:
        return ""
    out = text
    # Order matters: longer phrases first
    patterns = [
        (r"\bdownload\s+links?\b", "access"),
        (r"\bsecure\s+download\b", "secure access"),
        (r"\binstant\s+download\b", "instant delivery"),
        (r"\bdigital\s+downloads?\b", "digital edition"),
        (r"\bdownloadable\b", "digital"),
        (r"\bdownloads?\b", "files"),
        (r"\bpdfs?\b", "document"),
        (r"\(\s*pdf\s*\)", ""),
        (r"\bPDF\b", "Document"),
    ]
    for pat, repl in patterns:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    # Collapse leftover double spaces / empty parens
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\(\s*\)", "", out)
    return out.strip(" -–—")


def _product_description(product) -> str:
    kind = (getattr(product, "product_type", "") or "image_pack").replace("_", " ")
    preview_url = f"{PUBLIC_BASE_URL}/bundle/{product.slug}"
    raw_desc = product.description or product.name or ""
    description = escape(_scrub_bonanza_text(raw_desc))
    name = escape(_scrub_bonanza_text(product.name or ""))
    kind_label = escape(_scrub_bonanza_text(kind))
    return f"""
<h2>{name}</h2>
<p>{description}</p>
<p><strong>Digital product only.</strong> No physical item will be shipped.</p>
<h3>What is included</h3>
<ul>
  <li>MathRelaxing {kind_label} — digital edition</li>
  <li>Original generative mathematical artwork created for MathRelaxing</li>
  <li>Personal and creator-friendly use; no resale of the raw files</li>
  <li>No watermark on delivered files</li>
</ul>
<h3>Delivery</h3>
<p>After Bonanza checkout is complete, we send secure access by Bonanza message and email within the stated handling timeframe, usually within minutes.</p>
<p>This listing complies with Bonanza digital goods rules: the content is original/authorized, non-adult, and does not require software to complete the purchase.</p>
<p>Preview and product details: <a href="{preview_url}">{preview_url}</a></p>
""".strip()


def _item_payload(product, allow_for_sale: bool = True) -> dict[str, Any]:
    return {
        "title": _safe_title(product),
        "primaryCategory": {"categoryId": DIGITAL_ART_CATEGORY_ID},
        "description": _product_description(product),
        "allowForSale": allow_for_sale,
        "externalProductId": f"mathrelaxing:{product.slug}",
        "obo": False,
        "price": price_for_product(product),
        "quantity": 999,
        "sku": f"mr-{product.slug}",
        "returnPolicy": {
            "returnsAcceptedOption": "ReturnsNotAccepted",
            "description": "Digital products are not returnable after delivery.",
        },
        "shippingDetails": {
            "shipsWithinDays": 1,
            "shippingServiceOptions": {
                "shippingType": "Free",
                "freeShipping": True,
            },
        },
        "itemSpecifics": {
            "discardOld": True,
            "specifics": [
                ["Format", "Digital Edition"],
                ["Type", getattr(product, "product_type", "Digital Art")],
                ["Subject", "Mathematical Art"],
                ["Brand", "MathRelaxing"],
            ],
        },
        "pictureDetails": {
            "discardOld": True,
            "pictureURL": [_listing_image_url(product)],
        },
    }


def _pod_key(slug: str, format_id: str) -> str:
    return f"{slug}:{format_id}"


def _safe_pod_title(product, fmt: dict) -> str:
    size = fmt.get("size", "")
    title = f"{product.name} | {fmt['label']} {size}".strip()
    return title[:80]


def _pod_image_urls(product, format_id: str) -> list[str]:
    key = f"{product.slug}-{format_id}"
    urls = []
    for suffix in ("", "-lifestyle", "-preview"):
        filename = f"{key}{suffix}.jpg"
        static_path = os.path.join(STATIC_IMAGE_DIR, "pod", filename)
        if os.path.exists(static_path):
            urls.append(f"{PUBLIC_BASE_URL}/static/bonanza/pod/{filename}")
    if not urls:
        urls.append(f"{PUBLIC_BASE_URL}/api/render/mockup?product={product.slug}&format={format_id}-flat")
    return urls[:4]


def _pod_product_description(product, fmt: dict) -> str:
    name = escape(product.name)
    product_url = f"{PUBLIC_BASE_URL}/product/{product.slug}"
    description = escape(product.description or product.name)
    return f"""
<h2>{name} — {escape(fmt["label"])}</h2>
<p>{description}</p>
<p><strong>Physical print-on-demand product.</strong> This is a finished physical item, not a digital download.</p>
<h3>Product details</h3>
<ul>
  <li>{escape(fmt["label"])} — {escape(fmt.get("size", ""))}</li>
  <li>{escape(fmt.get("material", ""))}</li>
  <li>Original MathRelaxing mathematical artwork printed edge-to-edge</li>
  <li>Made to order and fulfilled through Printful</li>
</ul>
<h3>Shipping and fulfillment</h3>
<ul>
  <li>US shipping is included in the Bonanza item price.</li>
  <li>Bonanza international shipping is currently configured for Canada, the United Kingdom, Europe, Australia, Japan, and Mexico.</li>
  <li>Production normally starts after payment is confirmed and usually takes 2-5 business days before shipment.</li>
</ul>
<h3>Returns</h3>
<p>Because this item is made to order, returns are accepted only for damaged, defective, or incorrect items. Please contact us promptly if there is a fulfillment issue.</p>
<p>More details and live preview: <a href="{product_url}">{product_url}</a></p>
""".strip()


# Competitive flat Bonanza prices for the desk-mat POD formats. These override
# the default margin-preserving gross-up (which lands too high vs the
# marketplace) while staying comfortably above the Printful cost+US-shipping
# floor:  gaming_mouse_pad cost $19.33+$11.99=$31.32 → $44.99 nets ~$8.5 US;
# mouse_pad cost $9.13+$4.49=$13.62 → $21.99 nets ~$5.7 US. International buyers
# still pay the shipping surcharge (_pod_international_shipping_options), so the
# margin holds abroad too.
POD_PRICE_OVERRIDE: dict[str, float] = {
    "gaming_mouse_pad": 44.99,
    "mouse_pad": 21.99,
    "spiral_notebook": 24.99,
}


def _pod_item_payload(product, fmt: dict, allow_for_sale: bool = True) -> dict[str, Any]:
    format_id = fmt["id"]
    if format_id == "gaming_mouse_pad":
        type_value = "Computer Desk Mat"
    elif format_id == "spiral_notebook":
        type_value = "Notebook"
    else:
        type_value = "Mouse Pad"
    shipping_details: dict[str, Any] = {
        "shipsWithinDays": 5,
        "shippingServiceOptions": {
            "shippingType": "Free",
            "freeShipping": True,
        },
        "internationalShippingServiceOption": _pod_international_shipping_options(fmt),
    }

    return {
        "title": _safe_pod_title(product, fmt),
        "primaryCategory": {"categoryId": POD_MOUSE_PAD_CATEGORY_ID},
        "description": _pod_product_description(product, fmt),
        "allowForSale": allow_for_sale,
        "externalProductId": f"mathrelaxing-pod:{product.slug}:{format_id}",
        "obo": False,
        "price": POD_PRICE_OVERRIDE.get(format_id, price_for_pod_format(fmt)),
        "quantity": 25,
        "sku": f"mr-pod-{product.slug}-{format_id}",
        "returnPolicy": {
            "returnsAcceptedOption": "ReturnsAccepted",
            "returnsWithinOption": 14,
            "shippingCostPaidByOption": "buyer",
            "description": "Made-to-order item. Returns accepted for damaged, defective, or incorrect items.",
        },
        "shippingDetails": shipping_details,
        "itemSpecifics": {
            "discardOld": True,
            "specifics": [
                ["Condition", "New"],
                ["Type", type_value],
                ["Theme", "Abstract"],
                ["Brand", "MathRelaxing"],
                ["Material", fmt.get("material", "")],
                ["Size", fmt.get("size", "")],
            ],
        },
        "pictureDetails": {
            "discardOld": True,
            "pictureURL": _pod_image_urls(product, format_id),
        },
    }


# ── Physical coloring book (Lulu-fulfilled) ───────────────────────────────────
BOOK_FORMAT_ID = "book"
# Lulu drop-ships the printed book to these markets only; shipping is free.
# International destinations advertised on the Bonanza listing.
#   - "Europe" covers Spain, France, Italy, Netherlands, etc. Bonanza's "Europe"
#     option EXCLUDES Germany at checkout (German packaging/LUCID rules), so DE
#     is not reachable here until we register LUCID.
#   - UK is separate from Bonanza's "Europe" (post-Brexit) and Australia is its
#     own region. US ships domestically (separate setting).
# Lulu fulfils all of Europe (see services/lulu.py BOOK_COUNTRIES).
BOOK_SHIP_COUNTRIES = ("United Kingdom", "Europe", "Australia")


def price_for_book(product) -> float:
    """Gross the retail price up so the Bonanza fee + transaction fee are covered
    and we still net the store price ($24.99)."""
    return _gross_up(float(product.price_usd), include_transaction_fee=True)


def _book_image_urls(product) -> list[str]:
    urls = []
    if getattr(product, "image_url", None):
        urls.append(_absolute_url(product.image_url))
    if product.slug == "sacred-harmonics-coloring-book":
        for filename in ("page_01_Sacred_Harmonics_colored.png", "page_02_Sacred_Harmonics_colored.png", "page_10_Sacred_Harmonics_colored.png", "page_12_Sacred_Harmonics_colored.png"):
            static_path = os.path.join("/var/www/mathrelaxing.store/static/downloads/chladni_book", filename)
            if os.path.exists(static_path):
                urls.append(f"{PUBLIC_BASE_URL}/static/downloads/chladni_book/{filename}")
    elif product.slug == "hyperbolic-gardens-coloring-book":
        for filename in ("hyp_sample_1.png", "hyp_sample_2.png", "hyp_sample_3.png", "hyp_sample_4.png"):
            static_path = os.path.join("/var/www/mathrelaxing.store/static/img", filename)
            if os.path.exists(static_path):
                urls.append(f"{PUBLIC_BASE_URL}/static/img/{filename}")
    else:
        for filename in ("cover.jpg", "page1.jpg", "page2.jpg", "page3.jpg", "page4.jpg"):
            static_path = os.path.join(STATIC_IMAGE_DIR, "book", filename)
            if os.path.exists(static_path):
                urls.append(f"{PUBLIC_BASE_URL}/static/bonanza/book/{filename}")
    if not urls:
        urls.append(_absolute_url(getattr(product, "image_url", "") or "/static/img/book_cover.png"))
    return urls[:4]


def _safe_book_title(product) -> str:
    title = f"{product.name} | 50 Math Curve Designs Adult Coloring"
    return title[:80]


def _book_description(product) -> str:
    name = escape(product.name)
    product_url = f"{PUBLIC_BASE_URL}/book/{product.slug}"
    description = escape(product.description or product.name)
    return f"""
<h2>{name}</h2>
<p>{description}</p>
<p><strong>Physical paperback book, printed on demand.</strong> This is a finished
printed coloring book, not a digital download.</p>
<h3>Book details</h3>
<ul>
  <li>Format: perfect-bound paperback</li>
  <li>Size: 8.5 x 11 in (US Letter)</li>
  <li>54 pages &mdash; 50 unique mathematical line-art designs</li>
  <li>Paper: 60# (90gsm) uncoated white &middot; matte cover</li>
  <li>Language: English</li>
</ul>
<h3>Shipping &amp; delivery</h3>
<ul>
  <li><strong>Free shipping.</strong></li>
  <li>Printed and shipped to order from a local print facility.</li>
  <li>Handling / production: about 3&ndash;5 business days before dispatch.</li>
</ul>
<p><strong>Estimated total delivery time (production + shipping):</strong></p>
<ul>
  <li>United States &mdash; 6&ndash;9 business days</li>
  <li>United Kingdom &mdash; 6&ndash;9 business days</li>
  <li>Europe (Spain, France, Italy, Netherlands, and more) &mdash; 7&ndash;13 business days</li>
  <li>Australia &mdash; 8&ndash;14 business days</li>
</ul>
<h3>Returns</h3>
<p>Because each book is made to order, returns are accepted only for damaged,
defective, or incorrect items. Please contact us promptly if there is a
fulfillment issue.</p>
<p>More details and a look inside: <a href="{product_url}">{product_url}</a></p>
""".strip()


def _book_shipping_details() -> dict[str, Any]:
    return {
        "shipsWithinDays": 5,
        "shippingServiceOptions": {
            "shippingType": "Free",
            "freeShipping": True,
        },
        "internationalShippingServiceOption": [
            {"shippingType": "Free", "shipToLocation": loc}
            for loc in BOOK_SHIP_COUNTRIES
        ],
    }


def _book_item_payload(product, allow_for_sale: bool = True) -> dict[str, Any]:
    return {
        "title": _safe_book_title(product),
        "primaryCategory": {"categoryId": BOOK_CATEGORY_ID},
        "description": _book_description(product),
        "allowForSale": allow_for_sale,
        "externalProductId": f"mathrelaxing-book:{product.slug}",
        "obo": False,
        "price": price_for_book(product),
        "quantity": 50,
        "sku": f"mr-book-{product.slug}",
        "returnPolicy": {
            "returnsAcceptedOption": "ReturnsAccepted",
            "returnsWithinOption": 14,
            "shippingCostPaidByOption": "buyer",
            "description": "Made-to-order book. Returns accepted for damaged, defective, or incorrect items.",
        },
        "shippingDetails": _book_shipping_details(),
        "itemSpecifics": {
            "discardOld": True,
            "specifics": [
                ["Condition", "New"],
                ["Format", "Paperback"],
                ["Language", "English"],
                ["Type", "Coloring Book"],
                ["Subject", "Art & Crafts"],
                ["Topic", "Adult Coloring / Mathematical Art"],
                ["Brand", "MathRelaxing"],
                ["Number of Pages", "54"],
                ["Size", "8.5 x 11 in"],
            ],
        },
        "pictureDetails": {
            "discardOld": True,
            "pictureURL": _book_image_urls(product),
        },
    }


async def publish_book(product) -> dict:
    """List (or revise) the physical coloring book on Bonanza. Stored in the POD
    map keyed `slug:book` with provider=lulu so the fulfillment poller routes new
    orders to Lulu (not Printful)."""
    mapping = _load_pod_map()
    key = _pod_key(product.slug, BOOK_FORMAT_ID)
    existing = mapping.get(key, {})
    item = _book_item_payload(product, allow_for_sale=True)

    if existing.get("item_id"):
        data = await _request("reviseFixedPriceItemRequest", {
            "requesterCredentials": _credentials(),
            "itemId": existing["item_id"],
            "item": item,
        })
        response = data.get("reviseFixedPriceItemResponse", {})
        item_id = existing["item_id"]
        category_id = response.get("categoryId", existing.get("category_id", BOOK_CATEGORY_ID))
        selling_state = response.get("sellingState", existing.get("selling_state", "unknown"))
    else:
        data = await _request("addFixedPriceItemRequest", {
            "requesterCredentials": _credentials(),
            "item": item,
        })
        response = data.get("addFixedPriceItemResponse", {})
        item_id = response.get("itemId")
        category_id = response.get("categoryId", BOOK_CATEGORY_ID)
        selling_state = response.get("sellingState", "unknown")

    if not item_id:
        raise RuntimeError(f"Bonanza did not return an item ID: {data}")

    listing_url = f"https://www.bonanza.com/items/{item_id}"
    mapping[key] = {
        "item_id": str(item_id),
        "slug": product.slug,
        "format_id": BOOK_FORMAT_ID,
        "provider": "lulu",
        "category_id": category_id,
        "selling_state": selling_state,
        "listing_url": listing_url,
        "price_usd": price_for_book(product),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_pod_map(mapping)
    return {
        "item_id": str(item_id),
        "category_id": category_id,
        "selling_state": selling_state,
        "listing_url": listing_url,
        "price_usd": price_for_book(product),
    }


async def get_token_status() -> dict:
    data = await _request("getTokenStatusRequest", {
        "requesterCredentials": _credentials(),
    })
    return data.get("getTokenStatusResponse", {})


async def publish_product(product) -> dict:
    mapping = _load_map()
    existing = mapping.get(product.slug, {})
    item = _item_payload(product, allow_for_sale=True)

    if existing.get("item_id"):
        data = await _request("reviseFixedPriceItemRequest", {
            "requesterCredentials": _credentials(),
            "itemId": existing["item_id"],
            "item": item,
        })
        response = data.get("reviseFixedPriceItemResponse", {})
        item_id = existing["item_id"]
        category_id = response.get("categoryId", existing.get("category_id", DIGITAL_ART_CATEGORY_ID))
        selling_state = response.get("sellingState", existing.get("selling_state", "unknown"))
    else:
        data = await _request("addFixedPriceItemRequest", {
            "requesterCredentials": _credentials(),
            "item": item,
        })
        response = data.get("addFixedPriceItemResponse", {})
        item_id = response.get("itemId")
        category_id = response.get("categoryId", DIGITAL_ART_CATEGORY_ID)
        selling_state = response.get("sellingState", "unknown")

    if not item_id:
        raise RuntimeError(f"Bonanza did not return an item ID: {data}")

    listing_url = f"https://www.bonanza.com/items/{item_id}"
    mapping[product.slug] = {
        "item_id": str(item_id),
        "category_id": category_id,
        "selling_state": selling_state,
        "listing_url": listing_url,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_map(mapping)
    return {
        "item_id": str(item_id),
        "category_id": category_id,
        "selling_state": selling_state,
        "listing_url": listing_url,
    }


async def publish_pod_product(product, format_id: str) -> dict:
    from services.printful import FORMATS_BY_ID

    fmt = FORMATS_BY_ID.get(format_id)
    if not fmt:
        raise RuntimeError(f"Unknown POD format: {format_id}")

    mapping = _load_pod_map()
    key = _pod_key(product.slug, format_id)
    existing = mapping.get(key, {})
    item = _pod_item_payload(product, fmt, allow_for_sale=True)

    if existing.get("item_id"):
        data = await _request("reviseFixedPriceItemRequest", {
            "requesterCredentials": _credentials(),
            "itemId": existing["item_id"],
            "item": item,
        })
        response = data.get("reviseFixedPriceItemResponse", {})
        item_id = existing["item_id"]
        category_id = response.get("categoryId", existing.get("category_id", POD_MOUSE_PAD_CATEGORY_ID))
        selling_state = response.get("sellingState", existing.get("selling_state", "unknown"))
    else:
        data = await _request("addFixedPriceItemRequest", {
            "requesterCredentials": _credentials(),
            "item": item,
        })
        response = data.get("addFixedPriceItemResponse", {})
        item_id = response.get("itemId")
        category_id = response.get("categoryId", POD_MOUSE_PAD_CATEGORY_ID)
        selling_state = response.get("sellingState", "unknown")

    if not item_id:
        raise RuntimeError(f"Bonanza did not return an item ID: {data}")

    listing_url = f"https://www.bonanza.com/items/{item_id}"
    mapping[key] = {
        "item_id": str(item_id),
        "slug": product.slug,
        "format_id": format_id,
        "category_id": category_id,
        "selling_state": selling_state,
        "listing_url": listing_url,
        "price_usd": price_for_pod_format(fmt),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_pod_map(mapping)
    return {
        "item_id": str(item_id),
        "category_id": category_id,
        "selling_state": selling_state,
        "listing_url": listing_url,
        "price_usd": price_for_pod_format(fmt),
    }


async def unpublish_product(product) -> None:
    mapping = _load_map()
    existing = mapping.get(product.slug)
    if not existing or not existing.get("item_id"):
        raise RuntimeError("Product is not listed on Bonanza")
    await _request("endFixedPriceItemRequest", {
        "requesterCredentials": _credentials(),
        "itemID": int(existing["item_id"]),
    })
    existing["selling_state"] = "ended"
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()
    mapping[product.slug] = existing
    _save_map(mapping)


async def get_listing_status(product) -> dict:
    mapping = _load_map()
    existing = mapping.get(product.slug)
    if not existing or not existing.get("item_id"):
        return {"status": "not_listed", "item_id": None}
    item_id = str(existing["item_id"])
    try:
        data = await _request("getUnlistedItemRequest", {
            "requesterCredentials": _credentials(),
            "itemId": item_id,
        })
        item = data.get("getUnlistedItemResponse", {}).get("item", {})
        state = item.get("listingStatus") or existing.get("selling_state") or "unknown"
        url = item.get("viewItemURL") or existing.get("listing_url") or f"https://www.bonanza.com/items/{item_id}"
        return {
            "status": _normalize_state(state),
            "item_id": item_id,
            "bonanza_url": url,
            "selling_state": state,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)[:160],
            "item_id": item_id,
            "bonanza_url": existing.get("listing_url", ""),
        }


def _normalize_state(state: str) -> str:
    value = (state or "").strip().lower().replace(" ", "_")
    if value in {"active", "ready_for_sale", "missing_required_fields", "requires_admin_review", "ended", "sold"}:
        return value
    return "unknown"


def _slug_for_item_id(item_id: str | int) -> str | None:
    target = str(item_id)
    for slug, data in _load_map().items():
        if str(data.get("item_id")) == target:
            return slug
    return None


def _pod_for_item_id(item_id: str | int) -> dict | None:
    target = str(item_id)
    for data in _load_pod_map().values():
        if str(data.get("item_id")) == target:
            return data
    return None


def _buyer_email_from_order(order: dict, buyer: str) -> str:
    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if "email" in str(key).lower() and item:
                    return str(item).strip().lower()
                found = walk(item)
                if found:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = walk(item)
                if found:
                    return found
        return ""

    return walk(order) or f"{buyer}@bonanza.local"


def _shipping_address_from_order(order: dict, buyer: str) -> dict:
    raw = order.get("shippingAddress") or {}
    name = str(raw.get("name") or buyer or "Bonanza buyer").strip()
    parts = name.split()
    first_name = parts[0] if parts else name
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    return {
        "first_name": first_name,
        "last_name": last_name,
        "name": name,
        "address1": raw.get("street1", ""),
        "address2": raw.get("street2", ""),
        "city": raw.get("cityName", ""),
        "state": raw.get("stateOrProvince", ""),
        "zip": raw.get("postalCode", ""),
        "country": raw.get("country", "US"),
    }


async def get_completed_orders(limit: int = 50) -> list[dict]:
    data = await _request("getOrdersRequest", {
        "requesterCredentials": _credentials(),
        "orderRole": "seller",
        "orderStatus": "Completed",
        "paginationInput": {"entriesPerPage": limit, "pageNumber": 1},
    })
    order_array = data.get("getOrdersResponse", {}).get("orderArray", {})
    # Bonanza returns orderArray as [] when empty, a list of orders when populated,
    # or a {"order": ...} wrapper (order may itself be a dict or a list).
    if isinstance(order_array, list):
        orders = order_array
    else:
        orders = order_array.get("order", [])
    if isinstance(orders, dict):
        return [orders]
    return orders or []


async def create_message(to_user: str, subject: str, body: str) -> dict:
    data = await _request("createMessageRequest", {
        "requesterCredentials": _credentials(),
        "to": to_user,
        "subject": subject[:120],
        "body": body,
    })
    return data.get("createMessageResponse", {})


async def complete_sale(
    order_id: str | int,
    notes: str,
    tracking_number: str | None = None,
    carrier: str | None = None,
) -> dict:
    data = await _request("completeSaleRequest", {
        "requesterCredentials": _credentials(),
        "transactionID": int(order_id),
        "shipped": True,
        "shipment": {
            "notes": notes[:500],
            "shippingCarrierUsed": carrier or "other",
            "shippingTrackingNumber": tracking_number or f"DIGITAL-{order_id}",
        },
    })
    return data.get("completeSaleResponse", {})


async def mark_physical_order_shipped(order, shipment: dict) -> dict | None:
    ref = getattr(order, "lemon_order_id", "") or ""
    if not ref.startswith("bonanza_pod_"):
        return None
    parts = ref.split("_")
    if len(parts) < 4:
        return None
    bonanza_order_id = parts[2]
    tracking = str(shipment.get("tracking_number") or shipment.get("trackingNumber") or "")
    carrier = str(shipment.get("carrier") or shipment.get("service") or "other")
    notes = f"Printful shipped MathRelaxing order #{order.id}."
    return await complete_sale(bonanza_order_id, notes, tracking_number=tracking, carrier=carrier)


async def fulfill_new_orders(db) -> list[dict]:
    from models.product import DigitalProduct, Order, Product, Purchase
    from services import lulu, printful, telegram

    fulfilled = _load_fulfilled()
    orders = await get_completed_orders()
    results = []

    for order in orders:
        order_id = str(order.get("orderID", ""))
        if not order_id or order_id in fulfilled:
            continue

        buyer = str(order.get("buyerUserName") or "Bonanza buyer")
        item_container = (order.get("itemArray") or {}).get("item", [])
        items = [item_container] if isinstance(item_container, dict) else (item_container or [])
        links = []
        physical_orders = []
        physical_failures = []

        for item in items:
            item_id = item.get("parentItemID") or item.get("itemID")
            slug = _slug_for_item_id(item_id)
            if slug:
                product = db.query(DigitalProduct).filter(DigitalProduct.slug == slug).first()
                if not product:
                    continue

                purchase_key = f"bonanza_{order_id}_{item_id}"
                purchase = db.query(Purchase).filter(Purchase.lemon_order_id == purchase_key).first()
                if purchase:
                    links.append((product.name, f"{PUBLIC_BASE_URL}/download/{purchase.download_token}"))
                    continue

                purchase = Purchase(
                    lemon_order_id=purchase_key,
                    product_id=product.id,
                    customer_email=_buyer_email_from_order(order, buyer),
                    customer_name=buyer,
                    status="paid",
                    ref_source="bonanza",
                    item_index=None,
                    max_downloads=5,
                    expires_at=datetime.utcnow() + timedelta(days=30),
                )
                db.add(purchase)
                db.commit()
                db.refresh(purchase)
                links.append((product.name, f"{PUBLIC_BASE_URL}/download/{purchase.download_token}"))
                try:
                    await telegram.notify_new_digital_purchase(purchase, product)
                except Exception:
                    pass
                continue

            pod = _pod_for_item_id(item_id)
            if not pod:
                continue
            product = db.query(Product).filter(Product.slug == pod.get("slug")).first()
            if not product:
                continue

            fmt_id = pod.get("format_id") or "poster"
            provider_name = pod.get("provider") or ("lulu" if fmt_id == BOOK_FORMAT_ID else "printful")
            quantity = max(1, int(item.get("quantity") or 1))
            shipping_address = _shipping_address_from_order(order, buyer)
            customer_email = _buyer_email_from_order(order, buyer)
            customer_name = shipping_address.get("name") or buyer

            for index in range(quantity):
                suffix = "" if quantity == 1 else f"_{index + 1}"
                order_key = f"bonanza_pod_{order_id}_{item_id}{suffix}"
                physical_order = db.query(Order).filter(Order.lemon_order_id == order_key).first()
                if physical_order and physical_order.printful_order_id:
                    physical_orders.append(physical_order)
                    continue
                if not physical_order:
                    physical_order = Order(
                        lemon_order_id=order_key,
                        product_id=product.id,
                        product_slug=product.slug,
                        params_json=product.params_json,
                        format_id=fmt_id,
                        customer_email=customer_email,
                        customer_name=customer_name,
                        shipping_address=json.dumps(shipping_address),
                        status="paid",
                    )
                    db.add(physical_order)
                    db.commit()
                    db.refresh(physical_order)
                    try:
                        await telegram.notify_new_physical_order(physical_order)
                    except Exception:
                        pass

                if provider_name == "lulu":
                    # lulu.create_order sets printful_order_id ("lulu:<job>") and
                    # status in its own DB session, so refresh to observe it here.
                    job_id = await lulu.create_order(physical_order, shipping_address)
                    db.refresh(physical_order)
                    if job_id and physical_order.printful_order_id:
                        physical_orders.append(physical_order)
                    else:
                        physical_failures.append(physical_order.id)
                else:
                    pf_id = await printful.create_order(physical_order, shipping_address)
                    if pf_id:
                        physical_order.printful_order_id = pf_id
                        physical_order.status = "processing"
                        db.commit()
                        physical_orders.append(physical_order)
                    else:
                        physical_failures.append(physical_order.id)

        if not links and not physical_orders and not physical_failures:
            continue

        if links:
            body_lines = [
                f"Hi {buyer},",
                "",
                "Thanks for your MathRelaxing purchase. Your digital downloads are ready:",
                "",
            ]
            body_lines.extend(f"- {name}: {url}" for name, url in links)
            body_lines.extend([
                "",
                "No physical item will be shipped for digital downloads. The secure links expire in 30 days.",
                "If you need help, reply here on Bonanza.",
            ])
            await create_message(buyer, "Your MathRelaxing digital download is ready", "\n".join(body_lines))

        if physical_orders:
            body_lines = [
                f"Hi {buyer},",
                "",
                "Thanks for your MathRelaxing physical product order. It has been sent to production with our print-on-demand partner.",
                "",
                "We will update the Bonanza order with tracking when it ships.",
                "If you need help, reply here on Bonanza.",
            ]
            await create_message(buyer, "Your MathRelaxing POD order is in production", "\n".join(body_lines))

        if links and not physical_orders:
            await complete_sale(order_id, "Digital download delivered by Bonanza message.")

        if not physical_failures:
            fulfilled.add(order_id)
        results.append({
            "order_id": order_id,
            "buyer": buyer,
            "digital_items": len(links),
            "physical_items": len(physical_orders),
            "physical_failures": len(physical_failures),
        })

        try:
            await telegram.send_message(
                "Bonanza sale processed\n"
                f"Order: {order_id}\n"
                f"Buyer: {buyer}\n"
                f"Digital items: {len(links)}\n"
                f"Physical items: {len(physical_orders)}\n"
                f"Physical failures: {len(physical_failures)}"
            )
        except Exception:
            pass

    _save_fulfilled(fulfilled)
    return results
