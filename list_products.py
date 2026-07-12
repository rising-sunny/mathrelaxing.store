import sys
sys.path.insert(0, '/var/www/mathrelaxing.store')

from database import SessionLocal
from models.product import Product

db = SessionLocal()
products = db.query(Product).all()
for p in products:
    print(f"{p.id}: {p.name} (Price: {p.price_usd})")
