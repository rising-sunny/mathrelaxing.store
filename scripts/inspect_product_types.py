import sys

sys.path.insert(0, "/var/www/mathrelaxing.store")

from database import SessionLocal
from models.product import DigitalProduct, Product
from models.pinterest_pin import PinterestPin


def label_for_physical(product):
    collection = (product.collection or "").lower()
    name = (product.name or "").lower()
    slug = (product.slug or "").lower()
    text = f"{collection} {name} {slug}"
    if "desk" in text and "mat" in text:
        return "Desk Mat"
    if "canvas" in text:
        return "Canvas Print"
    if "framed" in text or "frame" in text:
        return "Framed Print"
    if "poster" in text:
        return "Gallery Poster"
    return "Art Print"


def label_for_digital(product):
    ptype = (product.product_type or "").lower()
    if ptype == "image_pack":
        return "Image Pack"
    if ptype == "animation_pack":
        return "Loop Animation Pack"
    if ptype == "creator_assets":
        return "Creator Assets"
    if ptype == "thematic_bundle":
        return "Digital Bundle"
    return "Digital Download"


db = SessionLocal()
try:
    print("PHYSICAL PRODUCTS")
    for p in db.query(Product).order_by(Product.collection, Product.slug).all():
        print(p.slug, "|", p.name, "|", p.collection, "|", label_for_physical(p), "|", p.price_usd)

    print("\nDIGITAL PRODUCTS")
    for p in db.query(DigitalProduct).order_by(DigitalProduct.product_type, DigitalProduct.slug).all():
        print(p.slug, "|", p.name, "|", p.product_type, "|", label_for_digital(p), "|", p.price_usd)

    print("\nRECENT PIN RECORDS")
    for rec in db.query(PinterestPin).order_by(PinterestPin.created_at.desc()).limit(60).all():
        print(rec.pin_id, "|", rec.status, "|", rec.product_type, "|", rec.product_slug, "|", rec.title)
finally:
    db.close()
