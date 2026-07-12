"""
Seed the 7 math-art Kiss-Cut stickers as POD products (collection="stickers").

The artwork is NOT generated from an equation at request time — each sticker is a
pre-made static print file in /static/stickers/print/ (real-equation art exported
to Printful's 900×900 kiss-cut printfile). The product carries its print file in
params_json["print_image"]; routers/render.py serves it for /render/print and the
Printful mockup generator.
"""
import json
from database import SessionLocal
from models.product import Product

STICKERS = [
    ("01", "dejong-attractor-sticker", "De Jong Attractor Sticker", "#0d0d0d",
     "A real De Jong strange attractor — 11,000 iterated points of the map traced in cream on black. Durable matte kiss-cut vinyl, 3×3in."),
    ("02", "golden-ratio-sticker", "Golden Ratio Sticker", "#f4efe3",
     "The golden ratio drawn for real: whirling φ-rectangles and a true logarithmic spiral that grows by φ every quarter turn. Kiss-cut vinyl, 3×3in."),
    ("03", "pi-sticker", "Pi (π) Sticker", "#0d0d0d",
     "A clean vector π over the real digits of pi in neon. Matte kiss-cut vinyl, 3×3in."),
    ("04", "math-is-beautiful-sticker", "Math Is Beautiful Sticker", "#0d0d0d",
     "“Math is beautiful” with Euler's identity, e^{iπ}+1=0 — the most elegant equation in mathematics. Kiss-cut vinyl, 3×3in."),
    ("05", "infinity-sticker", "Infinity (∞) Sticker", "#0d0d0d",
     "Infinity as a real curve: the lemniscate of Bernoulli in gold. Matte kiss-cut vinyl, 3×3in."),
    ("06", "sierpinski-sticker", "Sierpinski Triangle Sticker", "#f4efe3",
     "The Sierpinski triangle by exact recursive subdivision — 243 self-similar triangles. Kiss-cut vinyl, 3×3in."),
    ("07", "lorenz-attractor-sticker", "Lorenz Attractor Sticker", "#0d0d0d",
     "The Lorenz attractor — the butterfly of chaos theory — integrated with RK4 (σ=10, ρ=28, β=8/3). Kiss-cut vinyl, 3×3in."),
]


def seed_stickers():
    db = SessionLocal()
    try:
        for old in db.query(Product).filter(Product.collection == "stickers").all():
            db.delete(old)
        db.commit()

        for num, slug, name, bg, desc in STICKERS:
            db.add(Product(
                slug=slug,
                name=name,
                collection="stickers",
                equation_type="sticker",
                description=desc,
                params_json=json.dumps({
                    "print_image": f"stickers/print/sticker-{num}.png",
                    "background_color": bg,
                }),
                price_usd=5.99,
                background_color=bg,
                active=True,
            ))
            print(f"Created sticker: {slug}")
        db.commit()
        print(f"\nSeeded {len(STICKERS)} stickers (collection='stickers').")
    finally:
        db.close()


if __name__ == "__main__":
    seed_stickers()
