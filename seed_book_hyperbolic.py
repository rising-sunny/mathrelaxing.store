"""
seed_book_hyperbolic.py — register the "Hyperbolic Gardens" coloring book as a
Product (idempotent).

Run once:  cd /var/www/mathrelaxing.store && python3 seed_book_hyperbolic.py

The startup _seed_products() loop only touches products coming from
get_seed_products(), so this row is left untouched across restarts.

Print files (interior/cover/title) are resolved per-slug in services/lulu.py
(BOOK_PRINT_FILES). The interior + cover live under
static/downloads/hyperbolic-gardens/.
"""

from database import SessionLocal, engine
from models.product import Base, Product

BOOK = {
    "slug":             "hyperbolic-gardens-coloring-book",
    "name":             "Hyperbolic Gardens — Coloring Book",
    "collection":       "coloring-book",
    "equation_type":    "mixed",
    "description":      (
        "A 54-page perfect-bound coloring book of 50 hyperbolic tilings — "
        "Escher-style Circle Limit patterns drawn on the Poincaré disk. Each "
        "design packs infinitely many identical shapes into a single circle, "
        "growing ever smaller toward the rim, so there is always more to color. "
        "Printed on demand on 60# (90gsm) uncoated white paper with a matte "
        "cover, and shipped from a local print facility. Free shipping."
    ),
    "params_json":      "{}",
    "price_usd":        14.99,
    "image_url":        "/static/img/hyperbolic_gardens_cover.png",
    "background_color": "#1F1834",
    "active":           True,
}


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        row = db.query(Product).filter(Product.slug == BOOK["slug"]).first()
        if row:
            for k, v in BOOK.items():
                setattr(row, k, v)
            action = "updated"
        else:
            db.add(Product(**BOOK))
            action = "created"
        db.commit()
        print(f"book product {action}: {BOOK['slug']} (${BOOK['price_usd']})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
