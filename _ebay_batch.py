"""Setup location, smoke 1 product, then publish a small batch (default 8)."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from importlib import reload

sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")
from dotenv import load_dotenv

load_dotenv(".env")

import services.ebay as ebay

reload(ebay)

from database import SessionLocal
from models.product import DigitalProduct

# Prefer high-quality catalog first, then fill to BATCH_SIZE
PRIORITY = [
    "hyperbolic-gardens-digital",
    "fractal-flora-coloring-book-digital",
    "mathematical-tangle-art-digital",
    "sacred-geometry-coloring-book-digital",
    "sacred-harmonics-digital",
    "thomas-attractor-loop",
    "julia-set-loop",
    "bauhaus-print-set",
    "harmonograph-print-set",
    "voronoi-cell-garden-loop",
]
BATCH_SIZE = int(os.getenv("EBAY_BATCH_SIZE", "8"))


async def ensure_location() -> str:
    key = os.getenv("EBAY_MERCHANT_LOCATION_KEY", "default_location")
    try:
        data = await ebay._get("/sell/inventory/v1/location")
        locs = data.get("locations") or []
        print("locations:", [(l.get("merchantLocationKey"), l.get("merchantLocationStatus")) for l in locs])
        for loc in locs:
            if loc.get("merchantLocationKey") == key and loc.get("merchantLocationStatus") == "ENABLED":
                return key
        for loc in locs:
            if loc.get("merchantLocationStatus") == "ENABLED":
                return loc["merchantLocationKey"]
    except Exception as e:
        print("list loc err", e)

    import httpx

    token = await ebay.get_access_token()
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
    print("create location", resp.status_code, resp.text[:250])
    if resp.status_code not in (200, 201, 204):
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
        print("put location", resp.status_code, resp.text[:250])
        if resp.status_code not in (200, 201, 204):
            raise RuntimeError(f"location failed: {resp.text[:300]}")
    return key


async def publish_one(product, location_key: str) -> dict:
    # Temporarily force location key via env for create_offer
    os.environ["EBAY_MERCHANT_LOCATION_KEY"] = location_key
    # Prefer service publish with better images already in ebay.py
    # But create_offer uses LISTING_QUANTITY=1 — good.
    # Patch merchant location if create_offer uses env — we set env above.
    # Also need inventory qty 1 from updated ebay.py
    result = await ebay.publish_product(product)
    return result


async def main():
    import re
    import httpx

    token = await ebay.get_access_token()
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
    uid = re.search(r"<UserID[^>]*>(.*?)</UserID>", r.text)
    print("UserID:", uid.group(1) if uid else "?")
    priv = await ebay._get("/sell/account/v1/privilege")
    print("privilege:", json.dumps(priv))

    loc = await ensure_location()
    print("location_key:", loc)
    os.environ["EBAY_MERCHANT_LOCATION_KEY"] = loc

    # Ensure policies exist
    policies = await ebay.get_or_create_policies()
    print("policies:", policies)

    db = SessionLocal()
    by_slug = {
        p.slug: p
        for p in db.query(DigitalProduct).filter(DigitalProduct.active == True).all()
    }
    batch = []
    for s in PRIORITY:
        if s in by_slug and len(batch) < BATCH_SIZE:
            batch.append(by_slug[s])
    if len(batch) < BATCH_SIZE:
        for p in sorted(by_slug.values(), key=lambda x: x.slug):
            if p not in batch and len(batch) < BATCH_SIZE:
                batch.append(p)

    print(f"batch size={len(batch)} qty_per_listing={ebay.LISTING_QUANTITY}")
    print("slugs:", [p.slug for p in batch])

    # Smoke first
    smoke = batch[0]
    print(f"\n=== SMOKE {smoke.slug} ===")
    try:
        smoke_r = await publish_one(smoke, loc)
        print("SMOKE OK", smoke_r)
    except Exception as e:
        print("SMOKE FAIL", e)
        db.close()
        raise

    results = [{"slug": smoke.slug, "ok": True, **smoke_r}]
    for p in batch[1:]:
        print(f"\n=== {p.slug} ===")
        try:
            r = await publish_one(p, loc)
            results.append({"slug": p.slug, "ok": True, **r})
            print("OK", r)
        except Exception as e:
            results.append({"slug": p.slug, "ok": False, "error": str(e)[:350]})
            print("FAIL", e)
        await asyncio.sleep(0.5)

    ok = sum(1 for r in results if r.get("ok"))
    report = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "user": uid.group(1) if uid else None,
        "privilege": priv,
        "location": loc,
        "policies": policies,
        "qty": ebay.LISTING_QUANTITY,
        "ok": ok,
        "total": len(results),
        "results": results,
    }
    os.makedirs("meta_drafts", exist_ok=True)
    path = f"meta_drafts/ebay_batch_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    with open("meta_drafts/ebay_batch_latest.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nSUMMARY {ok}/{len(results)}")
    for r in results:
        if r.get("ok"):
            print(f"  OK  {r['slug']} listing={r.get('listing_id')}")
        else:
            print(f"  ERR {r['slug']} {r.get('error')}")
    print("WROTE", path)
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
