"""
Revise Bonanza digital listings so prices match the web/Etsy slash.

Uses services.bonanza.price_for_product (gross-up for Bonanza fee + $0.25 txn)
and publish_product → reviseFixedPriceItemRequest for already-mapped items.

POD / physical books are NOT touched (different pricing model).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from dotenv import load_dotenv

load_dotenv(".env")

from database import SessionLocal
from models.product import DigitalProduct
from services import bonanza as B

SLEEP = 0.4
REPORT = Path("/var/www/mathrelaxing.store/meta_drafts") / (
    f"bonanza_price_sync_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
)


async def main():
    if not B.is_configured():
        raise SystemExit("Bonanza credentials not configured")

    mapping = B._load_map()
    db = SessionLocal()
    products = (
        db.query(DigitalProduct)
        .filter(DigitalProduct.active == True)
        .order_by(DigitalProduct.slug)
        .all()
    )

    listed = []
    skipped = []
    for p in products:
        entry = mapping.get(p.slug) or {}
        if entry.get("item_id"):
            listed.append(p)
        else:
            skipped.append(p.slug)

    print(f"active digital={len(products)} already mapped={len(listed)} not_mapped={len(skipped)}")
    if skipped:
        print("not mapped (skip):", ", ".join(skipped[:20]), ("..." if len(skipped) > 20 else ""))

    print("\n=== PLAN (store → Bonanza list price) ===")
    for p in listed:
        base = float(p.price_usd)
        bz = B.price_for_product(p)
        print(f"  store ${base:5.2f} → bonanza ${bz:5.2f}  {p.slug}")

    results = []
    for i, p in enumerate(listed, 1):
        base = float(p.price_usd)
        bz = B.price_for_product(p)
        row = {
            "slug": p.slug,
            "store_price": base,
            "bonanza_price": bz,
            "item_id": (mapping.get(p.slug) or {}).get("item_id"),
        }
        try:
            r = await B.publish_product(p)
            row.update(
                {
                    "ok": True,
                    "selling_state": r.get("selling_state"),
                    "listing_url": r.get("listing_url"),
                    "item_id": r.get("item_id"),
                }
            )
            print(
                f"[{i}/{len(listed)}] OK  ${base:.2f}→${bz:.2f}  "
                f"state={r.get('selling_state')}  {p.slug}"
            )
        except Exception as e:
            row.update({"ok": False, "error": str(e)[:400]})
            print(f"[{i}/{len(listed)}] FAIL {p.slug}: {e}")
        results.append(row)
        await asyncio.sleep(SLEEP)

    ok = sum(1 for r in results if r.get("ok"))
    fail = [r for r in results if not r.get("ok")]
    prices = [r["bonanza_price"] for r in results if r.get("ok")]
    report = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "fail": len(fail),
        "mapped": len(listed),
        "not_mapped": skipped,
        "fee_rate": B.FEE_RATE,
        "transaction_fee": B.TRANSACTION_FEE,
        "bonanza_price_min": min(prices) if prices else None,
        "bonanza_price_max": max(prices) if prices else None,
        "results": results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nDONE ok={ok} fail={len(fail)} report={REPORT}")
    if fail:
        print("FAILURES:")
        for r in fail:
            print(f"  {r['slug']}: {r.get('error')}")
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
