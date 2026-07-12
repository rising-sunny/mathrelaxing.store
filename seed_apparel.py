from database import SessionLocal
from models.product import Product

def seed_apparel():
    db = SessionLocal()
    slugs = [
        "aizawa-copper",
        "chladni-mandala-5",
        "clifford-attractor-1",
        "poincare-disk-1",
        "fibonacci-spiral-1",
        "gray-scott-coral",
        "voronoi-cells-1",
        "fractal-flame-1",
        "turing-spots",
        "harmonograph-1"
    ]

    for slug in slugs:
        orig = db.query(Product).filter(Product.slug == slug).first()
        if not orig:
            print(f"Original {slug} not found.")
            continue
        
        new_slug = slug + "-apparel"
        existing = db.query(Product).filter(Product.slug == new_slug).first()
        if existing:
            print(f"{new_slug} already exists.")
            continue
            
        print(f"Creating {new_slug}...")
        new_p = Product(
            slug=new_slug,
            name=orig.name.replace("Art Print", "").strip() + " T-Shirt",
            description="Premium math-generated apparel. " + orig.description,
            collection="apparel",
            price_usd=28.0,
            equation_type=orig.equation_type,
            params_json=orig.params_json,
            active=True
        )
        db.add(new_p)

    db.commit()
    db.close()
    print("Done seeding apparel.")

if __name__ == "__main__":
    seed_apparel()
