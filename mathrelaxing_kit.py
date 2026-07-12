"""
mathrelaxing_kit.py  —  MathRelaxing VPS Toolkit
==================================================
Módulo base con todas las utilidades reutilizables para generar productos
digitales de MathRelaxing. Importar desde cualquier script nuevo:

    from mathrelaxing_kit import *          # todo
    from mathrelaxing_kit import BOOKS, kit_pdf, kit_ipad, kit_video

Organización:
  1. CONSTANTES   — rutas VPS, fuentes, colores de marca, paletas
  2. BOOKS        — catálogo de libros fuente (portada + interior)
  3. kit_draw     — helpers PIL: ctext, fnt, paste_logo, drawcheck
  4. kit_pdf      — helpers PyMuPDF: extract_front_cover, make_cta_page,
                    build_digital_pdf
  5. kit_image    — render_rgb, design_crop, prep_cells (flood-fill),
                    color_design_full, ipad_mockup, screen_fit
  6. kit_ipad     — build_hyperlinked_pdf, build_transparent_pngs,
                    build_swatches, build_guide, build_packages
  7. kit_preview  — make_preview_hero, make_preview_included,
                    make_preview_twoways
  8. kit_video    — animate_coloring_video, encode_video
  9. kit_attractor — render_attractor_density, thomas_attractor_points

Errores conocidos y sus fixes (NO repetir):
  - insert_textbox con Cinzel: box height >= fontsize*2 o no renderiza nada
  - Em-dash en Raleway: usar \xb7 (·) en lugar de — (glifo ausente)
  - np.ptp() eliminado en NumPy 2: usar arr.max()-arr.min()
  - Video mp4 con track fantasma (duracion erronea): ffmpeg -map 0:v:0 -map 0:a:0
  - Fractal lines (L-system): binary_dilation(gray<150, iterations=2) para cerrar
    micro-gaps; sacred geometry (low-poly): iterations=1 suficiente
  - PDF Hyperbolic Gardens original es vectorial 38MB: rasterizar a 200dpi grayscale
"""

import os, math, json, zipfile, glob, colorsys, subprocess, shutil, tempfile
import numpy as np
import fitz                                 # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import label, binary_dilation


# ==============================================================================
# 1. CONSTANTES
# ==============================================================================

ROOT   = "/var/www/mathrelaxing.store"
STATIC = f"{ROOT}/static"
FONTS  = f"{STATIC}/fonts"
LOGO   = f"{STATIC}/img/logo.png"
DL     = f"{STATIC}/downloads"          # raiz de descargas
DIGIT  = f"{DL}/digital"               # salidas digitales: {DIGIT}/<slug>/

CINZEL     = f"{FONTS}/Cinzel.ttf"
RALEWAY    = f"{FONTS}/Raleway.ttf"
RALEWAY_IT = f"{FONTS}/Raleway-Italic.ttf"

# Colores de marca (PIL RGB tuples)
NAVY  = (18,  23,  46)
GOLD  = (217, 173, 82)
WHITE = (244, 247, 245)
TEAL  = (125, 207, 179)
DIM   = (150, 162, 185)
CREAM = (248, 246, 240)

# Paletas de colorizacion (5 paradas, de clara a oscura)
PAL_WARM  = [(255,226,150),(255,168,88),(230,96,68),(150,48,82),(70,28,66)]    # sunset
PAL_COOL  = [(214,242,247),(140,200,224),(74,140,196),(40,86,150),(26,44,96)]  # ocean
PAL_AMTH  = [(232,216,246),(190,158,226),(138,98,190),(88,52,138),(48,28,84)]  # amethyst
PAL_FLORA = [(196,224,140),(140,200,120),(74,160,96),(168,224,212),(96,190,196)] # garden
PAL_GOLD  = [(255,248,200),(240,210,110),(196,168,60),(140,100,20),(80,50,0)]  # dorado

# Colores marca PyMuPDF (floats 0-1)
_MU_BG    = (0.07, 0.09, 0.18)
_MU_GOLD  = (0.85, 0.68, 0.32)
_MU_WHITE = (1.0,  1.0,  1.0 )
_MU_TEAL  = (0.49, 0.81, 0.70)
_MU_DIM   = (0.50, 0.57, 0.70)


# ==============================================================================
# 2. CATALOGO DE LIBROS FUENTE
# ==============================================================================

