import sys
sys.path.append('/var/www/mathrelaxing.store')
from database import SessionLocal
from models.product import DigitalProduct

db = SessionLocal()

slugs = ['quantified-self-planner-digital', 'stem-focus-planner-digital', 'stem-notebook-digital']

for slug in slugs:
    p = db.query(DigitalProduct).filter_by(slug=slug).first()
    if p:
        old = p.price_usd
        p.price_usd = 2.99
        print(f"{slug}: ${old:.2f} -> $2.99")
    else:
        print(f"{slug}: NOT FOUND")

db.commit()
db.close()
print("Done!")
