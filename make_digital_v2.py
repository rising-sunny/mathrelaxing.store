import fitz
import math
import os

OUT_DIR = "/var/www/mathrelaxing.store/static/downloads/digital"
os.makedirs(OUT_DIR, exist_ok=True)

PRINT_LINE = "Perfect-bound · 8.5 x 11 in · matte cover · printed on demand."
DIGITAL_LINE = "Digital Edition  ·  Printable PDF"

def extract_front_cover(src_path):
    doc = fitz.open(src_path)
    page = doc[0]
    W, H = page.rect.width, page.rect.height
    front_x = W - 612
    clip = fitz.Rect(front_x, 0, W, H)
    mat = fitz.Matrix(2, 2)
    pix = page.get_pixmap(matrix=mat, clip=clip, colorspace=fitz.csRGB)
    out = fitz.open()
    new_page = out.new_page(width=612, height=H)
    new_page.insert_image(new_page.rect, pixmap=pix)
    doc.close()
    return out

def fix_isbn(src_path):
    doc = fitz.open(src_path)
    page = doc[1]
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        block_text = " ".join(
            sp["text"] for ln in b["lines"] for sp in ln["spans"]
        )
        if "ISBN" in block_text:
            page.add_redact_annot(fitz.Rect(b["bbox"]), fill=(1, 1, 1))
    page.apply_redactions()
    return doc

def draw_rose(page, cx, cy, r, k, color, steps=2000, width=0.9):
    points = []
    for i in range(steps + 1):
        t = 2 * math.pi * i / steps
        rho = r * math.cos(k * t)
        x = cx + rho * math.cos(t)
        y = cy + rho * math.sin(t)
        points.append((x, y))
    shape = page.new_shape()
    shape.draw_polyline(points)
    shape.finish(color=color, width=width, fill=None, closePath=False)
    shape.commit()

def draw_lissajous(page, cx, cy, rx, ry, a, b, delta, color, steps=1200, width=0.7):
    points = []
    for i in range(steps + 1):
        t = 2 * math.pi * i / steps
        x = cx + rx * math.sin(a * t + delta)
        y = cy + ry * math.sin(b * t)
        points.append((x, y))
    shape = page.new_shape()
    shape.draw_polyline(points)
    shape.finish(color=color, width=width, fill=None, closePath=False)
    shape.commit()

def draw_spiral(page, cx, cy, r_max, turns, color, steps=500, width=0.5):
    points = []
    for i in range(steps + 1):
        t = turns * 2 * math.pi * i / steps
        rho = r_max * i / steps
        x = cx + rho * math.cos(t)
        y = cy + rho * math.sin(t)
        points.append((x, y))
    shape = page.new_shape()
    shape.draw_polyline(points)
    shape.finish(color=color, width=width, fill=None, closePath=False)
    shape.commit()

def draw_torus(page, cx, cy, scale, gold, dim,
               R=2.0, r=0.82, tilt=1.15, rot=0.35,
               n_u=18, n_v=11, samples=54, width=0.7):
    """3D torus wireframe, lines shaded by depth (z) for a volumetric look."""
    ct, st = math.cos(tilt), math.sin(tilt)
    cr, sr = math.cos(rot),  math.sin(rot)

    def project(u, v):
        x = (R + r*math.cos(v)) * math.cos(u)
        y = (R + r*math.cos(v)) * math.sin(u)
        z = r * math.sin(v)
        x, y = x*cr - y*sr, x*sr + y*cr      # rotate around z
        y, z = y*ct - z*st, y*st + z*ct      # tilt around x
        return (cx + x*scale, cy + y*scale, z)

    # collect segments, draw back-to-front so front lines sit on top
    segs = []
    for i in range(n_u):                      # longitudinal loops (const u)
        u = 2*math.pi*i/n_u
        prev = project(u, 0)
        for j in range(1, samples+1):
            cur = project(u, 2*math.pi*j/samples)
            segs.append((prev, cur)); prev = cur
    for j in range(n_v):                       # latitudinal loops (const v)
        v = 2*math.pi*j/n_v
        prev = project(0, v)
        for i in range(1, samples+1):
            cur = project(2*math.pi*i/samples, v)
            segs.append((prev, cur)); prev = cur

    # normalize depth using the ACTUAL projected z range (post-tilt)
    midz = [(s[0][2]+s[1][2])/2 for s in segs]
    zmin, zspan = min(midz), (max(midz) - min(midz)) or 1.0

    order = sorted(range(len(segs)), key=lambda i: midz[i])  # back first
    for i in order:
        p0, p1 = segs[i]
        d   = (midz[i] - zmin) / zspan             # 0 back .. 1 front
        col = tuple(min(1.0, max(0.0, dim[k]*(1-d) + gold[k]*d)) for k in range(3))
        sh = page.new_shape()
        sh.draw_line((p0[0], p0[1]), (p1[0], p1[1]))
        sh.finish(color=col, width=width*(0.5 + 0.7*d))
        sh.commit()

