"""List active digital products for Meta ad landing candidates."""
import sys
from collections import defaultdict

sys.path.insert(0, "/var/www/mathrelaxing.store")
from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
from database import SessionLocal
from models.product import DigitalProduct

db = SessionLocal()
ps = (
    db.query(DigitalProduct)
    .filter(DigitalProduct.active == True)
    .order_by(DigitalProduct.product_type, DigitalProduct.price_usd, DigitalProduct.slug)
    .all()
)
print(f"active={len(ps)}\n")
by = defaultdict(list)
for p in ps:
    by[p.product_type or "?"].append(p)

for t, items in sorted(by.items(), key=lambda x: -len(x[1])):
    print(f"=== {t} ({len(items)}) ===")
    for p in items:
        print(f"  ${p.price_usd:5.2f}  {p.slug}")
        print(f"           {p.name}")
        print(f"           https://mathrelaxing.store/bundle/{p.slug}")
    print()
db.close()
