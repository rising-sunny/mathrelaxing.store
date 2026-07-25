"""
Ensure free shipping (buyer pays $0 for ship) and fold shipping into item price.

Printify approx ship (catalog shipping.json, first item):
  - Posters US often ~$5.99–$9.99; intl CA/ROW often ~$13–$19
  - Stickers US ~$4.29; intl higher
Lulu books: free ship already in business model (retail absorbs it).

eBay fees: ~13.6% + $0.30/0.40 order fee on total sale (item + shipping).
With free shipping, FVF is only on item price → include ship in item price first.
"""
from __future__ import annotations

import asyncio
import math
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path("/var/www/mathrelaxing.store")
load_dotenv(ROOT / ".env")
os.chdir(ROOT)

import services.ebay as ebay  # noqa: E402

FEE = 0.136
ORDER_FEE_LOW = 0.30
ORDER_FEE_HIGH = 0.40

PRINTIFY_POLICY = "319595608011"
LULU_POLICY = "319595609011"

# base_catalog (Etsy size price) + ship_allowance → list with fee gross-up
# ship_allowance sized to cover typical Printify free-ship worldwide absorption
ITEMS = [
    {
        "sku": "mr-phys-penrose-poster-18x24",
        "policy": PRINTIFY_POLICY,
        "base": 26.00,
        "ship": 12.00,  # covers US ~$6 + buffer toward intl Printify rates
        "kind": "printify",
    },
    {
        "sku": "mr-phys-euler-poster-18x24",
        "policy": PRINTIFY_POLICY,
        "base": 26.00,
        "ship": 12.00,
        "kind": "printify",
    },
    {
        "sku": "mr-phys-golden-ratio-sticker-4x4",
        "policy": PRINTIFY_POLICY,
        "base": 4.99,
        "ship": 4.50,  # Printify sticker US first_item ~$4.29
        "kind": "printify",
    },
    {
        "sku": "mr-phys-fractal-flora-book",
        "policy": LULU_POLICY,
        "base": 18.99,
        "ship": 0.0,  # Lulu free-ship model already in retail
        "kind": "lulu",
    },
]


def list_price(base: float, ship: float) -> float:
    """(base + ship + order_fee) / (1 - fee), ceil to cent, prefer .99."""
    subtotal = base + ship
    p = (subtotal + ORDER_FEE_LOW) / (1.0 - FEE)
    p = math.ceil(p * 100 - 1e-9) / 100
    of = ORDER_FEE_LOW if p <= 10 else ORDER_FEE_HIGH
    if of != ORDER_FEE_LOW:
        p = (subtotal + of) / (1.0 - FEE)
        p = math.ceil(p * 100 - 1e-9) / 100
    # snap up to .99 if within 50c
    dollars = int(p)
    cand = dollars + 0.99
    if cand < p:
        cand = dollars + 1.99
    if cand - p <= 0.55:
        p = cand
    return round(p, 2)


def net_after_fees(price: float) -> float:
    of = ORDER_FEE_LOW if price <= 10 else ORDER_FEE_HIGH
    return round(price - price * FEE - of, 2)


def free_ship_policy_body(name: str, handling: int, domestic_code: str) -> dict:
    """Domestic + international both $0. Prefer freeShipping=true when eBay allows."""
    return {
        "name": name,
        "description": (
            "Free shipping — shipping cost included in item price. "
            f"Handling/production up to {handling} business days."
        ),
        "marketplaceId": "EBAY_US",
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "handlingTime": {"value": handling, "unit": "DAY"},
        "shipToLocations": {"regionIncluded": [{"regionName": "Worldwide"}]},
        "shippingOptions": [
            {
                "optionType": "DOMESTIC",
                "costType": "FLAT_RATE",
                "shippingServices": [
                    {
                        "sortOrder": 1,
                        "shippingCarrierCode": "USPS",
                        "shippingServiceCode": domestic_code,
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
                        # eBay often rejects freeShipping:true on intl; cost 0 is what matters
                        "freeShipping": True,
                        "buyerResponsibleForShipping": False,
                        "buyerResponsibleForPickup": False,
                        "shipToLocations": {
                            "regionIncluded": [{"regionName": "Worldwide"}],
                        },
                    }
                ],
            },
        ],
        "globalShipping": False,
        "freightShipping": False,
        "localPickup": False,
    }


def free_ship_lulu_body() -> dict:
    """Book: free ship, limited countries US+GB+AU+FR (what eBay accepted)."""
    intl = ["GB", "AU", "FR"]
    return {
        "name": "Lulu Book Free Ship — limited countries",
        "description": (
            "Free shipping (included in item price). "
            "Ships only to US, GB, AU, FR. Handling 5 business days production."
        ),
        "marketplaceId": "EBAY_US",
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "handlingTime": {"value": 5, "unit": "DAY"},
        "shipToLocations": {
            "regionIncluded": [{"regionName": "US"}]
            + [{"regionName": c} for c in intl],
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
                        "shipToLocations": {
                            "regionIncluded": [
                                {"regionName": c} for c in intl
                            ],
                        },
                    }
                ],
            },
        ],
        "globalShipping": False,
        "freightShipping": False,
        "localPickup": False,
    }


