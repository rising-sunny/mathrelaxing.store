import asyncio
import sys

sys.path.insert(0, '/var/www/mathrelaxing.store')

from database import SessionLocal
from models.product import Product
from services.bonanza import publish_pod_product

async def main():
    db = SessionLocal()
    # Let's get the Chladni Mandala and Aizawa Copper products
    p1 = db.query(Product).filter(Product.slug == "chladni-mandala").first()
    p2 = db.query(Product).filter(Product.slug == "aizawa-copper").first()
    
    if not p1 or not p2:
        print("No se encontraron los productos.")
        return
        
    print(f"Publicando {p1.name} en formato Notebook...")
    try:
        res1 = await publish_pod_product(p1, "spiral_notebook")
        print(f"Éxito p1: {res1}")
    except Exception as e:
        print(f"Error p1: {e}")

    print(f"Publicando {p2.name} en formato Notebook...")
    try:
        res2 = await publish_pod_product(p2, "spiral_notebook")
        print(f"Éxito p2: {res2}")
    except Exception as e:
        print(f"Error p2: {e}")

if __name__ == "__main__":
    asyncio.run(main())
