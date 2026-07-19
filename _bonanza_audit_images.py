"""Audit Bonanza digital listings for missing local/static images."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")
from dotenv import load_dotenv

load_dotenv(".env")

from database import SessionLocal
from models.product import DigitalProduct
from services import bonanza as B

BASE = Path("/var/www/mathrelaxing.store")
IMG_DIR = BASE / "static" / "bonanza"


def main():
    mapping = B._load_map()
    db = SessionLocal()
    products = (
        db.query(DigitalProduct)
        .filter(DigitalProduct.active == True)
        .order_by(DigitalProduct.slug)
        .all()
    )
    print(f"active={len(products)} mapped={len(mapping)} img_dir={IMG_DIR}")

    missing_file = []
    bad_url = []
    ok = []
    for p in products:
        entry = mapping.get(p.slug) or {}
        if not entry.get("item_id"):
            continue
        static = IMG_DIR / f"{p.slug}.jpg"
        url = B._listing_image_url(p)
        has_file = static.is_file() and static.stat().st_size > 500
        row = {
            "slug": p.slug,
            "item_id": entry.get("item_id"),
            "has_static": has_file,
            "static_bytes": static.stat().st_size if static.is_file() else 0,
            "url": url,
            "cover": getattr(p, "cover_image", None),
            "thumb": getattr(p, "thumbnail_url", None),
        }
        if has_file:
            ok.append(row)
        else:
            missing_file.append(row)
            if "lorenz-dream" in url or not url:
                bad_url.append(row)

    print(f"\nwith static jpg: {len(ok)}")
    print(f"missing static jpg: {len(missing_file)}")
    for r in missing_file:
        print(
            f"  MISS {r['slug']}\n"
            f"    cover={r['cover']}\n"
            f"    thumb={r['thumb']}\n"
            f"    resolved={r['url']}"
        )

    # also list files in img dir not matching products
    on_disk = {p.stem for p in IMG_DIR.glob("*.jpg")} if IMG_DIR.is_dir() else set()
    mapped_slugs = {s for s, e in mapping.items() if e.get("item_id")}
    orphan = sorted(on_disk - mapped_slugs)
    extra_needed = sorted(mapped_slugs - on_disk)
    print(f"\non_disk jpgs: {len(on_disk)}")
    print(f"mapped without disk file: {len(extra_needed)}")
    for s in extra_needed:
        print(" ", s)

    report = {
        "ok": len(ok),
        "missing": missing_file,
        "extra_needed": extra_needed,
    }
    out = BASE / "meta_drafts" / "bonanza_image_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", out)
    db.close()


if __name__ == "__main__":
    main()
