"""Publish digital coloring books + iPad editions to eBay (qty=1, fee-aware)."""
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

# Digital coloring books + iPad interactive/bundles (match Etsy STEM art coloring line)
COLORING_SLUGS = [
    # Printable PDF coloring books
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
    # iPad / interactive / GoodNotes bundles
    "celtic-knot-ipad-bundle",
    "fractal-flora-ipad-coloring",
    "geometric-cbn-ipad-interactive",
    "sacred-geometry-ipad-coloring",
    "sacred-geometry-svg-ipad-interactive",
    "spiral-tilings-ipad-interactive",
    "voronoi-gardens-ipad-coloring",
    "voronoi-gardens-ipad-interactive",
]


def ensure_gallery_from_zip(product: DigitalProduct) -> int:
    slug = product.slug
    out = ROOT / "static" / "ebay" / slug
    existing = list(out.glob("*.jpg")) + list(out.glob("*.png")) if out.is_dir() else []
    if len(existing) >= 4:
        return len(existing)

    candidates = []
    fu = (getattr(product, "file_url", None) or "").strip()
    if fu:
        candidates.append(ROOT / fu)
        candidates.append(ROOT / "private_downloads" / Path(fu).name)
    candidates.append(ROOT / "static" / "downloads" / f"{slug}.zip")
    candidates.append(ROOT / "private_downloads" / f"{slug}.zip")

    zpath = next((z for z in candidates if z.is_file()), None)
    if not zpath:
        return len(existing)

    # only real zips
    try:
        with zipfile.ZipFile(zpath) as z:
            names = [
                n
                for n in z.namelist()
                if n.lower().endswith((".jpg", ".jpeg", ".png"))
                and not n.startswith("__MACOSX")
                and "/." not in n
            ]
            if not names:
                return len(existing)
            out.mkdir(parents=True, exist_ok=True)

            def score(n: str):
                nl = n.lower()
                s = 0
                if "preview" in nl or "cover" in nl or "thumb" in nl:
                    s += 12
                if "page" in nl or "design" in nl:
                    s += 6
                if "a4" in nl or "letter" in nl:
                    s += 4
                if n.count("/") <= 1:
                    s += 2
                return (-s, len(n), n)

            names.sort(key=score)
            # diversify by folder
            seen_folder = set()
            picked = []
            for n in names:
                folder = Path(n).parts[0] if len(Path(n).parts) > 1 else "_"
                key = folder
                if key in seen_folder and len(picked) < 6:
                    # still allow a couple from same folder later
                    if sum(1 for p in picked if Path(p).parts[0] == folder) >= 2:
                        continue
                seen_folder.add(key)
                picked.append(n)
                if len(picked) >= 8:
                    break
            for i, n in enumerate(picked, 1):
                data = z.read(n)
                if len(data) < 2500:
                    continue
                ext = Path(n).suffix.lower() or ".jpg"
                if ext not in (".jpg", ".jpeg", ".png"):
                    ext = ".jpg"
                dest = out / f"{i:02d}_{Path(n).stem[:55]}{ext}"
                dest.write_bytes(data)
    except zipfile.BadZipFile:
        return len(existing)
    except Exception as e:
        print(f"  gallery warn {slug}: {e}")
        return len(existing)
    return len(list(out.glob("*.jpg")) + list(out.glob("*.png")))


async def publish_one(product: DigitalProduct) -> dict:
    st = await ebay.get_listing_status(product)
    if st.get("status") == "published":
        return {
            "slug": product.slug,
            "ok": True,
            "skipped": True,
            "listing_id": st.get("listing_id"),
            "list_price": ebay.price_for_product(product),
            "status": "published",
        }
    gallery_n = ensure_gallery_from_zip(product)
    imgs = ebay._listing_image_urls(product)
    if not imgs:
        return {"slug": product.slug, "ok": False, "error": "no_images"}
    r = await ebay.publish_product(product)
    after = await ebay.get_listing_status(product)
    return {
        "slug": product.slug,
        "ok": True,
        "skipped": False,
        "gallery": gallery_n,
        "images": len(imgs),
        "base_price": float(product.price_usd or 0),
        **r,
        **after,
    }


async def main():
    print("configured", ebay.is_configured(), "sku_qty", ebay._sku_quantity())
    print("limits", await ebay.get_selling_limits())

    db = SessionLocal()
    try:
        products = {
            p.slug: p
            for p in db.query(DigitalProduct)
            .filter(DigitalProduct.slug.in_(COLORING_SLUGS), DigitalProduct.active == True)
            .all()
        }
        print(f"matched {len(products)}/{len(COLORING_SLUGS)}")
        missing = [s for s in COLORING_SLUGS if s not in products]
        if missing:
            print("missing:", missing)

        # headroom check
        inv = await ebay._get("/sell/inventory/v1/inventory_item", {"limit": "100"})
        pub = 0
        for it in inv.get("inventoryItems") or []:
            offers = await ebay.get_offers_for_sku(it.get("sku"))
            if offers and offers[0].get("status") == "PUBLISHED":
                pub += 1
        lim = await ebay.get_selling_limits()
        max_q = int(lim.get("max_quantity") or 70)
        headroom = max_q - pub
        print(f"currently_published={pub} headroom≈{headroom}")
        if headroom < len(COLORING_SLUGS):
            print(f"NOTE: may hit limit; will stop before exceeding")

        results = []
        new_pub = 0
        for slug in COLORING_SLUGS:
            p = products.get(slug)
            if not p:
                continue
            if pub + new_pub >= max_q:
                print("STOP: selling limit quantity reached")
                break
            print(f"\n--- {slug} (${p.price_usd}) type={p.product_type} ---")
            try:
                r = await publish_one(p)
                results.append(r)
                if r.get("skipped"):
                    print(f"  SKIP live https://www.ebay.com/itm/{r.get('listing_id')} ${r.get('list_price')}")
                elif r.get("ok"):
                    new_pub += 1
                    print(
                        f"  OK ${r.get('list_price')} net~${r.get('est_net')} "
                        f"imgs={r.get('images')} gallery={r.get('gallery')} "
                        f"https://www.ebay.com/itm/{r.get('listing_id')}"
                    )
                else:
                    print(f"  FAIL {r}")
            except Exception as e:
                print(f"  ERROR {e}")
                results.append({"slug": slug, "ok": False, "error": str(e)[:300]})
            await asyncio.sleep(0.35)

        print("\n=== SUMMARY ===")
        ok = [r for r in results if r.get("ok") and not r.get("skipped")]
        skip = [r for r in results if r.get("skipped")]
        fail = [r for r in results if not r.get("ok")]
        print(f"new={len(ok)} skipped={len(skip)} failed={len(fail)}")
        for r in ok:
            print(f"  + {r['slug']} ${r.get('list_price')} https://www.ebay.com/itm/{r.get('listing_id')}")
        for r in fail:
            print(f"  x {r.get('slug')}: {r.get('error')}")

        # final count
        inv = await ebay._get("/sell/inventory/v1/inventory_item", {"limit": "100"})
        pub2 = 0
        for it in inv.get("inventoryItems") or []:
            offers = await ebay.get_offers_for_sku(it.get("sku"))
            if offers and offers[0].get("status") == "PUBLISHED":
                pub2 += 1
        print(f"\ntotal_published_now={pub2} / {max_q}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
