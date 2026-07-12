import sys

sys.path.insert(0, "/var/www/mathrelaxing.store")

from database import SessionLocal
from models.product import DigitalProduct, Product
from services.pinterest_jobs import _build_pin_body


SLUGS = [
    ("physical", "gray-scott-coral"),
    ("physical", "joukowski-midnight-flight"),
    ("physical", "topographic-circuit-desk-mat"),
    ("digital", "turing-patterns-image-pack"),
    ("digital", "reaction-diffusion-loop-pack"),
]

db = SessionLocal()
try:
    for ptype, slug in SLUGS:
        model = DigitalProduct if ptype == "digital" else Product
        product = db.query(model).filter(model.slug == slug).first()
        body = _build_pin_body(ptype, product, 0, "BOARD")
        print("---", slug)
        print("title:", body["title"])
        print("image:", body["media_source"]["url"])
        print("description:", body["description"][:180])
finally:
    db.close()
