"""Unpublish all eBay offers that are currently PUBLISHED."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path("/var/www/mathrelaxing.store")
load_dotenv(ROOT / ".env")
os.chdir(ROOT)

import services.ebay as ebay  # noqa: E402


async def main():
    print("configured", ebay.is_configured())
    inv = await ebay._get("/sell/inventory/v1/inventory_item", {"limit": "100"})
    items = inv.get("inventoryItems") or []
    print(f"inventory_items={len(items)}")

    published = []
    for it in items:
        sku = it.get("sku")
        title = ((it.get("product") or {}).get("title") or "")[:70]
        offers = await ebay.get_offers_for_sku(sku)
        for o in offers or []:
            if o.get("status") == "PUBLISHED":
                lid = o.get("listingId") or (o.get("listing") or {}).get("listingId")
                hold = (o.get("listing") or {}).get("listingOnHold")
                published.append(
                    {
                        "sku": sku,
                        "offer_id": o.get("offerId"),
                        "listing_id": lid,
                        "title": title,
                        "on_hold": hold,
                    }
                )

    print(f"to_unpublish={len(published)}")
    ok = fail = 0
    for row in published:
        oid = row["offer_id"]
        sku = row["sku"]
        try:
            await ebay.withdraw_offer(oid)
            print(
                f"  OK  {sku}  offer={oid}  listing={row['listing_id']}  "
                f"hold={row['on_hold']}  {row['title']}"
            )
            ok += 1
        except Exception as e:
            print(f"  FAIL {sku} offer={oid}: {e}")
            fail += 1
        await asyncio.sleep(0.25)

    # verify
    still = 0
    inv2 = await ebay._get("/sell/inventory/v1/inventory_item", {"limit": "100"})
    for it in inv2.get("inventoryItems") or []:
        for o in await ebay.get_offers_for_sku(it.get("sku")):
            if o.get("status") == "PUBLISHED":
                still += 1
                print(
                    "  STILL_PUBLISHED",
                    it.get("sku"),
                    o.get("offerId"),
                    o.get("listingId"),
                )

    print(f"\nSUMMARY unpublish_ok={ok} fail={fail} still_published={still}")


if __name__ == "__main__":
    asyncio.run(main())
