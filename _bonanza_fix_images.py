"""
Rebuild static/bonanza/{slug}.jpg for every mapped digital product
from the best local cover/preview, then revise listings (pictureURL).
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

ROOT = Path("/var/www/mathrelaxing.store")
BONANZA_IMG = ROOT / "static" / "bonanza"
SLEEP = 0.4


def _local_path(url_or_path: str | None) -> Path | None:
    if not url_or_path:
        return None
    p = url_or_path
    for prefix in (
        "https://mathrelaxing.store/",
        "http://mathrelaxing.store/",
        "https://www.mathrelaxing.store/",
    ):
        if p.startswith(prefix):
            p = "/" + p[len(prefix) :]
            break
    if p.startswith("http://") or p.startswith("https://"):
        return None
    p = p.split("?", 1)[0]
    candidate = ROOT / p.lstrip("/") if p.startswith("/") else ROOT / p
    return candidate if candidate.is_file() else None


def best_source(product) -> Path | None:
    candidates: list[Path | None] = [
        _local_path(getattr(product, "cover_image", None)),
        _local_path(getattr(product, "thumbnail_url", None)),
        ROOT / "static" / "img" / f"{product.slug}_cover.jpg",
        ROOT / "static" / "img" / f"{product.slug}_cover.png",
        ROOT / "static" / "digital" / product.slug / "01_hero.jpg",
        ROOT / "static" / "previews" / f"{product.slug}_clean.jpg",
        ROOT / "static" / "previews" / f"{product.slug}.jpg",
        ROOT / "static" / "covers" / f"{product.slug}.jpg",
    ]
    dig = ROOT / "static" / "digital" / product.slug
    if dig.is_dir():
        candidates.extend(sorted(dig.glob("*.jpg"))[:5])

    special = {
        "hyperbolic-gardens-digital": [ROOT / "static" / "img" / "hyperbolic_gardens_cover.png"],
        "fractal-flora-coloring-book-digital": [ROOT / "static" / "img" / "fractal_flora_cover.jpg"],
        "sacred-harmonics-digital": [ROOT / "static" / "img" / "sacred_harmonics_cover.png"],
        "mathematical-tangle-art-digital": [ROOT / "static" / "img" / "book_cover.png"],
        "bauhaus-print-set": [
            ROOT / "static" / "img" / "bauhaus-print-set_cover.jpg",
            ROOT / "static" / "digital" / "bauhaus-print-set" / "01_hero.jpg",
        ],
    }
    for extra in special.get(product.slug, []):
        candidates.insert(0, extra)

    best = None
    best_size = 0
    for c in candidates:
        if not c or not Path(c).is_file():
            continue
        sz = Path(c).stat().st_size
        if sz > best_size:
            best, best_size = Path(c), sz
    return best if best_size > 1500 else None


def write_bonanza_jpg(src: Path, dest: Path) -> int:
    from PIL import Image

    im = Image.open(src).convert("RGB")
    w, h = im.size
    if min(w, h) < 600:
        s = 600 / min(w, h)
        im = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.Resampling.LANCZOS)
    im.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=90, optimize=True)
    return dest.stat().st_size


async def http_check(url: str) -> tuple[bool, str]:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            r = await client.get(url)
            ct = (r.headers.get("content-type") or "").lower()
            ok = r.status_code == 200 and "image" in ct and len(r.content) > 2000
            return ok, f"http={r.status_code} ct={ct.split(';')[0]} bytes={len(r.content)}"
    except Exception as e:
        return False, str(e)[:160]


async def main():
    if not B.is_configured():
        raise SystemExit("Bonanza not configured")

    mapping = B._load_map()
    db = SessionLocal()
    products = (
        db.query(DigitalProduct)
        .filter(DigitalProduct.active == True)
        .order_by(DigitalProduct.slug)
        .all()
    )
    listed = [p for p in products if (mapping.get(p.slug) or {}).get("item_id")]
    print(f"active={len(products)} listed={len(listed)}")

    print("\n=== REBUILD IMAGES ===")
    rebuilt, no_src = [], []
    for p in listed:
        dest = BONANZA_IMG / f"{p.slug}.jpg"
        src = best_source(p)
        if not src:
            no_src.append(p.slug)
            print(f"  NO_SRC {p.slug} (keep {dest.stat().st_size if dest.is_file() else 0}b)")
            continue
        try:
            n = write_bonanza_jpg(src, dest)
            rebuilt.append(p.slug)
            print(f"  OK {p.slug} <- {src.name} ({n} bytes)")
        except Exception as e:
            print(f"  FAIL {p.slug}: {e}")

    print(f"\nrebuilt={len(rebuilt)} no_src={len(no_src)}")

    print("\n=== HTTP CHECK ===")
    http_bad = []
    for p in listed:
        url = B._listing_image_url(p)
        ok, note = await http_check(url)
        mark = "OK" if ok else "BAD"
        print(f"  {mark} {p.slug}: {note}")
        if not ok:
            http_bad.append({"slug": p.slug, "url": url, "note": note})
        await asyncio.sleep(0.03)

    print(f"\nhttp_bad={len(http_bad)}")

    print("\n=== REVISE BONANZA LISTINGS ===")
    results = []
    for i, p in enumerate(listed, 1):
        url = B._listing_image_url(p)
        row = {"slug": p.slug, "image": url, "item_id": (mapping.get(p.slug) or {}).get("item_id")}
        try:
            r = await B.publish_product(p)
            row.update({"ok": True, "state": r.get("selling_state")})
            print(f"[{i}/{len(listed)}] OK {p.slug}")
        except Exception as e:
            row.update({"ok": False, "error": str(e)[:300]})
            print(f"[{i}/{len(listed)}] FAIL {p.slug}: {e}")
        results.append(row)
        await asyncio.sleep(SLEEP)

    ok = sum(1 for r in results if r.get("ok"))
    report = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "rebuilt": len(rebuilt),
        "no_src": no_src,
        "http_bad": http_bad,
        "ok": ok,
        "fail": len(results) - ok,
        "results": results,
    }
    out = ROOT / "meta_drafts" / (
        f"bonanza_fix_images_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nDONE revise_ok={ok}/{len(results)} http_bad={len(http_bad)} report={out}")
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
