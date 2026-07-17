"""
seed_etsy_digital_batch5.py — Batch 2 of Etsy → web: career & household templates.

Products (all active on Etsy, assets from C:\\repos\\Etsy_mathrelaxing):
  1. editorial-resume-kit      ($8.99)
  2. atelier-resume-kit        ($12.99)
  3. letter-of-recommendation-pack ($7.99)
  4. family-emergency-binder   ($9.99)

Same delivery pattern as batch4:
  - item_type="file" + private_downloads/
  - gallery: static/digital/<slug>/
  - card: static/previews/<slug>.jpg
  - cover: static/img/<slug>_cover.jpg

Run:
    python seed_etsy_digital_batch5.py --assets
    python seed_etsy_digital_batch5.py --seed-only
    python seed_etsy_digital_batch5.py --verify
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


ASSET_JOBS = [
    {
        "slug": "editorial-resume-kit",
        "src_file": ETSY / "resume_kit" / "MathRelaxing_Editorial_Resume_Kit.zip",
        "dest_name": "editorial-resume-kit.zip",
        "preview_dir": ETSY / "resume_kit" / "previews",
        "hero": ETSY / "resume_kit" / "previews" / "resume_preview_1_hero.jpg",
        "gallery": [
            ("resume_preview_1_hero.jpg", "01_hero.jpg"),
            ("resume_preview_2_styles.jpg", "02_styles.jpg"),
            ("resume_preview_3_included.jpg", "03_included.jpg"),
            ("resume_preview_4_detail.jpg", "04_detail.jpg"),
            ("resume_preview_5_features.jpg", "05_features.jpg"),
            ("resume_preview_6_backgrounds.jpg", "06_backgrounds.jpg"),
        ],
        "preview_video": ETSY / "resume_kit" / "Editorial_Resume_Kit_promo.mp4",
    },
    {
        "slug": "atelier-resume-kit",
        "src_file": ETSY / "resume_luxe_kit" / "MathRelaxing_Atelier_Resume_Kit.zip",
        "dest_name": "atelier-resume-kit.zip",
        "preview_dir": ETSY / "resume_luxe_kit" / "previews",
        "hero": ETSY / "resume_luxe_kit" / "previews" / "luxe_preview_01_hero.jpg",
        "gallery": [
            ("luxe_preview_01_hero.jpg", "01_hero.jpg"),
            ("luxe_preview_02_layouts.jpg", "02_layouts.jpg"),
            ("luxe_preview_03_styles.jpg", "03_styles.jpg"),
            ("luxe_preview_04_application.jpg", "04_application.jpg"),
            ("luxe_preview_05_skills.jpg", "05_skills.jpg"),
            ("luxe_preview_06_blank_sample.jpg", "06_blank_sample.jpg"),
            ("luxe_preview_07_more_layouts.jpg", "07_more_layouts.jpg"),
            ("luxe_preview_08_inventory.jpg", "08_inventory.jpg"),
            ("luxe_preview_09_usecases.jpg", "09_usecases.jpg"),
            ("luxe_preview_10_value.jpg", "10_value.jpg"),
        ],
    },
    {
        "slug": "letter-of-recommendation-pack",
        "src_file": ETSY / "lor_pack" / "MathRelaxing_Letter_of_Recommendation_Pack.zip",
        "dest_name": "letter-of-recommendation-pack.zip",
        "preview_dir": ETSY / "lor_pack" / "previews",
        "hero": ETSY / "lor_pack" / "previews" / "lor_preview_1_hero.jpg",
        "gallery": [
            ("lor_preview_1_hero.jpg", "01_hero.jpg"),
            ("lor_preview_2_types.jpg", "02_types.jpg"),
            ("lor_preview_3_why.jpg", "03_why.jpg"),
            ("lor_preview_4_detail.jpg", "04_detail.jpg"),
            ("lor_preview_5_included.jpg", "05_included.jpg"),
            ("lor_preview_6_value.jpg", "06_value.jpg"),
        ],
    },
    {
        "slug": "family-emergency-binder",
        "src_file": ETSY / "emergency_binder" / "MathRelaxing_Family_Emergency_Binder.zip",
        "dest_name": "family-emergency-binder.zip",
        "preview_dir": ETSY / "emergency_binder" / "previews",
        "hero": ETSY / "emergency_binder" / "previews" / "eb_preview_1_hero.jpg",
        "gallery": [
            ("eb_preview_1_hero.jpg", "01_hero.jpg"),
            ("eb_preview_2_sections.jpg", "02_sections.jpg"),
            ("eb_preview_3_why.jpg", "03_why.jpg"),
            ("eb_preview_4_detail.jpg", "04_detail.jpg"),
            ("eb_preview_5_how.jpg", "05_how.jpg"),
            ("eb_preview_6_value.jpg", "06_value.jpg"),
            ("eb_preview_7_spine.jpg", "07_spine.jpg"),
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
        src: Path = job["src_file"]
        if not src.exists():
            raise FileNotFoundError(f"Missing source file for {slug}: {src}")

        dest_name = job["dest_name"]
        priv = _copy(src, PRIVATE / dest_name)
        _copy(src, STATIC_DL / dest_name)

        hero: Path = job["hero"]
        _write_preview_jpg(hero, slug)
        _copy(hero, STATIC_IMG / f"{slug}_cover.jpg")
        _gallery_from_previews(job["preview_dir"], slug, job["gallery"])

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

    # product_type document_template → "Templates & Organizers" section (main.py)
    products = [
        {
            "slug": "editorial-resume-kit",
            "name": "Editorial Resume Kit — ATS + 5 Background Styles",
            "product_type": "document_template",
            "collection": "digital-downloads",
            "equation_type": "none",
            "description": (
                "Instant download — Editorial Resume Kit for engineers, scientists, analysts "
                "and precision professionals. Navy, gold & cream MathRelaxing elegance — not floral Canva clutter.\n\n"
                "ATS Clean: single-column, pure white, portal-safe (Word / Google Docs / Pages).\n"
                "Editorial suite: 5 semi-transparent backgrounds already embedded "
                "(Cream Veil · Scientific Grid · Gold Geometry · Phi Whisper · Navy Edge).\n\n"
                "Full kit: ATS + Editorial resumes (blank + filled STEM sample), cover letter, "
                "references, sample PDF, how-to guide, and PNG background pack. Editable .docx."
            ),
            "price_usd": 8.99,
            "contents_json": json.dumps([
                {
                    "title": "Editorial Resume Kit — ATS + Editorial styles, cover letter & references",
                    "item_type": "file",
                    "filename": fname("editorial-resume-kit", "editorial-resume-kit.zip"),
                    "size": size_for("editorial-resume-kit", "0.9 MB"),
                },
            ]),
            "cover_image": "/static/img/editorial-resume-kit_cover.jpg",
            "thumbnail_url": "/static/previews/editorial-resume-kit.jpg",
            "file_url": "private_downloads/editorial-resume-kit.zip",
            "file_size": size_for("editorial-resume-kit", "0.9 MB"),
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "atelier-resume-kit",
            "name": "Atelier Resume Kit — 5 Layouts + Full Application Set",
            "product_type": "document_template",
            "collection": "digital-downloads",
            "equation_type": "none",
            "description": (
                "Instant download — premium Atelier Resume Kit. A complete application toolkit, "
                "not a single template.\n\n"
                "5 resume layouts: Atelier, Gallery, Manuscript, Architect, ATS.\n"
                "5 Atelier background styles: Cream Veil, Scientific Grid, Gold Geometry, "
                "Phi Whisper, Navy Edge.\n\n"
                "Full set: cover letter, references, thank-you note, LinkedIn pack (headline + About), "
                "portfolio one-pager, how-to PDF, and filled samples (Celine Mora persona). "
                "Blank + SAMPLE for every major document. Editable Word .docx."
            ),
            "price_usd": 12.99,
            "contents_json": json.dumps([
                {
                    "title": "Atelier Resume Kit — 5 layouts, application docs & samples",
                    "item_type": "file",
                    "filename": fname("atelier-resume-kit", "atelier-resume-kit.zip"),
                    "size": size_for("atelier-resume-kit", "1.4 MB"),
                },
            ]),
            "cover_image": "/static/img/atelier-resume-kit_cover.jpg",
            "thumbnail_url": "/static/previews/atelier-resume-kit.jpg",
            "file_url": "private_downloads/atelier-resume-kit.zip",
            "file_size": size_for("atelier-resume-kit", "1.4 MB"),
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "letter-of-recommendation-pack",
            "name": "Letter of Recommendation Template Pack — 6 Situations",
            "product_type": "document_template",
            "collection": "digital-downloads",
            "equation_type": "none",
            "description": (
                "Instant download — write a strong recommendation without starting from a blank page. "
                "Six editorial Word templates with filled samples and a practical writing guide.\n\n"
                "Situations: Job/Employee · Academic/Grad school · Teacher→Student · "
                "Character/Personal · Scholarship · Coworker/Peer.\n\n"
                "Each type includes a blank template + filled SAMPLE with specific praise and metrics, "
                "navy/gold editorial letterhead, and a how-to PDF (structure, tone, what to avoid). "
                "Microsoft Word (.docx), US Letter."
            ),
            "price_usd": 7.99,
            "contents_json": json.dumps([
                {
                    "title": "Letter of Recommendation Pack — 6 types + samples + guide",
                    "item_type": "file",
                    "filename": fname(
                        "letter-of-recommendation-pack",
                        "letter-of-recommendation-pack.zip",
                    ),
                    "size": size_for("letter-of-recommendation-pack", "0.4 MB"),
                },
            ]),
            "cover_image": "/static/img/letter-of-recommendation-pack_cover.jpg",
            "thumbnail_url": "/static/previews/letter-of-recommendation-pack.jpg",
            "file_url": "private_downloads/letter-of-recommendation-pack.zip",
            "file_size": size_for("letter-of-recommendation-pack", "0.4 MB"),
            "license_type": "personal",
            "active": True,
        },
        {
            "slug": "family-emergency-binder",
            "name": "Family Emergency Binder — Printable ICE Household Organizer",
            "product_type": "document_template",
            "collection": "digital-downloads",
            "equation_type": "none",
            "description": (
                "Instant download — Family Emergency Binder (printable PDF organizer). "
                "When something goes wrong, you should not be hunting for phone numbers, "
                "insurance cards, or school pickup rules.\n\n"
                "13+ US Letter sections: quick start, emergency contacts, household members, "
                "medical, insurance, home & utilities, finances snapshot, pets, digital access "
                "notes (privacy-aware), evacuation/go-bag, meeting place & school plans, "
                "quarterly update checklist, and spine labels.\n\n"
                "Navy · gold · cream MathRelaxing layout. Print, put in a 1–2\" binder with tabs, "
                "tell trusted people where it lives. Organizational tool only — not medical, "
                "legal, or financial advice."
            ),
            "price_usd": 9.99,
            "contents_json": json.dumps([
                {
                    "title": "Family Emergency Binder — printable PDF pack + spine labels",
                    "item_type": "file",
                    "filename": fname("family-emergency-binder", "family-emergency-binder.zip"),
                    "size": size_for("family-emergency-binder", "50 KB"),
                },
            ]),
            "cover_image": "/static/img/family-emergency-binder_cover.jpg",
            "thumbnail_url": "/static/previews/family-emergency-binder.jpg",
            "file_url": "private_downloads/family-emergency-binder.zip",
            "file_size": size_for("family-emergency-binder", "50 KB"),
            "license_type": "personal",
            "active": True,
        },
    ]
    return products


def seed_digital_etsy_batch5(file_meta: dict[str, dict] | None = None) -> None:
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
        print("Copying Batch 2 assets from Etsy_mathrelaxing …")
        file_meta = copy_assets()
        print()

    if do_seed and not do_verify:
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
            seed_digital_etsy_batch5(file_meta)
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
