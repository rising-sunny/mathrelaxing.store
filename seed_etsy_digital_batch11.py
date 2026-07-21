"""
seed_etsy_digital_batch11.py — Batch 7 of Etsy → web: printable wall-art sets.

Products (all active on Etsy; deliverables regenerated deterministically with
Etsy_mathrelaxing/wallart_set generate.py + build_mockups.py):
  1. quiet-mathematics-print-set       $3.99  (Etsy 4536831020, earth palette)
  2. quiet-mathematics-mono-print-set  $3.99  (Etsy 4536834070, mono palette)
  3. geometric-tilings-print-set       $3.99  (Etsy 4536907663, mono palette)

Each set = 6 original generative-math designs × 5 aspect ratios @300 DPI,
delivered as 5 per-ratio ZIPs.

Run:
    python seed_etsy_digital_batch11.py --assets     # local: copy assets + try seed
    python seed_etsy_digital_batch11.py --seed-only  # VPS: DB upsert only
    python seed_etsy_digital_batch11.py --verify
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

GALLERY_6 = [
    ("01_hero_gallery.jpg", "01_hero.jpg"),
    ("02_room.jpg", "02_room.jpg"),
    ("03_detail.jpg", "03_detail.jpg"),
    ("04_included.jpg", "04_included.jpg"),
    ("05_sizes.jpg", "05_sizes.jpg"),
    ("06_how.jpg", "06_how.jpg"),
]

RATIOS = ["2x3", "3x4", "4x5", "5x7", "ISO"]


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


def _ratio_files(out_dir: str, zip_prefix: str, slug: str) -> list[tuple[Path, str]]:
    return [
        (WALLART / out_dir / "zips" / f"{zip_prefix}_{r}.zip", f"{slug}-{r.lower()}.zip")
        for r in RATIOS
    ]


ASSET_JOBS = [
    {
        "slug": "quiet-mathematics-print-set",
        "src_files": _ratio_files("quiet/earth", "QuietMathematics_earth", "quiet-mathematics"),
        "preview_dir": WALLART / "quiet" / "earth" / "listing",
        "hero": WALLART / "quiet" / "earth" / "listing" / "01_hero_gallery.jpg",
        "gallery": GALLERY_6,
    },
    {
        "slug": "quiet-mathematics-mono-print-set",
        "src_files": _ratio_files("quiet/mono", "QuietMathematics_mono", "quiet-mathematics-mono"),
        "preview_dir": WALLART / "quiet" / "mono" / "listing",
        "hero": WALLART / "quiet" / "mono" / "listing" / "01_hero_gallery.jpg",
        "gallery": GALLERY_6,
    },
    {
        "slug": "geometric-tilings-print-set",
        "src_files": _ratio_files("geo/mono", "GeometricTilings_mono", "geometric-tilings"),
        "preview_dir": WALLART / "geo" / "mono" / "listing",
        "hero": WALLART / "geo" / "mono" / "listing" / "01_hero_gallery.jpg",
        "gallery": GALLERY_6,
    },
]

_META = {
    "quiet-mathematics-print-set": {
        "name": "Quiet Mathematics — Set of 6 Boho Line Art Prints",
        "description": (
            "Instant download — Quiet Mathematics, six original generative-math designs "
            "in a warm earth-tone Japandi/boho palette. Maurer rose, Vogel phyllotaxis "
            "spiral, Hilbert curve, times-table cardioid, Euler spiral, and a Barnsley "
            "fern — every line drawn from a mathematical expression, deterministic, so "
            "the delivered print is identical to the preview.\n\n"
            "6 designs × 5 aspect ratios (2:3, 3:4, 4:5, 5:7, ISO/A) @ 300 DPI, "
            "delivered as five per-ratio ZIPs. Print at home, a print shop, or an "
            "online lab."
        ),
    },
    "quiet-mathematics-mono-print-set": {
        "name": "Quiet Mathematics Mono — Set of 6 Scandinavian Prints",
        "description": (
            "Instant download — the Quiet Mathematics collection in a clean Scandinavian "
            "mono palette. Six original generative-math designs: Maurer rose, Vogel "
            "phyllotaxis spiral, Hilbert curve, times-table cardioid, Euler spiral, and "
            "a Barnsley fern — minimalist abstract line art computed from real "
            "mathematics, not clip art.\n\n"
            "6 designs × 5 aspect ratios (2:3, 3:4, 4:5, 5:7, ISO/A) @ 300 DPI, "
            "delivered as five per-ratio ZIPs."
        ),
    },
    "geometric-tilings-print-set": {
        "name": "Geometric Tilings — Set of 6 Tessellation Prints",
        "description": (
            "Instant download — Geometric Tilings, six classic tessellations drawn "
            "true, in black-and-white line art: Penrose P3 aperiodic tiling, Truchet "
            "quarter-arc weave, Islamic girih star grid, rhombille isometric-cube "
            "illusion, Sierpinski triangle, and the Flower of Life circle lattice.\n\n"
            "6 designs × 5 aspect ratios (2:3, 3:4, 4:5, 5:7, ISO/A) @ 300 DPI, "
            "delivered as five per-ratio ZIPs. Gallery-wall ready."
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
        print(f"  OK  {slug:36s}  {_fmt_size(total):>8s}  ({len(files)} zips)")

    return meta


_RATIO_TITLES = {
    "2x3": "2:3 ratio (12×18, 24×36 in)",
    "3x4": "3:4 ratio (12×16, 18×24 in)",
    "4x5": "4:5 ratio (16×20, 24×30 in)",
    "5x7": "5:7 ratio (10×14, 20×28 in)",
    "ISO": "ISO/A sizes (A4–A1)",
}


def build_products(file_meta: dict[str, dict] | None = None) -> list[dict]:
    products = []
    for job in ASSET_JOBS:
        slug = job["slug"]
        m = _META[slug]
        if file_meta and slug in file_meta:
            files = file_meta[slug]["files"]
        else:
            files = [{"filename": dest, "file_size": "9 MB"} for _, dest in job["src_files"]]

        contents = []
        for (src, dest), ratio in zip(job["src_files"], RATIOS):
            size = next((f["file_size"] for f in files if f["filename"] == dest), "9 MB")
            contents.append({
                "title": f"All 6 designs — {_RATIO_TITLES[ratio]}",
                "item_type": "file",
                "filename": dest,
                "size": size,
            })

        products.append({
            "slug": slug,
            "name": m["name"],
            "product_type": "thematic_bundle",
            "collection": "digital-downloads",
            "equation_type": "none",
            "description": m["description"],
            "price_usd": 3.99,
            "contents_json": json.dumps(contents),
            "cover_image": f"/static/img/{slug}_cover.jpg",
            "thumbnail_url": f"/static/previews/{slug}.jpg",
            "file_url": f"private_downloads/{contents[0]['filename']}",
            "file_size": contents[0]["size"],
            "license_type": "personal",
            "active": True,
        })
    return products


def seed_digital_etsy_batch11(file_meta: dict[str, dict] | None = None) -> None:
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
        checks = [ROOT / p["cover_image"].lstrip("/").replace("/", os.sep),
                  ROOT / p["thumbnail_url"].lstrip("/").replace("/", os.sep),
                  STATIC_DIG / slug]
        for item in json.loads(p["contents_json"]):
            checks.insert(0, PRIVATE / item["filename"])
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
        print("Copying Batch 7 assets from wallart_set output …")
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
            seed_digital_etsy_batch11(file_meta)
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
