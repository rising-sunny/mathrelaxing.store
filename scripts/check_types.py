import sys
sys.path.append('/var/www/mathrelaxing.store')
from database import SessionLocal
from models.product import DigitalProduct

db = SessionLocal()
types = db.query(DigitalProduct.product_type).distinct().all()
print([t[0] for t in types])
