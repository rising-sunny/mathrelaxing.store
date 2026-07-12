import json
from database import SessionLocal
from models.product import Product

def seed_apparel_v2():
    db = SessionLocal()
    
    # We will delete the old "-apparel" products that were just copies of posters
    # and create new ones specifically designed for t-shirts.
    old_apparel = db.query(Product).filter(Product.collection == "apparel").all()
    for p in old_apparel:
        db.delete(p)
    db.commit()

    new_designs = [
        {
            "slug": "neon-aizawa-apparel",
            "name": "Neon Torus T-Shirt",
            "description": "Premium math-generated apparel. An ultra-dense Aizawa attractor rendered in glowing neon cyan and green, perfectly mapped for transparent printing on black cotton.",
            "collection": "apparel",
            "price_usd": 28.0,
            "equation_type": "aizawa",
            "params_json": json.dumps({
                "a": 0.95, "b": 0.7, "c": 0.6, "d": 3.5, "e": 0.25, "f": 0.1,
                "color_start": "#000000",
                "color_end": "#00ffcc",
                "background_color": "#000000"
            }),
            "active": True
        },
        {
            "slug": "golden-clifford-apparel",
            "name": "Golden Clifford T-Shirt",
            "description": "Premium math-generated apparel. The Clifford attractor calculated to millions of iterations, producing a golden gossamer structure.",
            "collection": "apparel",
            "price_usd": 28.0,
            "equation_type": "clifford",
            "params_json": json.dumps({
                "a": -1.4, "b": 1.6, "c": 1.0, "d": 0.7,
                "color_start": "#000000",
                "color_end": "#ffcc00",
                "background_color": "#000000"
            }),
            "active": True
        },
        {
            "slug": "sacred-harmonograph-apparel",
            "name": "Sacred Harmonograph T-Shirt",
            "description": "Premium math-generated apparel. A perfectly balanced 4-pendulum harmonograph creating a pristine geometric mandala.",
            "collection": "apparel",
            "price_usd": 28.0,
            "equation_type": "harmonograph",
            "params_json": json.dumps({
                "f1": 3.0, "f2": 3.0, "f3": 4.0, "f4": 4.0,
                "d1": 0.001, "d2": 0.001, "d3": 0.001, "d4": 0.001,
                "p1": 0.0, "p2": 1.57, "p3": 0.0, "p4": 1.57,
                "color_start": "#000000",
                "color_end": "#ffffff",
                "background_color": "#000000"
            }),
            "active": True
        },
        {
            "slug": "quantum-dejong-apparel",
            "name": "Quantum De Jong T-Shirt",
            "description": "Premium math-generated apparel. A chaotic Peter De Jong map rendered in vibrant pink and blue quantum interference patterns.",
            "collection": "apparel",
            "price_usd": 28.0,
            "equation_type": "de_jong",
            "params_json": json.dumps({
                "a": 1.641, "b": -1.902, "c": 0.316, "d": 1.525,
                "color_start": "#000000",
                "color_end": "#ff007f",
                "background_color": "#000000"
            }),
            "active": True
        }
    ]

    for data in new_designs:
        p = Product(**data)
        db.add(p)
        print(f"Created {p.slug}")

    db.commit()
    db.close()
    print("Apparel collection successfully updated with transparent-optimized designs.")

if __name__ == "__main__":
    seed_apparel_v2()
