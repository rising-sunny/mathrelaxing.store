"""
Materialize static Bonanza POD images + revise all POD/book listings.

Root cause of "No photo available" on desk mats / apparel:
  _pod_image_urls falls back to /api/render/mockup?... which often fails
  Bonanza's image fetcher. Fix: save real JPEGs under static/bonanza/pod/
  then reviseFixedPriceItem with pictureURL pointing at those static files.
"""
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
from services.printful import FORMATS_BY_ID

ROOT = Path("/var/www/mathrelaxing.store")
POD_IMG = ROOT / "static" / "bonanza" / "pod"
BOOK_IMG = ROOT / "static" / "bonanza" / "book"
PUBLIC = os.getenv("PUBLIC_BASE_URL", "https://mathrelaxing.store").rstrip("/")
SLEEP = 0.45


def save_jpeg_bytes(data: bytes, dest: Path, min_edge: int = 600) -> int:
    im = Image.open(BytesIO(data)).convert("RGB")
    w, h = im.size
    if min(w, h) < min_edge:
        s = min_edge / min(w, h)
        im = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.Resampling.LANCZOS)
    im.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=90, optimize=True)
    return dest.stat().st_size


async def fetch_bytes(client: httpx.AsyncClient, url: str) -> bytes | None:
    try:
        r = await client.get(url, timeout=60)
        if r.status_code == 200 and len(r.content) > 2000:
            ct = (r.headers.get("content-type") or "").lower()
            if "image" in ct or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                return r.content
            # some endpoints return jpeg without perfect content-type
            if r.content[:3] == b"\xff\xd8\xff" or r.content[:8] == b"\x89PNG\r\n\x1a\n":
                return r.content
    except Exception as e:
        print(f"    fetch fail {url[:90]}: {e}")
    return None


def local_product_art(product: Product) -> Path | None:
    candidates = [
        Path(p) if p and not str(p).startswith("http") else None
        for p in [
            getattr(product, "image_url", None),
            getattr(product, "cover_image", None),
            getattr(product, "thumbnail_url", None),
        ]
    ]
    # normalize site-relative
    out: list[Path] = []
    for raw in (
        getattr(product, "image_url", None),
        getattr(product, "cover_image", None),
        getattr(product, "thumbnail_url", None),
        f"/static/img/{product.slug}_cover.jpg",
        f"/static/img/{product.slug}_cover.png",
        f"/static/previews/{product.slug}.jpg",
        f"/static/covers/{product.slug}.jpg",
    ):
        if not raw:
            continue
        s = str(raw)
        for pref in (
            "https://mathrelaxing.store/",
            "http://mathrelaxing.store/",
            "https://www.mathrelaxing.store/",
        ):
            if s.startswith(pref):
                s = "/" + s[len(pref) :]
        if s.startswith("http"):
            continue
        p = ROOT / s.lstrip("/")
        if p.is_file() and p.stat().st_size > 2000:
            out.append(p)
    return out[0] if out else None


async def materialize_pod_image(
    client: httpx.AsyncClient, product: Product, format_id: str
) -> tuple[bool, str]:
    dest = POD_IMG / f"{product.slug}-{format_id}.jpg"
    # Prefer mockup endpoint (flat product shot)
    mock_urls = [
        f"{PUBLIC}/api/render/mockup?product={product.slug}&format={format_id}-flat",
        f"{PUBLIC}/api/render/mockup?product={product.slug}&format={format_id}",
        f"{PUBLIC}/api/render/preview?product={product.slug}",
    ]
    for u in mock_urls:
        data = await fetch_bytes(client, u)
        if data:
            n = save_jpeg_bytes(data, dest)
            return True, f"mockup {n}b from {u.split('?')[0]}"

    art = local_product_art(product)
    if art:
        n = save_jpeg_bytes(art.read_bytes(), dest)
        return True, f"local_art {art.name} {n}b"

    return False, "no_source"


async def materialize_book_images(client: httpx.AsyncClient, product: Product) -> tuple[bool, str]:
    BOOK_IMG.mkdir(parents=True, exist_ok=True)
    # Prefer product-specific then shared book folder
    cover_dest = BOOK_IMG / f"{product.slug}_cover.jpg"
    generic = BOOK_IMG / "cover.jpg"
    art = local_product_art(product)
    notes = []
    if art:
        n = save_jpeg_bytes(art.read_bytes(), cover_dest)
        notes.append(f"cover {n}b")
        # also refresh generic if missing
        if not generic.is_file():
            save_jpeg_bytes(art.read_bytes(), generic)
    elif generic.is_file():
        save_jpeg_bytes(generic.read_bytes(), cover_dest)
        notes.append("cover from generic")
    else:
        # try preview
        data = await fetch_bytes(client, f"{PUBLIC}/api/render/preview?product={product.slug}")
        if data:
            n = save_jpeg_bytes(data, cover_dest)
            notes.append(f"preview {n}b")
        else:
            return False, "no_book_cover"

    # ensure shared cover.jpg exists for _book_image_urls default paths
    if cover_dest.is_file() and (not generic.is_file() or generic.stat().st_size < 2000):
        save_jpeg_bytes(cover_dest.read_bytes(), generic)

    return True, "; ".join(notes)


