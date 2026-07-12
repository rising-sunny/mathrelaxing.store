"""
iPad Edition bundle for Sacred Geometry color-by-number.
Generates:
  1) GoodNotes/Notability PDF with a hyperlinked thumbnail index
  2) Transparent high-res PNGs (Procreate) -- sample for prototype
  3) Procreate .swatches palette
  4) Branded "How to use on iPad" guide PDF
"""
import fitz, os, io, json, zipfile, math, colorsys, tempfile
import numpy as np
from PIL import Image

SRC      = "/var/www/mathrelaxing.store/static/downloads/sacred-math-coloring-book/interior.pdf"
OUT      = "/var/www/mathrelaxing.store/static/downloads/digital/ipad_sg"
FONT_DIR = "/var/www/mathrelaxing.store/static/fonts"
CINZEL   = FONT_DIR + "/Cinzel.ttf"
RALEWAY  = FONT_DIR + "/Raleway.ttf"
RALEWAY_IT = FONT_DIR + "/Raleway-Italic.ttf"
LOGO     = "/var/www/mathrelaxing.store/static/img/logo.png"

DESIGN_FROM, DESIGN_TO = 2, 51          # contiguous design pages (0-based, inclusive) = 50 designs
PNG_DIR = OUT + "/Procreate_PNG"

os.makedirs(OUT, exist_ok=True)
os.makedirs(PNG_DIR, exist_ok=True)

GOLD=(0.85,0.68,0.32); WHITE=(1,1,1); DIM=(0.5,0.57,0.7); BG=(0.07,0.09,0.18)

# ── 1) Hyperlinked GoodNotes PDF ─────────────────────────────────────────────
def build_hyperlinked_pdf():
    src = fitz.open(SRC)
    n_designs = DESIGN_TO - DESIGN_FROM + 1
    pw, ph = src[DESIGN_FROM].rect.width, src[DESIGN_FROM].rect.height

    COLS, ROWS = 4, 5
    per_page = COLS * ROWS
    n_index = math.ceil(n_designs / per_page)

    final = fitz.open()
    # index pages (blank, dark)
    for _ in range(n_index):
        pg = final.new_page(width=pw, height=ph)
        pg.draw_rect(pg.rect, color=None, fill=BG)
    # append the design pages
    final.insert_pdf(src, from_page=DESIGN_FROM, to_page=DESIGN_TO)

    # render thumbnails + place + link
    margin_x, margin_top = 40, 90
    gap = 14
    cell_w = (pw - 2*margin_x - (COLS-1)*gap) / COLS
    cell_h = (ph - margin_top - 40 - (ROWS-1)*gap) / ROWS

    tmpd = tempfile.mkdtemp()
    for i in range(n_designs):
        src_page_idx = DESIGN_FROM + i
        target_final_page = n_index + i
        idx_page_no = i // per_page
        slot = i % per_page
        r, c = slot // COLS, slot % COLS
        idx_page = final[idx_page_no]

        # title on index page (once)
        if slot == 0:
            idx_page.insert_textbox(fitz.Rect(40, 36, pw-40, 70),
                "Tap a design to jump to it", fontfile=CINZEL, fontsize=17,
                color=WHITE, align=1)

        x0 = margin_x + c*(cell_w+gap)
        y0 = margin_top + r*(cell_h+gap)
        rect = fitz.Rect(x0, y0, x0+cell_w, y0+cell_h-14)

        # thumbnail image (render design page small)
        pix = src[src_page_idx].get_pixmap(matrix=fitz.Matrix(0.5,0.5), colorspace=fitz.csRGB)
        tp = os.path.join(tmpd, f"t{i}.png"); pix.save(tp)
        # white card behind thumb
        idx_page.draw_rect(rect, color=(0.2,0.26,0.42), fill=(1,1,1), width=0.5)
        idx_page.insert_image(rect, filename=tp, keep_proportion=True)
        # number label
        idx_page.insert_textbox(fitz.Rect(x0, y0+cell_h-15, x0+cell_w, y0+cell_h+1),
            str(i+1), fontfile=RALEWAY, fontsize=8, color=GOLD, align=1)
        # hyperlink (goto)
        idx_page.insert_link({"kind": fitz.LINK_GOTO, "from": rect,
                              "page": target_final_page, "to": fitz.Point(0,0)})

    out = OUT + "/SacredGeometry_iPad_GoodNotes.pdf"
    final.save(out, deflate=True, garbage=4)
    src.close(); final.close()
    print(f"  PDF: {out} ({os.path.getsize(out)/1024/1024:.1f} MB, {n_index} index + {n_designs} designs)")

# ── 2) Transparent PNGs for Procreate (all 50) ───────────────────────────────
def build_transparent_pngs(dpi=300):
    src = fitz.open(SRC)
    n = 0
    for idx in range(DESIGN_FROM, DESIGN_TO + 1):
        n += 1
        pix = src[idx].get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), colorspace=fitz.csRGB, alpha=False)
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).astype(np.uint8)
        gray = arr.mean(axis=2)
        # >210 (white facets) -> fully transparent; <120 (lines) -> opaque; numbers in between stay faint
        alpha = (np.clip((210 - gray) / 90.0, 0, 1) * 255).astype(np.uint8)
        rgba = np.dstack([arr, alpha])
        Image.fromarray(rgba, "RGBA").save(f"{PNG_DIR}/SacredGeometry_{n:02d}.png", optimize=True)
    src.close()
    print(f"  PNGs: {n} transparent designs @ {dpi}dpi -> {PNG_DIR}")