FREE_SHIP_NOTE_PRINTIFY = """
<p><b>🆓 Free shipping</b> — the shipping cost is <b>already included in the item price</b>. You pay one total at checkout (no separate shipping charge).</p>
<p><b>Production:</b> up to 10 business days (Printify). <b>US transit:</b> ~2–5 business days after ship. <b>International transit:</b> ~10–30 business days after ship.</p>
""".strip()

FREE_SHIP_NOTE_LULU = """
<p><b>🆓 Free shipping</b> (eligible countries only) — shipping is <b>included in the item price</b>. One total at checkout.</p>
<p>Ships only to <b>US, United Kingdom, Australia, France</b>. Production ~3–5 business days; total delivery often 6–14 business days by market.</p>
""".strip()


async def upsert_printify_policy() -> str:
    body = free_ship_policy_body(
        "Printify POD Free Ship — 10d production",
        10,
        "USPSPriority",
    )
    try:
        await ebay._put(
            f"/sell/account/v1/fulfillment_policy/{PRINTIFY_POLICY}", body
        )
        print("updated printify policy", PRINTIFY_POLICY)
        return PRINTIFY_POLICY
    except Exception as e:
        print("printify put fail", e)
        r = await ebay._post("/sell/account/v1/fulfillment_policy", body)
        return r["fulfillmentPolicyId"]


async def upsert_lulu_policy() -> str:
    body = free_ship_lulu_body()
    try:
        await ebay._put(
            f"/sell/account/v1/fulfillment_policy/{LULU_POLICY}", body
        )
        print("updated lulu policy", LULU_POLICY)
        return LULU_POLICY
    except Exception as e:
        print("lulu put fail", e)
        r = await ebay._post("/sell/account/v1/fulfillment_policy", body)
        return r["fulfillmentPolicyId"]


async def apply_item(item: dict, policy_id: str) -> None:
    sku = item["sku"]
    price = list_price(item["base"], item["ship"])
    net = net_after_fees(price)
    print(
        f"\n{sku}: base={item['base']} + ship={item['ship']} "
        f"→ list=${price:.2f} (est. net after eBay fees ${net:.2f})"
    )

    inv = await ebay._get(f"/sell/inventory/v1/inventory_item/{sku}")
    prod = inv.get("product") or {}
    desc = prod.get("description") or ""
    # Ensure free-ship note present once
    note = (
        FREE_SHIP_NOTE_LULU
        if item["kind"] == "lulu"
        else FREE_SHIP_NOTE_PRINTIFY
    )
    if "already included in the item price" not in desc and "included in the item price" not in desc:
        # inject before closing </div> if present
        if desc.strip().endswith("</div>"):
            desc = desc.rstrip()[:-6] + note + "\n</div>"
        else:
            desc = desc + "\n" + note

    put_inv = {
        "product": {
            "title": prod.get("title"),
            "description": desc,
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
    await ebay._put(f"/sell/inventory/v1/inventory_item/{sku}", put_inv)

    offers = await ebay.get_offers_for_sku(sku)
    o = offers[0]
    pol = o.get("listingPolicies") or {}
    await ebay._put(
        f"/sell/inventory/v1/offer/{o['offerId']}",
        {
            "availableQuantity": o.get("availableQuantity") or 1,
            "categoryId": o.get("categoryId"),
            "listingDescription": desc,
            "listingPolicies": {
                "fulfillmentPolicyId": policy_id,
                "paymentPolicyId": pol.get("paymentPolicyId"),
                "returnPolicyId": pol.get("returnPolicyId"),
            },
            "pricingSummary": {
                "price": {"value": f"{price:.2f}", "currency": "USD"}
            },
            "merchantLocationKey": o.get("merchantLocationKey")
            or "default_location",
            "marketplaceId": "EBAY_US",
            "format": "FIXED_PRICE",
        },
    )
    o2 = (await ebay.get_offers_for_sku(sku))[0]
    lid = o2.get("listingId") or (o2.get("listing") or {}).get("listingId")
    print(
        f"  OK ${price:.2f} fulfillment={policy_id} "
        f"https://www.ebay.com/itm/{lid}"
    )


async def main():
    printify_id = await upsert_printify_policy()
    lulu_id = await upsert_lulu_policy()

    # verify free flags
    for pid, label in [
        (printify_id, "printify"),
        (lulu_id, "lulu"),
    ]:
        fp = await ebay._get(f"/sell/account/v1/fulfillment_policy/{pid}")
        print(f"\nPOLICY {label} {pid} handling={fp.get('handlingTime')}")
        for o in fp.get("shippingOptions") or []:
            for s in o.get("shippingServices") or []:
                print(
                    f"  {o.get('optionType')}: {s.get('shippingServiceCode')} "
                    f"free={s.get('freeShipping')} cost={s.get('shippingCost')}"
                )

    for item in ITEMS:
        pid = printify_id if item["kind"] == "printify" else lulu_id
        try:
            await apply_item(item, pid)
        except Exception as e:
            print(f"FAIL {item['sku']}: {e}")

    print("\nDONE — buyers should see Free shipping; ship cost baked into price.")


if __name__ == "__main__":
    asyncio.run(main())
