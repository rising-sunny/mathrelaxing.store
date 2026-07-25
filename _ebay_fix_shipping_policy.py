"""
Align eBay fulfillment policies with Printify / Lulu delivery reality.

Printify (posters blueprint 282 / stickers 400, provider 99):
  - handling_time from API: 10 days (production)
  - US transit (shop blurb): ~2–5 business days
  - CA/INTL transit (shop blurb): ~10–30 business days

Lulu printed books (services/lulu.py DELIVERY_ESTIMATES, total incl. production):
  - US/GB: 6–9 business days total
  - EU: ~7–13
  - AU/default: 8–14
  → handling ~5 days + economy transit is a reasonable eBay split

Also refresh listing descriptions on physical SKUs with matching copy.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path("/var/www/mathrelaxing.store")
load_dotenv(ROOT / ".env")
os.chdir(ROOT)

import services.ebay as ebay  # noqa: E402

MARKETPLACE = "EBAY_US"

# SKUs → which policy
PRINTIFY_SKUS = [
    "mr-phys-penrose-poster-18x24",
    "mr-phys-euler-poster-18x24",
    "mr-phys-golden-ratio-sticker-4x4",
]
LULU_SKUS = [
    "mr-phys-fractal-flora-book",
]

PRINTIFY_POLICY_NAME = "Printify POD Free Ship — 10d production"
LULU_POLICY_NAME = "Lulu Book Free Ship — 5d production"

# Descriptions: production + transit by region (business days)
PRINTIFY_SHIP_HTML = """
<div>
{body}
<h3>Shipping &amp; production (Printify print-on-demand)</h3>
<ul>
<li><b>Production / processing:</b> about <b>7–10 business days</b> after your order (Printify handling time: up to 10 days).</li>
<li><b>United States — transit after production:</b> about <b>2–5 business days</b>.</li>
<li><b>Canada &amp; international — transit after production:</b> about <b>10–30 business days</b> (customs may add time).</li>
</ul>
<p><b>Typical total:</b> US ~1–2 weeks; international often 3–5+ weeks. Tracking is provided when the print partner ships. This is a <b>physical product</b> — no digital file is included.</p>
</div>
""".strip()

LULU_SHIP_HTML = """
<div>
{body}
<h3>Shipping &amp; production (printed book)</h3>
<ul>
<li><b>Production:</b> typically about <b>3–5 business days</b>.</li>
<li><b>United States &amp; UK — total delivery:</b> about <b>6–9 business days</b>.</li>
<li><b>Europe — total delivery:</b> about <b>7–13 business days</b>.</li>
<li><b>Australia &amp; other markets we ship to:</b> about <b>8–14 business days</b>.</li>
</ul>
<p>Free shipping. Tracking when available. This is a <b>physical paperback</b> — no digital PDF/download is included with this listing.</p>
</div>
""".strip()

# Keep the unique product intro (first paragraphs) without old shipping section
PRODUCT_INTROS = {
    "mr-phys-penrose-poster-18x24": """
<h2>Penrose Tiling Poster — Geometric Math Line Art</h2>
<p>An aperiodic Penrose tiling — a pattern of two rhombi that fills the plane and never exactly repeats, built on the golden ratio. Clean black-and-white line art on a warm ivory ground. Part of the Geometric Tilings series.</p>
<ul>
<li><b>Physical printed poster</b> — ships to your door (not a download)</li>
<li>Size: <b>18 × 24 inches</b></li>
<li>Matte poster paper, giclée-quality print on demand</li>
<li>Charcoal line work · frame not included</li>
</ul>
<p>MathRelaxing — mathematics as wall art.</p>
""".strip(),
    "mr-phys-euler-poster-18x24": """
<h2>Euler's Identity Poster — The Most Beautiful Equation</h2>
<p>Euler's identity on the complex unit circle. Scientific-plate style wall art with cream graph paper and precise geometry. A classic gift for mathematicians, students, and teachers.</p>
<ul>
<li><b>Physical printed poster</b> — ships to your address (not a download)</li>
<li>Size: <b>18 × 24 inches</b></li>
<li>Matte poster, printed on demand</li>
<li>Frame not included</li>
</ul>
<p>MathRelaxing — code-drawn mathematics for your walls.</p>
""".strip(),
    "mr-phys-golden-ratio-sticker-4x4": """
