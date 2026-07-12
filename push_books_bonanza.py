import asyncio
import sys
import os

# Ensure the parent directory is in the sys.path for absolute imports
sys.path.insert(0, '/var/www/mathrelaxing.store')

from database import SessionLocal
from models.product import Product
from services.bonanza import publish_book

async def main():
    db = SessionLocal()
    try:
        products = db.query(Product).filter(Product.slug.like("%book%")).all()
        for p in products:
            res = await publish_book(p)
            print(f"Bonanza publish response for {p.slug}:", res)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
