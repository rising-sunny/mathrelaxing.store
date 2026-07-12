import sys

sys.path.insert(0, '/var/www/mathrelaxing.store')

from database import SessionLocal
from models.product import Product

def migrate():
    db = SessionLocal()
    try:
        # Get the original products
        p1 = db.query(Product).filter(Product.slug == "chladni-mandala").first()
        p2 = db.query(Product).filter(Product.slug == "aizawa-copper").first()

        for p in (p1, p2):
            if not p:
                continue
            new_slug = f"{p.slug}-notebook"
            existing = db.query(Product).filter(Product.slug == new_slug).first()
            if not existing:
                print(f"Creando {new_slug}...")
                new_p = Product(
                    slug=new_slug,
                    name=f"{p.name} Notebook",
                    collection="notebooks",
                    equation_type=p.equation_type,
                    description=f"Premium spiral notebook featuring the {p.name} design.",
                    params_json=p.params_json,
                    price_usd=24.99,
                    image_url=p.image_url,
                    active=True
                )
                db.add(new_p)
            else:
                print(f"{new_slug} ya existe.")
        
        db.commit()
        print("Migración completada.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