# ── 5) Package for Etsy (respect 20 MB/file limit) ───────────────────────────
def build_packages():
    import glob
    pngs = sorted(glob.glob(PNG_DIR + "/*.png"))
    LIMIT = 19 * 1024 * 1024     # stay safely under Etsy's 20 MB
    # greedily pack PNGs into as few zips as possible under the limit
    zips = [[]]; sizes = [0]
    for p in pngs:
        sz = os.path.getsize(p)
        if sizes[-1] + sz > LIMIT and zips[-1]:
            zips.append([]); sizes.append(0)
        zips[-1].append(p); sizes[-1] += sz
    zip_paths = []
    for i, group in enumerate(zips, 1):
        suffix = "" if len(zips) == 1 else f"_part{i}"
        zp = f"{OUT}/SacredGeometry_Procreate_PNG{suffix}.zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for p in group:
                z.write(p, "Procreate_PNG/" + os.path.basename(p))
        zip_paths.append(zp)
        print(f"  ZIP: {os.path.basename(zp)} ({len(group)} PNGs, {os.path.getsize(zp)/1024/1024:.1f} MB)")
    return zip_paths

# ── 3) Procreate .swatches palette ───────────────────────────────────────────
def build_swatches():
    colors = [
        (216,234,247),(150,196,224),(74,123,168),(26,61,107),(13,35,71),
        (255,226,150),(255,168,88),(230,96,68),(150,48,82),(70,28,66),
        (214,242,220),(140,210,170),(64,158,128),(28,98,88),(14,54,52),
        (232,216,246),(190,158,226),(138,98,190),(88,52,138),(48,28,84),
        (200,169,110),(126,207,179),(38,184,182),(216,72,120),(255,140,100),
        (90,110,140),(245,243,230),(40,46,66),(120,200,210),(170,140,90),
    ]
    sw = []
    for (r,g,b) in colors:
        h,s,v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        sw.append({"hue":round(h,4),"saturation":round(s,4),"brightness":round(v,4),
                   "alpha":1,"colorSpace":0})
    data = [{"name":"MathRelaxing — Sacred Geometry","swatches":sw}]
    out = OUT + "/SacredGeometry.swatches"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Swatches.json", json.dumps(data))
    print(f"  Swatches: {out} ({len(colors)} colors)")

# ── 4) Branded iPad guide PDF ────────────────────────────────────────────────
def build_guide():
    doc = fitz.open(); pw,ph = 612,792
    pg = doc.new_page(width=pw, height=ph)
    pg.draw_rect(pg.rect, color=None, fill=BG)
    # logo
    lw=120; lh=int(120*575/800)
    pg.insert_image(fitz.Rect(pw/2-lw/2, 56, pw/2+lw/2, 56+lh), filename=LOGO, keep_proportion=True)
    def line(y, t, f, s, col, pad=55):
        pg.insert_textbox(fitz.Rect(pad,y,pw-pad,y+s*2.0), t, fontfile=f, fontsize=s, color=col, align=1, lineheight=1.0)
    def para(y, t, s=10.5, col=(0.8,0.85,0.93), pad=70):
        return pg.insert_textbox(fitz.Rect(pad,y,pw-pad,y+200), t, fontfile=RALEWAY, fontsize=s, color=col, align=0, lineheight=1.35)
    TEAL=(0.49,0.81,0.7)
    def head(y, t): pg.insert_textbox(fitz.Rect(72,y,pw-72,y+22), t, fontfile=CINZEL, fontsize=12.5, color=TEAL)
    line(148, "Coloring on Your iPad", CINZEL, 21, WHITE)
    line(181, "Sacred Geometry  \xb7  iPad Edition", RALEWAY_IT, 11, GOLD)
    line(204, "No printer, no mess \xb7 just you, your Apple Pencil, and fifty worlds to color.",
         RALEWAY_IT, 9.5, (0.62,0.68,0.8))
    # divider
    sh=pg.new_shape(); sh.draw_line((72,234),(pw-72,234)); sh.finish(color=GOLD,width=0.8); sh.commit()

    head(258, "In GoodNotes or Notability")
    para(284,
        "Open the PDF and begin on the index page. Tap any design to glide straight to it, then color "
        "right on the artwork with whichever brush you love. Lift the exact shade you need from the "
        "numbered key beneath each piece with the eyedropper.")

    head(372, "In Procreate")
    para(398,
        "Drop a transparent PNG onto a fresh canvas. The linework rests on its own layer, so paint on a "
        "layer beneath it and every stroke stays effortlessly within the lines. Import the included "
        "palette and every number is one tap away.")

    head(486, "A gentle note")
    para(512,
        "Each number echoes a shade in the key \xb7 follow them for the intended palette, or make the piece "
        "entirely your own. Zoom in for the finest facets, and flat-fill or gradient-shade to let each "
        "form find its depth. There is no rush here \xb7 unwinding is the whole point.")

    line(712, "mathrelaxing.store", CINZEL, 12, GOLD)
    line(737, "\xa9 MathRelaxing \xb7 For personal use only", RALEWAY, 7.5, DIM)
    out = OUT + "/How_to_use_on_iPad.pdf"
    doc.save(out); doc.close()
    print(f"  Guide: {out}")

print("Building iPad bundle for Sacred Geometry...")
build_hyperlinked_pdf()
build_transparent_pngs()
build_swatches()
build_guide()
print("Packaging for Etsy...")
build_packages()
print("Done.")
