import sys
sys.path.append('/var/www/mathrelaxing.store')

from database import SessionLocal
from models.product import Product
from datetime import datetime

db = SessionLocal()
try:
    slug = "sacred-geometry-coloring-book"
    existing = db.query(Product).filter_by(slug=slug).first()
    if existing:
        print("Product already exists! Updating...")
        existing.name = "Sacred Geometry & Topology"
        existing.collection = "coloring-books"
        existing.description = """Immerse yourself in the world of mathematics. Every page in this book was generated using complex formulas and 3D modeling, bringing abstract concepts to life.

50 unique algorithmic structures, from Möbius Bands to Platonic Solids, rendered in a satisfying low-poly aesthetic. The mathematical engine pre-fills the smallest polygons automatically, ensuring a perfect colouring experience every time."""
        existing.price_usd = 14.99
        existing.status = "active"
        existing.is_active = True
        db.commit()
        print("Product updated successfully!")
    else:
        new_book = Product(
            slug=slug,
            name="Sacred Geometry & Topology",
            collection="coloring-books",
            description="""Immerse yourself in the world of mathematics. Every page in this book was generated using complex formulas and 3D modeling, bringing abstract concepts to life.

50 unique algorithmic structures, from Möbius Bands to Platonic Solids, rendered in a satisfying low-poly aesthetic. The mathematical engine pre-fills the smallest polygons automatically, ensuring a perfect colouring experience every time.""",
            price_usd=14.99,
            status="active",
            created_at=datetime.utcnow(),
            is_active=True
        )
        db.add(new_book)
        db.commit()
        print("Product added successfully!")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
