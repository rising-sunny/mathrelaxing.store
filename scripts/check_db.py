import sys
sys.path.append('/var/www/mathrelaxing.store')
from database import SessionLocal
from models.product import DigitalProduct
import json

db = SessionLocal()
slugs = ['quantified-self-planner-digital', 'stem-focus-planner-digital', 'stem-notebook-digital']

for slug in slugs:
    p = db.query(DigitalProduct).filter_by(slug=slug).first()
    if p:
        print(f"--- {slug} ---")
        print(f"cover_image: {p.cover_image}")
        print(f"thumbnail_url: {p.thumbnail_url}")
        print(f"contents_json: {json.dumps(json.loads(p.contents_json), indent=2)}")
    else:
        print(f"--- {slug} NOT FOUND ---")
