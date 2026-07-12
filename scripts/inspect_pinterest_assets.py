import sys
from pathlib import Path

sys.path.insert(0, "/var/www/mathrelaxing.store")

from database import SessionLocal
import json

from models.product import DigitalProduct


ROOT = Path("/var/www/mathrelaxing.store")
TERMS = ("chladni", "voronoi", "harmon", "lorenz", "complex", "radial", "turing", "particle", "strange")


def matches(path):
    name = path.name.lower()
    return any(term in name for term in TERMS)


print("VIDEOS")
for path in sorted((ROOT / "static/videos").glob("*")):
    if path.is_file() and matches(path):
        print(path.relative_to(ROOT), path.stat().st_size)

print("\nCOVERS")
for path in sorted((ROOT / "static/covers").glob("*")):
    if path.is_file() and matches(path):
        print(path.relative_to(ROOT), path.stat().st_size)

print("\nPRODUCTS")
slugs = [
    "chladni-figures-loop-pack",
    "voronoi-organics-loop-pack",
    "harmonic-geometry-loop-pack",
    "strange-attractors-loop-pack",
    "complex-plane-loop-pack",
    "radial-symmetry-loop-pack",
    "turing-patterns-loop-pack",
    "particle-systems-loop-pack",
]
db = SessionLocal()
try:
    for slug in slugs:
        product = db.query(DigitalProduct).filter(DigitalProduct.slug == slug).first()
        print(slug, bool(product), product.name if product else "")
        if product:
            try:
                contents = json.loads(product.contents_json or "[]")
            except Exception:
                contents = []
            for item in contents[:6]:
                if isinstance(item, dict):
                    print("  ", item.get("title") or item.get("name"), item.get("animation_key"), item.get("image_url"))
finally:
    db.close()
