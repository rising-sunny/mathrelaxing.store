"""
deactivate_batch3_duplicates.py — one-off cleanup: fractal-flora-ipad-bundle
and sacred-geometry-ipad-bundle (added in seed_etsy_digital_batch3.py) turned
out to duplicate real, already-live products under different slugs
(fractal-flora-ipad-coloring, sacred-geometry-ipad-coloring — same GoodNotes+
Procreate content, $10.99). They were removed from seed_etsy_digital_batch3.py
so future re-runs won't touch them; this script deactivates the two rows that
were already seeded live. Safe to re-run.

    python deactivate_batch3_duplicates.py
"""
from database import SessionLocal
from models.product import DigitalProduct

SLUGS_TO_DEACTIVATE = [
    "fractal-flora-ipad-bundle",
    "sacred-geometry-ipad-bundle",
]


def main():
    db = SessionLocal()
    for slug in SLUGS_TO_DEACTIVATE:
        p = db.query(DigitalProduct).filter_by(slug=slug).first()
        if p:
            p.active = False
            print(f"deactivated: {slug}")
        else:
            print(f"not found (already gone or never seeded): {slug}")
    db.commit()
    db.close()


if __name__ == "__main__":
    main()