FONT_DIR   = "/var/www/mathrelaxing.store/static/fonts"
CINZEL     = FONT_DIR + "/Cinzel.ttf"
RALEWAY    = FONT_DIR + "/Raleway.ttf"
RALEWAY_IT = FONT_DIR + "/Raleway-Italic.ttf"
LOGO_PATH  = "/var/www/mathrelaxing.store/static/img/logo.png"

def tbox(page, rect, text, fontfile, fontsize, color, align=1, lineheight=1.4):
    """Insert centered text in a rect. align=1 means center."""
    page.insert_textbox(
        rect, text,
        fontfile=fontfile, fontsize=fontsize,
        color=color, align=align,
        lineheight=lineheight,
    )

def gold_ornament(page, cx, y, half_width, color_gold, color_dim):
    """Draw  ── ✦ ──  style ornament."""
    shape = page.new_shape()
    shape.draw_line((cx - half_width, y), (cx - 14, y))
    shape.finish(color=color_gold, width=0.7)
    shape.draw_line((cx + 14, y), (cx + half_width, y))
    shape.finish(color=color_gold, width=0.7)
    shape.commit()
    # Diamond dot in center
    hw = 3.5
    shape = page.new_shape()
    shape.draw_quad(fitz.Quad(
        (cx, y - hw), (cx + hw, y), (cx, y + hw), (cx - hw, y)
    ))
    shape.finish(color=color_gold, fill=color_gold, width=0)
    shape.commit()

def make_cta_page(book_title, pw=612, ph=792, motif="harmonic",
                  subtitle="We hope you enjoyed every curve and equation."):
    doc = fitz.open()
    page = doc.new_page(width=pw, height=ph)

    BG     = (0.07, 0.09, 0.18)
    GOLD   = (0.85, 0.68, 0.32)
    GOLD2  = (0.55, 0.42, 0.14)
    LIGHT  = (0.78, 0.85, 0.95)
    WHITE  = (1.0,  1.0,  1.0)
    DIM    = (0.50, 0.57, 0.70)
    ACCENT = (0.38, 0.72, 0.82)
    DIMMER = (0.30, 0.36, 0.52)

    page.draw_rect(page.rect, color=None, fill=BG)

    cx, cy = pw / 2, ph * 0.375

    # Concentric circles (faint depth field)
    shape = page.new_shape()
    for radius in [188, 162, 136, 110]:
        shape.draw_circle((cx, cy), radius)
        shape.finish(color=(0.15, 0.22, 0.40), width=0.5, fill=None)
    shape.commit()

    # Central motif — chosen per book
    if motif == "geometric":
        # 3D torus wireframe — fits geometry / topology books
        draw_torus(page, cx, cy, 56, GOLD, (0.26, 0.34, 0.54))
    else:
        # harmonic curves — rose + lissajous + spiral
        draw_rose(page, cx, cy, 148, 5, GOLD, steps=2000, width=1.1)
        draw_lissajous(page, cx, cy, 84, 84, 3, 4, math.pi / 4, ACCENT, steps=1200, width=0.8)
        draw_spiral(page, cx, cy, 30, 5, (0.50, 0.58, 0.72), steps=500, width=0.5)

    # Logo — centered above text block
    logo_w, logo_h = 108, 78
    logo_top = ph * 0.672
    logo_rect = fitz.Rect(cx - logo_w/2, logo_top, cx + logo_w/2, logo_top + logo_h)
    page.insert_image(logo_rect, filename=LOGO_PATH, keep_proportion=True)

    # ── Text block: vertical cursor in points; boxes are generously tall
    #    (~2x font size) so Cinzel always fits and renders. ──────────────
    def line(y, text, font, size, color, side_pad=40):
        # box height = size*2 guarantees insert_textbox never silently fails
        page.insert_textbox(
            fitz.Rect(side_pad, y, pw - side_pad, y + size*2.0),
            text, fontfile=font, fontsize=size, color=color,
            align=1, lineheight=1.0,
        )

    # Full-width gold double rule
    rule_y = ph * 0.795
    shape = page.new_shape()
    shape.draw_line((50, rule_y),     (pw - 50, rule_y))
    shape.finish(color=GOLD, width=0.9)
    shape.draw_line((60, rule_y + 4), (pw - 60, rule_y + 4))
    shape.finish(color=DIMMER, width=0.35)
    shape.commit()

    y = rule_y + 18
    line(y, "Thank you for coloring!", CINZEL, 15, WHITE);            y += 27
    line(y, subtitle, RALEWAY_IT, 8.5, DIM, side_pad=60);             y += 22

    gold_ornament(page, cx, y, 70, GOLD, GOLD2);                      y += 16

    line(y, "mathrelaxing.store", CINZEL, 13.5, GOLD);               y += 23

    shape = page.new_shape()                                          # thin rule
    shape.draw_line((cx - 90, y), (cx + 90, y))
    shape.finish(color=GOLD2, width=0.35)
    shape.commit();                                                  y += 11

    line(y, "Shop on Etsy:  etsy.com/shop/themathrelaxing", RALEWAY, 8.0, LIGHT, side_pad=50); y += 17
    line(y, "YouTube  \xb7  Pinterest  \xb7  TikTok  \xb7  Instagram    @MathRelaxing", RALEWAY, 7.5, DIM); y += 18
    line(y, "\xa9 MathRelaxing  \xb7  For personal use only. Not for redistribution or commercial use.",
         RALEWAY, 6.0, DIMMER)

    return doc

