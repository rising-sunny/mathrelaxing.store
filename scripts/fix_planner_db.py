import sys
sys.path.append('/var/www/mathrelaxing.store')
from database import SessionLocal
from models.product import DigitalProduct
import json

db = SessionLocal()

# Quantified Self Planner
qs = db.query(DigitalProduct).filter_by(slug='quantified-self-planner-digital').first()
if qs:
    qs.contents_json = json.dumps([
        {"title": "Hero Preview", "item_type": "image", "description": "The Quantified Self Journal cover."},
        {"title": "Analytics Dashboard", "item_type": "image", "description": "Track your habits with a 365-day GitHub-style heatmap."},
        {"title": "Sprint Planning", "item_type": "image", "description": "Agile sprint Kanban boards for weekly planning."},
        {"title": "The Quantified Self Journal — 127-page hyperlinked PDF", "item_type": "file", "filename": "quantified-self-planner-digital.pdf", "size": "597 KB"}
    ])

# STEM Focus Planner
stem = db.query(DigitalProduct).filter_by(slug='stem-focus-planner-digital').first()
if stem:
    stem.contents_json = json.dumps([
        {"title": "STEM Focus Planner Preview", "item_type": "animation", "description": "Video preview of the STEM Focus Planner.", "animation_key": "stem_planner_promo"},
        {"title": "Hero Preview", "item_type": "image", "description": "STEM Focus Planner cover."},
        {"title": "Sections", "item_type": "image", "description": "Hyperlinked index for easy navigation."},
        {"title": "STEM Templates", "item_type": "image", "description": "Specialized layouts for engineering and math."},
        {"title": "Navigation", "item_type": "image", "description": "Quick access tabs across the planner."},
        {"title": "Math Stickers", "item_type": "image", "description": "14 included digital math stickers."},
        {"title": "Formula Reference", "item_type": "image", "description": "Cheat sheet for essential formulas."},
        {"title": "Academic Layout", "item_type": "image", "description": "Cornell notes and grid paper."},
        {"title": "Compatibility", "item_type": "image", "description": "Works with GoodNotes, Notability and standard PDF readers."},
        {"title": "STEM Focus Planner — 35-page hyperlinked PDF + math stickers", "item_type": "file", "filename": "stem-focus-planner-digital.zip", "size": "425 KB"}
    ])

# STEM Notebook
nb = db.query(DigitalProduct).filter_by(slug='stem-notebook-digital').first()
if nb:
    nb.contents_json = json.dumps([
        {"title": "Hero Preview", "item_type": "image", "description": "STEM Notebook digital cover."},
        {"title": "Grids and Templates", "item_type": "image", "description": "Engineering graph, dot grid, and isometric layouts."},
        {"title": "Subject Tabs", "item_type": "image", "description": "12 customizable linked subject dividers."},
        {"title": "What's Included", "item_type": "image", "description": "Everything you need for technical note-taking."},
        {"title": "STEM Digital Notebook — 142-page hyperlinked PDF", "item_type": "file", "filename": "stem-notebook-digital.pdf", "size": "978 KB"}
    ])

db.commit()
db.close()
print("Updated database for the planners.")
