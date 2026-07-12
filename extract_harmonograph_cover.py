import fitz
import os
import PIL.Image

pdf_path = "/var/www/mathrelaxing.store/static/downloads/Harmonograph_Dreams_Cover.pdf"
out_path = "/var/www/mathrelaxing.store/static/img/harmonograph_dreams_cover.png"

doc = fitz.open(pdf_path)
page = doc[0]
pix = page.get_pixmap(dpi=150)
img = PIL.Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

scale = 150.0 / 72.0
x0 = int(642 * scale)
w_px = int(img.size[0])
h_px = int(img.size[1])

front = img.crop((x0, 0, w_px, h_px))
front.save(out_path)
print(f"Saved {out_path}")
