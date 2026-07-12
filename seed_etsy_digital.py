import json
import os
from sqlalchemy.orm import Session
from database import SessionLocal
from models.product import DigitalProduct

def seed_digital_etsy():
    db = SessionLocal()
    
    products = [
        {
            "slug": "fractal-flora-coloring-book-digital",
            "name": "Fractal Flora Coloring Book (Digital Edition)",
            "product_type": "thematic_bundle",
            "collection": "radial-symmetry",
            "equation_type": "superformula",
            "description": "50 unique mathematical mandalas and floral geometries. Instant download digital PDF. Print at home or color digitally on your iPad.",
            "price_usd": 9.99,
            "contents_json": json.dumps([
                {"title": "Fractal Flora Digital Edition", "item_type": "pdf", "description": "50-page high-resolution coloring book", "resolution": "8.5x11in", "duration_secs": None}
            ]),
            "cover_image": "/static/img/fractal_flora_cover.jpg",
            "thumbnail_url": "/static/img/fractal_flora_cover.jpg",
            "file_url": "/static/downloads/fractal_flora_digital.pdf",
            "file_size": "2 MB",
            "active": True
        },
        {
            "slug": "sacred-geometry-coloring-book-digital",
            "name": "Sacred Geometry Coloring Book (Digital Edition)",
            "product_type": "thematic_bundle",
            "collection": "complex-plane-geometry",
            "equation_type": "mobius-grid",
            "description": "50 intricate designs exploring the geometry of the universe. Instant download digital PDF. Print at home or color digitally.",
            "price_usd": 9.99,
            "contents_json": json.dumps([
                {"title": "Sacred Geometry Digital Edition", "item_type": "pdf", "description": "50-page high-resolution coloring book", "resolution": "8.5x11in", "duration_secs": None}
            ]),
            "cover_image": "/static/img/sacred_geometry_cover.jpg",
            "thumbnail_url": "/static/img/sacred_geometry_cover.jpg",
            "file_url": "/static/downloads/sacred_geometry_digital.pdf",
            "file_size": "1.6 MB",
            "active": True
        },
        {
            "slug": "mathematical-tangle-art-digital",
            "name": "Mathematical Tangle Art (Digital Edition)",
            "product_type": "thematic_bundle",
            "collection": "strange-attractors",
            "equation_type": "lorenz",
            "description": "50 unique designs traced from real mathematics. Lissajous figures, polar roses, and spirographs. Instant download PDF.",
            "price_usd": 9.99,
            "contents_json": json.dumps([
                {"title": "Mathematical Tangle Art Digital Edition", "item_type": "pdf", "description": "50-page high-resolution coloring book", "resolution": "8.5x11in", "duration_secs": None}
            ]),
            "cover_image": "/static/img/book_cover.png",
            "thumbnail_url": "/static/img/book_cover.png",
            "file_url": "/static/downloads/mathematical_tangle_art_digital.pdf",
            "file_size": "8.9 MB",
            "active": True
        },
        {
            "slug": "hyperbolic-gardens-digital",
            "name": "Hyperbolic Gardens (Digital Edition)",
            "product_type": "thematic_bundle",
            "collection": "kleinian-gardens",
            "equation_type": "kleinian",
            "description": "Nested circles and limit sets. Color the infinite complexity of hyperbolic space. Instant download digital PDF.",
            "price_usd": 9.99,
            "contents_json": json.dumps([
                {"title": "Hyperbolic Gardens Digital Edition", "item_type": "pdf", "description": "50-page high-resolution coloring book", "resolution": "8.5x11in", "duration_secs": None}
            ]),
            "cover_image": "/static/img/book_hyperbolic_cover.png",
            "thumbnail_url": "/static/img/book_hyperbolic_cover.png",
            "file_url": "/static/downloads/hyperbolic_gardens_digital.pdf",
            "file_size": "9.2 MB",
            "active": True
        },
        {
            "slug": "sacred-harmonics-digital",
            "name": "Sacred Harmonics (Digital Edition)",
            "product_type": "thematic_bundle",
            "collection": "chladni-figures",
            "equation_type": "chladni",
            "description": "50 unique designs based on the vibrational patterns of Chladni plates. Instant download digital PDF.",
            "price_usd": 9.99,
            "contents_json": json.dumps([
                {"title": "Sacred Harmonics Digital Edition", "item_type": "pdf", "description": "50-page high-resolution coloring book", "resolution": "8.5x11in", "duration_secs": None}
            ]),
            "cover_image": "/static/img/sacred_harmonics_cover.png",
            "thumbnail_url": "/static/img/sacred_harmonics_cover.png",
            "file_url": "/static/downloads/sacred_harmonics_digital.pdf",
            "file_size": "10.4 MB",
            "active": True
        },
        {
            "slug": "thomas-attractor-loop",
            "name": "Thomas Attractor Loop (4K Animation)",
            "product_type": "animation_pack",
            "collection": "strange-attractors",
            "equation_type": "thomas",
            "description": "A hypnotic, seamlessly looping 4K visualization of the Thomas cyclically symmetric attractor. Perfect for creative projects or digital displays.",
            "price_usd": 5.00,
            "contents_json": json.dumps([
                {"title": "Thomas Attractor Loop", "item_type": "mp4", "description": "4K Seamless Loop", "resolution": "3840x2160", "duration_secs": 15}
            ]),
            "cover_image": "/static/img/thomas_preview_1_hero.jpg",
            "thumbnail_url": "/static/img/thomas_preview_3_loop.jpg",
            "file_url": "/static/video/thomas_attractor_loop.mp4",
            "file_size": "6.1 MB",
            "active": True
        }
    ]

    for p_data in products:
        existing = db.query(DigitalProduct).filter_by(slug=p_data["slug"]).first()
        if existing:
            for k, v in p_data.items():
                setattr(existing, k, v)
        else:
            new_prod = DigitalProduct(**p_data)
            db.add(new_prod)
            
    db.commit()
    db.close()
    print("Seed complete.")

if __name__ == "__main__":
    seed_digital_etsy()