async def main():
    if not B.is_configured():
        raise SystemExit("Bonanza not configured")

    pod_map = B._load_pod_map()
    db = SessionLocal()
    print(f"pod_map entries={len(pod_map)}")

    # Group by slug → format_ids
    by_slug: dict[str, list[str]] = {}
    for key, meta in pod_map.items():
        if ":" not in key:
            continue
        slug, fid = key.split(":", 1)
        by_slug.setdefault(slug, []).append(fid)

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        print("\n=== MATERIALIZE IMAGES ===")
        img_report = []
        for slug, fids in sorted(by_slug.items()):
            product = db.query(Product).filter(Product.slug == slug).first()
            if not product:
                print(f"  DB MISS {slug}")
                img_report.append({"slug": slug, "ok": False, "error": "no_product"})
                continue
            for fid in fids:
                if fid == "book" or fid == B.BOOK_FORMAT_ID:
                    ok, note = await materialize_book_images(client, product)
                    # also put a pod-style alias for consistency
                    src = BOOK_IMG / f"{slug}_cover.jpg"
                    if src.is_file():
                        dest = POD_IMG / f"{slug}-book.jpg"
                        save_jpeg_bytes(src.read_bytes(), dest)
                else:
                    ok, note = await materialize_pod_image(client, product, fid)
                print(f"  {'OK' if ok else 'FAIL'} {slug}:{fid} — {note}")
                img_report.append({"slug": slug, "format": fid, "ok": ok, "note": note})
                await asyncio.sleep(0.15)

        # HTTP verify static paths
        print("\n=== HTTP VERIFY STATIC ===")
        bad = []
        for slug, fids in sorted(by_slug.items()):
            for fid in fids:
                if fid == "book":
                    url = f"{PUBLIC}/static/bonanza/book/{slug}_cover.jpg"
                    if not (BOOK_IMG / f"{slug}_cover.jpg").is_file():
                        url = f"{PUBLIC}/static/bonanza/book/cover.jpg"
                else:
                    url = f"{PUBLIC}/static/bonanza/pod/{slug}-{fid}.jpg"
                data = await fetch_bytes(client, url)
                ok = bool(data)
                print(f"  {'OK' if ok else 'BAD'} {url} ({len(data) if data else 0})")
                if not ok:
                    bad.append(url)

    # Patch _pod_image_urls usage by ensuring files exist — then revise
    print("\n=== REVISE POD LISTINGS ===")
    results = []
    items = sorted(pod_map.items())
    for i, (key, meta) in enumerate(items, 1):
        if ":" not in key:
            continue
        slug, fid = key.split(":", 1)
        product = db.query(Product).filter(Product.slug == slug).first()
        row = {"key": key, "item_id": meta.get("item_id"), "slug": slug, "format": fid}
        if not product:
            row.update({"ok": False, "error": "no_product"})
            results.append(row)
            print(f"[{i}/{len(items)}] SKIP no product {key}")
            continue
        try:
            if fid == "book" or fid == B.BOOK_FORMAT_ID:
                # ensure book payload sees product-specific cover via image_url if possible
                cover = BOOK_IMG / f"{slug}_cover.jpg"
                if cover.is_file():
                    # temporarily point image_url for payload
                    product.image_url = f"/static/bonanza/book/{slug}_cover.jpg"
                r = await B.publish_book(product)
            else:
                r = await B.publish_pod_product(product, fid)
            row.update({"ok": True, "state": r.get("selling_state"), "listing_url": r.get("listing_url")})
            # show which picture URLs were sent
            if fid == "book":
                pics = B._book_image_urls(product)
            else:
                pics = B._pod_image_urls(product, fid)
            row["pictures"] = pics
            print(f"[{i}/{len(items)}] OK {key} pics={len(pics)} state={r.get('selling_state')}")
            for u in pics[:2]:
                print(f"         {u}")
        except Exception as e:
            row.update({"ok": False, "error": str(e)[:350]})
            print(f"[{i}/{len(items)}] FAIL {key}: {e}")
        results.append(row)
        await asyncio.sleep(SLEEP)

    ok = sum(1 for r in results if r.get("ok"))
    report = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "images": img_report,
        "http_bad": bad,
        "ok": ok,
        "fail": len(results) - ok,
        "results": results,
    }
    out = ROOT / "meta_drafts" / (
        f"bonanza_fix_pod_images_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nDONE ok={ok}/{len(results)} http_bad={len(bad)} report={out}")
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
