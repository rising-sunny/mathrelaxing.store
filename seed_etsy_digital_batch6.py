"""
seed_etsy_digital_batch6.py — Batch 3a of Etsy → web.

Only products with *local* deliverables (Etsy API cannot re-download digital files).

  1. bauhaus-print-set              $9.99  (Etsy draft-ready assets)
  2. mathematical-constants-bundle  $6.99  (active Etsy 4534820167)
  3. beautiful-equations-print-set  $6.99  (active Etsy 4534831774)
  4. golden-ratio-poster            $5.50  (active Etsy 4537362085)

Sources:
  - C:\\repos\\Etsy_mathrelaxing\\bauhaus_set\\
  - C:\\Users\\sunse\\Downloads\\Mathematical_Constants_Bundle.zip + GitHub previews
  - C:\\Users\\sunse\\Downloads\\Beautiful_Equations_Bundle.zip + GitHub
  - C:\\Users\\sunse\\Downloads\\GoldenRatio_prints.zip + Etsy listing images

Run:
    python seed_etsy_digital_batch6.py --assets
    python seed_etsy_digital_batch6.py --seed-only
    python seed_etsy_digital_batch6.py --verify
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ETSY = Path(r"C:\repos\Etsy_mathrelaxing")
DOWNLOADS = Path(r"C:\Users\sunse\Downloads")
GITHUB = Path(r"C:\Users\sunse\Documents\trae_projects\Etsy_MathRelaxing_GitHub")
BATCH3 = ETSY / "batch3_downloads"

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


def _clear_gallery(slug: str) -> Path:
    dest = STATIC_DIG / slug
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*"):
        if old.is_file():
            old.unlink()
    return dest


def _gallery_files(slug: str, files: list[Path]) -> None:
    dest = _clear_gallery(slug)
    for i, src in enumerate(files, start=1):
        if not src.exists():
            raise FileNotFoundError(src)
        if i == 1:
            name = f"01_hero{src.suffix.lower()}"
        else:
            name = f"{i:02d}_sample{src.suffix.lower()}"
        _copy(src, dest / name)


def _find_batch3_dir(listing_id: int) -> Path | None:
    if not BATCH3.exists():
        return None
    for d in BATCH3.iterdir():
        if d.is_dir() and d.name.startswith(f"{listing_id}_"):
            return d
    return None


def _listing_images(listing_id: int) -> list[Path]:
    d = _find_batch3_dir(listing_id)
    if not d:
        return []
    imgs = sorted((d / "images").glob("*.jpg"))
    return imgs


# ── Product definitions ───────────────────────────────────────────────────────

PRODUCTS_META = [
    {
        "slug": "bauhaus-print-set",
        "name": "Bauhaus Wall Art Print Set — 6 Geometric Modern Posters",
        "product_type": "thematic_bundle",
        "collection": "digital-downloads",
        "equation_type": "bauhaus",
        "description": (
            "Instant download — Bauhaus-inspired geometric wall-art set (6 compositions). "
            "Navy, cream and gold MathRelaxing palette: circles & bars, triangles, grid modules, "
            "arcs, form & type, and balance. Multiple print sizes per design (2:3, 3:4, 4:5, 5:7, A3, A4). "
            "Print at home or any print shop."
        ),
        "price_usd": 9.99,
        "src_file": ETSY / "bauhaus_set" / "MathRelaxing_Bauhaus_Print_Set.zip",
        "dest_name": "bauhaus-print-set.zip",
        "hero": ETSY / "bauhaus_set" / "previews" / "bauhaus_preview_1_hero.jpg",
        "gallery_sources": [
            ETSY / "bauhaus_set" / "previews" / "bauhaus_preview_1_hero.jpg",
            ETSY / "bauhaus_set" / "previews" / "bauhaus_preview_2_set.jpg",
            ETSY / "bauhaus_set" / "previews" / "bauhaus_preview_3_included.jpg",
            ETSY / "bauhaus_set" / "previews" / "bauhaus_preview_4_circles_bars.jpg",
            ETSY / "bauhaus_set" / "previews" / "bauhaus_preview_5_triangles.jpg",
            ETSY / "bauhaus_set" / "previews" / "bauhaus_preview_6_grid_modules.jpg",
            ETSY / "bauhaus_set" / "previews" / "bauhaus_preview_7_arcs.jpg",
            ETSY / "bauhaus_set" / "previews" / "bauhaus_preview_8_form_type.jpg",
            ETSY / "bauhaus_set" / "previews" / "bauhaus_preview_9_balance.jpg",
            ETSY / "bauhaus_set" / "previews" / "bauhaus_preview_10_all.jpg",
        ],
        "preview_video": ETSY / "bauhaus_set" / "Bauhaus_Print_Set_promo.mp4",
        "contents_title": "Bauhaus Print Set — 6 designs × multi-size ZIP",
        "fallback_size": "4.4 MB",
    },
    {
        "slug": "mathematical-constants-bundle",
        "name": "Mathematical Constants Bundle — Set of 8 Minimalist Math Posters",
        "product_type": "thematic_bundle",
        "collection": "digital-downloads",
        "equation_type": "latex-typography",
        "description": (
            "Instant download — 8 minimalist posters of iconic mathematical constants: "
            "π, e, the golden ratio φ, √2, the imaginary unit i, infinity, zero, and one. "
            "Each design ships as high-resolution PNG + vector PDF. Perfect for classrooms, "
            "study desks, and STEM gifts."
        ),
        "price_usd": 6.99,
        "src_file": DOWNLOADS / "Mathematical_Constants_Bundle.zip",
        "src_file_alt": GITHUB / "math_constants" / "Mathematical_Constants_Bundle.zip",
        "dest_name": "mathematical-constants-bundle.zip",
        "hero": GITHUB / "math_constants" / "previews" / "preview_1_hero.jpg",
        "gallery_sources": [
            GITHUB / "math_constants" / "previews" / "preview_1_hero.jpg",
            GITHUB / "math_constants" / "previews" / "preview_2_included.jpg",
            GITHUB / "math_constants" / "previews" / "preview_3_details.jpg",
            GITHUB / "math_constants" / "contact_sheet.jpg",
        ],
        "listing_id_images": 4534820167,
        "contents_title": "Mathematical Constants Bundle — 8 posters (PNG + PDF)",
        "fallback_size": "1.5 MB",
    },
    {
        "slug": "beautiful-equations-print-set",
        "name": "Beautiful Equations Print Set — 8 Navy & Gold LaTeX Posters",
        "product_type": "thematic_bundle",
        "collection": "digital-downloads",
        "equation_type": "latex-typography",
        "description": (
            "Instant download — 8 minimalist navy & gold posters of famous equations set in "
            "authentic LaTeX typography: Euler's identity, Pythagorean theorem, Schrödinger equation, "
            "Maxwell's first equation, E=mc², the Gaussian integral, the heat equation, and Bayes' theorem. "
            "PNG + PDF for each design."
        ),
        "price_usd": 6.99,
        "src_file": DOWNLOADS / "Beautiful_Equations_Bundle.zip",
        "src_file_alt": GITHUB / "beautiful_equations" / "Beautiful_Equations_Bundle.zip",
        "dest_name": "beautiful-equations-print-set.zip",
        "hero": GITHUB / "beautiful_equations" / "contact_sheet.jpg",
        "gallery_sources": [
            GITHUB / "beautiful_equations" / "contact_sheet.jpg",
            GITHUB / "beautiful_equations" / "eulers_identity.png",
            GITHUB / "beautiful_equations" / "maxwells_first_equation.png",
            GITHUB / "beautiful_equations" / "einsteins_mass-energy.png",
            GITHUB / "beautiful_equations" / "bayes_theorem.png",
        ],
        "listing_id_images": 4534831774,
        "contents_title": "Beautiful Equations Set — 8 posters (PNG + PDF)",
        "fallback_size": "2.3 MB",
    },
    {
        "slug": "golden-ratio-poster",
        "name": "Golden Ratio Art Print — Fibonacci Spiral Math Poster",
        "product_type": "thematic_bundle",
        "collection": "digital-downloads",
        "equation_type": "golden-ratio",
        "description": (
            "Instant download — scientific golden-ratio / Fibonacci spiral wall art. "
            "Print-ready files in multiple aspect ratios (2:3, 3:4, 4:5, 5:7, ISO). "
            "Clean MathRelaxing plate style for classrooms, studios, and STEM décor."
        ),
        "price_usd": 5.50,
        "src_file": DOWNLOADS / "GoldenRatio_prints.zip",
        "dest_name": "golden-ratio-poster.zip",
        "hero": None,  # prefer Etsy listing image
        "gallery_sources": [],
        "listing_id_images": 4537362085,
        "contents_title": "Golden Ratio Poster — multi-size ZIP",
        "fallback_size": "0.6 MB",
    },
]


def _resolve_src(job: dict) -> Path:
    src = Path(job["src_file"])
    if src.exists():
        return src
    alt = job.get("src_file_alt")
    if alt and Path(alt).exists():
        return Path(alt)
    raise FileNotFoundError(f"Missing deliverable for {job['slug']}: {src}")


def copy_assets() -> dict[str, dict]:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    meta: dict[str, dict] = {}

    for job in PRODUCTS_META:
        slug = job["slug"]
        src = _resolve_src(job)
        dest_name = job["dest_name"]
        priv = _copy(src, PRIVATE / dest_name)
        _copy(src, STATIC_DL / dest_name)

        # Gallery: prefer curated sources, fill from Etsy listing images
        gallery: list[Path] = []
        for p in job.get("gallery_sources") or []:
            if Path(p).exists():
                gallery.append(Path(p))
        lid = job.get("listing_id_images")
        if lid:
            for p in _listing_images(int(lid)):
                if p not in gallery:
                    gallery.append(p)
        hero = job.get("hero")
        if hero and Path(hero).exists():
            hero_p = Path(hero)
        elif gallery:
            hero_p = gallery[0]
        else:
            raise FileNotFoundError(f"No hero/preview for {slug}")

        if not gallery:
            gallery = [hero_p]

        _write_preview_jpg(hero_p, slug)
        _copy(hero_p, STATIC_IMG / f"{slug}_cover.jpg")
        _gallery_files(slug, gallery[:10])

        if job.get("preview_video") and Path(job["preview_video"]).exists():
            _copy(Path(job["preview_video"]), STATIC_DIG / slug / "00_preview.mp4")

        size = priv.stat().st_size
        meta[slug] = {
            "filename": dest_name,
            "file_size": _fmt_size(size),
            "bytes": size,
        }
        print(f"  OK  {slug:36s}  {_fmt_size(size):>8s}  → private_downloads/{dest_name}")

    return meta


def build_products(file_meta: dict[str, dict] | None = None) -> list[dict]:
    def size_for(slug: str, fallback: str) -> str:
        if file_meta and slug in file_meta:
            return file_meta[slug]["file_size"]
        return fallback

    def fname(slug: str, fallback: str) -> str:
        if file_meta and slug in file_meta:
            return file_meta[slug]["filename"]
        return fallback

    products = []
    for job in PRODUCTS_META:
        slug = job["slug"]
        dest = job["dest_name"]
        products.append(
            {
                "slug": slug,
                "name": job["name"],
                "product_type": job["product_type"],
                "collection": job["collection"],
                "equation_type": job["equation_type"],
                "description": job["description"],
                "price_usd": job["price_usd"],
                "contents_json": json.dumps(
                    [
                        {
                            "title": job["contents_title"],
                            "item_type": "file",
                            "filename": fname(slug, dest),
                            "size": size_for(slug, job["fallback_size"]),
                        }
                    ]
                ),
                "cover_image": f"/static/img/{slug}_cover.jpg",
                "thumbnail_url": f"/static/previews/{slug}.jpg",
                "file_url": f"private_downloads/{dest}",
                "file_size": size_for(slug, job["fallback_size"]),
                "license_type": "personal",
                "active": True,
            }
        )
    return products


def seed_digital_etsy_batch6(file_meta: dict[str, dict] | None = None) -> None:
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
        checks = [
            ROOT / p["file_url"],
            ROOT / p["cover_image"].lstrip("/").replace("/", os.sep),
            ROOT / p["thumbnail_url"].lstrip("/").replace("/", os.sep),
            STATIC_DIG / slug,
        ]
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
        print("Copying Batch 3a assets …")
        file_meta = copy_assets()
        print()

    if do_seed and not do_verify:
        if file_meta is None:
            guessed = {}
            for job in PRODUCTS_META:
                p = PRIVATE / job["dest_name"]
                if p.exists():
                    guessed[job["slug"]] = {
                        "filename": job["dest_name"],
                        "file_size": _fmt_size(p.stat().st_size),
                        "bytes": p.stat().st_size,
                    }
            file_meta = guessed or None
        print("Seeding digital_products …")
        try:
            seed_digital_etsy_batch6(file_meta)
        except Exception as e:
            print(f"DB seed skipped/failed ({type(e).__name__}: {e})")
            print("Assets (if copied) are ready; run on VPS with SQLAlchemy.")

    if do_verify or do_assets:
        print("\nVerifying assets …")
        if verify_assets():
            print("All asset paths present.")
        else:
            print("Some assets missing — re-run with --assets.")
            sys.exit(1)
