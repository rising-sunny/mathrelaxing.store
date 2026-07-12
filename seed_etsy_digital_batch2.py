"""
seed_etsy_digital_batch2.py — replicate a second batch of Etsy digital
products onto the web store. Same idempotent upsert-by-slug pattern as
seed_etsy_digital.py: run any time, safe to re-run.

    python seed_etsy_digital_batch2.py
"""
import json
from sqlalchemy.orm import Session
from database import SessionLocal
from models.product import DigitalProduct


def seed_digital_etsy_batch2():
    db = SessionLocal()

    products = [
        # ── coloring book PDFs (same shape as the first Etsy batch) ─────────
        {
            "slug": "voronoi-gardens-coloring-book-digital",
            "name": "Voronoi Gardens Coloring Book (Digital Edition)",
            "product_type": "thematic_bundle",
            "collection": "coloring-books",
            "equation_type": "voronoi",
            "description": "50 mandala and cell-tessellation designs built from Voronoi diagrams — the geometry behind bubbles, cracked earth, and biological tissue. Instant download digital PDF. Print at home or color digitally on your iPad.",
            "price_usd": 6.99,
            "contents_json": json.dumps([
                {"title": "Voronoi Gardens Digital Edition", "item_type": "pdf", "description": "50-page high-resolution coloring book", "resolution": "8.5x11in", "duration_secs": None}
            ]),
            "cover_image": "/static/img/voronoi_cover.jpg",
            "thumbnail_url": "/static/img/voronoi_cover.jpg",
            "file_url": "/static/downloads/voronoi_gardens_digital.pdf",
            "file_size": "1.5 MB",
            "active": True,
        },
        {
            "slug": "islamic-geometry-coloring-book-digital",
            "name": "Islamic Star Geometry Coloring Book (Digital Edition)",
            "product_type": "thematic_bundle",
            "collection": "coloring-books",
            "equation_type": "islamic-star",
            "description": "50 geometric star and tessellation designs drawn from classical Islamic geometric construction. Instant download digital PDF. Print at home or color digitally.",
            "price_usd": 3.99,
            "contents_json": json.dumps([
                {"title": "Islamic Star Geometry Digital Edition", "item_type": "pdf", "description": "50-page high-resolution coloring book", "resolution": "8.5x11in", "duration_secs": None}
            ]),
            "cover_image": "/static/img/islamic_geometry_cover.jpg",
            "thumbnail_url": "/static/img/islamic_geometry_cover.jpg",
            "file_url": "/static/downloads/islamic_geometry_digital.pdf",
            "file_size": "0.25 MB",
            "active": True,
        },
        {
            "slug": "celtic-knot-coloring-book-digital",
            "name": "Celtic Knot Mathematics Coloring Book (Digital Edition)",
            "product_type": "thematic_bundle",
            "collection": "coloring-books",
            "equation_type": "celtic-knot",
            "description": "50 interlace and knotwork designs exploring the mathematics of Celtic weave patterns. Instant download digital PDF. Print at home or color digitally.",
            "price_usd": 3.99,
            "contents_json": json.dumps([
                {"title": "Celtic Knot Mathematics Digital Edition", "item_type": "pdf", "description": "50-page high-resolution coloring book", "resolution": "8.5x11in", "duration_secs": None}
            ]),
            "cover_image": "/static/img/celtic_knot_cover.jpg",
            "thumbnail_url": "/static/img/celtic_knot_cover.jpg",
            "file_url": "/static/downloads/celtic_knot_digital.pdf",
            "file_size": "0.55 MB",
            "active": True,
        },
        {
            "slug": "spiral-tilings-coloring-book-digital",
            "name": "Spiral Tilings Coloring Book (Digital Edition)",
            "product_type": "thematic_bundle",
            "collection": "coloring-books",
            "equation_type": "superformula",
            "description": "50 radial spiral and mandala tiling designs built from parametric spiral mathematics. Instant download digital PDF. Print at home or color digitally.",
            "price_usd": 6.99,
            "contents_json": json.dumps([
                {"title": "Spiral Tilings Digital Edition", "item_type": "pdf", "description": "50-page high-resolution coloring book", "resolution": "8.5x11in", "duration_secs": None}
            ]),
            "cover_image": "/static/img/spiral_tilings_cover.jpg",
            "thumbnail_url": "/static/img/spiral_tilings_cover.jpg",
            "file_url": "/static/downloads/spiral_tilings_digital.pdf",
            "file_size": "9.3 MB",
            "active": True,
        },
        {
            "slug": "neural-network-coloring-book-digital",
            "name": "Neural Network & Tech Art Coloring Book (Digital Edition)",
            "product_type": "thematic_bundle",
            "collection": "coloring-books",
            "equation_type": "neural-network",
            "description": "50 cybernetic and circuit-inspired designs exploring the geometry of artificial neural networks. Instant download digital PDF. Print at home or color digitally.",
            "price_usd": 3.99,
            "contents_json": json.dumps([
                {"title": "Neural Network Digital Edition", "item_type": "pdf", "description": "50-page high-resolution coloring book", "resolution": "8.5x11in", "duration_secs": None}
            ]),
            "cover_image": "/static/img/neural_network_cover.jpg",
            "thumbnail_url": "/static/img/neural_network_cover.jpg",
            "file_url": "/static/downloads/neural_network_digital.pdf",
            "file_size": "0.8 MB",
            "active": True,
        },

        # ── generative art prints / posters ─────────────────────────────────
        {
            "slug": "physics-calculus-equations-print-set",
            "name": "Physics & Calculus Equation Art Prints — Set of 8",
            "product_type": "thematic_bundle",
            "collection": "digital-downloads",
            "equation_type": "latex-typography",
            "description": "8 minimalist navy & gold wall-art prints of iconic physics and calculus equations, set in authentic LaTeX typography. Includes vector PDF (any size) and 24x30in 300dpi JPG for each design. Instant download.",
            "price_usd": 7.99,
            "contents_json": json.dumps([
                {"title": "Physics & Calculus Equations — Set of 8", "item_type": "zip", "description": "8 designs, vector PDF + 300dpi JPG each", "resolution": "24x30in @300dpi", "duration_secs": None}
            ]),
            "cover_image": "/static/img/physics_calculus_equations_cover.jpg",
            "thumbnail_url": "/static/img/physics_calculus_equations_cover.jpg",
            "file_url": "/static/downloads/physics_calculus_equations_digital.zip",
            "file_size": "3.7 MB",
            "active": True,
        },
        {
            "slug": "chladni-figures-poster",
            "name": "Chladni Figures Poster — The Geometry of Sound",
            "product_type": "thematic_bundle",
            "collection": "chladni-figures",
            "equation_type": "chladni",
            "description": "A single large-format poster of 8 Chladni nodal figures — the vibration patterns of sound made visible on a resonant plate. High-resolution print file, instant download.",
            "price_usd": 9.99,
            "contents_json": json.dumps([
                {"title": "Chladni Figures Poster", "item_type": "image", "description": "18x24in high-resolution print", "resolution": "6840x9120", "duration_secs": None}
            ]),
            "cover_image": "/static/img/chladni_figures_poster_cover.jpg",
            "thumbnail_url": "/static/img/chladni_figures_poster_cover.jpg",
            "file_url": "/static/downloads/chladni_figures_poster_print.jpg",
            "file_size": "13.4 MB",
            "active": True,
        },
        {
            "slug": "rossler-attractor-print-set",
            "name": "Rössler Attractor Art Print — 3 Color Variants",
            "product_type": "thematic_bundle",
            "collection": "strange-attractors",
            "equation_type": "rossler",
            "description": "Generative code art from the Rössler chaotic attractor, in 3 curated colorways (classic cyan, violet rose, amber gold). High-resolution print files, instant download.",
            "price_usd": 8.99,
            "contents_json": json.dumps([
                {"title": "Rössler — Classic Cyan", "item_type": "image", "description": "High-resolution print", "resolution": "9000x12000"},
                {"title": "Rössler — Violet Rose",  "item_type": "image", "description": "High-resolution print", "resolution": "9000x12000"},
                {"title": "Rössler — Amber Gold",   "item_type": "image", "description": "High-resolution print", "resolution": "9000x12000"},
            ]),
            "cover_image": "/static/img/rossler_attractor_print_cover.jpg",
            "thumbnail_url": "/static/img/rossler_attractor_print_cover.jpg",
            "file_url": "/static/downloads/rossler_attractor_print_set.zip",
            "file_size": "8.8 MB",
            "active": True,
        },
        {
            "slug": "harmonograph-print-set",
            "name": "Harmonograph Art Print — 3 Color Variants",
            "product_type": "thematic_bundle",
            "collection": "harmonic-geometry",
            "equation_type": "harmonograph",
            "description": "Generative math art from a Victorian pendulum harmonograph, in 3 curated colorways (moonlit, rosegold, verdigris). High-resolution print files, instant download.",
            "price_usd": 8.99,
            "contents_json": json.dumps([
                {"title": "Harmonograph — Moonlit",   "item_type": "image", "description": "High-resolution print", "resolution": "9000x12000"},
                {"title": "Harmonograph — Rosegold",  "item_type": "image", "description": "High-resolution print", "resolution": "9000x12000"},
                {"title": "Harmonograph — Verdigris", "item_type": "image", "description": "High-resolution print", "resolution": "9000x12000"},
            ]),
            "cover_image": "/static/img/harmonograph_print_cover.jpg",
            "thumbnail_url": "/static/img/harmonograph_print_cover.jpg",
            "file_url": "/static/downloads/harmonograph_print_set.zip",
            "file_size": "21.7 MB",
            "active": True,
        },
        {
            "slug": "vector-field-print-set",
            "name": "Vector Field Art Print — 3 Color Variants",
            "product_type": "thematic_bundle",
            "collection": "flow-fields",
            "equation_type": "flow-field",
            "description": "Generative code art tracing a curl-noise vector field, in 3 curated colorways (teal, copper, indigo). High-resolution print files, instant download.",
            "price_usd": 8.99,
            "contents_json": json.dumps([
                {"title": "Vector Field — Teal",   "item_type": "image", "description": "High-resolution print", "resolution": "9000x12000"},
                {"title": "Vector Field — Copper", "item_type": "image", "description": "High-resolution print", "resolution": "9000x12000"},
                {"title": "Vector Field — Indigo", "item_type": "image", "description": "High-resolution print", "resolution": "9000x12000"},
            ]),
            "cover_image": "/static/img/vector_field_print_cover.jpg",
            "thumbnail_url": "/static/img/vector_field_print_cover.jpg",
            "file_url": "/static/downloads/vector_field_print_set.zip",
            "file_size": "44.4 MB",
            "active": True,
        },

        # ── Procreate palette packs ──────────────────────────────────────────
        {
            "slug": "fractal-color-palettes-procreate",
            "name": "Fractal Color Palettes for Procreate",
            "product_type": "thematic_bundle",
            "collection": "digital-downloads",
            "equation_type": "procreate-palette",
            "description": "8 Procreate swatch packs (240 colors) sourced from fractal art — Mandelbrot and Julia set color gradients, ready to import. Instant download.",
            "price_usd": 1.99,
            "contents_json": json.dumps([
                {"title": "Fractal Color Palettes — 8 Swatch Packs", "item_type": "zip", "description": "8 .swatches files for Procreate, 240 colors total", "resolution": None, "duration_secs": None}
            ]),
            "cover_image": "/static/img/fractal_color_palettes_cover.jpg",
            "thumbnail_url": "/static/img/fractal_color_palettes_cover.jpg",
            "file_url": "/static/downloads/fractal_color_palettes.zip",
            "file_size": "5 KB",
            "active": True,
        },
        {
            "slug": "chaos-theory-palettes-procreate",
            "name": "Chaos Theory Procreate Color Palettes",
            "product_type": "thematic_bundle",
            "collection": "digital-downloads",
            "equation_type": "procreate-palette",
            "description": "8 Procreate swatch packs (240 colors) sourced from strange-attractor and vector-field art. Ready to import. Instant download.",
            "price_usd": 1.99,
            "contents_json": json.dumps([
                {"title": "Chaos Theory Palettes — 8 Swatch Packs", "item_type": "zip", "description": "8 .swatches files for Procreate, 240 colors total", "resolution": None, "duration_secs": None}
            ]),
            "cover_image": "/static/img/chaos_theory_palettes_cover.jpg",
            "thumbnail_url": "/static/img/chaos_theory_palettes_cover.jpg",
            "file_url": "/static/downloads/chaos_theory_palettes.zip",
            "file_size": "5 KB",
            "active": True,
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
    seed_digital_etsy_batch2()
