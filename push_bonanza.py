import asyncio
from database import SessionLocal
from models.product import Product
from services.bonanza import publish_book

async def main():
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.slug == "sacred-harmonics-coloring-book").first()
        if product:
            res = await publish_book(product)
            print("Bonanza publish response:", res)
        else:
            print("Product not found")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
