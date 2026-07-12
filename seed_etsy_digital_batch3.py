"""
seed_etsy_digital_batch3.py — the iPad Coloring Bundle family (GoodNotes /
Procreate / interactive Safari SVG apps / the 3D CBN app). Same idempotent
upsert-by-slug pattern as batch 1 & 2.

These use product_type="ipad_bundle" + collection="digital-downloads" so
they populate the "iPad Coloring Bundles" section on /collection/digital-
downloads (see main.py's DIGITAL_GROUPS) — that section existed in the code
but had zero products until now.

Their detail page is bundle_download.html (gated on collection ==
"digital-downloads"), which builds its image gallery by listing files in
static/digital/<slug>/ (NOT from contents_json / static/previews — those
only matter for the collection-grid thumbnail via /api/render/preview).
contents_json here is shown as a plain "What you get" text list.

    python seed_etsy_digital_batch3.py
"""
import json
from database import SessionLocal
from models.product import DigitalProduct


def seed_digital_etsy_batch3():
    db = SessionLocal()

    products = [
        # NOTE: Fractal Flora and Sacred Geometry iPad bundles are deliberately
        # NOT here — the site already had real, working equivalents under
        # different slugs (fractal-flora-ipad-coloring, sacred-geometry-ipad-
        # coloring, $10.99, same GoodNotes+Procreate content). Adding this
        # batch's versions created duplicate cards on the collection page;
        # see deactivate_batch3_duplicates.py for the cleanup of the two that
        # had already been seeded live.
        {
            "slug": "celtic-knot-ipad-bundle",
            "name": "Celtic Knot iPad Edition — Digital Coloring Bundle",
            "product_type": "ipad_bundle",
            "collection": "digital-downloads",
            "equation_type": "celtic-knot",
            "description": "50 interlace and knotwork designs for iPad. Includes a GoodNotes/Notability PDF and a full Procreate PNG set with a matching swatch palette. Instant download.",
            "price_usd": 5.99,
            "contents_json": json.dumps([
                {"title": "GoodNotes / Notability PDF (50 designs)", "size": "9.2 MB"},
                {"title": "Procreate PNG set (50 files, 2 parts)", "size": "11.3 MB"},
                {"title": "Procreate .swatches palette", "size": None},
                {"title": "How to use on iPad — guide PDF", "size": "40 KB"},
            ]),
            "cover_image": "/static/img/celtic-knot-ipad-bundle_cover.jpg",
            "thumbnail_url": "/static/img/celtic-knot-ipad-bundle_cover.jpg",
            "file_url": "/static/downloads/celtic-knot-ipad-bundle.zip",
            "file_size": "18.5 MB",
            "active": True,
        },
        {
            "slug": "islamic-geometry-ipad-bundle",
            "name": "Islamic Star Geometry iPad Edition — Color by Number Bundle",
            "product_type": "ipad_bundle",
            "collection": "digital-downloads",
            "equation_type": "islamic-star",
            "description": "50 geometric star and tessellation designs for iPad, drawn from classical Islamic construction. Includes a GoodNotes/Notability PDF and a full Procreate PNG set with a matching swatch palette. Instant download.",
            "price_usd": 5.99,
            "contents_json": json.dumps([
                {"title": "GoodNotes / Notability PDF (50 designs)", "size": "10.2 MB"},
                {"title": "Procreate PNG set (50 files, 2 parts)", "size": "13.8 MB"},
                {"title": "Procreate .swatches palette", "size": None},
                {"title": "How to use on iPad — guide PDF", "size": "40 KB"},
            ]),
            "cover_image": "/static/img/islamic-geometry-ipad-bundle_cover.jpg",
            "thumbnail_url": "/static/img/islamic-geometry-ipad-bundle_cover.jpg",
            "file_url": "/static/downloads/islamic-geometry-ipad-bundle.zip",
            "file_size": "22.5 MB",
            # Pulled from the site 2026-07-12 — flip to True + re-run this script
            # when ready to republish.
            "active": False,
        },
        {
            "slug": "voronoi-gardens-ipad-interactive",
            "name": "Voronoi Gardens iPad Edition — Interactive Digital Coloring Bundle",
            "product_type": "ipad_bundle",
            "collection": "digital-downloads",
            "equation_type": "voronoi",
            "description": "50 Voronoi-cell designs as an interactive color-by-number app that runs right in iPad Safari — tap a number, tap a cell, it fills in. No app install, works offline. Instant download.",
            "price_usd": 9.99,
            "contents_json": json.dumps([
                {"title": "Interactive Safari app (50 designs)", "size": "0.5 MB"},
                {"title": "How to use — guide PDF", "size": None},
            ]),
            "cover_image": "/static/img/voronoi-gardens-ipad-interactive_cover.jpg",
            "thumbnail_url": "/static/img/voronoi-gardens-ipad-interactive_cover.jpg",
            "file_url": "/static/downloads/voronoi-gardens-ipad-interactive.zip",
            "file_size": "0.5 MB",
            "active": True,
        },
        {
            "slug": "spiral-tilings-ipad-interactive",
            "name": "Spiral Tilings iPad Edition — Interactive Color By Number",
            "product_type": "ipad_bundle",
            "collection": "digital-downloads",
            "equation_type": "superformula",
            "description": "50 radial spiral and mandala tiling designs as an interactive color-by-number app that runs right in iPad Safari. No app install, works offline. Instant download.",
            "price_usd": 9.99,
            "contents_json": json.dumps([
                {"title": "Interactive Safari app (50 designs)", "size": "2.6 MB"},
                {"title": "How to use — guide PDF", "size": None},
            ]),
            "cover_image": "/static/img/spiral-tilings-ipad-interactive_cover.jpg",
            "thumbnail_url": "/static/img/spiral-tilings-ipad-interactive_cover.jpg",
            "file_url": "/static/downloads/spiral-tilings-ipad-interactive.zip",
            "file_size": "2.6 MB",
            "active": True,
        },
        {
            "slug": "geometric-cbn-ipad-interactive",
            "name": "Geometric Color by Number iPad Edition — Interactive Safari App",
            "product_type": "ipad_bundle",
            "collection": "digital-downloads",
            "equation_type": "superformula",
            "description": "20 low-poly geometric designs as an interactive color-by-number app that runs right in iPad Safari. No app install, works offline. Instant download.",
            "price_usd": 9.99,
            "contents_json": json.dumps([
                {"title": "Interactive Safari app (20 designs)", "size": "0.6 MB"},
                {"title": "How to use — guide PDF", "size": None},
            ]),
            "cover_image": "/static/img/geometric-cbn-ipad-interactive_cover.jpg",
            "thumbnail_url": "/static/img/geometric-cbn-ipad-interactive_cover.jpg",
            "file_url": "/static/downloads/geometric-cbn-ipad-interactive.zip",
            "file_size": "0.6 MB",
            "active": True,
        },
        {
            "slug": "sacred-geometry-svg-ipad-interactive",
            "name": "Sacred Geometry iPad Edition — Interactive Safari SVG App",
            "product_type": "ipad_bundle",
            "collection": "digital-downloads",
            "equation_type": "mobius-grid",
            "description": "50 sacred-geometry designs as an interactive color-by-number app that runs right in iPad Safari. No app install, works offline. Instant download.",
            "price_usd": 9.99,
            "contents_json": json.dumps([
                {"title": "Interactive Safari app (50 designs)", "size": "0.8 MB"},
                {"title": "How to use — guide PDF", "size": None},
            ]),
            "cover_image": "/static/img/sacred-geometry-svg-ipad-interactive_cover.jpg",
            "thumbnail_url": "/static/img/sacred-geometry-svg-ipad-interactive_cover.jpg",
            "file_url": "/static/downloads/sacred-geometry-svg-ipad-interactive.zip",
            "file_size": "0.8 MB",
            "active": True,
        },
        {
            "slug": "cbn-3d-ipad",
            "name": "Interactive 3D Color By Number for iPad — Rotate, Zoom & Colour",
            "product_type": "ipad_bundle",
            "collection": "digital-downloads",
            "equation_type": "voronoi",
            "description": "8 low-poly 3D math solids (Platonic solids, geodesic sphere, torus, faceted gem) you rotate, pinch-zoom and colour by number right in iPad Safari. Numbers scale to each facet; progress saves per figure. No app install, works offline. Instant download.",
            "price_usd": 12.99,
            "contents_json": json.dumps([
                {"title": "Interactive Safari app (8 3D figures)", "size": "0.18 MB"},
                {"title": "How to use — guide PDF (included in app)", "size": None},
            ]),
            "cover_image": "/static/img/cbn-3d-ipad_cover.jpg",
            "thumbnail_url": "/static/img/cbn-3d-ipad_cover.jpg",
            "file_url": "/static/downloads/cbn-3d-ipad.zip",
            "file_size": "0.19 MB",
            # Not published yet — flip to True + re-run this script when ready.
            "active": False,
        },
    ]

    for p_data in products:
        existing = db.query(DigitalProduct).filter_by(slug=p_data["slug"]).first()
        if existing:
            for k, v in p_data.items():
                setattr(existing, k, v)
        else:
            db.add(DigitalProduct(**p_data))

    db.commit()
    db.close()
    print(f"Seed complete: {len(products)} products upserted.")


if __name__ == "__main__":
    seed_digital_etsy_batch3()
