"""
Publish curated math wall-art DigitalProducts to eBay.
- qty always 1 (selling limit)
- fee-aware list price via services.ebay.price_for_product
- multi-image: hero + static/ebay/{slug}/ if present; auto-extract A4s from ZIP when possible
"""
from __future__ import annotations

import asyncio
import os
import zipfile
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path("/var/www/mathrelaxing.store")
load_dotenv(ROOT / ".env")
os.chdir(ROOT)

from database import SessionLocal  # noqa: E402
from models.product import DigitalProduct  # noqa: E402
import services.ebay as ebay  # noqa: E402

# Etsy math-art digital wall art / posters / generative prints → store slugs
# (already-published bauhaus kept for status; publish skips if already PUBLISHED unless --force)
MATH_ART_SLUGS = [
    # High-traction on Etsy
    "famous-equations-print-set",
    "golden-ratio-poster",
    "unit-circle-poster",
    "euler-identity-poster",
    "chladni-figures-poster",
    "physics-calculus-equations-print-set",
    "mathematical-constants-bundle",
    "beautiful-equations-print-set",
    "mandelbrot-zoom-poster",
    "newton-fractal-print-set",
    "schrodinger-equation-print",
    "geometric-tilings-print-set",
    # Physics plate series
    "black-hole-poster",
    "fourier-series-poster",
    "maxwell-equations-poster",
    "harmonic-series-poster",
    "ulam-spiral-poster",
    # Generative / attractors
    "vector-field-print-set",
    "harmonograph-print-set",
    "clifford-attractor-print-set",
    "lorenz-attractor-print-set",
    "rossler-attractor-print-set",
    "de-jong-attractor-loop",
    "julia-set-loop",
    "thomas-attractor-loop",
    # Bundles also on Etsy
    "happy-chemicals-print-set",
    "computer-science-poster-set",
    "bauhaus-print-set",  # already live — verify only
]

# Soft cap: leave headroom under account qty limit of 70
MAX_NEW_PUBLISHES = 25


def ensure_gallery_from_zip(product: DigitalProduct) -> int:
    """If product has a downloadable ZIP with A4/preview JPGs, extract a few to static/ebay/{slug}/."""
    slug = product.slug
    out = ROOT / "static" / "ebay" / slug
    # already has gallery
    existing = list(out.glob("*.jpg")) + list(out.glob("*.png")) if out.is_dir() else []
    if len(existing) >= 3:
        return len(existing)

    zip_candidates = []
    fu = (getattr(product, "file_url", None) or "").strip()
    if fu:
        p = ROOT / fu if not fu.startswith("/") else ROOT / fu.lstrip("/")
        # private_downloads/...
        zip_candidates.append(ROOT / fu)
        zip_candidates.append(ROOT / "private_downloads" / Path(fu).name)
    zip_candidates.append(ROOT / "static" / "downloads" / f"{slug}.zip")
    zip_candidates.append(ROOT / "private_downloads" / f"{slug}.zip")

    zpath = next((z for z in zip_candidates if z.is_file()), None)
    if not zpath:
        return len(existing)

    out.mkdir(parents=True, exist_ok=True)
    added = 0
    with zipfile.ZipFile(zpath) as z:
        names = [
            n
            for n in z.namelist()
            if n.lower().endswith((".jpg", ".jpeg", ".png"))
            and not n.startswith("__MACOSX")
            and "/." not in n
        ]
        # Prefer A4 / medium / cover-like names
        def score(n: str) -> tuple:
            nl = n.lower()
            s = 0
            if "a4" in nl:
                s += 10
            if "preview" in nl or "cover" in nl:
                s += 8
            if "12x" in nl or "18x" in nl or "poster" in nl:
                s += 5
            if "thumb" in nl:
                s -= 5
            # smaller path depth first
            return (-s, n.count("/"), n)

        names.sort(key=score)
        # one per top-level folder if structure exists
        seen_folder = set()
        picked = []
        for n in names:
            parts = Path(n).parts
            folder = parts[0] if len(parts) > 1 else ""
            if folder and folder in seen_folder and "a4" not in n.lower():
                continue
            if folder:
                seen_folder.add(folder)
            picked.append(n)
            if len(picked) >= 8:
                break
        for i, n in enumerate(picked, 1):
            data = z.read(n)
            if len(data) < 3000:
                continue
            dest = out / f"{i:02d}_{Path(n).stem[:60]}.jpg"
            if not dest.suffix.lower() in (".jpg", ".jpeg", ".png"):
                dest = dest.with_suffix(".jpg")
            if dest.suffix.lower() == ".png":
                dest.write_bytes(data)
            else:
                dest.write_bytes(data)
            added += 1
    return len(list(out.glob("*.jpg")) + list(out.glob("*.png")))


