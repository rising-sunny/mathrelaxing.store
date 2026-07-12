import sys
sys.path.append('/var/www/mathrelaxing.store')
from database import SessionLocal
from models.product import DigitalProduct

db = SessionLocal()
p = db.query(DigitalProduct).filter(DigitalProduct.name.like('%Sacred Harmonics%')).first()
if p:
    print(f"Slug: {p.slug}")
    print(f"Cover Image: {p.cover_image}")
    print(f"Thumbnail URL: {p.thumbnail_url}")
else:
    print("Not found")
