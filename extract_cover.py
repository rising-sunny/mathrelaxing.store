import fitz
import os

pdf_path = "/var/www/mathrelaxing.store/static/downloads/Sacred_Harmonics_Cover_v3.pdf"
out_path = "/var/www/mathrelaxing.store/static/img/sacred_harmonics_cover.png"

# The cover is a single spread [back | spine | front]
# We want just the front half. Wait, the actual listing uses a 3D mockup or just the flat front cover?
# In `seed_book.py` it was `/static/img/book_cover.png`.
# The spread width is ~ 17.542 inches. The front is the right half (minus bleed/spine).
# It's easier to just take the whole image and crop the right half in PIL.
doc = fitz.open(pdf_path)
page = doc[0]
pix = page.get_pixmap(dpi=150)
import PIL.Image
img = PIL.Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

# Dimensions: 1263.0 pt wide. Right half is 1263/2 to 1263
w, h = img.size
# Let's crop the right half, which is the front cover. We can adjust a bit for spine
# front_box = fitz.Rect(panel_w + spine_w, 0, total_w, total_h)
# From `lulu_publish.py`: panel_w = 8.625 * 72 = 621. spine_w = 1263 - 2*621 = 21.
# So front_box x0 = 642.
# scale factor from 72 dpi to 150 dpi is 150/72
scale = 150.0 / 72.0
x0 = int(642 * scale)
w_px = int(w)
h_px = int(h)

front = img.crop((x0, 0, w_px, h_px))
front.save(out_path)
print(f"Saved {out_path}")
