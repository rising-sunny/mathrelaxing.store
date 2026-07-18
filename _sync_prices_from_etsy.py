"""
Sync digital product prices from Etsy_mathrelaxing slash policy to web DB.

Source of truth: CATALOG_PRICES in Etsy_mathrelaxing/_slash_digital_prices.py
plus title/slug heuristics for web-only products.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "/var/www/mathrelaxing.store")
from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")

from database import SessionLocal
from models.product import DigitalProduct

# Etsy catalog key → web slug(s)
ETSY_TO_WEB: dict[str, list[str]] = {
    "schrodinger_equation_print": ["schrodinger-equation-print"],
    "unit_circle_print": ["unit-circle-poster"],
    "bauhaus_print_set": ["bauhaus-print-set"],
    "morris_botanical_print_set": [],  # may not exist on web yet
    "sage_neutral_print_set": [],
    "cs_poster_set": ["computer-science-poster-set"],
    "happy_chemicals_prints": ["happy-chemicals-print-set"],
    "reader_os_stickers": [],
    "fractal_flora_pdf": ["fractal-flora-coloring-book-digital"],
    "sacred_geometry_pdf": ["sacred-geometry-coloring-book-digital"],
    "hyperbolic_gardens_pdf": ["hyperbolic-gardens-digital"],
    "mathematical_tangle_art_pdf": ["mathematical-tangle-art-digital"],
    "sacred_harmonics_pdf": ["sacred-harmonics-digital"],
    "neural_network_pdf": ["neural-network-coloring-book-digital"],
    "voronoi_gardens_pdf": ["voronoi-gardens-coloring-book-digital"],
    "islamic_geometry_pdf": ["islamic-geometry-coloring-book-digital"],
    "celtic_knot_pdf": ["celtic-knot-coloring-book-digital"],
    "spiral_tilings_pdf": ["spiral-tilings-coloring-book-digital"],
    "fractal_flora_ipad": ["fractal-flora-ipad-coloring"],
    "sacred_geometry_ipad": ["sacred-geometry-ipad-coloring", "sacred-geometry-svg-ipad-interactive"],
    "islamic_geometry_ipad": ["islamic-geometry-ipad-bundle"],
    "celtic_knot_ipad": ["celtic-knot-ipad-bundle"],
    "voronoi_gardens_ipad": [
        "voronoi-gardens-ipad-coloring",
        "voronoi-gardens-ipad-interactive",
    ],
    "spiral_tilings_ipad": ["spiral-tilings-ipad-interactive"],
    "thomas_attractor": ["thomas-attractor-loop"],
    "julia_morph_01": ["julia-set-loop"],
    "voronoi_cell_garden": ["voronoi-cell-garden-loop"],
    "stem_focus_planner": ["stem-focus-planner-digital"],
    "stem_notebook": ["stem-notebook-digital", "stem-digital-notebook"],
    "stem_lab_notebook": ["stem-lab-notebook"],
    "quantified_self_planner": ["quantified-self-planner-digital"],
    "editorial_resume_kit": ["editorial-resume-kit"],
    "atelier_resume_kit": ["atelier-resume-kit"],
    "lor_template_pack": ["letter-of-recommendation-pack"],
    "emergency_binder": ["family-emergency-binder"],
    "geometric_wedding_suite": [],
}

# Explicit prices from Etsy slash script
CATALOG_PRICES: dict[str, float] = {
    "schrodinger_equation_print": 2.99,
    "unit_circle_print": 2.99,
    "bauhaus_print_set": 3.99,
    "morris_botanical_print_set": 3.99,
    "sage_neutral_print_set": 3.99,
    "cs_poster_set": 3.99,
    "happy_chemicals_prints": 3.99,
    "reader_os_stickers": 2.99,
    "fractal_flora_pdf": 2.99,
    "sacred_geometry_pdf": 2.99,
    "hyperbolic_gardens_pdf": 2.99,
    "mathematical_tangle_art_pdf": 2.99,
    "sacred_harmonics_pdf": 2.99,
    "neural_network_pdf": 2.99,
    "voronoi_gardens_pdf": 2.99,
    "islamic_geometry_pdf": 2.99,
    "celtic_knot_pdf": 2.99,
    "spiral_tilings_pdf": 2.99,
    "fractal_flora_ipad": 3.99,
    "sacred_geometry_ipad": 3.99,
    "islamic_geometry_ipad": 3.99,
    "celtic_knot_ipad": 3.99,
    "voronoi_gardens_ipad": 3.99,
    "spiral_tilings_ipad": 3.99,
    "thomas_attractor": 2.99,
    "julia_morph_01": 2.99,
    "voronoi_cell_garden": 2.99,
    "stem_focus_planner": 2.99,
    "stem_notebook": 2.99,
    "stem_lab_notebook": 2.99,
    "quantified_self_planner": 2.99,
    "editorial_resume_kit": 3.99,
    "atelier_resume_kit": 4.99,
    "lor_template_pack": 2.99,
    "emergency_binder": 3.99,
    "geometric_wedding_suite": 4.99,
}


def price_from_web_slug(slug: str, name: str, ptype: str, current: float) -> float:
    """Heuristic matching Etsy slash policy for web-only products."""
    t = f"{slug} {name} {ptype}".lower()

    if current <= 1.99 and current > 0:
        return current

    if "palette" in t:
        return 1.99
    if "atelier" in t:
        return 4.99
    if "wedding" in t or "seating" in t:
        return 4.99
    if "resume" in t or "cv" in t or "cover-letter" in t or "cover letter" in t:
        return 3.99
    if "print-set" in t or "poster-set" in t or "bundle" in t and "print" in t:
        return 3.99
    if "sticker" in t:
        return 2.99
    if "ipad" in t or "interactive" in t:
        return 3.99
    if "planner" in t or "notebook" in t:
        return 2.99 if "emergency" not in t else 3.99
    if "emergency" in t:
        return 3.99
    if "recommendation" in t or "letter-of" in t:
        return 2.99
    if "coloring" in t or "color-by" in t or "printable_pdf" in t:
        return 2.99
    if "loop" in t or "animation" in t:
        return 2.99
    if "poster" in t or "print" in t or "equation" in t:
        return 2.99
    if "geometric-cbn" in t or "cbn" in t:
        return 3.99

    # Attractors / print sets that remain
    if "attractor" in t or "harmonograph" in t or "vector-field" in t:
        return 3.99 if "set" in t or "print" in t else 2.99
    if "constants" in t or "equations" in t or "chemicals" in t:
        return 3.99
    if "golden-ratio" in t or "chladni" in t:
        return 2.99
    if "de-jong" in t:
        return 2.99

    if current >= 8.0:
        return 3.99
    if current >= 5.0:
        return 2.99
    if current >= 3.5:
        return 2.99
    return max(1.99, min(current, 2.99))


def main():
    # Build slug → target price from catalog mapping
    slug_price: dict[str, float] = {}
    for etsy_key, price in CATALOG_PRICES.items():
        for slug in ETSY_TO_WEB.get(etsy_key, []):
            slug_price[slug] = price

    db = SessionLocal()
    products = (
        db.query(DigitalProduct)
        .filter(DigitalProduct.active == True)
        .order_by(DigitalProduct.slug)
        .all()
    )

    print(f"active digital products: {len(products)}")
    print(f"mapped from etsy catalog: {len(slug_price)}")

    changes = []
    unchanged = []
    raised_blocked = []

    for p in products:
        old = float(p.price_usd or 0)
        if p.slug in slug_price:
            new = slug_price[p.slug]
            source = "etsy_catalog"
        else:
            new = price_from_web_slug(
                p.slug, p.name or "", p.product_type or "", old
            )
            source = "heuristic"

        # never raise (same as Etsy script)
        if new > old + 0.001:
            raised_blocked.append((p.slug, old, new, source))
            new = old
            source = "blocked_raise"

        if abs(new - old) < 0.001:
            unchanged.append((p.slug, old, source))
            continue

        p.price_usd = new
        changes.append((p.slug, old, new, source, p.name))

    db.commit()

    print("\n=== UPDATED ===")
    for slug, old, new, source, name in changes:
        print(f"  ${old:5.2f} → ${new:5.2f}  [{source:12s}]  {slug}")

    print(f"\nupdated={len(changes)} unchanged={len(unchanged)}")
    if raised_blocked:
        print("blocked raises (would have gone up):", len(raised_blocked))
        for row in raised_blocked[:10]:
            print(" ", row)

    # Final distribution
    prices = [float(p.price_usd) for p in products]
    prices.sort()
    print(
        f"\nfinal: min=${prices[0]:.2f} median=${prices[len(prices)//2]:.2f} "
        f"mean=${sum(prices)/len(prices):.2f} max=${prices[-1]:.2f}"
    )
    print("\nall products:")
    for p in sorted(products, key=lambda x: (-float(x.price_usd), x.slug)):
        print(f"  ${float(p.price_usd):5.2f}  {p.slug}")

    db.close()
    print("DONE")


if __name__ == "__main__":
    main()
