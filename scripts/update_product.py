import sys
import os
import json

sys.path.insert(0, "/var/www/mathrelaxing.store")
from database import SessionLocal
from models.product import DigitalProduct

db = SessionLocal()
product = db.query(DigitalProduct).filter(DigitalProduct.slug == "fractal-flames-loop-pack").first()
if product:
    contents = json.loads(product.contents_json)
    # Keep only the first item (Aurora)
    if len(contents) > 1:
        product.contents_json = json.dumps(contents[:1])
        db.commit()
        print("Successfully updated fractal-flames-loop-pack to only contain Aurora.")
    else:
        print("Already updated.")
else:
    print("Product not found.")
db.close()
