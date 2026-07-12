from database import SessionLocal
from models.product import Product

def main():
    db = SessionLocal()
    p = db.query(Product).filter(Product.slug.like('%hyperbolic%')).first()
    if p:
        print(f"Name: {p.name}")
        print(f"Slug: {p.slug}")
        print(f"Price: {p.price_usd}")
        print(f"Collection: {p.collection}")
    else:
        print("Not found")

if __name__ == '__main__':
    main()