BOOKS = {
    # slug: cover, interior, title, subtitle, motif, design range, type
    "fractal_flora": {
        "cover":       f"{DL}/fractal-flora-coloring-book/cover.pdf",
        "interior":    f"{DL}/fractal-flora-coloring-book/interior.pdf",
        "audio":       f"{DL}/fractal-flora-coloring-book/promo.mp4",
        "title":       "Fractal Flora",
        "subtitle":    "50 Fractal & Botanical Line-Art Designs",
        "motif":       "harmonic",
        "design_from": 3,
        "design_to":   52,
        "fix_isbn":    False,
        "out_dir":     f"{DIGIT}/ipad_ff",
        "name":        "FractalFlora",
        "type":        "line_art",   # flood-fill necesita dilation=2
    },
    "sacred_geometry": {
        "cover":       f"{DL}/sacred-math-coloring-book/cover.pdf",
        "interior":    f"{DL}/sacred-math-coloring-book/interior.pdf",
        "audio":       f"{DL}/fractal-flora-coloring-book/promo.mp4",
        "title":       "Sacred Geometry",
        "subtitle":    "50 Low-Poly Color-by-Number Designs",
        "motif":       "geometric",
        "design_from": 2,
        "design_to":   51,
        "fix_isbn":    False,
        "out_dir":     f"{DIGIT}/ipad_sg",
        "name":        "SacredGeometry",
        "type":        "low_poly",   # flood-fill con dilation=1
    },
    "hyperbolic_gardens": {
        "cover":       f"{DL}/hyperbolic-gardens-coloring-book/cover.pdf",
        "interior":    f"{DL}/hyperbolic-gardens-coloring-book/interior.pdf",
        "audio":       f"{DL}/fractal-flora-coloring-book/promo.mp4",
        "title":       "Hyperbolic Gardens",
        "subtitle":    "50 Escher-Style Hyperbolic Tiling Designs",
        "motif":       "harmonic",
        "design_from": 3,
        "design_to":   52,
        "fix_isbn":    False,
        "out_dir":     f"{DIGIT}/ipad_hg",
        "name":        "HyperbolicGardens",
        "type":        "line_art",
    },
    "mathematical_tangle_art": {
        "cover":       f"{DL}/mathematical-tangle-art-coloring-book/cover.pdf",
        "interior":    f"{DL}/mathematical-tangle-art-coloring-book/interior.pdf",
        "audio":       f"{DL}/fractal-flora-coloring-book/promo.mp4",
        "title":       "Mathematical Tangle Art",
        "subtitle":    "50 Zentangle Mathematical Designs",
        "motif":       "harmonic",
        "design_from": 3,
        "design_to":   52,
        "fix_isbn":    True,         # tiene ISBN que remover
        "out_dir":     f"{DIGIT}/ipad_mta",
        "name":        "MathematicalTangleArt",
        "type":        "line_art",
    },
    "sacred_harmonics": {
        "cover":       f"{DL}/sacred-harmonics-coloring-book/cover.pdf",
        "interior":    f"{DL}/sacred-harmonics-coloring-book/interior.pdf",
        "audio":       f"{DL}/fractal-flora-coloring-book/promo.mp4",
        "title":       "Sacred Harmonics",
        "subtitle":    "50 Cymatics & Wave Geometry Designs",
        "motif":       "harmonic",
        "design_from": 3,
        "design_to":   52,
        "fix_isbn":    False,
        "out_dir":     f"{DIGIT}/ipad_sh",
        "name":        "SacredHarmonics",
        "type":        "line_art",
    },
}


# ==============================================================================
# 3. kit_draw — helpers PIL
# ==============================================================================

def fnt(path, size):
    """Carga una fuente TTF."""
    return ImageFont.truetype(path, size)

def ctext(draw, cx, y, text, font, fill):
    """Dibuja texto centrado horizontalmente en x=cx, y=y."""
    b = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (b[2]-b[0])/2, y), text, font=font, fill=fill)

