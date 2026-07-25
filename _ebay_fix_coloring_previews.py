"""
Build multi-page previews for coloring book / iPad listings and push to eBay inventory.
Sources (in order):
  1. static/previews/{slug}_N.jpg / _N_clean.jpg (already generated)
  2. PDF page renders via pdftoppm (from product file_url / private_downloads)
  3. ZIP: PNGs, or PDFs inside ZIP rendered
  4. Hero covers (bonanza/previews/img)
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path("/var/www/mathrelaxing.store")
load_dotenv(ROOT / ".env")
os.chdir(ROOT)

from database import SessionLocal  # noqa: E402
from models.product import DigitalProduct  # noqa: E402
import services.ebay as ebay  # noqa: E402

COLORING_SLUGS = [
    "celtic-knot-coloring-book-digital",
    "fractal-flora-coloring-book-digital",
    "hyperbolic-gardens-digital",
    "islamic-geometry-coloring-book-digital",
    "mathematical-tangle-art-digital",
    "neural-network-coloring-book-digital",
    "sacred-geometry-coloring-book-digital",
    "sacred-harmonics-digital",
    "spiral-tilings-coloring-book-digital",
    "voronoi-gardens-coloring-book-digital",
    "celtic-knot-ipad-bundle",
    "fractal-flora-ipad-coloring",
    "geometric-cbn-ipad-interactive",
    "sacred-geometry-ipad-coloring",
    "sacred-geometry-svg-ipad-interactive",
    "spiral-tilings-ipad-interactive",
    "voronoi-gardens-ipad-coloring",
    "voronoi-gardens-ipad-interactive",
]

MAX_GALLERY = 10  # eBay gallery room; leave slot for hero


def resolve_file(product: DigitalProduct) -> Path | None:
    cands = []
    fu = (product.file_url or "").strip()
    if fu:
        cands.append(ROOT / fu.lstrip("/"))
        cands.append(ROOT / "private_downloads" / Path(fu).name)
        cands.append(ROOT / "static" / "downloads" / Path(fu).name)
    slug = product.slug
    cands += [
        ROOT / "static" / "downloads" / f"{slug}.zip",
        ROOT / "static" / "downloads" / f"{slug}.pdf",
        ROOT / "private_downloads" / f"{slug}.zip",
        ROOT / "private_downloads" / f"{slug}.pdf",
    ]
    # known alternate names
    alt = {
        "celtic-knot-coloring-book-digital": ["celtic_knot_digital.pdf"],
        "islamic-geometry-coloring-book-digital": ["islamic_geometry_digital.pdf"],
        "neural-network-coloring-book-digital": ["neural_network_digital.pdf"],
        "spiral-tilings-coloring-book-digital": ["spiral_tilings_digital.pdf"],
        "voronoi-gardens-coloring-book-digital": ["voronoi_gardens_digital.pdf"],
    }
    for name in alt.get(slug, []):
        cands.append(ROOT / "static" / "downloads" / name)
        cands.append(ROOT / "private_downloads" / name)
    for c in cands:
        if c.is_file() and c.stat().st_size > 1000:
            return c
    return None


def collect_existing_numbered(slug: str) -> list[Path]:
    prev = ROOT / "static" / "previews"
    found = []
    # prefer clean page previews
    for pattern in (f"{slug}_*_clean.jpg", f"{slug}_*.jpg"):
        for p in sorted(prev.glob(pattern)):
            name = p.name
            # skip base slug.jpg and slug_clean.jpg
            stem = p.stem
            if stem in (slug, f"{slug}_clean"):
                continue
            # accept slug_0, slug_0_clean, slug_page1, etc.
            found.append(p)
        if found:
            break
    # dedupe by page index preferring clean
    by_key: dict[str, Path] = {}
    for p in found:
        key = p.stem.replace("_clean", "")
        if key not in by_key or "_clean" in p.stem:
            by_key[key] = p
    return [by_key[k] for k in sorted(by_key.keys())][:MAX_GALLERY]


def pdftoppm_pages(pdf: Path, out_dir: Path, prefix: str, max_pages: int = 8) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    # clear old renders for this prefix
    for old in out_dir.glob(f"{prefix}-*"):
        old.unlink(missing_ok=True)
    cmd = [
        "pdftoppm",
        "-jpeg",
        "-r",
        "120",
        "-f",
        "1",
        "-l",
        str(max_pages),
        str(pdf),
        str(out_dir / prefix),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    pages = sorted(out_dir.glob(f"{prefix}-*.jpg"))
    return pages


def extract_from_zip(zpath: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    produced: list[Path] = []
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        with zipfile.ZipFile(zpath) as zf:
            # 1) PNGs / JPGs
            imgs = [
                n
                for n in zf.namelist()
                if n.lower().endswith((".png", ".jpg", ".jpeg"))
                and not n.startswith("__MACOSX")
            ]
            imgs.sort()
            for i, n in enumerate(imgs[:MAX_GALLERY], 1):
                data = zf.read(n)
                if len(data) < 2000:
                    continue
                ext = Path(n).suffix.lower()
                dest = out_dir / f"{i:02d}_{Path(n).stem[:50]}{ext}"
                dest.write_bytes(data)
                produced.append(dest)
            if len(produced) >= 4:
                return produced[:MAX_GALLERY]

            # 2) PDFs inside zip (GoodNotes packs)
            pdfs = [
                n
                for n in zf.namelist()
                if n.lower().endswith(".pdf")
                and "how_to" not in n.lower()
                and "readme" not in n.lower()
                and not n.startswith("__MACOSX")
            ]
            for n in pdfs[:1]:
                pdf_path = td_path / Path(n).name
                pdf_path.write_bytes(zf.read(n))
                pages = pdftoppm_pages(pdf_path, out_dir, "page", max_pages=MAX_GALLERY)
                produced.extend(pages)
    return produced[:MAX_GALLERY]


def build_gallery(product: DigitalProduct) -> list[str]:
    """Return public image URLs (hero first, then pages). Writes to static/ebay/{slug}/."""
    slug = product.slug
    out = ROOT / "static" / "ebay" / slug
    out.mkdir(parents=True, exist_ok=True)

    urls: list[str] = []
    seen: set[str] = set()

    def add_path(path: Path) -> None:
        if not path.is_file() or path.stat().st_size < 1500:
            return
        # copy into static/ebay for stable URLs if not already there
        if out not in path.parents and path.parent != out:
            dest = out / path.name
            if not dest.exists() or dest.stat().st_size != path.stat().st_size:
                shutil.copy2(path, dest)
            path = dest
        rel = path.relative_to(ROOT).as_posix()
        url = f"https://mathrelaxing.store/{rel}"
        if url not in seen:
            seen.add(url)
            urls.append(url)

    # Heroes first
    for rel in (
        f"static/bonanza/{slug}.jpg",
        f"static/previews/{slug}.jpg",
        f"static/img/{slug}_cover.jpg",
        f"static/previews/{slug}_clean.jpg",
    ):
        add_path(ROOT / rel)
    for attr in ("cover_image", "thumbnail_url"):
        val = (getattr(product, attr, None) or "").split("?", 1)[0]
        if val.startswith("/static/"):
            add_path(ROOT / val.lstrip("/"))

    # Existing numbered previews
    for p in collect_existing_numbered(slug):
        add_path(p)
        if len(urls) >= MAX_GALLERY + 2:
            break

    # Generate from deliverable if still thin
    if len(urls) < 5:
        src = resolve_file(product)
        print(f"  source_file={src}")
        if src:
            try:
                if src.suffix.lower() == ".pdf":
                    pages = pdftoppm_pages(src, out, "page", max_pages=8)
                    for p in pages:
                        add_path(p)
                elif src.suffix.lower() == ".zip":
                    pages = extract_from_zip(src, out)
                    for p in pages:
                        add_path(p)
            except Exception as e:
                print(f"  render error: {e}")

    # Also pick any already in static/ebay
    for p in sorted(out.glob("*.jpg")) + sorted(out.glob("*.png")):
        add_path(p)
        if len(urls) >= 12:
            break

    return urls[:12]


async def push_images(product: DigitalProduct, image_urls: list[str]) -> dict:
    sku = f"mr-{product.slug}"
    if not image_urls:
        return {"slug": product.slug, "ok": False, "error": "no images"}

    # Read current inventory item to preserve title/description/aspects
    try:
        inv = await ebay._get(f"/sell/inventory/v1/inventory_item/{sku}")
    except Exception:
        inv = {}
    product_block = inv.get("product") or {}
    title = product_block.get("title") or ebay._safe_title(product)
    description = product_block.get("description") or ebay._product_description(product)
    aspects = product_block.get("aspects") or {
        "Format": ["Digital Download"],
        "File Type": ["PDF/ZIP/JPG"],
        "Subject": ["Mathematical Art", "Abstract"],
        "Style": ["Abstract", "Digital Art"],
    }
    qty = ebay._sku_quantity()

    await ebay._put(
        f"/sell/inventory/v1/inventory_item/{sku}",
        {
            "product": {
                "title": title,
                "description": description,
                "aspects": aspects,
                "imageUrls": image_urls,
            },
            "condition": "NEW",
            "availability": {
                "shipToLocationAvailability": {"quantity": qty},
            },
        },
    )
    # verify
    inv2 = await ebay._get(f"/sell/inventory/v1/inventory_item/{sku}")
    n = len((inv2.get("product") or {}).get("imageUrls") or [])
    st = await ebay.get_listing_status(product)
    return {
        "slug": product.slug,
        "ok": True,
        "images": n,
        "listing_id": st.get("listing_id"),
        "status": st.get("status"),
    }


async def main():
    print("configured", ebay.is_configured())
    db = SessionLocal()
    try:
        products = {
            p.slug: p
            for p in db.query(DigitalProduct)
            .filter(DigitalProduct.slug.in_(COLORING_SLUGS))
            .all()
        }
        results = []
        for slug in COLORING_SLUGS:
            p = products.get(slug)
            print(f"\n=== {slug} ===")
            if not p:
                print("  missing product")
                continue
            urls = build_gallery(p)
            print(f"  gallery_urls={len(urls)}")
            for u in urls:
                print(f"    {u}")
            try:
                r = await push_images(p, urls)
                results.append(r)
                print(f"  pushed images={r.get('images')} listing={r.get('listing_id')} status={r.get('status')}")
            except Exception as e:
                print(f"  FAIL {e}")
                results.append({"slug": slug, "ok": False, "error": str(e)[:250]})
            await asyncio.sleep(0.3)

        print("\n=== SUMMARY ===")
        for r in results:
            if r.get("ok"):
                print(f"  OK {r['slug']}: {r.get('images')} imgs https://www.ebay.com/itm/{r.get('listing_id')}")
            else:
                print(f"  x  {r.get('slug')}: {r.get('error')}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
