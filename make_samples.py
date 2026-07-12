"""
Fractal Flora — clean individual page photos + cover for Etsy listing.
"""

import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

INTERIOR_PDF = "/var/www/mathrelaxing.store/static/downloads/fractal-flora-coloring-book/interior.pdf"
COVER_PDF    = "/var/www/mathrelaxing.store/static/downloads/fractal-flora-coloring-book/cover.pdf"
OUT_DIR      = "/var/www/mathrelaxing.store/static/downloads/digital"

BG   = (245, 243, 238)   # warm off-white
GOLD = (200, 160, 60)

# Pages to export as individual photos (0-indexed, skip intro pages)
PAGE_INDICES = [4, 10, 18, 28, 38]

def render_page(doc, idx, target_w=1800):
    page  = doc[idx]
    scale = target_w / page.rect.width
    mat   = fitz.Matrix(scale, scale)
    pix   = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

def page_on_canvas(page_img, size=2000):
    """Place page centered on a square warm canvas with soft shadow."""
    canvas = Image.new("RGB", (size, size), BG)
    draw   = ImageDraw.Draw(canvas)

    # Subtle dot grid
    for x in range(0, size, 36):
        for y in range(0, size, 36):
            draw.ellipse([(x-1,y-1),(x+1,y+1)], fill=(232,229,222))

    # Fit page with margin
    margin  = 80
    max_w   = size - margin * 2
    max_h   = size - margin * 2
    ratio   = min(max_w / page_img.width, max_h / page_img.height)
    pw      = int(page_img.width  * ratio)
    ph      = int(page_img.height * ratio)
    page_r  = page_img.resize((pw, ph), Image.LANCZOS)

    # Drop shadow
    shadow = Image.new("RGBA", (pw + 40, ph + 40), (0,0,0,0))
    smask  = Image.new("RGBA", (pw, ph), (0,0,0,90))
    shadow.paste(smask, (8, 10))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    xo     = (size - pw) // 2
    yo     = (size - ph) // 2
    canvas.paste(shadow.convert("RGB"), (xo - 12, yo - 8))

    # Page itself (white background with lines)
    canvas.paste(page_r, (xo, yo))

    # Thin gold frame around page
    draw.rectangle([(xo-2, yo-2),(xo+pw+1, yo+ph+1)], outline=GOLD, width=2)

    return canvas

# ── Individual pages ─────────────────────────────────────────────────────────
doc = fitz.open(INTERIOR_PDF)

print(f"Exporting {len(PAGE_INDICES)} pages...")
for i, pidx in enumerate(PAGE_INDICES):
    pg  = render_page(doc, pidx, target_w=1600)
    out = page_on_canvas(pg, size=2000)
    path = f"{OUT_DIR}/fractal_flora_page_{i+1:02d}.jpg"
    out.save(path, "JPEG", quality=93)
    print(f"  Saved: fractal_flora_page_{i+1:02d}.jpg  (page {pidx})")

doc.close()

# ── Cover ────────────────────────────────────────────────────────────────────
print("Exporting cover...")
doc_cover = fitz.open(COVER_PDF)
page      = doc_cover[0]
W, H      = page.rect.width, page.rect.height

# Front cover is the right half (Lulu wrap: back | spine | front)
front_x   = W - 612
clip      = fitz.Rect(front_x, 0, W, H)
mat       = fitz.Matrix(3.0, 3.0)
pix       = page.get_pixmap(matrix=mat, clip=clip, colorspace=fitz.csRGB, alpha=False)
cover_img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

# Place on square canvas
out_cover = page_on_canvas(cover_img, size=2000)
cover_path = f"{OUT_DIR}/fractal_flora_cover.jpg"
out_cover.save(cover_path, "JPEG", quality=93)
print(f"  Saved: fractal_flora_cover.jpg")
doc_cover.close()

print("\nAll done!")
