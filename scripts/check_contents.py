import sys, json
sys.path.append('/var/www/mathrelaxing.store')
from database import SessionLocal
from models.product import DigitalProduct

db = SessionLocal()
p = db.query(DigitalProduct).filter_by(slug="sacred-harmonics-digital").first()
if p:
    print(json.dumps(json.loads(p.contents_json), indent=2))
else:
    print("Not found")
