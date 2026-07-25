#!/usr/bin/env python3
"""Run on VPS: report active DigitalProducts missing from Bonanza map."""
from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")

from database import SessionLocal
from models.product import DigitalProduct
from services import bonanza as B

db = SessionLocal()
prods = db.query(DigitalProduct).filter(DigitalProduct.active == True).all()  # noqa: E712
m = B._load_map()
missing = [p for p in prods if p.slug not in m]
print(f"active_digital={len(prods)}")
print(f"bonanza_map={len(m)}")
print(f"missing={len(missing)}")
for p in sorted(missing, key=lambda x: x.slug):
    print(f"MISSING\t{p.slug}\t${p.price_usd}\t{p.name[:60]}")
print("---MAP_KEYS---")
for k in sorted(m.keys()):
    print(k)
