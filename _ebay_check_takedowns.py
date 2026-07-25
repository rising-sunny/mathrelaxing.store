"""Find eBay offers not live / policy issues."""
from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path("/var/www/mathrelaxing.store")
load_dotenv(ROOT / ".env")
os.chdir(ROOT)

import services.ebay as ebay  # noqa: E402


async def main():
    inv = await ebay._get("/sell/inventory/v1/inventory_item", {"limit": "100"})
    items = inv.get("inventoryItems") or []
    print("inventory_items", len(items), "total", inv.get("total"))

    rows = []
    for it in items:
        sku = it.get("sku")
        title = ((it.get("product") or {}).get("title") or "")[:90]
        offers = await ebay.get_offers_for_sku(sku)
        if not offers:
            rows.append(
                {
                    "sku": sku,
                    "title": title,
                    "status": "NO_OFFER",
                    "listing_id": None,
                    "price": None,
                    "offer_id": None,
                    "listing": None,
                    "offer": None,
                }
            )
            continue
        # check ALL offers for sku
        for o in offers:
            lid = o.get("listingId") or (o.get("listing") or {}).get("listingId")
            listing = o.get("listing") or {}
            rows.append(
                {
                    "sku": sku,
                    "title": title,
                    "status": o.get("status"),
                    "listing_id": lid,
                    "price": ((o.get("pricingSummary") or {}).get("price") or {}).get(
                        "value"
                    ),
                    "offer_id": o.get("offerId"),
                    "listing": listing,
                    "offer": o,
                }
            )

    c = Counter(r["status"] for r in rows)
    print("by_status", dict(c))

    not_pub = [r for r in rows if r["status"] != "PUBLISHED"]
    print(f"\n=== NOT PUBLISHED ({len(not_pub)}) ===")
    for r in not_pub:
        print(
            f"  [{r['status']}] {r['sku']}  listing={r['listing_id']}  "
            f"price={r.get('price')}  offer={r.get('offer_id')}"
        )
        print(f"    {r['title']}")
        if r.get("listing"):
            print(f"    listing={json.dumps(r['listing'], default=str)[:400]}")

    # Full dump of every PUBLISHED offer's listing object (may show ended/restricted)
    print("\n=== PUBLISHED listing objects (non-empty) ===")
    suspicious = []
    for r in rows:
        if r["status"] != "PUBLISHED":
            continue
        listing = r.get("listing") or {}
        if listing:
            print(r["sku"], json.dumps(listing, default=str)[:300])
        # flag if sold out quantity 0
        o = r.get("offer") or {}
        qty = o.get("availableQuantity")
        if qty == 0:
            suspicious.append((r, "qty0"))

    print("\n=== COMPLIANCE ===")
    for path in [
        "/sell/compliance/v1/listing_violation_summary",
        "/sell/compliance/v1/listing_violation?compliance_type=PRODUCT_ADOPTION&limit=50",
        "/sell/compliance/v1/listing_violation?compliance_type=ASPECTS_ADOPTION&limit=50",
        "/sell/compliance/v1/listing_violation?compliance_type=HTTPS&limit=50",
        "/sell/compliance/v1/listing_violation?compliance_type=OUTSIDE_EBAY_BUYING_AND_SELLING&limit=50",
        "/sell/compliance/v1/listing_violation?compliance_type=RETURNS_POLICY&limit=50",
        "/sell/compliance/v1/listing_violation?compliance_type=ITEM_NOT_AS_DESCRIBED&limit=50",
    ]:
        try:
            r = await ebay._get(path)
            print("\nOK", path)
            print(json.dumps(r, indent=2, default=str)[:3000])
        except Exception as e:
            print("\nFAIL", path[:80], str(e)[:300])

    # try Fulfillment / Marketing? or getOffers without sku
    print("\n=== GET OFFERS (marketplace all) ===")
    try:
        # limit+offset marketplace
        r = await ebay._get(
            "/sell/inventory/v1/offer",
            {"limit": "200", "marketplace_id": "EBAY_US"},
        )
        offers = r.get("offers") or []
        print("offers_total", r.get("total"), "returned", len(offers))
        oc = Counter(o.get("status") for o in offers)
        print("offer_status", dict(oc))
        for o in offers:
            st = o.get("status")
            if st != "PUBLISHED":
                sku = o.get("sku")
                lid = o.get("listingId") or (o.get("listing") or {}).get("listingId")
                title = ((o.get("listing") or {}).get("title") or o.get("sku") or "")[
                    :70
                ]
                print(
                    f"  [{st}] sku={sku} listing={lid} "
                    f"https://www.ebay.com/itm/{lid if lid else ''}"
                )
                print(f"    listing_obj={json.dumps(o.get('listing'), default=str)[:400]}")
                print(
                    f"    keys={list(o.keys())} price="
                    f"{((o.get('pricingSummary') or {}).get('price') or {}).get('value')}"
                )
    except Exception as e:
        print("get offers fail", e)

    # Inventory item groups? 
    # Try account privilege again
    try:
        priv = await ebay._get("/sell/account/v1/privilege")
        print("\nprivilege", json.dumps(priv, indent=2)[:800])
    except Exception as e:
        print("priv fail", e)


if __name__ == "__main__":
    asyncio.run(main())
