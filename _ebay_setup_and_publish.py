"""
Prepare mathrelaxing eBay account (location + policies) and smoke-publish
one digital product, then optionally publish all active digitals.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")
from dotenv import load_dotenv

load_dotenv(".env")

# Reload ebay module so it picks up current .env token
from importlib import reload
import services.ebay as ebay

reload(ebay)

from database import SessionLocal
from models.product import DigitalProduct


async def ensure_location() -> str:
    """Ensure a merchant location exists; return merchantLocationKey."""
    key = "default_location"
    try:
        data = await ebay._get("/sell/inventory/v1/location")
        locs = data.get("locations") or []
        print(f"locations total={data.get('total')} keys={[l.get('merchantLocationKey') for l in locs]}")
        for loc in locs:
            if loc.get("merchantLocationKey") == key and loc.get("merchantLocationStatus") == "ENABLED":
                print("location ok:", key)
                return key
        if locs:
            # reuse first enabled
            for loc in locs:
                if loc.get("merchantLocationStatus") == "ENABLED":
                    k = loc["merchantLocationKey"]
                    print("reusing location:", k)
                    return k
    except Exception as e:
        print("list locations err:", e)

    # Create default warehouse/store location (Santiago / digital)
    body = {
        "location": {
            "address": {
                "addressLine1": "Santiago Centro",
                "city": "Santiago",
                "stateOrProvince": "RM",
                "postalCode": "8320000",
                "country": "CL",
            }
        },
        "locationTypes": ["WAREHOUSE"],
        "name": "MathRelaxing Digital Fulfillment",
        "merchantLocationStatus": "ENABLED",
    }
    try:
        # createInventoryLocation is POST .../location/{merchantLocationKey}
        token = await ebay.get_access_token()
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{ebay.API_BASE}/sell/inventory/v1/location/{key}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Content-Language": "en-US",
                },
                json=body,
            )
        print("create location status", resp.status_code, resp.text[:300])
        if resp.status_code in (200, 201, 204):
            return key
        # try PUT
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                f"{ebay.API_BASE}/sell/inventory/v1/location/{key}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Content-Language": "en-US",
                },
                json=body,
            )
        print("put location status", resp.status_code, resp.text[:300])
        if resp.status_code in (200, 201, 204):
            return key
    except Exception as e:
        print("create location failed:", e)
    raise RuntimeError("Could not ensure merchant location")


async def patch_create_offer_location(location_key: str):
    """Monkey-patch create_offer to use the right merchantLocationKey if needed."""
    orig = ebay.create_offer

    async def create_offer_fixed(product, policies):
        sku = f"mr-{product.slug}"
        price_str = f"{product.price_usd:.2f}"
        body = {
            "sku": sku,
            "marketplaceId": ebay.MARKETPLACE_ID,
            "format": "FIXED_PRICE",
            "availableQuantity": max(1, min(getattr(ebay, "LISTING_QUANTITY", 1), 3)),
            "categoryId": ebay.DIGITAL_CATEGORY_ID,
            "listingDescription": ebay._product_description(product),
            "listingPolicies": {
                "fulfillmentPolicyId": policies["fulfillment_policy_id"],
                "paymentPolicyId": policies["payment_policy_id"],
                "returnPolicyId": policies["return_policy_id"],
            },
            "pricingSummary": {
                "price": {"value": price_str, "currency": ebay.CURRENCY},
            },
            "merchantLocationKey": location_key,
            "includeCatalogProductDetails": False,
        }
        r = await ebay._post("/sell/inventory/v1/offer", body)
        return r.get("offerId", "")

    ebay.create_offer = create_offer_fixed
    return orig


def better_image_url(product) -> str:
    """Prefer static cover/thumb over render preview."""
    import os
    from pathlib import Path

    root = Path("/var/www/mathrelaxing.store")
    candidates = [
        root / "static" / "bonanza" / f"{product.slug}.jpg",
        root / "static" / "previews" / f"{product.slug}.jpg",
        root / "static" / "img" / f"{product.slug}_cover.jpg",
    ]
    for c in candidates:
        if c.is_file() and c.stat().st_size > 1000:
            return f"https://mathrelaxing.store/{c.relative_to(root).as_posix()}"
    # cover_image / thumbnail from DB
    for attr in ("cover_image", "thumbnail_url"):
        val = getattr(product, attr, None) or ""
        if val.startswith("/static/"):
            p = root / val.lstrip("/")
            if p.is_file():
                return f"https://mathrelaxing.store{val.split('?')[0]}"
        if val.startswith("http"):
            return val
    return f"https://mathrelaxing.store/api/render/preview?product={product.slug}"


async def upsert_with_better_image(product, policies):
    sku = f"mr-{product.slug}"
    ptype = getattr(product, "product_type", "image_pack") or "image_pack"
    is_loop = "loop" in ptype or "animation" in ptype
    aspects = {
        "Format": ["Digital Download"],
        "File Type": ["JPG/MP4"] if is_loop or "animation" in ptype else ["PDF/ZIP/JPG"],
        "Subject": ["Mathematical Art", "Abstract"],
        "Style": ["Abstract", "Digital Art"],
    }
    img = better_image_url(product)
    title = f"{product.name} — Digital Download | Math Art"
    if len(title) > 80:
        title = title[:77] + "..."
    await ebay._put(
        f"/sell/inventory/v1/inventory_item/{sku}",
        {
            "product": {
                "title": title,
                "description": ebay._product_description(product),
                "aspects": aspects,
                "imageUrls": [img],
            },
            "condition": "NEW",
            "availability": {
                # Low qty: eBay seller limits (often total qty ~50 on new accounts).
                "shipToLocationAvailability": {"quantity": ebay.LISTING_QUANTITY},
            },
        },
    )
    print(f"  inventory upsert {sku} qty={ebay.LISTING_QUANTITY} img={img}")


async def publish_product_fixed(product, location_key: str) -> dict:
    policies = await ebay.get_or_create_policies()
    print(
        "  policies:",
        policies.get("fulfillment_policy_id"),
        policies.get("payment_policy_id"),
        policies.get("return_policy_id"),
    )
    await upsert_with_better_image(product, policies)
    sku = f"mr-{product.slug}"
    qty = max(1, min(getattr(ebay, "LISTING_QUANTITY", 1), 3))
    offers = await ebay.get_offers_for_sku(sku)
    if offers:
        offer_id = offers[0]["offerId"]
        status = offers[0].get("status", "")
        listing_id = offers[0].get("listingId") or (offers[0].get("listing") or {}).get(
            "listingId"
        )
        print(f"  existing offer {offer_id} status={status}")
        if status != "PUBLISHED":
            # may need to update offer location/policies
            try:
                await ebay._put(
                    f"/sell/inventory/v1/offer/{offer_id}",
                    {
                        "availableQuantity": qty,
                        "categoryId": ebay.DIGITAL_CATEGORY_ID,
                        "listingDescription": ebay._product_description(product),
                        "listingPolicies": {
                            "fulfillmentPolicyId": policies["fulfillment_policy_id"],
                            "paymentPolicyId": policies["payment_policy_id"],
                            "returnPolicyId": policies["return_policy_id"],
                        },
                        "pricingSummary": {
                            "price": {
                                "value": f"{product.price_usd:.2f}",
                                "currency": ebay.CURRENCY,
                            }
                        },
                        "merchantLocationKey": location_key,
                        "marketplaceId": ebay.MARKETPLACE_ID,
                        "format": "FIXED_PRICE",
                    },
                )
            except Exception as e:
                print("  offer update warn:", e)
            listing_id = await ebay.publish_offer(offer_id)
    else:
        # create offer with correct location
        body = {
            "sku": sku,
            "marketplaceId": ebay.MARKETPLACE_ID,
            "format": "FIXED_PRICE",
            "availableQuantity": qty,
            "categoryId": ebay.DIGITAL_CATEGORY_ID,
            "listingDescription": ebay._product_description(product),
            "listingPolicies": {
                "fulfillmentPolicyId": policies["fulfillment_policy_id"],
                "paymentPolicyId": policies["payment_policy_id"],
                "returnPolicyId": policies["return_policy_id"],
            },
            "pricingSummary": {
                "price": {"value": f"{product.price_usd:.2f}", "currency": ebay.CURRENCY},
            },
            "merchantLocationKey": location_key,
            "includeCatalogProductDetails": False,
        }
        r = await ebay._post("/sell/inventory/v1/offer", body)
        offer_id = r.get("offerId", "")
        print(f"  created offer {offer_id}")
        listing_id = await ebay.publish_offer(offer_id)
    return {"offer_id": offer_id, "listing_id": listing_id, "sku": sku}


async def whoami():
    token = await ebay.get_access_token()
    import httpx
    import re

    xml = """<?xml version="1.0" encoding="utf-8"?>
<GetUserRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <DetailLevel>ReturnSummary</DetailLevel>
</GetUserRequest>"""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            "https://api.ebay.com/ws/api.dll",
            headers={
                "X-EBAY-API-SITEID": "0",
                "X-EBAY-API-COMPATIBILITY-LEVEL": "1193",
                "X-EBAY-API-CALL-NAME": "GetUser",
                "X-EBAY-API-IAF-TOKEN": token,
                "Content-Type": "text/xml",
            },
            content=xml,
        )
    m = re.search(r"<UserID[^>]*>(.*?)</UserID>", r.text)
    print("account UserID:", m.group(1) if m else "?")
    try:
        inv = await ebay._get("/sell/inventory/v1/inventory_item", {"limit": "5"})
        print("inventory total:", inv.get("total"))
    except Exception as e:
        print("inventory err:", e)
    try:
        pol = await ebay.get_or_create_policies()
        print("policies:", pol)
    except Exception as e:
        print("policies err:", e)


async def main():
    publish_all = "--all" in sys.argv
    print("=== WHOAMI ===")
    await whoami()

    print("\n=== LOCATION ===")
    loc = await ensure_location()

    db = SessionLocal()
    products = (
        db.query(DigitalProduct)
        .filter(DigitalProduct.active == True)
        .order_by(DigitalProduct.slug)
        .all()
    )
    print(f"active_digital={len(products)}")

    # Smoke: one product first (prefer hyperbolic or first)
    smoke = next((p for p in products if p.slug == "hyperbolic-gardens-digital"), products[0])
    print(f"\n=== SMOKE PUBLISH {smoke.slug} ===")
    try:
        result = await publish_product_fixed(smoke, loc)
        print("SMOKE OK", result)
    except Exception as e:
        print("SMOKE FAIL", e)
        db.close()
        raise

    report = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "location": loc,
        "smoke": {"slug": smoke.slug, "result": result},
        "results": [],
    }

    if publish_all:
        print(f"\n=== PUBLISH ALL ({len(products)}) ===")
        for i, p in enumerate(products, 1):
            row = {"slug": p.slug}
            try:
                r = await publish_product_fixed(p, loc)
                row.update({"ok": True, **r})
                print(f"  [{i}/{len(products)}] {p.slug}: OK listing={r.get('listing_id')}")
            except Exception as e:
                row.update({"ok": False, "error": str(e)[:300]})
                print(f"  [{i}/{len(products)}] {p.slug}: FAIL {e}")
            report["results"].append(row)
            await asyncio.sleep(0.4)

        ok = sum(1 for r in report["results"] if r.get("ok"))
        print(f"\nSUMMARY {ok}/{len(report['results'])} published")

    out = f"meta_drafts/ebay_publish_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    os.makedirs("meta_drafts", exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    with open("meta_drafts/ebay_publish_latest.json", "w") as f:
        json.dump(report, f, indent=2)
    print("WROTE", out)
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