def paste_logo(img, y, scale=0.13, alpha=0.9):
    """Pega el logo de MathRelaxing centrado en img, a altura y."""
    lg = Image.open(LOGO).convert("RGBA")
    lw = int(img.width * scale)
    lh = int(lg.height * lw / lg.width)
    lg = lg.resize((lw, lh), Image.LANCZOS)
    if alpha < 1:
        r, g, b, a = lg.split()
        a = a.point(lambda p: int(p * alpha))
        lg = Image.merge("RGBA", (r, g, b, a))
    img.paste(lg, ((img.width - lw) // 2, y), lg)

def drawcheck(draw, cx, cy, size, color):
    """Dibuja un checkmark con lineas — reemplaza emoji que no estan en las fuentes."""
    draw.line(
        [(cx - size*0.34, cy + size*0.02),
         (cx - size*0.06, cy + size*0.28),
         (cx + size*0.36, cy - size*0.32)],
        fill=color, width=8, joint="curve"
    )

def dot_bg(draw, size, step=46, color=(26, 32, 58)):
    """Fondo de puntos sutiles estilo MathRelaxing."""
    for x in range(0, size, step):
        for y in range(0, size, step):
            draw.ellipse([x-1, y-1, x+1, y+1], fill=color)

# ── Texto en PDF (fitz) — SIEMPRE usar este helper ────────────────────────────
# GOTCHA: fitz.insert_textbox con fontfile pero SIN fontname propio cae a
# Helvetica e ignora el archivo. Hay que pasar un fontname unico por fuente.
# Ademas la caja debe medir >= fontsize*2 de alto o Cinzel no renderiza nada.
_PDF_FONTNAME = {CINZEL: "mrcz", RALEWAY: "mrrw", RALEWAY_IT: "mrrwi"}

def put_text(page, rect, text, fontfile, fontsize, color, align=1, lineheight=1.0):
    """insert_textbox correcto: fontname propio + (idealmente) caja alta."""
    return page.insert_textbox(
        rect, text,
        fontname=_PDF_FONTNAME.get(fontfile, "mrf0"),
        fontfile=fontfile, fontsize=fontsize, color=color,
        align=align, lineheight=lineheight,
    )


# ==============================================================================
# 4. kit_pdf — builders de PDF con PyMuPDF
# ==============================================================================

def extract_front_cover(cover_path):
    """
    Recorta la portada delantera de un PDF Lulu wrap-around (aprox 1255pt ancho).
    La delantera es los ultimos 612pt del PDF de cubierta.
    Devuelve un fitz.Document de una pagina.
    """
    src  = fitz.open(cover_path)
    pg   = src[0]
    w    = pg.rect.width
    clip = fitz.Rect(w - 612, 0, w, pg.rect.height)
    out  = fitz.open()
    new  = out.new_page(width=612, height=pg.rect.height)
    new.show_pdf_page(new.rect, src, 0, clip=clip)
    return out

def fix_isbn_block(interior_path):
    """
    Devuelve fitz.Document con el bloque ISBN borrado (Mathematical Tangle Art).
    Redibuja en blanco el area ISBN en la ultima pagina del interior.
    """
    doc = fitz.open(interior_path)
    pg  = doc[-1]
    for block in pg.get_text("blocks"):
        if "ISBN" in block[4]:
            rect = fitz.Rect(block[:4])
            pg.draw_rect(rect, color=None, fill=(1, 1, 1))
    return doc

def _mu_line(page, y, text, fontfile, fontsize, color, pad=55):
    """Inserta texto centrado con caja de altura segura (fontsize*2 — requerido por Cinzel)."""
    w = page.rect.width
    page.insert_textbox(
        fitz.Rect(pad, y, w - pad, y + fontsize * 2.0),
        text, fontfile=fontfile, fontsize=fontsize, color=color,
        align=1, lineheight=1.0
    )

def make_cta_page(book_title, pw=612, ph=792, motif="harmonic", subtitle=""):
    """
    Genera la pagina CTA final del PDF digital.
    motif='harmonic'  -> rosa matematica + Lissajous (libros de lineas)
    motif='geometric' -> toro wireframe con elipses (Sacred Geometry)
    Devuelve fitz.Document de una pagina.
    """
    doc = fitz.open()
    pg  = doc.new_page(width=pw, height=ph)
    pg.draw_rect(pg.rect, color=None, fill=_MU_BG)

    if motif == "harmonic":
        cx, cy, R = pw/2, ph*0.38, 110
        pts = [(cx + R*abs(math.cos(3*math.radians(i)))*math.cos(math.radians(i)),
                cy + R*abs(math.cos(3*math.radians(i)))*math.sin(math.radians(i)))
               for i in range(361)]
        sh = pg.new_shape()
        for i in range(len(pts)-1):
            sh.draw_line(fitz.Point(*pts[i]), fitz.Point(*pts[i+1]))
        sh.finish(color=_MU_GOLD, width=1.2); sh.commit()

        pts2 = [(cx + 70*math.sin(3*math.radians(i) + math.pi/4),
                 cy + 70*math.sin(2*math.radians(i))) for i in range(361)]
        sh2 = pg.new_shape()
        for i in range(len(pts2)-1):
            sh2.draw_line(fitz.Point(*pts2[i]), fitz.Point(*pts2[i+1]))
        sh2.finish(color=(*_MU_TEAL, 0.7), width=0.8); sh2.commit()

    elif motif == "geometric":
        cx, cy = pw/2, ph*0.36
        sh = pg.new_shape()
        for i in range(8):
            a = 90 + i*12; b = 35 + i*5
            sh.draw_oval(fitz.Rect(cx-a, cy-b, cx+a, cy+b))
        sh.finish(color=_MU_GOLD, width=0.9); sh.commit()
        sh2 = pg.new_shape()
        for i in range(6):
            a = 30 + i*14; b = 55 + i*8
            sh2.draw_oval(fitz.Rect(cx-a, cy-b, cx+a, cy+b))
        sh2.finish(color=(*_MU_TEAL, 0.6), width=0.7); sh2.commit()

    _mu_line(pg, ph*0.57, "mathrelaxing.store",         CINZEL,     13, _MU_GOLD)
    _mu_line(pg, ph*0.62, book_title,                   CINZEL,     18, _MU_WHITE)
    if subtitle:
        _mu_line(pg, ph*0.67, subtitle,                 RALEWAY_IT,  9, _MU_DIM)
    _mu_line(pg, ph*0.73, "Thank you for coloring with us", RALEWAY_IT, 9.5, _MU_TEAL)
    _mu_line(pg, ph*0.79,
             "\xa9 MathRelaxing \xb7 For personal use only \xb7 Not for redistribution",
             RALEWAY, 7, _MU_DIM)
    return doc

def build_digital_pdf(book_slug, out_path=None):
    """
    Construye el PDF digital completo: portada recortada + interior + pagina CTA.
    Devuelve la ruta del PDF generado.
    """
    b = BOOKS[book_slug]
    if out_path is None:
        out_path = f"{DIGIT}/{book_slug.replace('_','-')}_digital.pdf"

    cover_doc = extract_front_cover(b["cover"])
    interior_doc = fix_isbn_block(b["interior"]) if b.get("fix_isbn") else fitz.open(b["interior"])
    cta_doc = make_cta_page(b["title"], motif=b["motif"], subtitle=b["subtitle"])

    out = fitz.open()
    out.insert_pdf(cover_doc)
    out.insert_pdf(interior_doc)
    out.insert_pdf(cta_doc)
    out.save(out_path, deflate=True, garbage=4)
    out.close()
    print(f"  PDF digital: {out_path} ({os.path.getsize(out_path)/1024/1024:.1f} MB)")
    return out_path


# ==============================================================================
# 5. kit_image — rendering y flood-fill
# ==============================================================================

def render_rgb(pdf_path, page_idx, target_width=1000):
    """Renderiza una pagina PDF como array numpy RGB uint8 (H, W, 3)."""
    p   = fitz.open(pdf_path)[page_idx]
    mat = fitz.Matrix(target_width / p.rect.width, target_width / p.rect.width)
    pix = p.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).copy()

def design_crop(arr, content_ratio=0.86, dark_thresh=140, pad_ratio=0.04):
    """
    Recorta el area de diseno eliminando margenes blancos y numero de pagina.
    content_ratio: fraccion de altura a usar (excluye pie de pagina).
    """
    g = arr.mean(2); h, w = g.shape
    reg = g[:int(h * content_ratio), :]
    ys, xs = np.where(reg < dark_thresh)
    if len(xs) == 0:
        return arr
    pad = int(pad_ratio * max(w, h))
    return arr[
        max(0, ys.min()-pad) : min(int(h*content_ratio), ys.max()+pad),
        max(0, xs.min()-pad) : min(w, xs.max()+pad)
    ]

def prep_cells(arr, palette, book_type="line_art"):
    """
    Detecta celdas coloreables por flood-fill y las ordena del centro hacia afuera.

    arr:       numpy float32 (H, W, 3) ya recortado.
    palette:   lista de 5 tuplas RGB (clara a oscura).
    book_type: 'line_art' usa dilation=2 (fractales, lineas finas)
               'low_poly' usa dilation=1 (poligonos cerrados Sacred Geometry)

    Devuelve lista de (mask_bool, color_rgb_list).
    """
    g = arr.mean(2); h, w = g.shape
    base_dil = 2 if book_type == "line_art" else 1
    best = None
    for dil in (base_dil, base_dil + 1):
        lines = binary_dilation(g < 150, iterations=dil)
        lbl, n = label(~lines)
        border = set(lbl[0,:]) | set(lbl[-1,:]) | set(lbl[:,0]) | set(lbl[:,-1])
        cells = [lbl == i for i in range(1, n+1)
                 if i not in border and 18 < (lbl==i).sum() < g.size*0.04]
        if best is None or len(cells) > len(best):
            best = cells

    cells = best or []
    cx, cy = w / 2, h / 2
    info = [(m, math.hypot(np.where(m)[1].mean()-cx, np.where(m)[0].mean()-cy))
            for m in cells]
    info.sort(key=lambda t: t[1])

    if info:
        dd = np.array([d for _, d in info])
        dmin, dspan = dd.min(), (dd.max() - dd.min()) or 1
    else:
        dmin, dspan = 0, 1

    out = []
    for (m, d) in info:
        t = (d - dmin) / dspan
        pos = t * (len(palette)-1); k = int(pos); fr = pos - k
        a = palette[k]; b = palette[min(k+1, len(palette)-1)]
        col = [a[j]*(1-fr) + b[j]*fr for j in range(3)]
        out.append((m, col))
    return out

def color_design_full(arr, palette, book_type="line_art"):
    """Colorea un diseno completo de una vez. Devuelve PIL Image RGB."""
    cells = prep_cells(arr.astype(np.float32), palette, book_type)
    cur = arr.astype(np.float32).copy()
    for (m, col) in cells:
        for j in range(3):
            cur[:,:,j][m] = col[j]
    return Image.fromarray(np.clip(cur, 0, 255).astype(np.uint8), "RGB")

def ipad_mockup(screen_img, fw=1080, fh=1440):
    """
    Crea mockup de iPad con screen_img en pantalla.
    Devuelve PIL Image RGBA (cuerpo con fondo transparente).
    """
    body = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    d = ImageDraw.Draw(body)
    d.rounded_rectangle([0, 0, fw, fh], radius=70, fill=(28, 30, 38, 255))
    bz = 34; sx, sy = bz, bz+10; sw, sh = fw-2*bz, fh-2*bz-20
    scr = Image.new("RGB", (sw, sh), (255, 255, 255))
    im = screen_img.copy()
    r = min(sw/im.width, sh/im.height) * 0.94
    im = im.resize((int(im.width*r), int(im.height*r)), Image.LANCZOS)
    scr.paste(im, ((sw-im.width)//2, (sh-im.height)//2))
    body.paste(scr, (sx, sy))
    d.ellipse([fw/2-5, 15, fw/2+5, 25], fill=(80, 84, 96, 255))
    return body

def screen_fit(img, sw, sh):
    """Escala img para caber en sw x sh con margen 5%, sobre fondo blanco."""
    r = min(sw/img.width, sh/img.height) * 0.95
    im = img.resize((int(img.width*r), int(img.height*r)), Image.LANCZOS)
    sc = Image.new("RGB", (sw, sh), (255, 255, 255))
    sc.paste(im, ((sw-im.width)//2, (sh-im.height)//2))
    return sc


# ==============================================================================
# 6. kit_ipad — bundle completo GoodNotes + Procreate
# ==============================================================================

def build_hyperlinked_pdf(book_slug, out_dir=None):
    """
    PDF con indice de miniaturas hipervinculadas (tap -> salta al diseno).
    Grilla 4x5, tantas paginas indice como hagan falta, luego los disenos.
    """
    b = BOOKS[book_slug]
    if out_dir is None:
        out_dir = b["out_dir"]
    os.makedirs(out_dir, exist_ok=True)

    src = fitz.open(b["interior"])
    d_from, d_to = b["design_from"], b["design_to"]
    nd = d_to - d_from + 1
    pw, ph = src[d_from].rect.width, src[d_from].rect.height
    COLS, ROWS, per = 4, 5, 20
    nidx = math.ceil(nd / per)

    final = fitz.open()
    for _ in range(nidx):
        pg = final.new_page(width=pw, height=ph)
        pg.draw_rect(pg.rect, color=None, fill=_MU_BG)
    final.insert_pdf(src, from_page=d_from, to_page=d_to)

    mx, mtop, gap = 40, 90, 14
    cw = (pw - 2*mx - (COLS-1)*gap) / COLS
    ch = (ph - mtop - 40 - (ROWS-1)*gap) / ROWS
    td = tempfile.mkdtemp()

    for i in range(nd):
        idxp = i // per; slot = i % per
        row, col = slot // COLS, slot % COLS
        pg = final[idxp]
        if slot == 0:
            put_text(pg, fitz.Rect(40, 36, pw-40, 36+34),
                     "Tap a design to jump to it",
                     CINZEL, 17, _MU_WHITE, align=1)
        x0 = mx + col*(cw+gap); y0 = mtop + row*(ch+gap)
        rect = fitz.Rect(x0, y0, x0+cw, y0+ch-14)
        pix = src[d_from+i].get_pixmap(matrix=fitz.Matrix(0.5, 0.5), colorspace=fitz.csRGB)
        tp = os.path.join(td, f"t{i}.png"); pix.save(tp)
        pg.draw_rect(rect, color=(0.2,0.26,0.42), fill=(1,1,1), width=0.5)
        pg.insert_image(rect, filename=tp, keep_proportion=True)
        put_text(pg, fitz.Rect(x0, y0+ch-16, x0+cw, y0+ch+1), str(i+1),
                 RALEWAY, 8, _MU_GOLD, align=1)
        pg.insert_link({"kind": fitz.LINK_GOTO, "from": rect,
                        "page": nidx+i, "to": fitz.Point(0,0)})

    name = b["name"]
    out = f"{out_dir}/{name}_iPad_GoodNotes.pdf"
    final.save(out, deflate=True, garbage=4)
    src.close(); final.close(); shutil.rmtree(td, ignore_errors=True)
    print(f"  PDF iPad: {os.path.basename(out)} ({os.path.getsize(out)/1024/1024:.1f} MB)")
    return out

def build_transparent_pngs(book_slug, out_dir=None, dpi=300):
    """
    Exporta los disenos del interior como PNGs RGBA transparentes.
    Lineas/numeros = opacos, zonas blancas = transparentes.
    Formula alpha: clip((210 - gray) / 90, 0, 1) * 255
    """
    b = BOOKS[book_slug]
    if out_dir is None:
        out_dir = b["out_dir"]
    png_dir = f"{out_dir}/Procreate_PNG"
    os.makedirs(png_dir, exist_ok=True)

    src = fitz.open(b["interior"]); n = 0; name = b["name"]
    for idx in range(b["design_from"], b["design_to"]+1):
        n += 1
        pix = src[idx].get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72),
                                   colorspace=fitz.csRGB, alpha=False)
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).astype(np.uint8)
        gray = arr.mean(2)
        alpha = (np.clip((210 - gray) / 90.0, 0, 1) * 255).astype(np.uint8)
        Image.fromarray(np.dstack([arr, alpha]), "RGBA").save(
            f"{png_dir}/{name}_{n:02d}.png", optimize=True)
    src.close()
    print(f"  PNGs: {n} disenos transparentes @ {dpi}dpi -> {png_dir}")
    return png_dir

def build_swatches(colors_rgb, book_slug, out_dir=None):
    """
    Genera paleta .swatches para Procreate (ZIP con Swatches.json en HSB).
    colors_rgb: lista de tuplas (R, G, B), maximo 30.
    """
    b = BOOKS[book_slug]
    if out_dir is None:
        out_dir = b["out_dir"]
    name = b["name"]; title = f"MathRelaxing — {b['title']}"
    sw = []
    for (r, g, bv) in colors_rgb[:30]:
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, bv/255)
        sw.append({"hue": round(h,4), "saturation": round(s,4),
                   "brightness": round(v,4), "alpha": 1, "colorSpace": 0})
    data = [{"name": title, "swatches": sw}]
    out = f"{out_dir}/{name}.swatches"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Swatches.json", json.dumps(data))
    print(f"  Swatches: {len(sw)} colores -> {os.path.basename(out)}")
    return out

def build_guide(book_slug, goodnotes_text, procreate_text, note_text, out_dir=None):
    """
    Genera 'How to use on iPad' como PDF elegante Cinzel + Raleway.
    """
    b = BOOKS[book_slug]
    if out_dir is None:
        out_dir = b["out_dir"]

    doc = fitz.open(); pw, ph = 612, 792
    pg  = doc.new_page(width=pw, height=ph)
    pg.draw_rect(pg.rect, color=None, fill=_MU_BG)
    lw = 120; lh = int(120 * 575 / 800)
    pg.insert_image(fitz.Rect(pw/2-lw/2, 56, pw/2+lw/2, 56+lh), filename=LOGO)

    def line(y, text, fontfile, size, color, pad=55):
        put_text(pg, fitz.Rect(pad, y, pw-pad, y+size*2.2),
                 text, fontfile, size, color, align=1, lineheight=1.0)
    def para(y, text, size=10.5, color=_MU_WHITE, pad=70):
        put_text(pg, fitz.Rect(pad, y, pw-pad, y+200),
                 text, RALEWAY, size, color, align=0, lineheight=1.35)
    def head(y, text):
        put_text(pg, fitz.Rect(72, y, pw-72, y+30),
                 text, CINZEL, 12.5, _MU_TEAL, align=0)

    line(148, "Coloring on Your iPad",           CINZEL,     21, _MU_WHITE)
    line(181, f"{b['title']}  \xb7  iPad Edition", RALEWAY_IT, 11, _MU_GOLD)
    line(204, "No printer, no mess \xb7 just you, your Apple Pencil, and the designs.",
         RALEWAY_IT, 9.5, (0.62, 0.68, 0.8))
    sh = pg.new_shape(); sh.draw_line((72, 234), (pw-72, 234))
    sh.finish(color=_MU_GOLD, width=0.8); sh.commit()

    head(258, "In GoodNotes or Notability"); para(284, goodnotes_text)
    head(372, "In Procreate");               para(398, procreate_text)
    head(486, "A gentle note");              para(512, note_text)
    line(712, "mathrelaxing.store", CINZEL, 12, _MU_GOLD)
    line(737, "\xa9 MathRelaxing \xb7 For personal use only", RALEWAY, 7.5, _MU_DIM)

    out = f"{out_dir}/How_to_use_on_iPad.pdf"
    doc.save(out); doc.close()
    print(f"  Guide: {os.path.basename(out)}")
    return out

def build_packages(book_slug, out_dir=None, limit_mb=19):
    """
    Empaqueta PNGs en ZIPs de max limit_mb MB (limite Etsy = 20MB/archivo).
    Devuelve lista de rutas ZIP generadas.
    """
    b = BOOKS[book_slug]
    if out_dir is None:
        out_dir = b["out_dir"]
    name = b["name"]
    png_dir = f"{out_dir}/Procreate_PNG"
    pngs = sorted(glob.glob(f"{png_dir}/*.png"))
    limit = limit_mb * 1024 * 1024
    groups = [[]]; sizes = [0]
    for p in pngs:
        sz = os.path.getsize(p)
        if sizes[-1] + sz > limit and groups[-1]:
            groups.append([]); sizes.append(0)
        groups[-1].append(p); sizes[-1] += sz
    zips = []
    for i, g in enumerate(groups, 1):
        suf = "" if len(groups) == 1 else f"_part{i}"
        zp = f"{out_dir}/{name}_Procreate_PNG{suf}.zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for pp in g:
                z.write(pp, "Procreate_PNG/" + os.path.basename(pp))
        print(f"  ZIP: {os.path.basename(zp)} ({len(g)} PNGs, {os.path.getsize(zp)/1024/1024:.1f} MB)")
        zips.append(zp)
    return zips


# ==============================================================================
# 7. kit_preview — imagenes Etsy 2000x2000
# ==============================================================================

S_PREV = 2000

def _prev_base():
    cv = Image.new("RGB", (S_PREV, S_PREV), NAVY)
    d  = ImageDraw.Draw(cv)
    dot_bg(d, S_PREV)
    return cv, d

def make_preview_hero(book_slug, design_idx, palette, out_dir=None, book_type=None):
    """
    Preview 1: iPad mockup con diseno coloreado en pantalla.
    design_idx: indice 0-based en interior.pdf.
    """
    b = BOOKS[book_slug]
    if out_dir is None: out_dir = b["out_dir"]
    if book_type is None: book_type = b.get("type", "line_art")
    os.makedirs(f"{out_dir}/previews", exist_ok=True)

    arr = design_crop(render_rgb(b["interior"], design_idx).astype(np.float32))
    colored = color_design_full(arr, palette, book_type)
    pad = ipad_mockup(colored)
    r = 900 / pad.width
    pad = pad.resize((int(pad.width*r), int(pad.height*r)), Image.LANCZOS)

    cv, d = _prev_base()
    ctext(d, S_PREV/2, 90,  "Coloring Book for iPad",                fnt(CINZEL, 76),     WHITE)
    ctext(d, S_PREV/2, 196, f"{b['title']}  \xb7  {b['subtitle']}", fnt(RALEWAY_IT, 40), GOLD)
    px = (S_PREV - pad.width) // 2; py = 300
    cv.paste(pad, (px, py), pad)
    d = ImageDraw.Draw(cv)
    ctext(d, S_PREV/2, py+pad.height+34,
          "GoodNotes  \xb7  Notability  \xb7  Procreate", fnt(RALEWAY, 34), TEAL)
    paste_logo(cv, S_PREV - 150)
    out = f"{out_dir}/previews/ipad_preview_1_hero.jpg"
    cv.save(out, "JPEG", quality=92)
    print(f"  Preview 1 hero -> {os.path.basename(out)}")
    return out

def make_preview_included(book_slug, items, out_dir=None):
    """
    Preview 2: lista 'Everything Included' con checkmarks.
    items: lista de strings, maximo 6 lineas.
    """
    b = BOOKS[book_slug]
    if out_dir is None: out_dir = b["out_dir"]
    os.makedirs(f"{out_dir}/previews", exist_ok=True)

    cv = Image.new("RGB", (S_PREV, S_PREV), NAVY)
    d  = ImageDraw.Draw(cv)
    d.rectangle([0, 0, S_PREV, 8], fill=GOLD)
    ctext(d, S_PREV/2, 110, "Everything Included",               fnt(CINZEL, 80),     WHITE)
    ctext(d, S_PREV/2, 220, f"{b['title']}  \xb7  iPad Edition", fnt(RALEWAY_IT, 38), GOLD)
    y = 400
    for desc in items[:6]:
        d.rounded_rectangle([160, y, 250, y+84], radius=18, fill=(30, 38, 64))
        drawcheck(d, 205, y+42, 40, GOLD)
        d.text((300, y+20), desc, font=fnt(RALEWAY, 38), fill=WHITE)
        y += 135
    paste_logo(cv, S_PREV - 150)
    out = f"{out_dir}/previews/ipad_preview_2_included.jpg"
    cv.save(out, "JPEG", quality=92)
    print(f"  Preview 2 included -> {os.path.basename(out)}")
    return out

def make_preview_twoways(book_slug, design_idx, palette, out_dir=None, book_type=None):
    """
    Preview 3: 'Two Ways to Color' — GoodNotes (lineas) vs Procreate (coloreado).
    """
    b = BOOKS[book_slug]
    if out_dir is None: out_dir = b["out_dir"]
    if book_type is None: book_type = b.get("type", "line_art")
    os.makedirs(f"{out_dir}/previews", exist_ok=True)

    arr   = design_crop(render_rgb(b["interior"], design_idx).astype(np.float32))
    lined = Image.fromarray(arr.astype(np.uint8), "RGB")
    col   = color_design_full(arr, palette, book_type)

    cv, d = _prev_base()
    ctext(d, S_PREV/2, 90,  "Two Ways to Color",                      fnt(CINZEL, 78),     WHITE)
    ctext(d, S_PREV/2, 196, "however you love to work on your iPad",  fnt(RALEWAY_IT, 38), GOLD)

    def panel(cx, img, label_text, sub_text):
        r    = min(620/img.width, 820/img.height)
        im   = img.resize((int(img.width*r), int(img.height*r)), Image.LANCZOS)
        card = Image.new("RGB", (im.width+60, im.height+60), (250,250,248))
        card.paste(im, (30, 30))
        cv.paste(card, (cx - card.width//2, 330))
        dd = ImageDraw.Draw(cv)
        ctext(dd, cx, 330+card.height+30, label_text, fnt(CINZEL, 42),  TEAL)
        ctext(dd, cx, 330+card.height+88, sub_text,   fnt(RALEWAY, 30), DIM)

    panel(S_PREV//4 + 40,          lined, "GoodNotes",  "color on top with Apple Pencil")
    panel(S_PREV//2+S_PREV//4-40,  col,   "Procreate",  "color beneath the line art")
    paste_logo(cv, S_PREV - 150)
    out = f"{out_dir}/previews/ipad_preview_3_twoways.jpg"
    cv.save(out, "JPEG", quality=92)
    print(f"  Preview 3 twoways -> {os.path.basename(out)}")
    return out


# ==============================================================================
# 8. kit_video — animacion de colorizacion + ffmpeg
# ==============================================================================

V_SIZE = 1080; FPS = 30
_IPW, _IPH = 560, 748
_IPX = (V_SIZE - _IPW) // 2; _IPY = 150
_BZ  = 16
_SX, _SY = _IPX + _BZ, _IPY + _BZ
_SW, _SH  = _IPW - 2*_BZ, _IPH - 2*_BZ

def _video_base(book_title, subtitle_line):
    """Canvas base 1080x1080 con branding y mockup iPad vacio."""
    cv = Image.new("RGB", (V_SIZE, V_SIZE), NAVY)
    d  = ImageDraw.Draw(cv)
    dot_bg(d, V_SIZE)
    ctext(d, V_SIZE/2, 46,  book_title,    fnt(CINZEL, 52),     WHITE)
    ctext(d, V_SIZE/2, 118, subtitle_line, fnt(RALEWAY_IT, 27), GOLD)
    d.rounded_rectangle([_IPX, _IPY, _IPX+_IPW, _IPY+_IPH], radius=44, fill=(25,27,34))
    d.ellipse([V_SIZE/2-5, _IPY+7, V_SIZE/2+5, _IPY+17], fill=(52,55,63))
    d.rectangle([_SX, _SY, _SX+_SW, _SY+_SH], fill=(255,255,255))
    ctext(d, V_SIZE/2, _IPY+_IPH+34,
          "GoodNotes  \xb7  Notability  \xb7  Procreate", fnt(RALEWAY, 26), TEAL)
    lg = Image.open(LOGO).convert("RGBA")
    lw = 120; lh = int(lg.height * lw / lg.width)
    lg = lg.resize((lw, lh), Image.LANCZOS)
    cv = cv.convert("RGBA"); cv.alpha_composite(lg, ((V_SIZE-lw)//2, V_SIZE-lh-26))
    return cv.convert("RGB")

def animate_coloring_video(book_slug, designs, out_path=None,
                           fill_frames=138, hold_bw=18, hold_done=39,
                           cross_frames=15, fade_frames=21):
    """
    Genera video de colorizacion celda-por-celda (centro hacia afuera).

    book_slug: clave de BOOKS.
    designs:   lista de (page_idx, palette, book_type).
               Ej: [(17, PAL_WARM, 'line_art'), (18, PAL_COOL, 'line_art')]
    fill_frames: frames totales para rellenar todas las celdas de un diseno.
    hold_bw:     frames de pausa inicial en blanco/negro.
    hold_done:   frames de pausa al terminar cada diseno.
    cross_frames: frames de crossfade entre disenos.
    fade_frames:  frames de fade a NAVY al final.
    """
    b = BOOKS[book_slug]
    if out_path is None:
        out_path = f"{b['out_dir']}/{b['name']}_iPad_promo.mp4"

    base = _video_base(
        "Coloring Book for iPad",
        f"{b['title']}  \xb7  GoodNotes & Procreate"
    )
    tmp = tempfile.mkdtemp(prefix="kit_vid_"); fi = [0]

    def save(cv): cv.save(os.path.join(tmp, f"f_{fi[0]:05d}.png")); fi[0] += 1
    def frame_with(arr):
        cv = base.copy()
        sc = screen_fit(Image.fromarray(np.clip(arr,0,255).astype(np.uint8),"RGB"), _SW, _SH)
        cv.paste(sc, (_SX, _SY)); return cv

    last = None
    for di, (pidx, pal, btype) in enumerate(designs):
        arr_orig = design_crop(render_rgb(b["interior"], pidx).astype(np.float32))
        cells    = prep_cells(arr_orig, pal, btype)
        cur      = arr_orig.copy(); n = len(cells)
        print(f"  diseno pagina {pidx}: {n} celdas")

        if di == 0:
            for _ in range(hold_bw): save(frame_with(cur))

        per = max(1, math.ceil(n / fill_frames)); i = 0
        while i < n:
            for (m, col) in cells[i:i+per]:
                for j in range(3): cur[:,:,j][m] = col[j]
            save(frame_with(cur)); i += per

        done = frame_with(cur)
        for _ in range(hold_done): save(done)

        if di < len(designs) - 1:
            nxt_arr = design_crop(render_rgb(b["interior"], designs[di+1][0]).astype(np.float32))
            nxt_fr  = frame_with(nxt_arr)
            for f in range(cross_frames):
                save(Image.blend(done, nxt_fr, (f+1)/cross_frames))
        last = done

    navy_img = Image.new("RGB", (V_SIZE, V_SIZE), NAVY)
    for f in range(fade_frames):
        save(Image.blend(last, navy_img, ((f+1)/fade_frames)*0.6))

    dur = fi[0] / FPS
    print(f"  {fi[0]} frames ({dur:.1f}s)")
    encode_video(tmp, out_path, b.get("audio"), dur)
    shutil.rmtree(tmp, ignore_errors=True)
    return out_path

def encode_video(frames_dir, out_path, audio_src=None, duration=None):
    """
    Codifica frames PNG -> mp4 con libx264.
    audio_src: ruta mp4/aac para extraer audio con fade in/out.
    Usa -map 0:v:0 -map 1:a:0 para evitar tracks fantasma.
    """
    aud_path = None
    if audio_src and os.path.exists(audio_src) and duration:
        aud_path = "/tmp/kit_audio.aac"
        fade_out = max(0.5, duration - 1.3)
        subprocess.run(
            f'ffmpeg -y -i "{audio_src}" -map 0:a:0 -t {duration:.2f} '
            f'-af "afade=t=in:st=0:d=0.8,afade=t=out:st={fade_out:.2f}:d=1.3" '
            f'-ac 2 -c:a aac -b:a 160k "{aud_path}"',
            shell=True, capture_output=True
        )
        if not (os.path.exists(aud_path) and os.path.getsize(aud_path) > 1000):
            aud_path = None

    cmd = (f'ffmpeg -y -framerate {FPS} -i "{frames_dir}/f_%05d.png"'
           + (f' -i "{aud_path}"' if aud_path else '')
           + ' -c:v libx264 -pix_fmt yuv420p -crf 18 -preset slow -movflags +faststart'
           + (' -map 0:v:0 -map 1:a:0 -c:a aac -shortest' if aud_path else '')
           + f' "{out_path}"')
    subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"  Video: {os.path.basename(out_path)} ({mb:.1f} MB, audio={'si' if aud_path else 'no'})")


# ==============================================================================
# 9. kit_attractor — arte matematico generativo
# ==============================================================================

def render_attractor_density(points_xy, size=1080, sigma=1.2, log_scale=True,
                              color_start=(200,160,40), color_end=(40,200,190)):
    """
    Renderiza un atractor como nube de densidad con colormap gold->teal.
    points_xy: array (N, 2) — proyeccion 2D de la trayectoria.
    Devuelve PIL Image RGB.
    """
    from scipy.ndimage import gaussian_filter
    x, y = points_xy[:,0], points_xy[:,1]
    margin = 0.05
    xi = ((x-x.min())/(x.max()-x.min()) * (1-2*margin) + margin) * (size-1)
    yi = ((y-y.min())/(y.max()-y.min()) * (1-2*margin) + margin) * (size-1)
    hist, _, _ = np.histogram2d(xi, yi, bins=size, range=[[0,size],[0,size]])
    dens = gaussian_filter(hist.T, sigma=sigma)
    if log_scale:
        dens = np.log1p(dens)
    dens = dens / dens.max()
    img = np.zeros((size, size, 3), dtype=np.uint8)
    for c in range(3):
        img[:,:,c] = (dens*color_end[c] + (1-dens)*color_start[c]).astype(np.uint8)
    return Image.fromarray(img, "RGB")

def thomas_attractor_points(b=0.19, n_points=1_200_000, dt=0.05, burnin=1000):
    """
    Integra el atractor de Thomas. b=0.19 -> caos simetrico con estructura limpia.
    Devuelve array (N, 2) con proyeccion XY.
    """
    x, y, z = 1.0, 0.0, 0.0
    for _ in range(burnin):
        x, y, z = (x + dt*(math.sin(y)-b*x),
                   y + dt*(math.sin(z)-b*y),
                   z + dt*(math.sin(x)-b*z))
    pts = np.empty((n_points, 2))
    for i in range(n_points):
        x, y, z = (x + dt*(math.sin(y)-b*x),
                   y + dt*(math.sin(z)-b*y),
                   z + dt*(math.sin(x)-b*z))
        pts[i] = (x, y)
    return pts

def lorenz_attractor_points(sigma=10, rho=28, beta=8/3,
                             n_points=800_000, dt=0.005, burnin=500):
    """
    Integra el atractor de Lorenz (clasico del caos).
    Devuelve array (N, 2) con proyeccion XZ.
    """
    x, y, z = 1.0, 1.0, 1.0
    for _ in range(burnin):
        x, y, z = (x + dt*sigma*(y-x),
                   y + dt*(x*(rho-z)-y),
                   z + dt*(x*y - beta*z))
    pts = np.empty((n_points, 2))
    for i in range(n_points):
        x, y, z = (x + dt*sigma*(y-x),
                   y + dt*(x*(rho-z)-y),
                   z + dt*(x*y - beta*z))
        pts[i] = (x, z)
    return pts


# ==============================================================================
# CLI minimo de test
# ==============================================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        slug = sys.argv[2] if len(sys.argv) > 2 else "fractal_flora"
        b = BOOKS[slug]
        print(f"Test rapido para '{slug}':")
        print(f"  cover    : {os.path.exists(b['cover'])}")
        print(f"  interior : {os.path.exists(b['interior'])}")
        print(f"  out_dir  : {b['out_dir']}")
        arr = design_crop(render_rgb(b["interior"], b["design_from"]))
        print(f"  1er diseno: {arr.shape} px")
        cells = prep_cells(arr.astype(np.float32), PAL_WARM, b.get("type","line_art"))
        print(f"  celdas detectadas: {len(cells)}")
        print("OK")
    else:
        print("Uso: python3 mathrelaxing_kit.py test [book_slug]")
        print("Libros:", list(BOOKS.keys()))
