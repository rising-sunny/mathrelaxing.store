"""
seed_etsy_digital_batch10.py — Batch 6 of Etsy → web: grid papers & notebooks.

Products (all active on Etsy; deliverables regenerated deterministically with
Etsy_mathrelaxing/wallart_set gridpaper_build.py / gridpaper_goodnotes.py /
scigrid_build.py; galleries from the live Etsy listing photos):
  1. boho-grid-paper-bundle        $2.99  (Etsy 4536968985, earth edition)
  2. grid-paper-bundle-mono        $2.99  (Etsy 4536990190, mono-flower edition)
  3. hyperlinked-notebook-boho     $2.99  (Etsy 4536971373, earth edition)
  4. hyperlinked-notebook-mono     $2.99  (Etsy 4536990226, mono-flower edition)
  5. engineering-graph-paper       $2.99  (Etsy 4537937498, earth edition)

Run:
    python seed_etsy_digital_batch10.py --assets     # local: copy assets + try seed
    python seed_etsy_digital_batch10.py --seed-only  # VPS: DB upsert only
    python seed_etsy_digital_batch10.py --verify
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WALLART = Path(r"C:\repos\Etsy_mathrelaxing\wallart_set\out")
B3 = Path(r"C:\repos\Etsy_mathrelaxing\batch3_downloads")

PRIVATE = ROOT / "private_downloads"
STATIC_DL = ROOT / "static" / "downloads"
STATIC_IMG = ROOT / "static" / "img"
STATIC_PREV = ROOT / "static" / "previews"
STATIC_DIG = ROOT / "static" / "digital"


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


def _etsy_images_dir(listing_id: str) -> Path:
    for d in B3.iterdir():
        if d.is_dir() and d.name.startswith(listing_id):
            return d / "images"
    raise FileNotFoundError(f"No batch3_downloads dir for listing {listing_id}")


def _gallery_from_etsy(listing_id: str, slug: str) -> Path:
    """Copy the Etsy listing photos (rankNN_*.jpg) as the web gallery."""
    src_dir = _etsy_images_dir(listing_id)
    dest = STATIC_DIG / slug
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*"):
        if old.is_file():
            old.unlink()
    hero = None
    for i, src in enumerate(sorted(src_dir.glob("rank*.jpg")), start=1):
        out = dest / f"{i:02d}_listing.jpg"
        _copy(src, out)
        if hero is None:
            hero = src
    if hero is None:
        raise FileNotFoundError(f"No images in {src_dir}")
    return hero


ASSET_JOBS = [
    {
        "slug": "boho-grid-paper-bundle",
        "listing_id": "4536968985",
        "src_files": [(WALLART / "gridpaper" / "earth" / "AestheticGridPaper_earth.zip",
                       "boho-grid-paper-bundle.zip")],
    },
    {
        "slug": "grid-paper-bundle-mono",
        "listing_id": "4536990190",
        "src_files": [(WALLART / "gridpaper" / "mono-flower" / "AestheticGridPaper_mono-flower.zip",
                       "grid-paper-bundle-mono.zip")],
    },
    {
        "slug": "hyperlinked-notebook-boho",
        "listing_id": "4536971373",
        "src_files": [(WALLART / "gridpaper" / "earth" / "AestheticGridNotebook_earth_GoodNotes.pdf",
                       "hyperlinked-notebook-boho.pdf")],
    },
    {
        "slug": "hyperlinked-notebook-mono",
        "listing_id": "4536990226",
        "src_files": [(WALLART / "gridpaper" / "mono-flower" / "AestheticGridNotebook_mono-flower_GoodNotes.pdf",
                       "hyperlinked-notebook-mono.pdf")],
    },
    {
        "slug": "engineering-graph-paper",
        "listing_id": "4537937498",
        "src_files": [(WALLART / "scigrid" / "earth" / "EngineeringScienceGraphPaper_earth.zip",
                       "engineering-graph-paper.zip")],
    },
]

_META = {
    "boho-grid-paper-bundle": {
        "name": "Boho Grid Paper Bundle — 10 Styles",
        "product_type": "digital_notebook",
        "contents_title": "Aesthetic Grid Paper (earth) — 10 styles, PDF + PNG",
        "description": (
            "Instant download — Aesthetic Grid Paper bundle in a warm boho earth-tone "
            "palette. Ten paper styles: Square Grid, Dot Grid, Isometric, Triangular, "
            "Hexagonal, Ruled Notes, Cornell Notes, Penrose Grid, Polar Grid, and "
            "Sketch + Notes.\n\n"
            "Vector PDFs in US Letter and A4 (crisp at any print size) plus 300-DPI "
            "PNG pages sized for GoodNotes, Notability and other iPad note apps. "
            "Print it, import it, or both — reuse forever."
        ),
    },
    "grid-paper-bundle-mono": {
        "name": "Grid Paper Bundle — 10 Styles, Black & White",
        "product_type": "digital_notebook",
        "contents_title": "Aesthetic Grid Paper (mono) — 10 styles, PDF + PNG",
        "description": (
            "Instant download — Aesthetic Grid Paper bundle in a clean black-and-white "
            "mono palette with a Flower of Life featured page. Ten paper styles: Square "
            "Grid, Dot Grid, Isometric, Triangular, Hexagonal, Ruled Notes, Cornell "
            "Notes, Flower of Life, Polar Grid, and Sketch + Notes.\n\n"
            "Vector PDFs in US Letter and A4 plus 300-DPI PNG pages for GoodNotes, "
            "Notability and other iPad note apps. Minimal ink, maximum structure."
        ),
    },
    "hyperlinked-notebook-boho": {
        "name": "Hyperlinked Digital Notebook — Boho Earth-Tone",
        "product_type": "digital_notebook",
        "contents_title": "Hyperlinked notebook (earth) — GoodNotes/Notability PDF",
        "description": (
            "Instant download — a fully hyperlinked digital notebook for GoodNotes, "
            "Notability, and any PDF app. Cover + contents + 10 tabbed sections of "
            "aesthetic grid paper in a warm earth-tone palette.\n\n"
            "Every page carries a right-edge tab strip: tap a tab and jump straight to "
            "that section (real PDF GOTO links, not decorations). Vector pages — crisp "
            "at any zoom, tiny file."
        ),
    },
    "hyperlinked-notebook-mono": {
        "name": "Hyperlinked Digital Notebook — Black & White",
        "product_type": "digital_notebook",
        "contents_title": "Hyperlinked notebook (mono) — GoodNotes/Notability PDF",
        "description": (
            "Instant download — a fully hyperlinked digital notebook for GoodNotes, "
            "Notability, and any PDF app. Cover + contents + 10 tabbed sections of "
            "black-and-white grid paper (with a Flower of Life featured style).\n\n"
            "Every page carries a right-edge tab strip: tap a tab and jump straight to "
            "that section (real PDF GOTO links). Vector pages — crisp at any zoom, "
            "tiny file."
        ),
    },
    "engineering-graph-paper": {
        "name": "Engineering Graph Paper Bundle — 8 STEM Grids",
        "product_type": "digital_notebook",
        "contents_title": "Engineering & Science Graph Paper — 8 grids, PDF + PNG",
        "description": (
            "Instant download — the Engineering & Science Graph Paper bundle: eight "
            "technical grids for real work. Engineering 5×5, Millimeter, Log-Log, "
            "Semi-Log, Cartesian Plane, Polar (degrees), Log-Polar, and Isometric 3D.\n\n"
            "Vector PDFs in US Letter and A4 plus 300-DPI PNG pages for GoodNotes and "
            "iPad. For engineers, physics and math students, lab notebooks, and anyone "
            "who plots by hand."
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

        hero = _gallery_from_etsy(job["listing_id"], slug)
        _write_preview_jpg(hero, slug)
        _copy(hero, STATIC_IMG / f"{slug}_cover.jpg")

        meta[slug] = {"files": files}
        total = sum(f["bytes"] for f in files)
        print(f"  OK  {slug:36s}  {_fmt_size(total):>8s}")

    return meta


def build_products(file_meta: dict[str, dict] | None = None) -> list[dict]:
    fallbacks = {
        "boho-grid-paper-bundle": "2.9 MB",
        "grid-paper-bundle-mono": "2.2 MB",
        "hyperlinked-notebook-boho": "0.8 MB",
        "hyperlinked-notebook-mono": "0.8 MB",
        "engineering-graph-paper": "2.8 MB",
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
            "product_type": m["product_type"],
            "collection": "digital-downloads",
            "equation_type": "none",
            "description": m["description"],
            "price_usd": 2.99,
            "contents_json": json.dumps([
                {
                    "title": m["contents_title"],
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


def seed_digital_etsy_batch10(file_meta: dict[str, dict] | None = None) -> None:
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
        print("Copying Batch 6 assets from wallart_set output …")
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
            seed_digital_etsy_batch10(file_meta)
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
