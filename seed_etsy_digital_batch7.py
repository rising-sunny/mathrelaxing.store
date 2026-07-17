"""
seed_etsy_digital_batch7.py — Batch 3b: attractor prints + De Jong loop.

Assets recovered from VPS /var/www/mathrelaxing.store/static/ print files
(matching active Etsy listings).

  1. lorenz-attractor-print-set   $8.99  (Etsy 4528168404)
  2. clifford-attractor-print-set $8.99  (Etsy 4528164675)
  3. newton-fractal-print-set     $6.99  (Etsy 4528187340)
  4. de-jong-attractor-loop       $4.99  (Etsy 4528196710)

Run on VPS:
    python seed_etsy_digital_batch7.py --seed-only
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / "private_downloads"

PRODUCTS = [
    {
        "slug": "lorenz-attractor-print-set",
        "name": "Lorenz Attractor Art Print — 3 Color Variants",
        "product_type": "thematic_bundle",
        "collection": "digital-downloads",
        "equation_type": "lorenz",
        "description": (
            "Instant download — generative code art of the Lorenz strange attractor, "
            "the classic butterfly of chaos theory. Three curated colorways: classic, "
            "golden, and violet. High-resolution print files ready for home or print shop."
        ),
        "price_usd": 8.99,
        "filename": "lorenz-attractor-print-set.zip",
        "file_size": "32 MB",
        "contents_title": "Lorenz Attractor Print Set — 3 color variants (JPG)",
    },
    {
        "slug": "clifford-attractor-print-set",
        "name": "Clifford Attractor Art Print — 3 Color Variants",
        "product_type": "thematic_bundle",
        "collection": "digital-downloads",
        "equation_type": "clifford",
        "description": (
            "Instant download — generative code art from the Clifford attractor map. "
            "Three colorways: amber, earth, and forest. High-resolution print files "
            "for wall art, posters, and creative projects."
        ),
        "price_usd": 8.99,
        "filename": "clifford-attractor-print-set.zip",
        "file_size": "32 MB",
        "contents_title": "Clifford Attractor Print Set — 3 color variants (JPG)",
    },
    {
        "slug": "newton-fractal-print-set",
        "name": "Newton Fractal Art Print — 4 Root Variants",
        "product_type": "thematic_bundle",
        "collection": "digital-downloads",
        "equation_type": "newton",
        "description": (
            "Instant download — Newton-method fractals for polynomials of degree 3–6. "
            "Four high-resolution root-basin designs (z³, z⁴, z⁵, z⁶). Mathematical "
            "wall art for classrooms, offices, and collectors."
        ),
        "price_usd": 6.99,
        "filename": "newton-fractal-print-set.zip",
        "file_size": "11 MB",
        "contents_title": "Newton Fractal Print Set — 4 variants (JPG)",
    },
    {
        "slug": "de-jong-attractor-loop",
        "name": "De Jong Attractor Seamless Loop — Mathematical Animation",
        "product_type": "animation_pack",
        "collection": "digital-downloads",
        "equation_type": "de-jong",
        "description": (
            "Instant download — seamless loop animation of the Peter de Jong attractor. "
            "1080×1080 mathematical particle art, perfect for wallpapers, screensavers, "
            "digital frames, and ambient backgrounds."
        ),
        "price_usd": 4.99,
        "filename": "de-jong-attractor-loop.mp4",
        "file_size": "17 MB",
        "contents_title": "De Jong Attractor Loop — 1080p seamless MP4",
    },
]


def _fmt_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n} B"


def build_products() -> list[dict]:
    out = []
    for p in PRODUCTS:
        path = PRIVATE / p["filename"]
        size = _fmt_size(path.stat().st_size) if path.exists() else p["file_size"]
        out.append(
            {
                "slug": p["slug"],
                "name": p["name"],
                "product_type": p["product_type"],
                "collection": p["collection"],
                "equation_type": p["equation_type"],
                "description": p["description"],
                "price_usd": p["price_usd"],
                "contents_json": json.dumps(
                    [
                        {
                            "title": p["contents_title"],
                            "item_type": "file",
                            "filename": p["filename"],
                            "size": size,
                        }
                    ]
                ),
                "cover_image": f"/static/img/{p['slug']}_cover.jpg",
                "thumbnail_url": f"/static/previews/{p['slug']}.jpg",
                "file_url": f"private_downloads/{p['filename']}",
                "file_size": size,
                "license_type": "personal",
                "active": True,
            }
        )
    return out


def seed():
    from database import SessionLocal
    from models.product import DigitalProduct

    products = build_products()
    db = SessionLocal()
    try:
        for p_data in products:
            existing = db.query(DigitalProduct).filter_by(slug=p_data["slug"]).first()
            if existing:
                for k, v in p_data.items():
                    setattr(existing, k, v)
                action = "updated"
            else:
                db.add(DigitalProduct(**p_data))
                action = "created"
            print(f"  {action:8s}  {p_data['slug']:36s}  ${p_data['price_usd']:.2f}")
        db.commit()
    finally:
        db.close()
    print(f"Seed complete: {len(products)} products.")


def verify():
    ok = True
    for p in PRODUCTS:
        path = PRIVATE / p["filename"]
        cover = ROOT / "static" / "img" / f"{p['slug']}_cover.jpg"
        prev = ROOT / "static" / "previews" / f"{p['slug']}.jpg"
        gal = ROOT / "static" / "digital" / p["slug"]
        for label, path2 in [
            ("file", path),
            ("cover", cover),
            ("preview", prev),
        ]:
            ex = path2.exists()
            if not ex:
                ok = False
            print(f"  [{'OK' if ex else 'MISS':5s}] {label} {path2}")
        n = len(list(gal.iterdir())) if gal.exists() else 0
        if n == 0:
            ok = False
        print(f"  [{'OK' if n else 'EMPTY':5s}] gallery {p['slug']} ({n})")
    return ok


if __name__ == "__main__":
    if "--verify" in sys.argv:
        sys.exit(0 if verify() else 1)
    seed()
