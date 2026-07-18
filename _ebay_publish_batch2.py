"""Publish small eBay batch with fixed payload (qty=1, safe aspects/images)."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from importlib import reload
from pathlib import Path

sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")
from dotenv import load_dotenv

load_dotenv(".env")
import services.ebay as ebay

reload(ebay)

from database import SessionLocal
from models.product import DigitalProduct

PRIORITY = [
    "hyperbolic-gardens-digital",
    "fractal-flora-coloring-book-digital",
    "mathematical-tangle-art-digital",
    "sacred-geometry-coloring-book-digital",
    "sacred-harmonics-digital",
    "thomas-attractor-loop",
    "julia-set-loop",
    "bauhaus-print-set",
]
BATCH = 8
QTY = 1
LOC = "default_location"


def image_url(product) -> str:
    root = Path("/var/www/mathrelaxing.store")
    for rel in (
        f"static/bonanza/{product.slug}.jpg",
        f"static/previews/{product.slug}.jpg",
        f"static/img/{product.slug}_cover.jpg",
    ):
        if (root / rel).is_file():
            return f"https://mathrelaxing.store/{rel}"
    for attr in ("cover_image", "thumbnail_url"):
        val = (getattr(product, attr, None) or "").split("?", 1)[0]
        if val.startswith("/static/") and (root / val.lstrip("/")).is_file():
            return f"https://mathrelaxing.store{val}"
    return "https://mathrelaxing.store/static/bonanza/hyperbolic-gardens-digital.jpg"


def title(product) -> str:
    t = f"{product.name} — Digital Download"
    return t[:80]


async def upsert(product):
    sku = f"mr-{product.slug}"
    body = {
        "availability": {"shipToLocationAvailability": {"quantity": QTY}},
        "condition": "NEW",
        "product": {
            "title": title(product),
            "description": ebay._product_description(product)[:4000],
            "imageUrls": [image_url(product)],
            "aspects": {
                "Brand": ["MathRelaxing"],
                "Type": ["Digital Download"],
            },
        },
    }
    await ebay._put(f"/sell/inventory/v1/inventory_item/{sku}", body)
    return sku


async def ensure_offer(product, policies, sku) -> str:
    offers = await ebay.get_offers_for_sku(sku)
    if offers:
        return offers[0]["offerId"], offers[0].get("status"), offers[0].get("listingId") or (
            offers[0].get("listing") or {}
        ).get("listingId")
    body = {
        "sku": sku,
        "marketplaceId": "EBAY_US",
        "format": "FIXED_PRICE",
        "availableQuantity": QTY,
        "categoryId": ebay.DIGITAL_CATEGORY_ID,
        "listingDescription": ebay._product_description(product)[:4000],
        "listingPolicies": {
            "fulfillmentPolicyId": policies["fulfillment_policy_id"],
            "paymentPolicyId": policies["payment_policy_id"],
            "returnPolicyId": policies["return_policy_id"],
        },
        "pricingSummary": {
            "price": {"value": f"{float(product.price_usd):.2f}", "currency": "USD"}
        },
        "merchantLocationKey": LOC,
        "includeCatalogProductDetails": False,
    }
    r = await ebay._post("/sell/inventory/v1/offer", body)
    return r.get("offerId"), "UNPUBLISHED", None


async def publish_one(product, policies):
    sku = await upsert(product)
    print(f"  inv ok {sku} img={image_url(product)}")
    offer_id, status, listing_id = await ensure_offer(product, policies, sku)
    print(f"  offer {offer_id} status={status}")
    if status != "PUBLISHED":
        listing_id = await ebay.publish_offer(offer_id)
    return {"sku": sku, "offer_id": offer_id, "listing_id": listing_id}


async def main():
    priv = await ebay._get("/sell/account/v1/privilege")
    pay = await ebay._get("/sell/account/v1/payments_program/EBAY_US/EBAY_PAYMENTS")
    print("privilege", priv)
    print("payments", pay)

    policies = await ebay.get_or_create_policies()
    print("policies", policies)

    db = SessionLocal()
    by = {
        p.slug: p
        for p in db.query(DigitalProduct).filter(DigitalProduct.active == True).all()
    }
    batch = [by[s] for s in PRIORITY if s in by][:BATCH]
    print("batch", [p.slug for p in batch])

    results = []
    for i, p in enumerate(batch, 1):
        print(f"\n[{i}/{len(batch)}] {p.slug}")
        try:
            r = await publish_one(p, policies)
            results.append({"slug": p.slug, "ok": True, **r})
            print("  PUBLISHED", r)
        except Exception as e:
            results.append({"slug": p.slug, "ok": False, "error": str(e)[:400]})
            print("  FAIL", e)
        await asyncio.sleep(0.6)

    ok = sum(1 for r in results if r.get("ok"))
    report = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "privilege": priv,
        "payments": pay,
        "qty": QTY,
        "ok": ok,
        "total": len(results),
        "results": results,
    }
    Path("meta_drafts").mkdir(exist_ok=True)
    out = f"meta_drafts/ebay_batch_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    Path(out).write_text(json.dumps(report, indent=2))
    Path("meta_drafts/ebay_batch_latest.json").write_text(json.dumps(report, indent=2))
    print(f"\nSUMMARY {ok}/{len(results)} -> {out}")
    for r in results:
        print(
            ("OK " if r.get("ok") else "ERR"),
            r["slug"],
            r.get("listing_id") or r.get("error", "")[:120],
        )
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