async def publish_one(product: DigitalProduct, force: bool = False) -> dict:
    sku = f"mr-{product.slug}"
    status_before = await ebay.get_listing_status(product)
    if status_before.get("status") == "published" and not force:
        return {
            "slug": product.slug,
            "ok": True,
            "skipped": True,
            "reason": "already_published",
            **status_before,
            "list_price": ebay.price_for_product(product),
        }

    gallery_n = ensure_gallery_from_zip(product)
    images = ebay._listing_image_urls(product)
    if not images:
        return {"slug": product.slug, "ok": False, "error": "no_images"}

    result = await ebay.publish_product(product)
    after = await ebay.get_listing_status(product)
    return {
        "slug": product.slug,
        "ok": True,
        "skipped": False,
        "gallery_extracted": gallery_n,
        "images": len(images),
        "base_price": float(product.price_usd or 0),
        **result,
        **after,
    }


async def main():
    print("configured", ebay.is_configured())
    print("sku_qty", ebay._sku_quantity())
    limits = await ebay.get_selling_limits()
    print("limits", limits)

    db = SessionLocal()
    try:
        products = (
            db.query(DigitalProduct)
            .filter(DigitalProduct.slug.in_(MATH_ART_SLUGS), DigitalProduct.active == True)
            .all()
        )
        by_slug = {p.slug: p for p in products}
        print(f"matched_in_db {len(by_slug)} / {len(MATH_ART_SLUGS)}")
        missing = [s for s in MATH_ART_SLUGS if s not in by_slug]
        if missing:
            print("missing slugs:", missing)

        # status of currently published
        inv = await ebay._get("/sell/inventory/v1/inventory_item", {"limit": "100"})
        items = inv.get("inventoryItems") or []
        published = 0
        for it in items:
            sku = it.get("sku")
            offers = await ebay.get_offers_for_sku(sku)
            if offers and offers[0].get("status") == "PUBLISHED":
                published += 1
        print(f"currently_published_offers={published}")

        results = []
        new_count = 0
        for slug in MATH_ART_SLUGS:
            p = by_slug.get(slug)
            if not p:
                continue
            if new_count >= MAX_NEW_PUBLISHES:
                print(f"hit MAX_NEW_PUBLISHES={MAX_NEW_PUBLISHES}, stop")
                break
            print(f"\n--- {slug} (${p.price_usd}) ---")
            try:
                r = await publish_one(p)
                results.append(r)
                lid = r.get("listing_id")
                if r.get("skipped"):
                    print(f"  SKIP already live listing={lid} price={r.get('list_price')}")
                elif r.get("ok"):
                    new_count += 1 if not r.get("skipped") else 0
                    # recount new publishes
                    if r.get("status") == "published" or r.get("listing_id"):
                        print(
                            f"  OK listing={lid} list=${r.get('list_price')} "
                            f"net~${r.get('est_net')} imgs={r.get('images')} "
                            f"url=https://www.ebay.com/itm/{lid}"
                        )
                else:
                    print(f"  FAIL {r}")
            except Exception as e:
                print(f"  ERROR {e}")
                results.append({"slug": slug, "ok": False, "error": str(e)[:300]})
            await asyncio.sleep(0.4)

        print("\n=== SUMMARY ===")
        ok = [r for r in results if r.get("ok") and not r.get("skipped")]
        skip = [r for r in results if r.get("skipped")]
        fail = [r for r in results if not r.get("ok")]
        print(f"published_now={len(ok)} skipped={len(skip)} failed={len(fail)}")
        for r in ok:
            print(
                f"  + {r['slug']} ${r.get('list_price')} "
                f"https://www.ebay.com/itm/{r.get('listing_id')}"
            )
        for r in fail:
            print(f"  x {r.get('slug')}: {r.get('error')}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