<h2>Golden Ratio / Fibonacci Spiral Sticker</h2>
<p>Math-art kiss-cut vinyl sticker with the golden-ratio spiral. Durable, water-resistant vinyl — peel and stick on a laptop, water bottle, notebook, or phone.</p>
<ul>
<li><b>Physical vinyl sticker</b> — ships to you (not a digital file)</li>
<li>Size: <b>4 × 4 inches</b> (kiss-cut)</li>
<li>Water-resistant vinyl</li>
</ul>
<p>MathRelaxing.</p>
""".strip(),
    "mr-phys-fractal-flora-book": """
<h2>Fractal Flora Coloring Book — Printed Physical Edition</h2>
<p><b>Printed paperback coloring book</b> that ships to your door. Fifty unique fractal and botanical line-art designs: Dragon Curves, Julia Sets, Barnsley Ferns, and more — drawn with mathematical precision.</p>
<ul>
<li><b>Physical book</b> — perfect-bound, approx. 8.5 × 11 in</li>
<li>50 original line-art designs (no color-by-number numbers)</li>
<li>Printed on demand and shipped to you</li>
<li><b>No digital PDF / no download</b> is included with this listing</li>
</ul>
<p>MathRelaxing.</p>
""".strip(),
}


def printify_policy_body(name: str) -> dict:
    """
    handlingTime = production (Printify API: 10 days).
    Domestic service ≈ US 2–5 day transit after production.
    International ≈ longer economy transit (Printify CA/ROW 10–30 day transit).
    Free shipping worldwide (seller absorbs Printify rates).
    """
    return {
        "name": name,
        "description": (
            "Printify POD. Production up to 10 business days. "
            "US transit ~2–5 business days after ship. "
            "International transit ~10–30 business days after ship. Free shipping."
        ),
        "marketplaceId": MARKETPLACE,
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "handlingTime": {"value": 10, "unit": "DAY"},
        "shipToLocations": {
            # empty regionIncluded often means worldwide; be explicit
            "regionIncluded": [{"regionName": "Worldwide"}],
        },
        "shippingOptions": [
            {
                "optionType": "DOMESTIC",
                "costType": "FLAT_RATE",
                "shippingServices": [
                    {
                        "sortOrder": 1,
                        "shippingCarrierCode": "USPS",
                        # Priority ~1–3 business days; close to Printify US 2–5 transit
                        "shippingServiceCode": "USPSPriorityFlatRateEnvelope"
                        if False
                        else "USPSPriority",
                        "shippingCost": {"value": "0.0", "currency": "USD"},
                        "additionalShippingCost": {"value": "0.0", "currency": "USD"},
                        "freeShipping": True,
                        "buyerResponsibleForShipping": False,
                        "buyerResponsibleForPickup": False,
                    }
                ],
            },
            {
                "optionType": "INTERNATIONAL",
                "costType": "FLAT_RATE",
                "shippingServices": [
                    {
                        "sortOrder": 1,
                        "shippingCarrierCode": "USPS",
                        # Economy intl — multi-week transit aligns with Printify 10–30 day intl
                        "shippingServiceCode": "USPSFirstClassMailInternational",
                        "shippingCost": {"value": "0.0", "currency": "USD"},
                        "additionalShippingCost": {"value": "0.0", "currency": "USD"},
                        "freeShipping": True,
                        "buyerResponsibleForShipping": False,
                        "buyerResponsibleForPickup": False,
                        "shipToLocations": {
                            "regionIncluded": [{"regionName": "Worldwide"}],
                            "regionExcluded": [{"regionName": "US"}],
                        },
                    }
                ],
            },
        ],
        "globalShipping": False,
        "freightShipping": False,
        "pickupDropOff": False,
        "localPickup": False,
    }


def lulu_policy_body(name: str) -> dict:
    """Shorter production handling for Lulu books; free ship domestic + intl."""
    return {
        "name": name,
        "description": (
            "Lulu printed book. Production ~3–5 business days. "
            "Total delivery often 6–14 business days by market. Free shipping."
        ),
        "marketplaceId": MARKETPLACE,
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "handlingTime": {"value": 5, "unit": "DAY"},
        "shipToLocations": {
            "regionIncluded": [{"regionName": "Worldwide"}],
        },
        "shippingOptions": [
            {
                "optionType": "DOMESTIC",
                "costType": "FLAT_RATE",
                "shippingServices": [
                    {
                        "sortOrder": 1,
                        "shippingCarrierCode": "USPS",
                        "shippingServiceCode": "USPSMedia",
                        "shippingCost": {"value": "0.0", "currency": "USD"},
                        "additionalShippingCost": {"value": "0.0", "currency": "USD"},
                        "freeShipping": True,
                        "buyerResponsibleForShipping": False,
                        "buyerResponsibleForPickup": False,
                    }
                ],
            },
            {
                "optionType": "INTERNATIONAL",
                "costType": "FLAT_RATE",
                "shippingServices": [
                    {
                        "sortOrder": 1,
                        "shippingCarrierCode": "USPS",
                        "shippingServiceCode": "USPSFirstClassMailInternational",
                        "shippingCost": {"value": "0.0", "currency": "USD"},
                        "additionalShippingCost": {"value": "0.0", "currency": "USD"},
                        "freeShipping": True,
                        "buyerResponsibleForShipping": False,
                        "buyerResponsibleForPickup": False,
                        "shipToLocations": {
                            "regionIncluded": [{"regionName": "Worldwide"}],
                            "regionExcluded": [{"regionName": "US"}],
                        },
                    }
                ],
            },
        ],
        "globalShipping": False,
        "freightShipping": False,
        "pickupDropOff": False,
        "localPickup": False,
    }


async def find_policy_by_name(name: str) -> str | None:
    fp = await ebay._get(
        "/sell/account/v1/fulfillment_policy",
        {"marketplace_id": MARKETPLACE},
    )
    for p in fp.get("fulfillmentPolicies") or []:
        if p.get("name") == name:
            return p.get("fulfillmentPolicyId")
    return None


async def upsert_policy(name: str, body: dict) -> str:
    existing = await find_policy_by_name(name)
    if existing:
        try:
            await ebay._put(
                f"/sell/account/v1/fulfillment_policy/{existing}",
                body,
            )
            print(f"updated policy {name} id={existing}")
            return existing
        except Exception as e:
            print(f"put policy failed ({e}); trying create new name")
            body = dict(body)
            body["name"] = name + " v2"
    r = await ebay._post("/sell/account/v1/fulfillment_policy", body)
    fid = r.get("fulfillmentPolicyId")
    print(f"created policy {body['name']} id={fid}")
    return fid


async def apply_policy_to_sku(sku: str, fulfillment_id: str, description: str) -> None:
    inv = await ebay._get(f"/sell/inventory/v1/inventory_item/{sku}")
    prod = inv.get("product") or {}
    # refresh inventory description
    await ebay._put(
        f"/sell/inventory/v1/inventory_item/{sku}",
        {
            "product": {
                "title": prod.get("title"),
                "description": description,
                "aspects": prod.get("aspects") or {},
                "imageUrls": (prod.get("imageUrls") or [])[:12],
            },
            "condition": inv.get("condition") or "NEW",
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": (
                        (inv.get("availability") or {})
                        .get("shipToLocationAvailability", {})
                        .get("quantity")
                        or 1
                    )
                }
            },
            **(
                {"packageWeightAndSize": inv["packageWeightAndSize"]}
                if inv.get("packageWeightAndSize")
                else {}
            ),
        },
    )
    offers = await ebay.get_offers_for_sku(sku)
    if not offers:
        print(f"  no offer for {sku}")
        return
    o = offers[0]
    oid = o["offerId"]
    policies = o.get("listingPolicies") or {}
    body = {
        "availableQuantity": o.get("availableQuantity") or 1,
        "categoryId": o.get("categoryId"),
        "listingDescription": description,
        "listingPolicies": {
            "fulfillmentPolicyId": fulfillment_id,
            "paymentPolicyId": policies.get("paymentPolicyId"),
            "returnPolicyId": policies.get("returnPolicyId"),
        },
        "pricingSummary": o.get("pricingSummary"),
        "merchantLocationKey": o.get("merchantLocationKey") or "default_location",
        "marketplaceId": MARKETPLACE,
        "format": "FIXED_PRICE",
    }
    # drop Nones
    body["listingPolicies"] = {
        k: v for k, v in body["listingPolicies"].items() if v
    }
    await ebay._put(f"/sell/inventory/v1/offer/{oid}", body)
    # republish if needed so policy sticks on live listing
    st = o.get("status")
    if st == "PUBLISHED":
        try:
            # withdraw+publish can drop ranking; prefer just offer update for live
            print(f"  {sku}: offer updated (live) fulfillment={fulfillment_id}")
        except Exception as e:
            print(f"  {sku}: update warn {e}")
    else:
        lid = await ebay.publish_offer(oid)
        print(f"  {sku}: published {lid}")

    offers2 = await ebay.get_offers_for_sku(sku)
    o2 = offers2[0] if offers2 else {}
    print(
        f"  verify status={o2.get('status')} "
        f"fulfillment={(o2.get('listingPolicies') or {}).get('fulfillmentPolicyId')} "
        f"https://www.ebay.com/itm/{o2.get('listingId') or (o2.get('listing') or {}).get('listingId')}"
    )


async def main():
    print("=== Create/update fulfillment policies ===")
    # Try with USPSPriority; if intl service fails, fallback simpler codes
    printify_body = printify_policy_body(PRINTIFY_POLICY_NAME)
    lulu_body = lulu_policy_body(LULU_POLICY_NAME)

    try:
        printify_id = await upsert_policy(PRINTIFY_POLICY_NAME, printify_body)
    except Exception as e:
        print("printify policy error, simplifying intl service", e)
        printify_body["shippingOptions"][1]["shippingServices"][0][
            "shippingServiceCode"
        ] = "OtherInternational"
        printify_body["shippingOptions"][1]["shippingServices"][0][
            "shippingCarrierCode"
        ] = "Other"
        printify_id = await upsert_policy(PRINTIFY_POLICY_NAME + " v2", printify_body)

    try:
        lulu_id = await upsert_policy(LULU_POLICY_NAME, lulu_body)
    except Exception as e:
        print("lulu policy error, simplifying", e)
        lulu_body["shippingOptions"][1]["shippingServices"][0][
            "shippingServiceCode"
        ] = "OtherInternational"
        lulu_body["shippingOptions"][1]["shippingServices"][0][
            "shippingCarrierCode"
        ] = "Other"
        lulu_id = await upsert_policy(LULU_POLICY_NAME + " v2", lulu_body)

    print("printify_policy", printify_id)
    print("lulu_policy", lulu_id)

    # dump final policy JSON
    fp = await ebay._get(
        "/sell/account/v1/fulfillment_policy",
        {"marketplace_id": MARKETPLACE},
    )
    for p in fp.get("fulfillmentPolicies") or []:
        if p.get("fulfillmentPolicyId") in (printify_id, lulu_id):
            print(
                "\nPOLICY",
                p.get("name"),
                json.dumps(
                    {
                        "id": p.get("fulfillmentPolicyId"),
                        "handlingTime": p.get("handlingTime"),
                        "shipToLocations": p.get("shipToLocations"),
                        "shippingOptions": p.get("shippingOptions"),
                    },
                    indent=2,
                    default=str,
                )[:3500],
            )

    print("\n=== Apply to Printify SKUs ===")
    for sku in PRINTIFY_SKUS:
        intro = PRODUCT_INTROS[sku]
        desc = PRINTIFY_SHIP_HTML.format(body=intro)
        try:
            await apply_policy_to_sku(sku, printify_id, desc)
        except Exception as e:
            print(f"  FAIL {sku}: {e}")

    print("\n=== Apply to Lulu book SKU ===")
    for sku in LULU_SKUS:
        intro = PRODUCT_INTROS[sku]
        desc = LULU_SHIP_HTML.format(body=intro)
        try:
            await apply_policy_to_sku(sku, lulu_id, desc)
        except Exception as e:
            print(f"  FAIL {sku}: {e}")

    print("\nDONE")


if __name__ == "__main__":
    asyncio.run(main())
