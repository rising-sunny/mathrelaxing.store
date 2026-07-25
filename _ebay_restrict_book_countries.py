"""Restrict Fractal Flora book eBay shipping to Lulu-fulfillable markets."""
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

LULU_POLICY_ID = "319595609011"
SKU = "mr-phys-fractal-flora-book"

# Match services/lulu.py BOOK_COUNTRIES intent:
# US, GB, ES, AU + Europe EXCEPT Germany (VerpackG / LUCID).
# eBay does not accept every ISO-2 code; use supported region names.

DESC = """
<div>
<h2>Fractal Flora Coloring Book — Printed Physical Edition</h2>
<p><b>Printed paperback coloring book</b> that ships to your door. Fifty unique fractal and botanical line-art designs: Dragon Curves, Julia Sets, Barnsley Ferns, and more — drawn with mathematical precision.</p>
<ul>
<li><b>Physical book</b> — perfect-bound, approx. 8.5 × 11 in</li>
<li>50 original line-art designs (no color-by-number numbers)</li>
<li>Printed on demand and shipped to you</li>
<li><b>No digital PDF / no download</b> is included with this listing</li>
</ul>
<h3>Where we ship</h3>
<p>Ships <b>only</b> to:</p>
<ul>
<li>United States</li>
<li>United Kingdom</li>
<li>Australia</li>
<li>Spain</li>
<li>European Union countries <b>except Germany</b></li>
</ul>
<p><b>Germany is not available.</b> We cannot fulfill orders outside these destinations (same limits as our Lulu print partner).</p>
<h3>Shipping &amp; production (printed book)</h3>
<ul>
<li><b>Production:</b> typically about <b>3–5 business days</b>.</li>
<li><b>United States &amp; UK — total delivery:</b> about <b>6–9 business days</b>.</li>
<li><b>Europe (excl. Germany) — total delivery:</b> about <b>7–13 business days</b>.</li>
<li><b>Australia:</b> about <b>8–14 business days</b>.</li>
</ul>
<p>Free shipping to eligible countries. Tracking when the printer provides it. MathRelaxing.</p>
</div>
""".strip()


async def try_policy(include: list[str], exclude: list[str], label: str) -> str | None:
    ship_to: dict = {
        "regionIncluded": [{"regionName": c} for c in include],
    }
    if exclude:
        ship_to["regionExcluded"] = [{"regionName": c} for c in exclude]

    intl_include = [c for c in include if c not in ("US", "United States")]
    intl_ship: dict = {
        "regionIncluded": [{"regionName": c} for c in intl_include],
    }
    if exclude:
        intl_ship["regionExcluded"] = [{"regionName": c} for c in exclude]

    body = {
        "name": f"Lulu Book Free Ship — {label}"[:64],
        "description": (
            "Lulu printed book. Ship-to limited to US, UK, AU, ES and EU except DE. "
            "Handling 5 business days (production). Free shipping. "
            "Total delivery ~6–14 business days by market."
        ),
        "marketplaceId": "EBAY_US",
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "handlingTime": {"value": 5, "unit": "DAY"},
        "shipToLocations": ship_to,
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
                        "additionalShippingCost": {
                            "value": "0.0",
                            "currency": "USD",
                        },
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
                        "shippingCarrierCode": "Other",
                        "shippingServiceCode": "OtherInternational",
                        "shippingCost": {"value": "0.0", "currency": "USD"},
                        "additionalShippingCost": {
                            "value": "0.0",
                            "currency": "USD",
                        },
                        "freeShipping": True,
                        "buyerResponsibleForShipping": False,
                        "buyerResponsibleForPickup": False,
                        "shipToLocations": intl_ship,
                    }
                ],
            },
        ],
        "globalShipping": False,
        "freightShipping": False,
        "localPickup": False,
    }

    try:
        await ebay._put(
            f"/sell/account/v1/fulfillment_policy/{LULU_POLICY_ID}", body
        )
        print("OK put", label)
        return LULU_POLICY_ID
    except Exception as e:
        print("FAIL put", label, str(e)[:220])
    try:
        r = await ebay._post("/sell/account/v1/fulfillment_policy", body)
        pid = r.get("fulfillmentPolicyId")
        print("OK create", label, pid)
        return pid
    except Exception as e:
        print("FAIL create", label, str(e)[:220])
        return None


async def main():
    candidates = [
        (
            ["US", "GB", "AU", "ES", "EuropeanUnion"],
            ["DE"],
            "EU+core excl DE",
        ),
        (
            ["US", "GB", "AU", "EuropeanUnion"],
            ["DE"],
            "EU+core no ES code",
        ),
        (
            ["United States", "United Kingdom", "Australia", "Spain", "European Union"],
            ["Germany"],
            "full names",
        ),
        (["US", "GB", "AU", "ES"], [], "core4 only"),
        (["US", "GB", "AU"], [], "US GB AU"),
        (["US", "GB"], [], "US GB only"),
    ]

    policy_id = None
    for include, exclude, label in candidates:
        policy_id = await try_policy(include, exclude, label)
        if policy_id:
            break
    if not policy_id:
        raise SystemExit("Could not create/update restricted shipping policy")

    fp = await ebay._get(f"/sell/account/v1/fulfillment_policy/{policy_id}")
    print(
        "FINAL shipToLocations:",
        json.dumps(fp.get("shipToLocations"), indent=2),
    )
    print("handling:", fp.get("handlingTime"))
    for o in fp.get("shippingOptions") or []:
        print("option", o.get("optionType"))
        for s in o.get("shippingServices") or []:
            print(
                " ",
                s.get("shippingServiceCode"),
                "free=",
                s.get("freeShipping"),
                "cost=",
                s.get("shippingCost"),
                "to=",
                json.dumps(s.get("shipToLocations")),
            )

    inv = await ebay._get(f"/sell/inventory/v1/inventory_item/{SKU}")
    prod = inv.get("product") or {}
    put_inv = {
        "product": {
            "title": prod.get("title"),
            "description": DESC,
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
    }
    if inv.get("packageWeightAndSize"):
        put_inv["packageWeightAndSize"] = inv["packageWeightAndSize"]
    await ebay._put(f"/sell/inventory/v1/inventory_item/{SKU}", put_inv)

    offers = await ebay.get_offers_for_sku(SKU)
    o = offers[0]
    pol = o.get("listingPolicies") or {}
    offer_id = o["offerId"]
    await ebay._put(
        f"/sell/inventory/v1/offer/{offer_id}",
        {
            "availableQuantity": o.get("availableQuantity") or 1,
            "categoryId": o.get("categoryId"),
            "listingDescription": DESC,
            "listingPolicies": {
                "fulfillmentPolicyId": policy_id,
                "paymentPolicyId": pol.get("paymentPolicyId"),
                "returnPolicyId": pol.get("returnPolicyId"),
            },
            "pricingSummary": o.get("pricingSummary"),
            "merchantLocationKey": o.get("merchantLocationKey")
            or "default_location",
            "marketplaceId": "EBAY_US",
            "format": "FIXED_PRICE",
        },
    )

    o2 = (await ebay.get_offers_for_sku(SKU))[0]
    lid = o2.get("listingId") or (o2.get("listing") or {}).get("listingId")
    print(
        "DONE",
        o2.get("status"),
        "fulfillment=",
        (o2.get("listingPolicies") or {}).get("fulfillmentPolicyId"),
        f"https://www.ebay.com/itm/{lid}",
    )


if __name__ == "__main__":
    asyncio.run(main())
