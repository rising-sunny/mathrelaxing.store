"""List published eBay offers and physical candidates."""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from services import ebay  # noqa: E402


async def offers_for_sku(sku: str) -> list:
    try:
        data = await ebay._get(
            "/sell/inventory/v1/offer",
            {"sku": sku, "limit": 25},
        )
        return data.get("offers") or []
    except Exception as e:
        return [{"error": str(e)[:200]}]


async def main():
    priv = await ebay._get("/sell/account/v1/privilege")
    print("PRIVILEGE", json.dumps(priv.get("sellingLimit"), indent=2))

    inv = await ebay._get("/sell/inventory/v1/inventory_item", {"limit": 200})
    items = inv.get("inventoryItems") or []
    print("inventory_items", len(items))

    published = []
    unpublished = []
    for it in items:
        sku = it.get("sku")
        title = ((it.get("product") or {}).get("title") or "")[:70]
        ofs = await offers_for_sku(sku)
        for o in ofs:
            if o.get("error"):
                print("SKU", sku, "offer_err", o["error"])
                continue
            st = o.get("status")
            lid = (o.get("listing") or {}).get("listingId")
            price = ((o.get("pricingSummary") or {}).get("price") or {}).get("value")
            row = {
                "sku": sku,
                "status": st,
                "listingId": lid,
                "price": price,
                "title": title,
            }
            if st == "PUBLISHED":
                published.append(row)
            else:
                unpublished.append(row)

    print("\n=== PUBLISHED", len(published), "===")
    for r in published:
        print(f"  {r['listingId']}  ${r['price']}  {r['sku']}  {r['title']}")

    print("\n=== UNPUBLISHED OFFERS", len(unpublished), "===")
    for r in unpublished[:30]:
        print(f"  {r['status']}  ${r['price']}  {r['sku']}  {r['title']}")

    # inventory without offers
    pub_skus = {r["sku"] for r in published}
    unp_skus = {r["sku"] for r in unpublished}
    bare = [it.get("sku") for it in items if it.get("sku") not in pub_skus | unp_skus]
    print("\n=== INVENTORY NO OFFER", len(bare), "===")
    for s in bare[:40]:
        print(" ", s)


if __name__ == "__main__":
    asyncio.run(main())
