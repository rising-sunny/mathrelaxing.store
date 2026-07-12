from pathlib import Path
import os
import sys

sys.path.insert(0, "/var/www/mathrelaxing.store")

from database import SessionLocal
from models.product import DigitalProduct

ROOT = Path("/var/www/mathrelaxing.store")
TERMS = ("gumroad", "whop")
SUFFIXES = {".py", ".html", ".js", ".md", ".txt", ".service", ".timer", ".env"}

print("FILES")
for path in sorted(ROOT.rglob("*")):
    if not path.is_file() or path.suffix not in SUFFIXES:
        continue
    if "__pycache__" in path.parts or ".venv" in path.parts:
        continue
    rel = path.relative_to(ROOT)
    name = str(rel).lower()
    if any(term in name for term in TERMS):
        print(rel)

print("\nREFERENCES")
for path in sorted(ROOT.rglob("*")):
    if not path.is_file() or path.suffix not in SUFFIXES:
        continue
    if "__pycache__" in path.parts or ".venv" in path.parts:
        continue
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        continue
    for idx, line in enumerate(lines, 1):
        low = line.lower()
        if any(term in low for term in TERMS):
            display = line
            # Avoid showing secret values if this scans .env.
            if path.name == ".env" and "=" in display:
                key = display.split("=", 1)[0]
                display = f"{key}=<set>"
            print(f"{path.relative_to(ROOT)}:{idx}:{display[:220]}")

print("\nENV FLAGS")
for key in sorted(os.environ):
    if "GUMROAD" in key or "WHOP" in key:
        print(f"{key}=<set>")

print("\nACTIVE DIGITAL PRODUCTS")
db = SessionLocal()
try:
    rows = (
        db.query(DigitalProduct)
        .filter(DigitalProduct.active == True)
        .order_by(DigitalProduct.product_type, DigitalProduct.slug)
        .all()
    )
    print("count", len(rows))
    for p in rows:
        print(
            " | ".join(
                [
                    p.slug,
                    p.name,
                    p.product_type,
                    str(p.price_usd),
                    f"whop_product={bool(p.whop_product_id)}",
                    f"whop_plan={bool(p.whop_plan_id)}",
                    f"whop_checkout={bool(p.whop_checkout_url)}",
                    f"lemon_variant={bool(p.lemon_variant_id)}",
                    f"file_url={bool(p.file_url)}",
                ]
            )
        )
finally:
    db.close()
