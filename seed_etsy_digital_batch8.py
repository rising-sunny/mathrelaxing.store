"""
seed_etsy_digital_batch8.py — Batch 4 of Etsy → web: wall-art sets + Reader OS.

Products (all active on Etsy, assets from C:\\repos\\Etsy_mathrelaxing):
  1. reader-os-stickers          $2.99  (Etsy 4540003882)
  2. morris-botanical-print-set  $3.99  (Etsy 4539170520)
  3. sage-neutral-print-set      $3.99  (Etsy 4536825589)
  4. famous-equations-print-set  $3.99  (Etsy 4540082607)
  5. mandelbrot-zoom-poster      $2.99  (Etsy 4540109240)

Same delivery pattern as batch4/5:
  - item_type="file" + private_downloads/ (multi-file OK: one entry per zip)
  - gallery: static/digital/<slug>/
  - card: static/previews/<slug>.jpg
  - cover: static/img/<slug>_cover.jpg

Run:
    python seed_etsy_digital_batch8.py --assets     # local: copy assets + try seed
    python seed_etsy_digital_batch8.py --seed-only  # VPS: DB upsert only
    python seed_etsy_digital_batch8.py --verify
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ETSY = Path(r"C:\repos\Etsy_mathrelaxing")

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


# src_files: [(source_path, dest_filename)] — first one is the primary file_url.
ASSET_JOBS = [
    {
        "slug": "reader-os-stickers",
        "src_files": [
            (ETSY / "reader_os" / "MathRelaxing_Reader_OS_Stickers.zip", "reader-os-stickers.zip"),
        ],
        "preview_dir": ETSY / "reader_os" / "previews",
        "hero": ETSY / "reader_os" / "previews" / "reader_os_preview_1_hero.jpg",
        "gallery": [
            ("reader_os_preview_1_hero.jpg", "01_hero.jpg"),
            ("reader_os_preview_2_ipad.jpg", "02_ipad.jpg"),
            ("reader_os_preview_3_modules.jpg", "03_modules.jpg"),
            ("reader_os_preview_4_included.jpg", "04_included.jpg"),
            ("reader_os_preview_5_howto.jpg", "05_howto.jpg"),
            ("reader_os_preview_6_sheet.jpg", "06_sheet.jpg"),
        ],
        "preview_video": ETSY / "reader_os" / "Reader_OS_promo.mp4",
    },
    {
        "slug": "morris-botanical-print-set",
        "src_files": [
            (ETSY / "morris_set" / "MathRelaxing_Morris_01_Willow.zip", "morris-01-willow.zip"),
            (ETSY / "morris_set" / "MathRelaxing_Morris_02_Strawberry.zip", "morris-02-strawberry.zip"),
            (ETSY / "morris_set" / "MathRelaxing_Morris_03_Trellis.zip", "morris-03-trellis.zip"),
            (
                ETSY / "morris_set" / "MathRelaxing_Morris_04_05_Pimpernel_Honeysuckle.zip",
                "morris-04-05-pimpernel-honeysuckle.zip",
            ),
            (ETSY / "morris_set" / "MathRelaxing_Morris_06_Acanthus.zip", "morris-06-acanthus.zip"),
        ],
        "preview_dir": ETSY / "morris_set" / "previews",
        "hero": ETSY / "morris_set" / "previews" / "morris_preview_1_hero.jpg",
        "gallery": [
            ("morris_preview_1_hero.jpg", "01_hero.jpg"),
            ("morris_preview_2_set.jpg", "02_set.jpg"),
            ("morris_preview_3_included.jpg", "03_included.jpg"),
            ("morris_preview_4_willow_boughs.jpg", "04_willow_boughs.jpg"),
            ("morris_preview_5_strawberry_garden.jpg", "05_strawberry_garden.jpg"),
            ("morris_preview_6_trellis_rose.jpg", "06_trellis_rose.jpg"),
            ("morris_preview_7_pimpernel_field.jpg", "07_pimpernel_field.jpg"),
            ("morris_preview_8_honeysuckle.jpg", "08_honeysuckle.jpg"),
            ("morris_preview_9_acanthus_scroll.jpg", "09_acanthus_scroll.jpg"),
            ("morris_preview_10_all.jpg", "10_all.jpg"),
        ],
    },
    {
        "slug": "sage-neutral-print-set",
        "src_files": [
            (ETSY / "sage_set" / "MathRelaxing_Sage_Neutral_Print_Set.zip", "sage-neutral-print-set.zip"),
        ],
        "preview_dir": ETSY / "sage_set" / "previews",
        "hero": ETSY / "sage_set" / "previews" / "sage_preview_1_hero.jpg",
        "gallery": [
            ("sage_preview_1_hero.jpg", "01_hero.jpg"),
            ("sage_preview_2_set.jpg", "02_set.jpg"),
            ("sage_preview_3_included.jpg", "03_included.jpg"),
            ("sage_preview_4_balance_forms.jpg", "04_balance_forms.jpg"),
            ("sage_preview_5_stacked_horizon.jpg", "05_stacked_horizon.jpg"),
            ("sage_preview_6_arch_still.jpg", "06_arch_still.jpg"),
            ("sage_preview_7_rings_field.jpg", "07_rings_field.jpg"),
            ("sage_preview_8_grid_calm.jpg", "08_grid_calm.jpg"),
            ("sage_preview_9_path_stone.jpg", "09_path_stone.jpg"),
            ("sage_preview_10_all.jpg", "10_all.jpg"),
        ],
    },
    {
        "slug": "famous-equations-print-set",
        "src_files": [
            (
                ETSY / "equation_plates" / "famous_equations_set" / "Famous_Equations_Wall_Art_Set_of_6.zip",
                "famous-equations-print-set.zip",
            ),
        ],
        "preview_dir": ETSY / "equation_plates" / "famous_equations_set" / "previews",
        "hero": ETSY / "equation_plates" / "famous_equations_set" / "previews" / "famous_equations_preview_1_hero.jpg",
        "gallery": [
            ("famous_equations_preview_1_hero.jpg", "01_hero.jpg"),
            ("famous_equations_preview_2_included.jpg", "02_included.jpg"),
            ("famous_equations_preview_3_eq.jpg", "03_eq.jpg"),
            ("famous_equations_preview_4_eq.jpg", "04_eq.jpg"),
            ("famous_equations_preview_5_eq.jpg", "05_eq.jpg"),
            ("famous_equations_preview_6_eq.jpg", "06_eq.jpg"),
        ],
    },
    {
        "slug": "mandelbrot-zoom-poster",
        "src_files": [
            (
                ETSY / "special_plates" / "mandelbrot_zoom" / "Mandelbrot_Zoom_Math_Wall_Art.zip",
                "mandelbrot-zoom-poster.zip",
            ),
        ],
        "preview_dir": ETSY / "special_plates" / "mandelbrot_zoom" / "previews",
        "hero": ETSY / "special_plates" / "mandelbrot_zoom" / "previews" / "mandelbrot_zoom_preview_1_hero.jpg",
        "gallery": [
            ("mandelbrot_zoom_preview_1_hero.jpg", "01_hero.jpg"),
            ("mandelbrot_zoom_preview_2_detail.jpg", "02_detail.jpg"),
            ("mandelbrot_zoom_preview_3_included.jpg", "03_included.jpg"),
            ("mandelbrot_zoom_preview_4_plate.jpg", "04_plate.jpg"),
            ("mandelbrot_zoom_preview_5_equation.jpg", "05_equation.jpg"),
        ],
    },
]


def copy_assets() -> dict[str, dict]:
    if not ETSY.is_dir():
        raise SystemExit(f"Etsy source not found: {ETSY}")

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

        if job.get("preview_video") and Path(job["preview_video"]).exists():
            _copy(Path(job["preview_video"]), STATIC_DIG / slug / "00_preview.mp4")

        meta[slug] = {"files": files}
        total = sum(f["bytes"] for f in files)
        print(f"  OK  {slug:36s}  {_fmt_size(total):>8s}  ({len(files)} file(s))")

    return meta


def _sizes(file_meta: dict[str, dict] | None, slug: str, fallbacks: list[str]) -> list[str]:
    if file_meta and slug in file_meta:
        return [f["file_size"] for f in file_meta[slug]["files"]]
    return fallbacks


def build_products(file_meta: dict[str, dict] | None = None) -> list[dict]:
    reader_sz = _sizes(file_meta, "reader-os-stickers", ["11.1 MB"])
    morris_sz = _sizes(
        file_meta, "morris-botanical-print-set",
        ["8.9 MB", "10.2 MB", "14.9 MB", "15.9 MB", "4.8 MB"],
    )
    sage_sz = _sizes(file_meta, "sage-neutral-print-set", ["5.9 MB"])
    famous_sz = _sizes(file_meta, "famous-equations-print-set", ["4.5 MB"])
    mandel_sz = _sizes(file_meta, "mandelbrot-zoom-poster", ["3.3 MB"])

    products = [
        {
            "slug": "reader-os-stickers",
            "name": "Reader OS — iPad Reading Journal Sticker System",
            "product_type": "creator_assets",
            "collection": "digital-downloads",
            "equation_type": "none",
            "description": (
                "Instant download — Reader OS digital sticker system for iPad readers. "
                "Made for digital reading logs in GoodNotes, Notability, Procreate and Freeform — "
                "not a random cute pack, a functional sticker system for your reading life.\n\n"
                "Six modules that work together: STATUS (Currently Reading, TBR, DNF, Finished…), "
                "PROGRESS (10%–100% rings, Cliffhanger), RATING (1–5 stars + Life Changing), "
                "GENRE (Fantasy, Romance, Thriller, Sci-Fi…), ANNOTATION (Plot Twist, Highlight, "
                "Trope Unlocked…), MOOD (Cozy, Spicy, Dark Academia…), plus chips and mini book icons.\n\n"
                "61 individual transparent PNG stickers (900×900, crisp on retina iPad), organized "
                "by module, plus an all-stickers sheet. Import once, reuse forever."
            ),
            "price_usd": 2.99,
            "contents_json": json.dumps([
                {
                    "title": "Reader OS Stickers — 61 transparent PNGs by module + sheet",
                    "item_type": "file",
                    "filename": "reader-os-stickers.zip",
                    "size": reader_sz[0],
                },
            ]),
            "cover_image": "/static/img/reader-os-stickers_cover.jpg",
            "thumbnail_url": "/static/previews/reader-os-stickers.jpg",
            "file_url": "private_downloads/reader-os-stickers.zip",
            "file_size": reader_sz[0],
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "morris-botanical-print-set",
            "name": "William Morris Botanical Print Set — 6 Posters",
            "product_type": "thematic_bundle",
            "collection": "digital-downloads",
            "equation_type": "none",
            "description": (
                "Instant download — William Morris–inspired botanical print set (6 posters). "
                "Six original Arts & Crafts botanical compositions: Willow Boughs, Strawberry "
                "Garden, Trellis Rose, Pimpernel Field, Honeysuckle, and Acanthus Scroll. "
                "Rich indigo, cream, sage, and rose tones for a timeless gallery wall.\n\n"
                "Original drawings (not wallpaper scans), built for LARGE posters: true 300 dpi "
                "masters up to 24×36 in and ISO A1. Delivered as five ZIPs (one or two designs "
                "each) with folders per design."
            ),
            "price_usd": 3.99,
            "contents_json": json.dumps([
                {
                    "title": "Morris 01 — Willow Boughs (300 dpi, all sizes)",
                    "item_type": "file",
                    "filename": "morris-01-willow.zip",
                    "size": morris_sz[0],
                },
                {
                    "title": "Morris 02 — Strawberry Garden (300 dpi, all sizes)",
                    "item_type": "file",
                    "filename": "morris-02-strawberry.zip",
                    "size": morris_sz[1],
                },
                {
                    "title": "Morris 03 — Trellis Rose (300 dpi, all sizes)",
                    "item_type": "file",
                    "filename": "morris-03-trellis.zip",
                    "size": morris_sz[2],
                },
                {
                    "title": "Morris 04+05 — Pimpernel Field & Honeysuckle (300 dpi)",
                    "item_type": "file",
                    "filename": "morris-04-05-pimpernel-honeysuckle.zip",
                    "size": morris_sz[3],
                },
                {
                    "title": "Morris 06 — Acanthus Scroll (300 dpi, all sizes)",
                    "item_type": "file",
                    "filename": "morris-06-acanthus.zip",
                    "size": morris_sz[4],
                },
            ]),
            "cover_image": "/static/img/morris-botanical-print-set_cover.jpg",
            "thumbnail_url": "/static/previews/morris-botanical-print-set.jpg",
            "file_url": "private_downloads/morris-01-willow.zip",
            "file_size": morris_sz[0],
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "sage-neutral-print-set",
            "name": "Sage Green Neutral Print Set — 6 Japandi Posters",
            "product_type": "thematic_bundle",
            "collection": "digital-downloads",
            "equation_type": "none",
            "description": (
                "Instant download — Sage Green Neutral Abstract print set (6 posters). "
                "Six quiet-luxury abstract compositions in sage, cream, stone, and soft clay — "
                "calm gallery wall art for modern, Japandi, and neutral interiors.\n\n"
                "Designs: Balance Forms, Stacked Horizon, Arch Still, Rings Field, Grid Calm, "
                "and Path Stone. Clean forms, generous space, museum-soft palette.\n\n"
                "High-quality JPG @ 300 dpi: 24×36, 18×24, 16×20, 12×18, A4. One ZIP with "
                "folders per design + README."
            ),
            "price_usd": 3.99,
            "contents_json": json.dumps([
                {
                    "title": "Sage Neutral Print Set — 6 designs (300 dpi JPG)",
                    "item_type": "file",
                    "filename": "sage-neutral-print-set.zip",
                    "size": sage_sz[0],
                },
            ]),
            "cover_image": "/static/img/sage-neutral-print-set_cover.jpg",
            "thumbnail_url": "/static/previews/sage-neutral-print-set.jpg",
            "file_url": "private_downloads/sage-neutral-print-set.zip",
            "file_size": sage_sz[0],
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "famous-equations-print-set",
            "name": "Famous Equations Wall Art — Set of 6 Scientific Plates",
            "product_type": "thematic_bundle",
            "collection": "digital-downloads",
            "equation_type": "none",
            "description": (
                "Instant download — Famous Equations wall art set of 6 scientific plates. "
                "Six MathRelaxing gallery prints in one download: Fourier Series (square-wave "
                "harmonics), Wave Equation (standing modes), Dirac Equation (matter & antimatter), "
                "Navier–Stokes (flow past a cylinder), Euler's Identity (complex unit circle), "
                "and the Mandelbrot Set (geometry of chaos).\n\n"
                "Same cream graph-paper family as our Maxwell and Schrödinger plates, with real "
                "LaTeX equations. Masters @ 300 dpi (12×18 / 2:3 + A4 per design). Build a STEM "
                "gallery wall in one click — matte paper recommended."
            ),
            "price_usd": 3.99,
            "contents_json": json.dumps([
                {
                    "title": "Famous Equations Set — 6 plates @ 300 dpi (2:3 + A4)",
                    "item_type": "file",
                    "filename": "famous-equations-print-set.zip",
                    "size": famous_sz[0],
                },
            ]),
            "cover_image": "/static/img/famous-equations-print-set_cover.jpg",
            "thumbnail_url": "/static/previews/famous-equations-print-set.jpg",
            "file_url": "private_downloads/famous-equations-print-set.zip",
            "file_size": famous_sz[0],
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "mandelbrot-zoom-poster",
            "name": "Mandelbrot Zoom — Seahorse Valley Fractal Print",
            "product_type": "thematic_bundle",
            "collection": "digital-downloads",
            "equation_type": "mandelbrot",
            "description": (
                "Instant download — Infinite Coastline: a deep Mandelbrot zoom into seahorse "
                "valley with smooth escape-time coloring. Companion plate to the classic full-set "
                "Mandelbrot portrait, in the cream/ink/rust scientific-plate style.\n\n"
                "High-quality JPG @ 300 dpi in 2:3, 3:4, 4:5, 5:7, ISO A4 and A3. One ZIP, "
                "no physical item ships. For chaos-theory fans, fractal lovers, and math "
                "gallery walls."
            ),
            "price_usd": 2.99,
            "contents_json": json.dumps([
                {
                    "title": "Mandelbrot Zoom plate — 300 dpi (2:3, 3:4, 4:5, 5:7, A4, A3)",
                    "item_type": "file",
                    "filename": "mandelbrot-zoom-poster.zip",
                    "size": mandel_sz[0],
                },
            ]),
            "cover_image": "/static/img/mandelbrot-zoom-poster_cover.jpg",
            "thumbnail_url": "/static/previews/mandelbrot-zoom-poster.jpg",
            "file_url": "private_downloads/mandelbrot-zoom-poster.zip",
            "file_size": mandel_sz[0],
            "license_type": "personal",
            "active": True,
        },
    ]
    return products


def seed_digital_etsy_batch8(file_meta: dict[str, dict] | None = None) -> None:
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
        for item in json.loads(p["contents_json"]):
            checks.insert(1, PRIVATE / item["filename"])
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
        print("Copying Batch 4 assets from Etsy_mathrelaxing …")
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
            seed_digital_etsy_batch8(file_meta)
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
