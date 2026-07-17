"""
seed_etsy_digital_batch4.py — Batch 1 of Etsy → web: STEM prints, notebooks, loops.

Products (all active on Etsy, assets from C:\\repos\\Etsy_mathrelaxing):
  1. happy-chemicals-print-set
  2. computer-science-poster-set
  3. unit-circle-poster
  4. schrodinger-equation-print
  5. stem-lab-notebook
  6. stem-digital-notebook
  7. julia-set-loop
  8. voronoi-cell-garden-loop

Delivery pattern (same as add_planners_to_db.py):
  - contents_json items use item_type="file" + filename
  - paid files live in private_downloads/ (token-gated via /api/digital-file)
  - product page gallery: static/digital/<slug>/
  - collection card: static/previews/<slug>.jpg
  - cover / OG: static/img/<slug>_cover.jpg (or cover_image path)

Run:
    python seed_etsy_digital_batch4.py           # seed DB only
    python seed_etsy_digital_batch4.py --assets  # copy assets + seed
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
    """Card preview + clean zoom copy under static/previews/."""
    from PIL import Image

    STATIC_PREV.mkdir(parents=True, exist_ok=True)
    img = Image.open(src).convert("RGB")

    # Full-res clean for zoom / HQ fallbacks
    clean = STATIC_PREV / f"{slug}_clean.jpg"
    img.save(clean, "JPEG", quality=90, optimize=True)

    # Card-sized preview (max 900px on the long edge)
    card = img.copy()
    card.thumbnail((900, 900), Image.Resampling.LANCZOS)
    card.save(STATIC_PREV / f"{slug}.jpg", "JPEG", quality=85, optimize=True)


def _gallery_from_previews(src_dir: Path, slug: str, rename_map: list[tuple[str, str]] | None = None) -> None:
    """Copy preview images into static/digital/<slug>/ for bundle_download gallery."""
    dest = STATIC_DIG / slug
    dest.mkdir(parents=True, exist_ok=True)
    # clear old gallery images only (keep any hand-added assets)
    for old in dest.glob("*"):
        if old.is_file():
            old.unlink()

    if rename_map:
        for i, (src_name, dest_name) in enumerate(rename_map, start=1):
            src = src_dir / src_name
            if not src.exists():
                raise FileNotFoundError(src)
            _copy(src, dest / dest_name)
        return

    files = sorted(src_dir.glob("*.jpg")) + sorted(src_dir.glob("*.png"))
    for i, src in enumerate(files, start=1):
        # Prefer hero first via name sort; renumber for stable order
        suffix = "hero" if i == 1 or "hero" in src.name.lower() else f"sample"
        if "hero" in src.name.lower():
            name = f"01_hero{src.suffix.lower()}"
        else:
            name = f"{i:02d}_{suffix}{src.suffix.lower()}"
        _copy(src, dest / name)


# ── Asset map ────────────────────────────────────────────────────────────────
# Each entry: deliverable copy + gallery + covers.

ASSET_JOBS = [
    {
        "slug": "happy-chemicals-print-set",
        "src_file": ETSY / "happy_chemicals" / "Happy_Chemicals_Print_Set.zip",
        "dest_name": "happy-chemicals-print-set.zip",
        "preview_dir": ETSY / "happy_chemicals" / "previews",
        "hero": ETSY / "happy_chemicals" / "previews" / "happy_chemicals_preview_1_hero.jpg",
        "gallery": [
            ("happy_chemicals_preview_1_hero.jpg", "01_hero.jpg"),
            ("happy_chemicals_preview_2_set.jpg", "02_set.jpg"),
            ("happy_chemicals_preview_3_included.jpg", "03_included.jpg"),
            ("happy_chemicals_preview_4_serotonin.jpg", "04_serotonin.jpg"),
            ("happy_chemicals_preview_5_dopamine.jpg", "05_dopamine.jpg"),
            ("happy_chemicals_preview_6_oxytocin.jpg", "06_oxytocin.jpg"),
            ("happy_chemicals_preview_7_caffeine.jpg", "07_caffeine.jpg"),
        ],
    },
    {
        "slug": "computer-science-poster-set",
        "src_file": ETSY / "cs_poster_set" / "Computer_Science_Poster_Set.zip",
        "dest_name": "computer-science-poster-set.zip",
        "preview_dir": ETSY / "cs_poster_set" / "previews",
        "hero": ETSY / "cs_poster_set" / "previews" / "cs_preview_1_hero.jpg",
        "gallery": [
            ("cs_preview_1_hero.jpg", "01_hero.jpg"),
            ("cs_preview_2_set.jpg", "02_set.jpg"),
            ("cs_preview_3_included.jpg", "03_included.jpg"),
            ("cs_preview_big_o.jpg", "04_big_o.jpg"),
            ("cs_preview_bst.jpg", "05_bst.jpg"),
            ("cs_preview_sorting.jpg", "06_sorting.jpg"),
            ("cs_preview_logic.jpg", "07_logic.jpg"),
            ("cs_preview_osi.jpg", "08_osi.jpg"),
            ("cs_preview_stack_queue.jpg", "09_stack_queue.jpg"),
            ("cs_preview_fsm.jpg", "10_fsm.jpg"),
        ],
    },
    {
        "slug": "unit-circle-poster",
        "src_file": ETSY / "unit_circle" / "Unit_Circle_Trigonometry_Wall_Art.zip",
        "dest_name": "unit-circle-poster.zip",
        "preview_dir": ETSY / "unit_circle" / "previews",
        "hero": ETSY / "unit_circle" / "previews" / "unit_circle_preview_1_hero.jpg",
        "gallery": [
            ("unit_circle_preview_1_hero.jpg", "01_hero.jpg"),
            ("unit_circle_preview_2_detail.jpg", "02_detail.jpg"),
            ("unit_circle_preview_3_included.jpg", "03_included.jpg"),
            ("unit_circle_preview_4_plate.jpg", "04_plate.jpg"),
            ("unit_circle_preview_5_equation.jpg", "05_equation.jpg"),
        ],
    },
    {
        "slug": "schrodinger-equation-print",
        "src_file": ETSY / "schrodinger_equation" / "Schrodinger_Equation_Physics_Wall_Art.zip",
        "dest_name": "schrodinger-equation-print.zip",
        "preview_dir": ETSY / "schrodinger_equation" / "previews",
        "hero": ETSY / "schrodinger_equation" / "previews" / "schrodinger_preview_1_hero.jpg",
        "gallery": [
            ("schrodinger_preview_1_hero.jpg", "01_hero.jpg"),
            ("schrodinger_preview_2_detail.jpg", "02_detail.jpg"),
            ("schrodinger_preview_3_included.jpg", "03_included.jpg"),
            ("schrodinger_preview_4_plate.jpg", "04_plate.jpg"),
            ("schrodinger_preview_5_equation.jpg", "05_equation.jpg"),
        ],
    },
    {
        "slug": "stem-lab-notebook",
        "src_file": ETSY / "lab_notebook" / "STEM_Lab_Notebook.pdf",
        "dest_name": "stem-lab-notebook.pdf",
        "preview_dir": ETSY / "lab_notebook" / "previews",
        "hero": ETSY / "lab_notebook" / "previews" / "lab_notebook_preview_1_hero.jpg",
        "gallery": [
            ("lab_notebook_preview_1_hero.jpg", "01_hero.jpg"),
            ("lab_notebook_preview_2_pages.jpg", "02_pages.jpg"),
            ("lab_notebook_preview_3_included.jpg", "03_included.jpg"),
            ("lab_notebook_preview_4_experiment.jpg", "04_experiment.jpg"),
            ("lab_notebook_preview_5_graph.jpg", "05_graph.jpg"),
            ("lab_notebook_preview_6_chemistry.jpg", "06_chemistry.jpg"),
        ],
    },
    {
        "slug": "stem-digital-notebook",
        "src_file": ETSY / "stem_notebook" / "STEM_Notebook.pdf",
        "dest_name": "stem-digital-notebook.pdf",
        "preview_dir": ETSY / "stem_notebook" / "previews",
        "hero": ETSY / "stem_notebook" / "previews" / "stem_preview_1_hero.jpg",
        "gallery": [
            ("stem_preview_1_hero.jpg", "01_hero.jpg"),
            ("stem_preview_2_grids.jpg", "02_grids.jpg"),
            ("stem_preview_3_tabs.jpg", "03_tabs.jpg"),
            ("stem_preview_4_included.jpg", "04_included.jpg"),
        ],
    },
    {
        "slug": "julia-set-loop",
        "src_file": ETSY / "julia" / "JuliaMorph_01.mp4",
        "dest_name": "julia-set-loop.mp4",
        "preview_dir": ETSY / "julia" / "previews",
        "hero": ETSY / "julia" / "previews" / "julia_preview_1_hero.jpg",
        "gallery": [
            ("julia_preview_1_hero.jpg", "01_hero.jpg"),
            ("julia_preview_2_specs.jpg", "02_specs.jpg"),
            ("julia_preview_3_loop.jpg", "03_loop.jpg"),
        ],
        "preview_video": ETSY / "julia" / "JuliaMorph_01_preview.mp4",
    },
    {
        "slug": "voronoi-cell-garden-loop",
        "src_file": ETSY / "voronoi_loop" / "VoronoiCellGarden_loop.mp4",
        "dest_name": "voronoi-cell-garden-loop.mp4",
        "preview_dir": ETSY / "voronoi_loop" / "previews",
        "hero": ETSY / "voronoi_loop" / "previews" / "voronoi_preview_1_hero.jpg",
        "gallery": [
            ("voronoi_preview_1_hero.jpg", "01_hero.jpg"),
            ("voronoi_preview_2_titled.jpg", "02_titled.jpg"),
            ("voronoi_preview_3_loop.jpg", "03_loop.jpg"),
        ],
        "preview_video": ETSY / "voronoi_loop" / "VoronoiCellGarden_preview.mp4",
    },
]


def copy_assets() -> dict[str, dict]:
    """Copy deliverables + previews. Returns per-slug file metadata."""
    if not ETSY.is_dir():
        raise SystemExit(f"Etsy source not found: {ETSY}")

    PRIVATE.mkdir(parents=True, exist_ok=True)
    meta: dict[str, dict] = {}

    for job in ASSET_JOBS:
        slug = job["slug"]
        src: Path = job["src_file"]
        if not src.exists():
            raise FileNotFoundError(f"Missing source file for {slug}: {src}")

        dest_name = job["dest_name"]
        priv = _copy(src, PRIVATE / dest_name)
        # Also mirror into static/downloads for ops/admin convenience (gitignored).
        # Paid delivery still goes through private_downloads + token gate.
        _copy(src, STATIC_DL / dest_name)

        hero: Path = job["hero"]
        _write_preview_jpg(hero, slug)
        cover_dst = STATIC_IMG / f"{slug}_cover.jpg"
        _copy(hero, cover_dst)

        _gallery_from_previews(job["preview_dir"], slug, job.get("gallery"))

        # Optional low-res preview video for the product gallery (not the paid file)
        if job.get("preview_video") and Path(job["preview_video"]).exists():
            _copy(Path(job["preview_video"]), STATIC_DIG / slug / "00_preview.mp4")

        size = priv.stat().st_size
        meta[slug] = {
            "filename": dest_name,
            "file_size": _fmt_size(size),
            "bytes": size,
        }
        print(f"  OK  {slug:32s}  {_fmt_size(size):>8s}  → private_downloads/{dest_name}")

    return meta


def build_products(file_meta: dict[str, dict] | None = None) -> list[dict]:
    """Product rows for digital_products. file_meta fills sizes if assets were copied."""

    def size_for(slug: str, fallback: str) -> str:
        if file_meta and slug in file_meta:
            return file_meta[slug]["file_size"]
        return fallback

    def fname(slug: str, fallback: str) -> str:
        if file_meta and slug in file_meta:
            return file_meta[slug]["filename"]
        return fallback

    products = [
        {
            "slug": "happy-chemicals-print-set",
            "name": "Happy Chemicals Print Set — Serotonin, Dopamine, Oxytocin & Caffeine",
            "product_type": "thematic_bundle",
            "collection": "digital-downloads",
            "equation_type": "molecule-art",
            "description": (
                "Four minimalist molecular-structure wall-art prints on a warm paper aesthetic: "
                "Serotonin, Dopamine, Oxytocin, and Caffeine. Multiple print sizes per design "
                "(5×7, 8×10, 11×14, 16×20, A4, A3). Instant download ZIP — print at home or any print shop."
            ),
            "price_usd": 8.99,
            "contents_json": json.dumps([
                {
                    "title": "Happy Chemicals Print Set — Serotonin, Dopamine, Oxytocin, Caffeine (6 sizes each)",
                    "item_type": "file",
                    "filename": fname("happy-chemicals-print-set", "happy-chemicals-print-set.zip"),
                    "size": size_for("happy-chemicals-print-set", "10.2 MB"),
                },
            ]),
            "cover_image": "/static/img/happy-chemicals-print-set_cover.jpg",
            "thumbnail_url": "/static/previews/happy-chemicals-print-set.jpg",
            "file_url": "private_downloads/happy-chemicals-print-set.zip",
            "file_size": size_for("happy-chemicals-print-set", "10.2 MB"),
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "computer-science-poster-set",
            "name": "Computer Science Poster Set — Big-O, Trees, Logic Gates & OSI",
            "product_type": "thematic_bundle",
            "collection": "digital-downloads",
            "equation_type": "cs-diagrams",
            "description": (
                "Seven classroom-ready CS diagrams in the MathRelaxing scientific-plate style: "
                "Big-O growth curves, binary search tree, sorting comparison, logic gates, "
                "OSI model, stack & queue, and a finite-state machine. Multiple aspect ratios "
                "per plate (2:3, 3:4, 4:5, 5:7, A4, A3). Instant download ZIP."
            ),
            "price_usd": 9.99,
            "contents_json": json.dumps([
                {
                    "title": "Computer Science Poster Set — 7 plates, multi-size ZIP",
                    "item_type": "file",
                    "filename": fname("computer-science-poster-set", "computer-science-poster-set.zip"),
                    "size": size_for("computer-science-poster-set", "8.6 MB"),
                },
            ]),
            "cover_image": "/static/img/computer-science-poster-set_cover.jpg",
            "thumbnail_url": "/static/previews/computer-science-poster-set.jpg",
            "file_url": "private_downloads/computer-science-poster-set.zip",
            "file_size": size_for("computer-science-poster-set", "8.6 MB"),
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "unit-circle-poster",
            "name": "Unit Circle Poster — Trigonometry Reference Wall Art",
            "product_type": "thematic_bundle",
            "collection": "digital-downloads",
            "equation_type": "unit-circle",
            "description": (
                "A clean scientific unit-circle reference plate — degrees, radians, cosine and sine "
                "coordinates in authentic LaTeX typography. Print-ready files in multiple sizes "
                "(2:3, 3:4, 4:5, 5:7, A3, A4). Perfect for math classrooms, study desks, and STEM gifts."
            ),
            "price_usd": 5.99,
            "contents_json": json.dumps([
                {
                    "title": "Unit Circle Poster — multi-size ZIP",
                    "item_type": "file",
                    "filename": fname("unit-circle-poster", "unit-circle-poster.zip"),
                    "size": size_for("unit-circle-poster", "2.9 MB"),
                },
            ]),
            "cover_image": "/static/img/unit-circle-poster_cover.jpg",
            "thumbnail_url": "/static/previews/unit-circle-poster.jpg",
            "file_url": "private_downloads/unit-circle-poster.zip",
            "file_size": size_for("unit-circle-poster", "2.9 MB"),
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "schrodinger-equation-print",
            "name": "Schrödinger Equation Print — Quantum Mechanics Wall Art",
            "product_type": "thematic_bundle",
            "collection": "digital-downloads",
            "equation_type": "schrodinger",
            "description": (
                "Physics wall art featuring the time-independent Schrödinger equation and a "
                "particle-in-a-box diagram, rendered as a scientific plate. Multiple print sizes "
                "included. Instant digital download — no physical item ships."
            ),
            "price_usd": 5.50,
            "contents_json": json.dumps([
                {
                    "title": "Schrödinger Equation Physics Wall Art — multi-size ZIP",
                    "item_type": "file",
                    "filename": fname("schrodinger-equation-print", "schrodinger-equation-print.zip"),
                    "size": size_for("schrodinger-equation-print", "2.5 MB"),
                },
            ]),
            "cover_image": "/static/img/schrodinger-equation-print_cover.jpg",
            "thumbnail_url": "/static/previews/schrodinger-equation-print.jpg",
            "file_url": "private_downloads/schrodinger-equation-print.zip",
            "file_size": size_for("schrodinger-equation-print", "2.5 MB"),
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "stem-lab-notebook",
            "name": "STEM Lab Notebook — Printable Science Experiment Log",
            "product_type": "digital_notebook",
            "collection": "digital-downloads",
            "equation_type": "none",
            "description": (
                "48-page printable / iPad lab notebook built for real experiments: scientific-method "
                "logs, data tables, observation pages, graph & dot grids, chemistry/physics/biology "
                "layouts, inventory and safety checklist. Hyperlinked for GoodNotes & Notability. "
                "US Letter PDF — instant download."
            ),
            "price_usd": 7.99,
            "contents_json": json.dumps([
                {
                    "title": "STEM Lab Notebook — 48-page hyperlinked PDF",
                    "item_type": "file",
                    "filename": fname("stem-lab-notebook", "stem-lab-notebook.pdf"),
                    "size": size_for("stem-lab-notebook", "0.7 MB"),
                },
            ]),
            "cover_image": "/static/img/stem-lab-notebook_cover.jpg",
            "thumbnail_url": "/static/previews/stem-lab-notebook.jpg",
            "file_url": "private_downloads/stem-lab-notebook.pdf",
            "file_size": size_for("stem-lab-notebook", "0.7 MB"),
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "stem-digital-notebook",
            "name": "STEM Digital Notebook — Hex, Isometric, Dot & Cornell Grids",
            "product_type": "digital_notebook",
            "collection": "digital-downloads",
            "equation_type": "none",
            "description": (
                "142-page hyperlinked digital notebook for GoodNotes, Notability and any PDF app. "
                "Seven grid types students actually use: dot, graph, hexagonal, isometric, Cornell, "
                "polar and lined — with side-tab navigation for instant jumps. Landscape 4:3 for iPad."
            ),
            "price_usd": 2.99,
            "contents_json": json.dumps([
                {
                    "title": "STEM Digital Notebook — 142-page hyperlinked PDF",
                    "item_type": "file",
                    "filename": fname("stem-digital-notebook", "stem-digital-notebook.pdf"),
                    "size": size_for("stem-digital-notebook", "1.0 MB"),
                },
            ]),
            "cover_image": "/static/img/stem-digital-notebook_cover.jpg",
            "thumbnail_url": "/static/previews/stem-digital-notebook.jpg",
            "file_url": "private_downloads/stem-digital-notebook.pdf",
            "file_size": size_for("stem-digital-notebook", "1.0 MB"),
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "julia-set-loop",
            "name": "Julia Set Seamless Loop — Fractal Animation Wallpaper",
            "product_type": "animation_pack",
            "collection": "digital-downloads",
            "equation_type": "julia",
            "description": (
                "A Julia set fractal endlessly morphing as its parameter glides along the edge of "
                "the Mandelbrot set — teal and gold on deep navy. Seamless ~12 s loop, 1080×1080, "
                "60 fps MP4. Perfect for wallpapers, screensavers, digital frames and social backgrounds."
            ),
            "price_usd": 4.99,
            "contents_json": json.dumps([
                {
                    "title": "Julia Set Morph Loop — 1080×1080 60fps MP4",
                    "item_type": "file",
                    "filename": fname("julia-set-loop", "julia-set-loop.mp4"),
                    "size": size_for("julia-set-loop", "12.6 MB"),
                },
            ]),
            "cover_image": "/static/img/julia-set-loop_cover.jpg",
            "thumbnail_url": "/static/previews/julia-set-loop.jpg",
            "file_url": "private_downloads/julia-set-loop.mp4",
            "file_size": size_for("julia-set-loop", "12.6 MB"),
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "voronoi-cell-garden-loop",
            "name": "Voronoi Cell Garden Loop — Organic Mosaic Animation",
            "product_type": "animation_pack",
            "collection": "digital-downloads",
            "equation_type": "voronoi",
            "description": (
                "A living Voronoi mosaic along a golden-angle spiral — cells pulse in amethyst, "
                "rose and gold with stained-glass borders. Seamless 10 s loop, 1080×1080, 30 fps MP4. "
                "Ambient wallpaper for meditation, streams and digital frames."
            ),
            "price_usd": 4.99,
            "contents_json": json.dumps([
                {
                    "title": "Voronoi Cell Garden Loop — 1080×1080 30fps MP4",
                    "item_type": "file",
                    "filename": fname("voronoi-cell-garden-loop", "voronoi-cell-garden-loop.mp4"),
                    "size": size_for("voronoi-cell-garden-loop", "2.5 MB"),
                },
            ]),
            "cover_image": "/static/img/voronoi-cell-garden-loop_cover.jpg",
            "thumbnail_url": "/static/previews/voronoi-cell-garden-loop.jpg",
            "file_url": "private_downloads/voronoi-cell-garden-loop.mp4",
            "file_size": size_for("voronoi-cell-garden-loop", "2.5 MB"),
            "license_type": "personal",
            "active": True,
        },
    ]
    return products


def seed_digital_etsy_batch4(file_meta: dict[str, dict] | None = None) -> None:
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
            print(f"  {action:8s}  {p_data['slug']:32s}  ${p_data['price_usd']:.2f}")
        db.commit()
    finally:
        db.close()
    print(f"Seed complete: {len(products)} products upserted.")


def verify_assets() -> bool:
    ok = True
    products = build_products()
    for p in products:
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
                status = "OK" if n > 0 else "EMPTY"
                if n == 0:
                    ok = False
                print(f"  [{status:5s}] gallery {slug}/ ({n} files)")
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
        print("Copying assets from Etsy_mathrelaxing …")
        file_meta = copy_assets()
        print()

    if do_seed and not do_verify:
        # Prefer live sizes if private_downloads already filled
        if file_meta is None:
            guessed = {}
            for job in ASSET_JOBS:
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
            seed_digital_etsy_batch4(file_meta)
        except Exception as e:
            print(f"DB seed skipped/failed ({type(e).__name__}: {e})")
            print("Assets (if copied) are ready; run this on the VPS with SQLAlchemy configured.")
            # Still write a JSON snapshot so deploy can inspect product defs
            out = ROOT / "seed_etsy_digital_batch4_products.json"
            out.write_text(
                json.dumps(build_products(file_meta), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"Wrote product snapshot → {out.name}")

    if do_verify or do_assets:
        print("\nVerifying assets …")
        if verify_assets():
            print("All asset paths present.")
        else:
            print("Some assets missing — re-run with --assets.")
            sys.exit(1)
