"""Finish remaining POD images + revise ALL pod map listings."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")
from dotenv import load_dotenv

load_dotenv(".env")

import httpx
from PIL import Image

from database import SessionLocal
from models.product import Product
from services import bonanza as B

ROOT = Path("/var/www/mathrelaxing.store")
POD_IMG = ROOT / "static" / "bonanza" / "pod"
BOOK_IMG = ROOT / "static" / "bonanza" / "book"
PUBLIC = "https://mathrelaxing.store"
SLEEP = 0.4


def save_jpeg(data: bytes, dest: Path) -> int:
    im = Image.open(BytesIO(data)).convert("RGB")
    w, h = im.size
    if min(w, h) < 600:
        s = 600 / min(w, h)
        im = im.resize((int(w * s), int(h * s)), Image.Resampling.LANCZOS)
    im.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=90, optimize=True)
    return dest.stat().st_size


async def fetch(client, url):
    try:
        r = await client.get(url, timeout=90)
        if r.status_code == 200 and len(r.content) > 2000:
            return r.content
    except Exception as e:
        print("  fetch err", url[:90], e)
    return None


async def ensure_image(client, product, fid):
    if fid == "book":
        dest = BOOK_IMG / f"{product.slug}_cover.jpg"
        BOOK_IMG.mkdir(parents=True, exist_ok=True)
        if dest.is_file() and dest.stat().st_size > 2000:
            return True, f"exists {dest.stat().st_size}"
        urls = [
            f"{PUBLIC}/api/render/preview?product={product.slug}",
            f"{PUBLIC}/api/render/mockup?product={product.slug}&format=book",
        ]
        for u in urls:
            data = await fetch(client, u)
            if data:
                n = save_jpeg(data, dest)
                # alias
                save_jpeg(data, POD_IMG / f"{product.slug}-book.jpg")
                if not (BOOK_IMG / "cover.jpg").is_file():
                    save_jpeg(data, BOOK_IMG / "cover.jpg")
                return True, f"book {n}"
        return False, "no book src"

    dest = POD_IMG / f"{product.slug}-{fid}.jpg"
    if dest.is_file() and dest.stat().st_size > 2000:
        return True, f"exists {dest.stat().st_size}"
    urls = [
        f"{PUBLIC}/api/render/mockup?product={product.slug}&format={fid}-flat",
        f"{PUBLIC}/api/render/mockup?product={product.slug}&format={fid}",
        f"{PUBLIC}/api/render/preview?product={product.slug}",
    ]
    for u in urls:
        data = await fetch(client, u)
        if data:
            n = save_jpeg(data, dest)
            return True, f"ok {n} {u.split('format=')[-1][:40]}"
    return False, "no src"


async def main():
    pod_map = B._load_pod_map()
    db = SessionLocal()
    print("pod entries", len(pod_map))

    async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
        print("=== ENSURE IMAGES ===")
        for key in sorted(pod_map):
            if ":" not in key:
                continue
            slug, fid = key.split(":", 1)
            p = db.query(Product).filter(Product.slug == slug).first()
            if not p:
                print("  no product", key)
                continue
            ok, note = await ensure_image(client, p, fid)
            print(f"  {'OK' if ok else 'FAIL'} {key}: {note}")
            await asyncio.sleep(0.1)

        # verify static http
        print("=== HTTP ===")
        for key in sorted(pod_map):
            if ":" not in key:
                continue
            slug, fid = key.split(":", 1)
            if fid == "book":
                path = BOOK_IMG / f"{slug}_cover.jpg"
                url = f"{PUBLIC}/static/bonanza/book/{slug}_cover.jpg"
                if not path.is_file():
                    url = f"{PUBLIC}/static/bonanza/book/cover.jpg"
            else:
                url = f"{PUBLIC}/static/bonanza/pod/{slug}-{fid}.jpg"
            data = await fetch(client, url)
            print(f"  {'OK' if data else 'BAD'} {key} {len(data or b'')}")

    print("=== REVISE ===")
    results = []
    items = sorted(pod_map.items())
    for i, (key, meta) in enumerate(items, 1):
        if ":" not in key:
            continue
        slug, fid = key.split(":", 1)
        p = db.query(Product).filter(Product.slug == slug).first()
        row = {"key": key, "item_id": meta.get("item_id")}
        if not p:
            row["ok"] = False
            row["error"] = "no product"
            results.append(row)
            continue
        try:
            if fid == "book":
                cover = BOOK_IMG / f"{slug}_cover.jpg"
                if cover.is_file():
                    p.image_url = f"/static/bonanza/book/{slug}_cover.jpg"
                r = await B.publish_book(p)
                pics = B._book_image_urls(p)
            else:
                r = await B.publish_pod_product(p, fid)
                pics = B._pod_image_urls(p, fid)
            row.update({"ok": True, "state": r.get("selling_state"), "pics": pics})
            print(f"[{i}/{len(items)}] OK {key} pics={len(pics)} {pics[0] if pics else ''}")
        except Exception as e:
            row.update({"ok": False, "error": str(e)[:300]})
            print(f"[{i}/{len(items)}] FAIL {key}: {e}")
        results.append(row)
        await asyncio.sleep(SLEEP)

    ok = sum(1 for r in results if r.get("ok"))
    out = ROOT / "meta_drafts" / f"bonanza_finish_pod_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"ok": ok, "total": len(results), "results": results}, indent=2), encoding="utf-8")
    print(f"DONE ok={ok}/{len(results)} report={out}")
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
