#!/usr/bin/env python3
"""Publish active DigitalProducts that are not yet in .bonanza_products.json."""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/var/www/mathrelaxing.store")
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from database import SessionLocal
from models.product import DigitalProduct
from services import bonanza as B

BONANZA_IMG = ROOT / "static" / "bonanza"
REPORT = ROOT / f".bonanza_publish_missing_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
SLEEP = 0.5


def _local_path(url_or_path: str | None) -> Path | None:
    if not url_or_path:
        return None
    p = url_or_path
    if p.startswith("http://") or p.startswith("https://"):
        for prefix in (
            "https://mathrelaxing.store/",
            "http://mathrelaxing.store/",
            "https://www.mathrelaxing.store/",
        ):
            if p.startswith(prefix):
                p = "/" + p[len(prefix) :]
                break
        else:
            return None
    p = p.split("?", 1)[0]
    candidate = ROOT / p.lstrip("/")
    return candidate if candidate.is_file() else None


def ensure_image(product) -> tuple[bool, str]:
    BONANZA_IMG.mkdir(parents=True, exist_ok=True)
    dest = BONANZA_IMG / f"{product.slug}.jpg"
    if dest.is_file() and dest.stat().st_size > 1000:
        return True, f"exists:{dest.name}"

    candidates = [
        _local_path(getattr(product, "cover_image", None)),
        _local_path(getattr(product, "thumbnail_url", None)),
        ROOT / "static" / "previews" / f"{product.slug}_clean.jpg",
        ROOT / "static" / "previews" / f"{product.slug}.jpg",
        ROOT / "static" / "img" / f"{product.slug}_cover.jpg",
        ROOT / "static" / "img" / f"{product.slug}_cover.png",
        ROOT / "static" / "digital" / product.slug / "01_hero.jpg",
        ROOT / "static" / "digital" / product.slug / "01_listing.jpg",
    ]
    src = next((c for c in candidates if c and Path(c).is_file()), None)
    if not src:
        return False, "no_local_image"
    src = Path(src)
    try:
        if src.suffix.lower() in {".jpg", ".jpeg"}:
            shutil.copy2(src, dest)
            return True, f"copied:{src.name}"
        from PIL import Image

        im = Image.open(src).convert("RGB")
        im.thumbnail((1600, 1600))
        im.save(dest, "JPEG", quality=88, optimize=True)
        return True, f"converted:{src.name}"
    except Exception as e:
        return False, f"image_err:{e}"


async def publish_one(product) -> dict:
    ok_img, note_img = ensure_image(product)
    row = {
        "slug": product.slug,
        "name": product.name,
        "price_usd": product.price_usd,
        "image_ok": ok_img,
        "image_note": note_img,
    }
    if not ok_img:
        row["ok"] = False
        row["error"] = f"skip_no_image:{note_img}"
        return row
    try:
        result = await B.publish_product(product)
        row["ok"] = True
        row.update(result)
    except Exception as e:
        row["ok"] = False
        row["error"] = str(e)[:300]
        row["trace"] = traceback.format_exc()[-400:]
    return row


async def main():
    if not B.is_configured():
        print("Bonanza credentials not configured")
        sys.exit(1)

    token = await B.get_token_status()
    print("token:", json.dumps(token)[:200])

    db = SessionLocal()
    try:
        prods = db.query(DigitalProduct).filter(DigitalProduct.active == True).all()  # noqa: E712
        mapping = B._load_map()
        missing = [p for p in prods if p.slug not in mapping]
        print(f"active={len(prods)} mapped={len(mapping)} missing={len(missing)}")

        results = []
        for i, p in enumerate(sorted(missing, key=lambda x: x.slug), 1):
            print(f"\n[{i}/{len(missing)}] {p.slug} …", flush=True)
            row = await publish_one(p)
            results.append(row)
            if row.get("ok"):
                print(f"  OK item_id={row.get('item_id')} state={row.get('selling_state')} {row.get('listing_url')}")
            else:
                print(f"  FAIL {row.get('error')}")
            await asyncio.sleep(SLEEP)

        ok_n = sum(1 for r in results if r.get("ok"))
        fail_n = len(results) - ok_n
        report = {
            "when": datetime.now(timezone.utc).isoformat(),
            "token": token,
            "missing_before": len(missing),
            "ok": ok_n,
            "fail": fail_n,
            "results": results,
            "map_size_after": len(B._load_map()),
        }
        REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nDONE ok={ok_n} fail={fail_n} map={report['map_size_after']}")
        print("report", REPORT)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
