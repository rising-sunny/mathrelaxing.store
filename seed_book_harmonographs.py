"""
seed_book_harmonographs.py — register the fourth physical coloring book as a Product.
"""

from database import SessionLocal, engine
from models.product import Base, Product

BOOK = {
    "slug":             "harmonograph-dreams-coloring-book",
    "name":             "Harmonograph Dreams — Coloring Book",
    "collection":       "coloring-book",
    "equation_type":    "harmonograph",
    "description":      (
        "A 54-page perfect-bound coloring book of 50 unique mathematical "
        "line-art designs based on the physical motion of coupled pendulums "
        "(harmonographs). Printed on demand on 60# "
        "(90gsm) uncoated white paper with a matte cover, and shipped from a "
        "local print facility. Free shipping."
    ),
    "params_json":      "{}",
    "price_usd":        24.99,
    "image_url":        "/static/img/harmonograph_dreams_cover.png",
    "background_color": "#1a1226", # Deep Purple
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