def build_book(name, cover_doc, interior_path, out_path, fix_isbn_flag=False,
               motif="harmonic", subtitle="We hope you enjoyed every curve and equation."):
    if fix_isbn_flag:
        interior_doc = fix_isbn(interior_path)
        tmp = "/tmp/" + name.replace(" ", "_") + "_interior.pdf"
        interior_doc.save(tmp)
        interior_doc.close()
        interior_path = tmp

    interior = fitz.open(interior_path)
    pw = interior[0].rect.width
    ph = interior[0].rect.height
    cta = make_cta_page(name, pw, ph, motif, subtitle)

    final = fitz.open()
    if cover_doc:
        final.insert_pdf(cover_doc)
        cover_doc.close()
    final.insert_pdf(interior)
    final.insert_pdf(cta)
    final.save(out_path, deflate=True, garbage=4)
    total = final.page_count
    final.close()
    interior.close()
    cta.close()
    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print("  OK: " + out_path + "  (" + str(total) + " pages, " + str(round(size_mb, 1)) + " MB)")

import sys
DL = "/var/www/mathrelaxing.store/static/downloads"

# key -> (display name, cover_path|None, interior_path, out_name, fix_isbn, motif, subtitle)
BOOKS = {
    "fractal_flora": ("Fractal Flora",
        f"{DL}/fractal-flora-coloring-book/cover.pdf",
        f"{DL}/fractal-flora-coloring-book/interior.pdf",
        "fractal_flora_digital.pdf", False, "harmonic",
        "We hope you enjoyed every curve and equation."),
    "hyperbolic_gardens": ("Hyperbolic Gardens",
        f"{DL}/hyperbolic-gardens/cover.pdf",
        f"{DL}/hyperbolic-gardens/interior.pdf",
        "hyperbolic_gardens_digital.pdf", False, "harmonic",
        "We hope you enjoyed every curve and equation."),
    "sacred_geometry": ("Sacred Geometry",
        f"{DL}/sacred-math-coloring-book/cover.pdf",
        f"{DL}/sacred-math-coloring-book/interior.pdf",
        "sacred_geometry_digital.pdf", False, "geometric",
        "We hope you enjoyed every facet and form."),
    "mathematical_tangle_art": ("Mathematical Tangle Art",
        f"{DL}/book/cover.pdf",
        f"{DL}/book/interior.pdf",
        "mathematical_tangle_art_digital.pdf", True, "harmonic",
        "We hope you enjoyed every curve and equation."),
    "sacred_harmonics": ("Sacred Harmonics",
        None,
        f"{DL}/Sacred_Harmonics_Book.pdf",
        "sacred_harmonics_digital.pdf", False, "harmonic",
        "We hope you enjoyed every curve and equation."),
}

# Optional: pass one or more book keys as args to regenerate only those.
targets = sys.argv[1:] if len(sys.argv) > 1 else list(BOOKS.keys())

for key in targets:
    name, cover_p, interior_p, out_name, fix_isbn_flag, motif, subtitle = BOOKS[key]
    print(f"\n-- {name} --")
    cover = extract_front_cover(cover_p) if cover_p else None
    build_book(name, cover, interior_p, OUT_DIR + "/" + out_name,
               fix_isbn_flag=fix_isbn_flag, motif=motif, subtitle=subtitle)

print("\nAll done!")
