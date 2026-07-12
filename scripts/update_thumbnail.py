import sys
import os

sys.path.insert(0, "/var/www/mathrelaxing.store")
from database import SessionLocal
from models.product import DigitalProduct

db = SessionLocal()
product = db.query(DigitalProduct).filter(DigitalProduct.slug == "fractal-flames-loop-pack").first()
if product:
    product.thumbnail_url = "/static/videos/ff_flame_aurora_preview.mp4"
    db.commit()
    print("Successfully updated thumbnail_url to point to the web-optimized preview.")
else:
    print("Product not found.")
db.close()
