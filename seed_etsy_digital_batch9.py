"""
seed_etsy_digital_batch9.py — Batch 5 of Etsy → web: scientific-plate posters.

Products (all active on Etsy; deliverables regenerated deterministically with
Etsy_mathrelaxing/wallart_set concept_build.py / physics_build.py):
  1. euler-identity-poster    $2.99  (Etsy 4537377786)
  2. ulam-spiral-poster       $2.99  (Etsy 4537362221)
  3. fourier-series-poster    $2.99  (Etsy 4537363031)
  4. harmonic-series-poster   $2.99  (Etsy 4537344385)
  5. black-hole-poster        $2.99  (Etsy 4537623005)
  6. maxwell-equations-poster $2.99  (Etsy 4537623277)

Same delivery pattern as batch4-8.

Run:
    python seed_etsy_digital_batch9.py --assets     # local: copy assets + try seed
    python seed_etsy_digital_batch9.py --seed-only  # VPS: DB upsert only
    python seed_etsy_digital_batch9.py --verify
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WALLART = Path(r"C:\repos\Etsy_mathrelaxing\wallart_set\out")

PRIVATE = ROOT / "private_downloads"
STATIC_DL = ROOT / "static" / "downloads"
STATIC_IMG = ROOT / "static" / "img"
STATIC_PREV = ROOT / "static" / "previews"
STATIC_DIG = ROOT / "static" / "digital"

GALLERY_5 = [
    ("01_hero.jpg", "01_hero.jpg"),
    ("02_detail.jpg", "02_detail.jpg"),
    ("03_framed.jpg", "03_framed.jpg"),
    ("04_sizes.jpg", "04_sizes.jpg"),
    ("05_note.jpg", "05_note.jpg"),
]


def _fmt_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n} B"


def _copy(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def _write_preview_jpg(src: Path, slug: str) -> None:
    from PIL import Image

    STATIC_PREV.mkdir(parents=True, exist_ok=True)
    img = Image.open(src).convert("RGB")
    img.save(STATIC_PREV / f"{slug}_clean.jpg", "JPEG", quality=90, optimize=True)
    card = img.copy()
    card.thumbnail((900, 900), Image.Resampling.LANCZOS)
    card.save(STATIC_PREV / f"{slug}.jpg", "JPEG", quality=85, optimize=True)


def _gallery_from_previews(src_dir: Path, slug: str, rename_map: list[tuple[str, str]]) -> None:
    dest = STATIC_DIG / slug
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*"):
        if old.is_file():
            old.unlink()
    for src_name, dest_name in rename_map:
        src = src_dir / src_name
        if not src.exists():
            raise FileNotFoundError(src)
        _copy(src, dest / dest_name)


ASSET_JOBS = [
    {
        "slug": "euler-identity-poster",
        "src_files": [(WALLART / "concept" / "euler" / "EulersIdentity_prints.zip",
                       "euler-identity-poster.zip")],
        "preview_dir": WALLART / "concept" / "euler" / "listing",
        "hero": WALLART / "concept" / "euler" / "listing" / "01_hero.jpg",
        "gallery": GALLERY_5,
    },
    {
        "slug": "ulam-spiral-poster",
        "src_files": [(WALLART / "concept" / "ulam" / "UlamSpiral_prints.zip",
                       "ulam-spiral-poster.zip")],
        "preview_dir": WALLART / "concept" / "ulam" / "listing",
        "hero": WALLART / "concept" / "ulam" / "listing" / "01_hero.jpg",
        "gallery": GALLERY_5,
    },
    {
        "slug": "fourier-series-poster",
        "src_files": [(WALLART / "concept" / "fourier" / "FourierSquareWave_prints.zip",
                       "fourier-series-poster.zip")],
        "preview_dir": WALLART / "concept" / "fourier" / "listing",
        "hero": WALLART / "concept" / "fourier" / "listing" / "01_hero.jpg",
        "gallery": GALLERY_5,
    },
    {
        "slug": "harmonic-series-poster",
        "src_files": [(WALLART / "concept" / "harmonic" / "HarmonicSeries_prints.zip",
                       "harmonic-series-poster.zip")],
        "preview_dir": WALLART / "concept" / "harmonic" / "listing",
        "hero": WALLART / "concept" / "harmonic" / "listing" / "01_hero.jpg",
        "gallery": GALLERY_5,
    },
    {
        "slug": "black-hole-poster",
        "src_files": [(WALLART / "physics" / "blackhole" / "BlackHole_prints.zip",
                       "black-hole-poster.zip")],
        "preview_dir": WALLART / "physics" / "blackhole" / "listing",
        "hero": WALLART / "physics" / "blackhole" / "listing" / "01_hero.jpg",
        "gallery": GALLERY_5,
    },
    {
        "slug": "maxwell-equations-poster",
        "src_files": [(WALLART / "physics" / "maxwell" / "Electromagnetism_prints.zip",
                       "maxwell-equations-poster.zip")],
        "preview_dir": WALLART / "physics" / "maxwell" / "listing",
        "hero": WALLART / "physics" / "maxwell" / "listing" / "01_hero.jpg",
        "gallery": GALLERY_5,
    },
]

_COMMON = (
    "\n\nEvery line is computed from the mathematics — not stock art, not AI.\n\n"
    "What you get (instant download): one ZIP with 5 aspect ratios (2:3, 3:4, 4:5, "
    "5:7 and ISO/A) at 300 DPI — print small or large, at home, a print shop, or an "
    "online lab. For personal use. Frame not included."
)

_META = {
    "euler-identity-poster": {
        "name": "Euler's Identity — Scientific Plate Print",
        "equation_type": "none",
        "description": (
            "Instant download — Euler's Identity as a scientific-plate art print. "
            "Walk the unit circle: e^(iθ) = cos θ + i sin θ. A quarter turn lands on i, "
            "a half turn on −1 — so e^(iπ) + 1 = 0, one line tying together e, i, π, 1 "
            "and 0, arguably the five most important numbers in mathematics." + _COMMON
        ),
    },
    "ulam-spiral-poster": {
        "name": "Ulam Spiral — Prime Numbers Plate Print",
        "equation_type": "none",
        "description": (
            "Instant download — the Ulam Spiral as a scientific-plate art print. "
            "Write the whole numbers in a square spiral and shade the primes: they "
            "refuse to scatter evenly, crowding onto diagonal tracks of simple "
            "quadratics like n² + n + 41. Even so, no formula catches every prime." + _COMMON
        ),
    },
    "fourier-series-poster": {
        "name": "Fourier Series — Square Wave Plate Print",
        "equation_type": "none",
        "description": (
            "Instant download — Building a Square Wave, a scientific-plate art print. "
            "Add sine waves of frequency 1, 3, 5, 7… with heights 1, 1/3, 1/5… and a "
            "square wave takes shape. Any repeating signal is a sum of pure tones — the "
            "same idea behind a synthesiser, an MP3, and how your ear pulls a chord apart." + _COMMON
        ),
    },
    "harmonic-series-poster": {
        "name": "Vibrating String — Harmonic Series Plate Print",
        "equation_type": "none",
        "description": (
            "Instant download — Modes of a Vibrating String, a scientific-plate art print. "
            "A plucked string sounds all of its modes at once; their wavelengths are L, "
            "L/2, L/3… — the harmonic series. The sum 1 + 1/2 + 1/3 + … never settles: "
            "reaching a total of just 100 takes about 1.5 × 10⁴³ terms." + _COMMON
        ),
    },
    "black-hole-poster": {
        "name": "Anatomy of a Black Hole — Physics Plate Print",
        "equation_type": "none",
        "description": (
            "Instant download — Anatomy of a Black Hole, a physics-plate art print. "
            "Cross the event horizon at r = 2GM/c² and no path — not even light — leads "
            "back out. At 1.5 rₛ light can circle the hole on the photon sphere; inside "
            "3 rₛ no stable orbit survives. For the Sun that horizon would be just 3 km "
            "across; for Earth, 9 mm." + _COMMON
        ),
    },
    "maxwell-equations-poster": {
        "name": "Maxwell Equations — What Light Is Made Of",
        "equation_type": "none",
        "description": (
            "Instant download — What Light Is Made Of, a physics-plate art print of "
            "Maxwell's equations. A changing electric field E makes a magnetic field B, "
            "and a changing B remakes E — the two roll forward together as a wave whose "
            "speed, computed from the lab constants μ₀ and ε₀, is exactly c. Light, "
            "radio and X-rays are all this same wave." + _COMMON
        ),
    },
}


def copy_assets() -> dict[str, dict]:
    if not WALLART.is_dir():
        raise SystemExit(f"wallart_set output not found: {WALLART}")

    PRIVATE.mkdir(parents=True, exist_ok=True)
    meta: dict[str, dict] = {}

    for job in ASSET_JOBS:
        slug = job["slug"]
        files = []
        for src, dest_name in job["src_files"]:
            if not src.exists():
                raise FileNotFoundError(f"Missing source file for {slug}: {src}")
            priv = _copy(src, PRIVATE / dest_name)
            _copy(src, STATIC_DL / dest_name)
            files.append({"filename": dest_name, "bytes": priv.stat().st_size,
                          "file_size": _fmt_size(priv.stat().st_size)})

        hero: Path = job["hero"]
        _write_preview_jpg(hero, slug)
        _copy(hero, STATIC_IMG / f"{slug}_cover.jpg")
        _gallery_from_previews(job["preview_dir"], slug, job["gallery"])

        meta[slug] = {"files": files}
        total = sum(f["bytes"] for f in files)
        print(f"  OK  {slug:36s}  {_fmt_size(total):>8s}")

    return meta


def build_products(file_meta: dict[str, dict] | None = None) -> list[dict]:
    fallbacks = {
        "euler-identity-poster": "0.6 MB",
        "ulam-spiral-poster": "2.9 MB",
        "fourier-series-poster": "0.9 MB",
        "harmonic-series-poster": "1.6 MB",
        "black-hole-poster": "2.2 MB",
        "maxwell-equations-poster": "1.0 MB",
    }

    products = []
    for job in ASSET_JOBS:
        slug = job["slug"]
        m = _META[slug]
        fname = job["src_files"][0][1]
        if file_meta and slug in file_meta:
            size = file_meta[slug]["files"][0]["file_size"]
        else:
            size = fallbacks[slug]
        products.append({
            "slug": slug,
            "name": m["name"],
            "product_type": "thematic_bundle",
            "collection": "digital-downloads",
            "equation_type": m["equation_type"],
            "description": m["description"],
            "price_usd": 2.99,
            "contents_json": json.dumps([
                {
                    "title": f"{m['name']} — 300 dpi (2:3, 3:4, 4:5, 5:7, ISO)",
                    "item_type": "file",
                    "filename": fname,
                    "size": size,
                },
            ]),
            "cover_image": f"/static/img/{slug}_cover.jpg",
            "thumbnail_url": f"/static/previews/{slug}.jpg",
            "file_url": f"private_downloads/{fname}",
            "file_size": size,
            "license_type": "personal",
            "active": True,
        })
    return products


def seed_digital_etsy_batch9(file_meta: dict[str, dict] | None = None) -> None:
    from database import SessionLocal
    from models.product import DigitalProduct

    products = build_products(file_meta)
    db = SessionLocal()
    try:
        for p_data in products:
            existing = db.query(DigitalProduct).filter_by(slug=p_data["slug"]).first()
            if existing:
                for k, v in p_data.items():
                    setattr(existing, k, v)
                action = "updated"
            else:
                db.add(DigitalProduct(**p_data))
                action = "created"
            print(f"  {action:8s}  {p_data['slug']:36s}  ${p_data['price_usd']:.2f}")
        db.commit()
    finally:
        db.close()
    print(f"Seed complete: {len(products)} products upserted.")


def verify_assets() -> bool:
    ok = True
    for p in build_products():
        slug = p["slug"]
        checks = [ROOT / p["file_url"],
                  ROOT / p["cover_image"].lstrip("/").replace("/", os.sep),
                  ROOT / p["thumbnail_url"].lstrip("/").replace("/", os.sep),
                  STATIC_DIG / slug]
        for path in checks:
            if path.is_dir():
                n = len(list(path.iterdir())) if path.exists() else 0
                if n == 0:
                    ok = False
                print(f"  [{'OK' if n else 'EMPTY':5s}] gallery {slug}/ ({n} files)")
            else:
                exists = path.exists()
                if not exists:
                    ok = False
                print(f"  [{'OK' if exists else 'MISS':5s}] {path.relative_to(ROOT)}")
    return ok


if __name__ == "__main__":
    do_assets = "--assets" in sys.argv
    do_verify = "--verify" in sys.argv
    do_seed = "--seed-only" in sys.argv or (not do_verify and not do_assets) or do_assets

    file_meta = None
    if do_assets:
        print("Copying Batch 5 assets from wallart_set output …")
        file_meta = copy_assets()
        print()

    if do_seed and not do_verify:
        if file_meta is None:
            guessed = {}
            for job in ASSET_JOBS:
                files = []
                for _, dest_name in job["src_files"]:
                    p = PRIVATE / dest_name
                    if p.exists():
                        files.append({"filename": dest_name, "bytes": p.stat().st_size,
                                      "file_size": _fmt_size(p.stat().st_size)})
                if files:
                    guessed[job["slug"]] = {"files": files}
            file_meta = guessed or None
        print("Seeding digital_products …")
        try:
            seed_digital_etsy_batch9(file_meta)
        except Exception as e:
            print(f"DB seed skipped/failed ({type(e).__name__}: {e})")
            print("Assets (if copied) are ready; run this on the VPS with SQLAlchemy configured.")

    if do_verify or do_assets:
        print("\nVerifying assets …")
        if verify_assets():
            print("All asset paths present.")
        else:
            print("Some assets missing — re-run with --assets.")
            sys.exit(1)
