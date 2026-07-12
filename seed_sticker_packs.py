"""
Seed the 3 discounted sticker packs as POD products (collection="sticker-packs").

A pack is a single Product whose price lives in Product.price_usd and whose
member sticker slugs live in params_json["pack_members"]. On purchase,
services.printful.create_order fans the pack out into one Printful Kiss-Cut
line item per member design. The product page + checkout read the price from
the Product (see main.product_page and routers/orders).
"""
import json
from database import SessionLocal
from models.product import Product

PACKS = [
    ("math-essentials-sticker-pack", "Math Essentials Sticker Pack", 14.99,
     ["dejong-attractor-sticker", "pi-sticker", "infinity-sticker", "sierpinski-sticker"],
     "Our four most iconic math stickers in one discounted set: the De Jong attractor, π, infinity (the lemniscate), and the Sierpinski triangle. Four 3×3in kiss-cut vinyl stickers, shipped together."),
    ("theory-sticker-pack", "Theory Sticker Pack", 12.99,
     ["dejong-attractor-sticker", "lorenz-attractor-sticker", "golden-ratio-sticker"],
     "Three stickers for the chaos-and-order crowd: the De Jong and Lorenz strange attractors plus the golden ratio spiral. Three 3×3in kiss-cut vinyl stickers, shipped together."),
    ("icons-sticker-pack", "Icons Sticker Pack", 9.99,
     ["pi-sticker", "infinity-sticker"],
     "The two cleanest math icons — π and infinity — as a discounted pair. Two 3×3in kiss-cut vinyl stickers, shipped together."),
]


def seed_sticker_packs():
    db = SessionLocal()
    try:
        for old in db.query(Product).filter(Product.collection == "sticker-packs").all():
            db.delete(old)
        db.commit()

        for slug, name, price, members, desc in PACKS:
            db.add(Product(
                slug=slug,
                name=name,
                collection="sticker-packs",
                equation_type="sticker-pack",
                description=desc,
                params_json=json.dumps({
                    "pack_members": members,
                    "background_color": "#efece4",
                }),
                price_usd=price,
                background_color="#efece4",
                active=True,
            ))
            print(f"Created pack: {slug}  (${price}, {len(members)} stickers)")
        db.commit()
        print(f"\nSeeded {len(PACKS)} sticker packs (collection='sticker-packs').")
    finally:
        db.close()


if __name__ == "__main__":
    seed_sticker_packs()
