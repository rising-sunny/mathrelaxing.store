
import sqlite3
import os
import json

# We'll run this on the VPS later, but let's write the code now
def add_planners_to_db():
    DB_PATH = "mathrelaxing.db"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. STEM Focus Planner
    stem_slug = "stem-focus-planner-digital"
    stem_name = "STEM Focus Planner — Undated Digital (GoodNotes/Notability)"
    stem_product_type = "digital_planner"
    stem_collection = "digital-downloads"
    stem_equation_type = "none"
    stem_description = "Instant download — undated STEM focus planner for GoodNotes, Notability & any PDF app. A minimalist, hyperlinked planner built for students, researchers and analytical minds — cream & gold MathRelaxing aesthetic, not another generic wellness journal. Includes 35 hyperlinked pages, 14 math stickers, formula reference page, graph paper, and dot grid notes."
    stem_price = 8.99
    stem_contents_json = json.dumps([
        {
            "title": "STEM Focus Planner — 35-page hyperlinked PDF + math stickers",
            "item_type": "file",
            "filename": "stem-focus-planner-digital.zip",
            "size": "425 KB"
        }
    ])
    stem_cover_image = "/static/previews/stem-focus-planner-digital.jpg"
    stem_thumbnail_url = "/static/previews/stem-focus-planner-digital.jpg"
    stem_file_url = "private_downloads/stem-focus-planner-digital.zip"
    stem_file_size = "425 KB"
    stem_license_type = "personal"
    stem_active = True

    # Check if already exists
    cursor.execute("SELECT id FROM digital_products WHERE slug = ?", (stem_slug,))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO digital_products (
                slug, name, product_type, collection, equation_type,
                description, price_usd, contents_json, cover_image,
                thumbnail_url, file_url, file_size, license_type, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            stem_slug, stem_name, stem_product_type, stem_collection,
            stem_equation_type, stem_description, stem_price,
            stem_contents_json, stem_cover_image, stem_thumbnail_url,
            stem_file_url, stem_file_size, stem_license_type, stem_active
        ))
        print(f"Added: {stem_name}")
    else:
        print(f"Skipped, already exists: {stem_name}")

    # 2. Quantified Self Planner
    qs_slug = "quantified-self-planner-digital"
    qs_name = "The Quantified Self Journal — Digital Data Planner (GoodNotes/Notability)"
    qs_product_type = "digital_planner"
    qs_collection = "digital-downloads"
    qs_equation_type = "none"
    qs_description = "Instant download — hyperlinked digital quantified self journal for data lovers, software engineers and analytical minds. Move beyond simple to-do lists and visualize your progress with a 365-day GitHub-style heatmap, monthly scatter plots, bar charts, and weekly agile sprint Kanban boards. Designed with our elegant Dark Mode (Navy & Gold) aesthetic to match your favorite IDE and reduce eye strain."
    qs_price = 9.99
    qs_contents_json = json.dumps([
        {
            "title": "The Quantified Self Journal — 127-page hyperlinked PDF",
            "item_type": "file",
            "filename": "quantified-self-planner-digital.pdf",
            "size": "597 KB"
        }
    ])
    qs_cover_image = "/static/previews/quantified-self-planner-digital.jpg"
    qs_thumbnail_url = "/static/previews/quantified-self-planner-digital.jpg"
    qs_file_url = "private_downloads/quantified-self-planner-digital.pdf"
    qs_file_size = "597 KB"
    qs_license_type = "personal"
    qs_active = True

    # Check if already exists
    cursor.execute("SELECT id FROM digital_products WHERE slug = ?", (qs_slug,))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO digital_products (
                slug, name, product_type, collection, equation_type,
                description, price_usd, contents_json, cover_image,
                thumbnail_url, file_url, file_size, license_type, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            qs_slug, qs_name, qs_product_type, qs_collection,
            qs_equation_type, qs_description, qs_price,
            qs_contents_json, qs_cover_image, qs_thumbnail_url,
            qs_file_url, qs_file_size, qs_license_type, qs_active
        ))
        print(f"Added: {qs_name}")
    else:
        print(f"Skipped, already exists: {qs_name}")

    conn.commit()
    conn.close()
    print("Done!")

if __name__ == "__main__":
    add_planners_to_db()
