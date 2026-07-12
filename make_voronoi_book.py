"""
make_voronoi_book.py  —  Voronoi Gardens (v2, rich mandalas)
=============================================================
Coloring book digital al estilo exacto de MathRelaxing:
  - Portada frontal (verde casa + mandala Voronoi dorado)
  - Front matter: Title / About this book / The mathematics
  - 50 disenos RICOS centrados (mandalas k-fold, phyllotaxis,
    rosetones concentricos, celulas organicas relajadas) — sin marco,
    con nombre + subtitulo de metodo + numero de pagina
  - Pagina CTA estilo casa
  - Bundle iPad + previews + video (via mathrelaxing_kit)

Uso:
  python3 make_voronoi_book.py sample     # portada + frontmatter + 4 disenos -> /tmp/vor_sample/
  python3 make_voronoi_book.py interior
  python3 make_voronoi_book.py cover
  python3 make_voronoi_book.py digital
  python3 make_voronoi_book.py ipad
  python3 make_voronoi_book.py previews
  python3 make_voronoi_book.py video
  python3 make_voronoi_book.py all
"""

import sys, os, math
sys.path.insert(0, "/var/www/mathrelaxing.store")
from mathrelaxing_kit import *           # fonts, colors, logo, kit_*, put_text
import numpy as np
from scipy.spatial import Voronoi

# Texto PDF correcto (fontname propio + caja alta). Reusa put_text del kit.
def T(page, x, y, w, text, font, size, color, align=1, lh=1.0):
    """Texto centrado-en-caja: x,y esquina; w ancho; alto auto = size*2.4."""
    put_text(page, fitz.Rect(x, y, x+w, y+size*2.4), text, font, size, color, align, lh)
def Tbox(page, x, y, w, h, text, font, size, color, align=0, lh=1.4):
    put_text(page, fitz.Rect(x, y, x+w, y+h), text, font, size, color, align, lh)

# ── Identidad del libro ───────────────────────────────────────────────────────
SLUG  = "voronoi_gardens"
NAME  = "VoronoiGardens"
TITLE_1, TITLE_2 = "VORONOI", "GARDENS"
TITLE = "Voronoi Gardens"
SUB_ITALIC = "A Coloring Book of Cellular Geometry"
SUB_SMALL  = "50 Voronoi Mandalas & Organic Tessellations"
OUT   = f"{DIGIT}/voronoi"
os.makedirs(OUT, exist_ok=True)

PW, PH = 612, 792          # US Letter en puntos
CX, CY = PW/2, PH*0.44     # centro de composicion de los disenos
RDISK  = 250               # radio del disco de diseno

# Colores casa (floats 0-1 para fitz)
C_BG    = (17/255, 34/255, 29/255)      # verde bosque portada
C_WHITE = (236/255, 229/255, 214/255)   # crema titulo
C_GOLD  = (195/255, 165/255, 108/255)
C_GOLD_HI = (0.85, 0.68, 0.32)
C_TEAL  = (0.40, 0.72, 0.74)
C_DIMGREEN = (0.16, 0.30, 0.26)
C_INK   = (0.12, 0.12, 0.12)            # texto interior negro suave
C_GRAY  = (0.35, 0.35, 0.35)
C_LGRAY = (0.60, 0.60, 0.60)

# Paleta swatches Procreate (30 colores naturaleza+matematica)
VORONOI_PALETTE = [
    (220,195,155),(190,150, 90),(160,110, 60),(230,170, 80),(200,130, 50),
    (100,190,200),( 60,145,185),( 80,205,180),( 40,125,160),(120,170,210),
    (145,205,125),(100,170, 90),( 60,140, 80),(185,225,140),( 80,160, 70),
    (165,130,205),(120, 85,185),(205,165,225),(145,105,195),(100, 70,160),
    (225,165, 85),(245,205, 75),( 85, 65,125),(205, 85, 65),(240,120,100),
    (225,215,205),(185,175,165),(245,235,215),(145,135,125),( 65, 85,125),
]


# ══════════════════════════════════════════════════════════════════════════════
# GEOMETRIA VORONOI
# ══════════════════════════════════════════════════════════════════════════════

def _disk_polygon(cx, cy, r, n=160):
    """Disco aproximado como n-gono CCW (para recorte convexo)."""
    return [(cx + r*math.cos(2*math.pi*i/n), cy + r*math.sin(2*math.pi*i/n))
            for i in range(n)]

def _clip_convex(subject, clip):
    """Sutherland-Hodgman: recorta poligono subject contra poligono convexo clip (CCW)."""
    def inside(p, a, b):
        return (b[0]-a[0])*(p[1]-a[1]) - (b[1]-a[1])*(p[0]-a[0]) >= -1e-9
    def inter(s, e, a, b):
        x1,y1=s; x2,y2=e; x3,y3=a; x4,y4=b
        den=(x1-x2)*(y3-y4)-(y1-y2)*(x3-x4)
        if abs(den)<1e-12: return e
        t=((x1-x3)*(y3-y4)-(y1-y3)*(x3-x4))/den
        return (x1+t*(x2-x1), y1+t*(y2-y1))
    out=subject
    for i in range(len(clip)):
        a=clip[i]; b=clip[(i+1)%len(clip)]
        inp=out; out=[]
        if not inp: break
        s=inp[-1]
        for e in inp:
            if inside(e,a,b):
                if not inside(s,a,b): out.append(inter(s,e,a,b))
                out.append(e)
            elif inside(s,a,b):
                out.append(inter(s,e,a,b))
            s=e
    return out

def _cell_polygons(pts, far_r, sym=0):
    """
    Poligonos de celda finitos para cada punto de pts.
    sym>0: los puntos espejo exteriores se reparten en multiplo de sym
           para PRESERVAR la simetria k-fold en las celdas del borde.
    """
    if sym and sym > 0:
        n_far = sym * max(3, round(48/sym))   # multiplo de sym, ~>=48
    else:
        n_far = 64
    mirrors = [(CX + far_r*math.cos(2*math.pi*i/n_far),
                CY + far_r*math.sin(2*math.pi*i/n_far)) for i in range(n_far)]
    allp = np.vstack([pts, mirrors])
    vor = Voronoi(allp)
    cells = []
    for i in range(len(pts)):
        reg = vor.regions[vor.point_region[i]]
        if not reg or -1 in reg:
            continue
        cells.append([tuple(vor.vertices[v]) for v in reg])
    return cells

def _centroid(poly):
    a=0; cx=0; cy=0
    for i in range(len(poly)):
        x1,y1=poly[i]; x2,y2=poly[(i+1)%len(poly)]
        cr=x1*y2-x2*y1; a+=cr; cx+=(x1+x2)*cr; cy+=(y1+y2)*cr
    if abs(a)<1e-9:
        xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
        return (sum(xs)/len(xs), sum(ys)/len(ys))
    a*=0.5
    return (cx/(6*a), cy/(6*a))

def _poly_area(poly):
    a=0
    for i in range(len(poly)):
        x1,y1=poly[i]; x2,y2=poly[(i+1)%len(poly)]
        a+=x1*y2-x2*y1
    return abs(a)/2


# ── Generadores de semillas (cada uno crea un patron distinto) ────────────────

def seeds_mandala(k, rings, seed, center=True):
    """
    Mandala k-fold CRISP: en cada anillo coloca semillas en fracciones fijas
    de la cuna fundamental (bisectriz / bordes), replicadas por rotacion.
    Los radios se calculan una vez por anillo => simetria k-fold exacta.
    """
    rng=np.random.default_rng(seed)
    wedge=2*math.pi/k
    pts=[]
    if center: pts.append((CX,CY))
    for ri in range(rings):
        r=RDISK*((ri+0.6)/(rings+0.5))**0.95
        rr=r*(1+rng.uniform(-0.015,0.015))      # jitter global del anillo (simetrico)
        # alterna entre bisectriz y bordes para dar textura, pero consistente
        fracs = [0.5] if ri%2==0 else [0.27, 0.73]
        if ri==rings-1: fracs=[0.18,0.5,0.82]    # anillo exterior mas denso
        for f in fracs:
            a0=f*wedge
            for j in range(k):
                a=a0+j*wedge
                pts.append((CX+rr*math.cos(a), CY+rr*math.sin(a)))
    return np.array(pts)

def seeds_rosewindow(k, rings, seed):
    """Rosetón concéntrico regular: k puntos por anillo, fase alterna."""
    rng=np.random.default_rng(seed)
    pts=[(CX,CY)]
    for ri in range(1,rings+1):
        r=RDISK*(ri/(rings+0.3))
        phase=(ri%2)*(math.pi/k)
        kk=k*(1 if ri<rings*0.6 else 2)   # mas densidad afuera
        for j in range(kk):
            a=phase+2*math.pi*j/kk
            pts.append((CX+r*math.cos(a), CY+r*math.sin(a)))
    return np.array(pts)

def seeds_phyllotaxis(n, seed, spread=None):
    """Espiral áurea (girasol): r=c*sqrt(i), θ=i*137.5°."""
    spread = spread or RDISK/math.sqrt(n)
    golden=math.radians(137.50776405)
    pts=[]
    for i in range(n):
        r=spread*math.sqrt(i)
        a=i*golden
        pts.append((CX+r*math.cos(a), CY+r*math.sin(a)))
    return np.array(pts)

def seeds_organic(n, seed, lloyd=3):
    """Células orgánicas: aleatorias dentro del disco + relajación de Lloyd."""
    rng=np.random.default_rng(seed)
    pts=[]
    while len(pts)<n:
        x=rng.uniform(-RDISK,RDISK); y=rng.uniform(-RDISK,RDISK)
        if x*x+y*y<=RDISK*RDISK*0.95:
            pts.append((CX+x,CY+y))
    pts=np.array(pts)
    disk=_disk_polygon(CX,CY,RDISK)
    for _ in range(lloyd):
        cells=_cell_polygons(pts, RDISK*3)
        newp=[]
        for poly in cells:
            c=_clip_convex(poly, disk)
            if len(c)>=3: newp.append(_centroid(c))
        if len(newp)>=3: pts=np.array(newp)
    return pts

def seeds_spiralarms(arms, n, seed):
    """Brazos espirales logarítmicos (galaxia)."""
    rng=np.random.default_rng(seed)
    pts=[(CX,CY)]
    per=max(1,n//arms)
    for arm in range(arms):
        a0=2*math.pi*arm/arms
        for i in range(per):
            t=i/per
            r=RDISK*t
            a=a0+t*3.0
            jit=rng.uniform(-0.06,0.06)
            pts.append((CX+r*math.cos(a+jit), CY+r*math.sin(a+jit)))
    return np.array(pts)


# ══════════════════════════════════════════════════════════════════════════════
# DEFINICION DE LOS 50 DISENOS  (nombre + metodo + generador)
# ══════════════════════════════════════════════════════════════════════════════

def _mk(name, method, fn, sym=0, lw=1.1):
    return {"name":name, "method":method, "fn":fn, "sym":sym, "lw":lw}

DESIGNS = [
    # ── Mandalas k-fold (1-14) ─ sym=k
    _mk("Sixfold Bloom",        "Voronoi Mandala \xb7 6-fold symmetry",  lambda s: seeds_mandala(6, 5, s),  sym=6),
    _mk("Eightfold Rosette",    "Voronoi Mandala \xb7 8-fold symmetry",  lambda s: seeds_mandala(8, 5, s),  sym=8),
    _mk("Fivefold Star",        "Voronoi Mandala \xb7 5-fold symmetry",  lambda s: seeds_mandala(5, 6, s),  sym=5),
    _mk("Twelvefold Cathedral", "Voronoi Mandala \xb7 12-fold symmetry", lambda s: seeds_mandala(12, 5, s), sym=12),
    _mk("Sevenfold Lotus",      "Voronoi Mandala \xb7 7-fold symmetry",  lambda s: seeds_mandala(7, 6, s),  sym=7),
    _mk("Tenfold Compass",      "Voronoi Mandala \xb7 10-fold symmetry", lambda s: seeds_mandala(10, 5, s), sym=10),
    _mk("Ninefold Wheel",       "Voronoi Mandala \xb7 9-fold symmetry",  lambda s: seeds_mandala(9, 6, s),  sym=9),
    _mk("Fourfold Crossing",    "Voronoi Mandala \xb7 4-fold symmetry",  lambda s: seeds_mandala(4, 6, s),  sym=4),
    _mk("Sixteenfold Halo",     "Voronoi Mandala \xb7 16-fold symmetry", lambda s: seeds_mandala(16, 4, s), sym=16),
    _mk("Sixfold Snowflake",    "Voronoi Mandala \xb7 6-fold symmetry",  lambda s: seeds_mandala(6, 7, s),  sym=6),
    _mk("Eightfold Mariner",    "Voronoi Mandala \xb7 8-fold symmetry",  lambda s: seeds_mandala(8, 6, s),  sym=8),
    _mk("Elevenfold Crown",     "Voronoi Mandala \xb7 11-fold symmetry", lambda s: seeds_mandala(11, 5, s), sym=11),
    _mk("Threefold Trefoil",    "Voronoi Mandala \xb7 3-fold symmetry",  lambda s: seeds_mandala(3, 7, s),  sym=3),
    _mk("Fourteenfold Sun",     "Voronoi Mandala \xb7 14-fold symmetry", lambda s: seeds_mandala(14, 5, s), sym=14),
    # ── Rosetones concentricos (15-22) ─ sym=k
    _mk("Rose Window I",        "Concentric Voronoi \xb7 radial rings",  lambda s: seeds_rosewindow(6, 5, s),  sym=6),
    _mk("Rose Window II",       "Concentric Voronoi \xb7 radial rings",  lambda s: seeds_rosewindow(8, 5, s),  sym=8),
    _mk("Rose Window III",      "Concentric Voronoi \xb7 radial rings",  lambda s: seeds_rosewindow(10, 6, s), sym=10),
    _mk("Gothic Oculus",        "Concentric Voronoi \xb7 radial rings",  lambda s: seeds_rosewindow(12, 5, s), sym=12),
    _mk("Solar Disc",           "Concentric Voronoi \xb7 radial rings",  lambda s: seeds_rosewindow(7, 6, s),  sym=7),
    _mk("Mosaic Wheel",         "Concentric Voronoi \xb7 radial rings",  lambda s: seeds_rosewindow(9, 5, s),  sym=9),
    _mk("Lunar Ring",           "Concentric Voronoi \xb7 radial rings",  lambda s: seeds_rosewindow(5, 6, s),  sym=5),
    _mk("Clockwork Mandala",    "Concentric Voronoi \xb7 radial rings",  lambda s: seeds_rosewindow(11, 5, s), sym=11),
    # ── Phyllotaxis / girasol (23-32) ─ sin simetria rotacional
    _mk("Sunflower Lattice",    "Phyllotaxis Voronoi \xb7 golden angle 137.5\xb0", lambda s: seeds_phyllotaxis(160, s)),
    _mk("Golden Spiral Field",  "Phyllotaxis Voronoi \xb7 golden angle 137.5\xb0", lambda s: seeds_phyllotaxis(220, s)),
    _mk("Seed Head",            "Phyllotaxis Voronoi \xb7 golden angle 137.5\xb0", lambda s: seeds_phyllotaxis(110, s)),
    _mk("Daisy Heart",          "Phyllotaxis Voronoi \xb7 golden angle 137.5\xb0", lambda s: seeds_phyllotaxis(190, s)),
    _mk("Pinecone Spiral",      "Phyllotaxis Voronoi \xb7 golden angle 137.5\xb0", lambda s: seeds_phyllotaxis(140, s)),
    _mk("Fibonacci Bloom",      "Phyllotaxis Voronoi \xb7 golden angle 137.5\xb0", lambda s: seeds_phyllotaxis(250, s)),
    _mk("Aster Field",          "Phyllotaxis Voronoi \xb7 golden angle 137.5\xb0", lambda s: seeds_phyllotaxis(175, s)),
    _mk("Dandelion Clock",      "Phyllotaxis Voronoi \xb7 golden angle 137.5\xb0", lambda s: seeds_phyllotaxis(130, s)),
    _mk("Chamomile Crown",      "Phyllotaxis Voronoi \xb7 golden angle 137.5\xb0", lambda s: seeds_phyllotaxis(205, s)),
    _mk("Helianthus",           "Phyllotaxis Voronoi \xb7 golden angle 137.5\xb0", lambda s: seeds_phyllotaxis(280, s)),
    # ── Brazos espirales (33-38) ─ sym=arms
    _mk("Spiral Galaxy",        "Logarithmic-spiral Voronoi \xb7 2 arms",  lambda s: seeds_spiralarms(2, 150, s), sym=2),
    _mk("Triple Vortex",        "Logarithmic-spiral Voronoi \xb7 3 arms",  lambda s: seeds_spiralarms(3, 160, s), sym=3),
    _mk("Pinwheel",             "Logarithmic-spiral Voronoi \xb7 4 arms",  lambda s: seeds_spiralarms(4, 170, s), sym=4),
    _mk("Catherine Wheel",      "Logarithmic-spiral Voronoi \xb7 5 arms",  lambda s: seeds_spiralarms(5, 180, s), sym=5),
    _mk("Whirlpool",            "Logarithmic-spiral Voronoi \xb7 2 arms",  lambda s: seeds_spiralarms(2, 200, s), sym=2),
    _mk("Nautilus Arms",        "Logarithmic-spiral Voronoi \xb7 6 arms",  lambda s: seeds_spiralarms(6, 190, s), sym=6),
    # ── Celulas organicas (39-50) ─ sin simetria
    _mk("Cellular Garden",      "Lloyd-relaxed Voronoi \xb7 organic cells", lambda s: seeds_organic(90, s)),
    _mk("Honeycomb Drift",      "Lloyd-relaxed Voronoi \xb7 organic cells", lambda s: seeds_organic(120, s)),
    _mk("Soap Bubbles",         "Lloyd-relaxed Voronoi \xb7 organic cells", lambda s: seeds_organic(70, s)),
    _mk("Leaf Venation",        "Lloyd-relaxed Voronoi \xb7 organic cells", lambda s: seeds_organic(150, s)),
    _mk("Dragonfly Wing",       "Lloyd-relaxed Voronoi \xb7 organic cells", lambda s: seeds_organic(100, s)),
    _mk("Giraffe Coat",         "Lloyd-relaxed Voronoi \xb7 organic cells", lambda s: seeds_organic(60, s)),
    _mk("Cracked Earth",        "Lloyd-relaxed Voronoi \xb7 organic cells", lambda s: seeds_organic(80, s)),
    _mk("Stone Mosaic",         "Lloyd-relaxed Voronoi \xb7 organic cells", lambda s: seeds_organic(110, s)),
    _mk("Tortoise Shell",       "Lloyd-relaxed Voronoi \xb7 organic cells", lambda s: seeds_organic(85, s)),
    _mk("Coral Polyps",         "Lloyd-relaxed Voronoi \xb7 organic cells", lambda s: seeds_organic(130, s)),
    _mk("River Delta",          "Lloyd-relaxed Voronoi \xb7 organic cells", lambda s: seeds_organic(95, s)),
    _mk("Frost Pane",           "Lloyd-relaxed Voronoi \xb7 organic cells", lambda s: seeds_organic(140, s)),
]
assert len(DESIGNS)==50, len(DESIGNS)


# ══════════════════════════════════════════════════════════════════════════════
# RENDER DE UN DISENO
# ══════════════════════════════════════════════════════════════════════════════

def draw_design(page, cfg, number, seed):
    pts = cfg["fn"](seed)
    disk = _disk_polygon(CX, CY, RDISK)
    cells = _cell_polygons(pts, RDISK*3, sym=cfg.get("sym", 0))

    sh = page.new_shape()
    for poly in cells:
        c = _clip_convex(poly, disk)
        if len(c) < 3:
            continue
        sh.draw_polyline([fitz.Point(*p) for p in c] + [fitz.Point(*c[0])])
    sh.finish(color=C_INK, width=cfg["lw"], closePath=False)
    sh.commit()

    # Circulo exterior
    oc=page.new_shape()
    oc.draw_circle(fitz.Point(CX,CY), RDISK)
    oc.finish(color=C_INK, width=cfg["lw"]*1.2)
    oc.commit()

    # Nombre + metodo + numero (estilo casa, Cinzel small-caps)
    T(page, 40, PH*0.875, PW-80, f"{number}. {cfg['name']}", CINZEL, 15, C_INK, align=1)
    T(page, 40, PH*0.918, PW-80, cfg["method"],             RALEWAY_IT, 9.5, C_GRAY, align=1)
    T(page, PW-70, PH-24, 40, str(number),                  RALEWAY, 8.5, C_LGRAY, align=1)


# ══════════════════════════════════════════════════════════════════════════════
# FRONT MATTER (estilo casa: blanco, Cinzel negro)
# ══════════════════════════════════════════════════════════════════════════════

def page_title(doc):
    pg=doc.new_page(width=PW,height=PH)
    T(pg, 40, PH*0.30,      PW-80, TITLE_1, CINZEL, 52, C_INK, align=1)
    T(pg, 40, PH*0.30+66,   PW-80, TITLE_2, CINZEL, 52, C_INK, align=1)
    # regla dorada fina
    sh=pg.new_shape(); sh.draw_line((PW/2-70,PH*0.46),(PW/2+70,PH*0.46))
    sh.finish(color=C_GOLD_HI,width=0.8); sh.commit()
    T(pg, 60, PH*0.50, PW-120, SUB_ITALIC, RALEWAY_IT, 17, C_GRAY, align=1)
    T(pg, 60, PH*0.555, PW-120, f"{SUB_SMALL}  \xb7  MathRelaxing", RALEWAY, 11, C_LGRAY, align=1)

def page_about(doc):
    pg=doc.new_page(width=PW,height=PH); L=70
    T(pg, L, 90, PW-2*L, "About this book", CINZEL, 24, C_INK, align=0)
    body=("Every page in this book begins with nothing but a scatter of points. "
          "From each point grows a cell \xb7 the region of space closer to that "
          "point than to any other. Together these cells lock into a Voronoi "
          "diagram: the same hidden geometry that shapes honeycombs, dragonfly "
          "wings, cracked riverbeds and the seeds of a sunflower.\n\n"
          "Fifty unique designs await \xb7 radial mandalas, golden-angle spirals, "
          "cathedral rose windows and softly relaxed organic cells. Each is drawn "
          "as clean line art, every cell a closed region ready for your colour.")
    Tbox(pg, L, 148, PW-2*L, 210, body, RALEWAY, 11, (0.2,0.2,0.2), align=0, lh=1.5)
    Tbox(pg, L, 400, PW-2*L, 28, "How to colour:", RALEWAY, 11.5, C_INK, align=0, lh=1.2)
    tips=("   -  Any pens, pencils or markers work beautifully.\n"
          "   -  Colour each cell on its own, or blend across neighbours.\n"
          "   -  Work from the centre outward to watch the pattern bloom.\n"
          "   -  On an iPad, drop the artwork into GoodNotes or Procreate.")
    Tbox(pg, L, 430, PW-2*L, 120, tips, RALEWAY, 10.5, (0.2,0.2,0.2), align=0, lh=1.6)
    Tbox(pg, L, 562, PW-2*L, 26, "Enjoy the quiet geometry of growth.",
         RALEWAY_IT, 10.5, C_GRAY, align=0, lh=1.2)

def page_math(doc):
    pg=doc.new_page(width=PW,height=PH); L=70
    T(pg, L, 90, PW-2*L, "The mathematics", CINZEL, 24, C_INK, align=0)
    paras=[
      ("A Voronoi diagram is built from a set of seed points. For every location "
       "on the page we ask a single question: which seed is nearest? All the points "
       "that answer with the same seed form that seed's cell. The cell walls fall "
       "exactly halfway between neighbouring seeds."),
      ("Where the seeds sit decides everything. Place them with k-fold rotational "
       "symmetry and a mandala appears. Place them along the golden angle of 137.5\xb0 "
       "and you recreate the spiral packing of a sunflower head. Scatter them at "
       "random, then nudge each seed toward the centre of its own cell \xb7 a step "
       "called Lloyd's relaxation \xb7 and the mesh softens into organic, bubble-like tissue."),
      ("The dual of a Voronoi diagram is the Delaunay triangulation, and the two "
       "appear throughout nature and science: in crystal grains, foam, cellular "
       "biology, mesh generation and the territories of nesting birds."),
    ]
    y=150
    for p in paras:
        Tbox(pg, L, y, PW-2*L, 160, p, RALEWAY, 11, (0.2,0.2,0.2), align=0, lh=1.5); y+=120
    Tbox(pg, L, y+6, PW-2*L, 26, "Turn the page \xb7 fifty gardens of points are waiting to grow.",
         RALEWAY_IT, 10.5, C_GRAY, align=0, lh=1.2)


# ══════════════════════════════════════════════════════════════════════════════
# CTA estilo casa (rosa + lissajous, footer completo)
# ══════════════════════════════════════════════════════════════════════════════

def _rose(page,cx,cy,r,k,color,steps=2000,w=1.1):
    pts=[(cx+r*math.cos(k*2*math.pi*i/steps)*math.cos(2*math.pi*i/steps),
          cy+r*math.cos(k*2*math.pi*i/steps)*math.sin(2*math.pi*i/steps)) for i in range(steps+1)]
    sh=page.new_shape(); sh.draw_polyline(pts); sh.finish(color=color,width=w,closePath=False); sh.commit()

def _voronoi_motif(page,cx,cy,color,seed=7):
    """Pequeno mandala Voronoi dorado para CTA/portada."""
    global CX,CY,RDISK
    oldcx,oldcy,oldr=CX,CY,RDISK
    CX,CY,RDISK=cx,cy,150
    pts=seeds_mandala(8,4,seed)
    disk=_disk_polygon(cx,cy,RDISK)
    cells=_cell_polygons(pts,RDISK*3)
    sh=page.new_shape()
    for poly in cells:
        c=_clip_convex(poly,disk)
        if len(c)>=3:
            sh.draw_polyline([fitz.Point(*p) for p in c]+[fitz.Point(*c[0])])
    sh.finish(color=color,width=0.9,closePath=False); sh.commit()
    oc=page.new_shape(); oc.draw_circle(fitz.Point(cx,cy),RDISK); oc.finish(color=color,width=1.1); oc.commit()
    CX,CY,RDISK=oldcx,oldcy,oldr

def page_cta(doc):
    pg=doc.new_page(width=PW,height=PH)
    BG=(0.07,0.09,0.18); GOLD=C_GOLD_HI; WHITE=(1,1,1); DIM=(0.50,0.57,0.70)
    GOLD2=(0.55,0.42,0.14); LIGHT=(0.78,0.85,0.95); DIMMER=(0.30,0.36,0.52)
    pg.draw_rect(pg.rect,color=None,fill=BG)
    cx,cy=PW/2,PH*0.375
    sh=pg.new_shape()
    for rad in (188,162,136,110): sh.draw_circle((cx,cy),rad)
    sh.finish(color=(0.15,0.22,0.40),width=0.5); sh.commit()
    _voronoi_motif(pg,cx,cy,GOLD,seed=11)
    # logo
    lw,lh=108,78; lt=PH*0.672
    pg.insert_image(fitz.Rect(cx-lw/2,lt,cx+lw/2,lt+lh),filename=LOGO,keep_proportion=True)
    def line(y,t,f,s,col,pad=40):
        put_text(pg,fitz.Rect(pad,y,PW-pad,y+s*2.2),t,f,s,col,align=1,lineheight=1.0)
    ry=PH*0.795
    sh=pg.new_shape(); sh.draw_line((50,ry),(PW-50,ry)); sh.finish(color=GOLD,width=0.9)
    sh.draw_line((60,ry+4),(PW-60,ry+4)); sh.finish(color=DIMMER,width=0.35); sh.commit()
    y=ry+18
    line(y,"Thank you for coloring!",CINZEL,15,WHITE); y+=27
    line(y,"We hope you enjoyed every cell and seed.",RALEWAY_IT,8.5,DIM,pad=60); y+=24
    line(y,"mathrelaxing.store",CINZEL,13.5,GOLD); y+=23
    sh=pg.new_shape(); sh.draw_line((cx-90,y),(cx+90,y)); sh.finish(color=GOLD2,width=0.35); sh.commit(); y+=11
    line(y,"Shop on Etsy:  etsy.com/shop/themathrelaxing",RALEWAY,8.0,LIGHT,pad=50); y+=17
    line(y,"YouTube  \xb7  Pinterest  \xb7  TikTok  \xb7  Instagram    @MathRelaxing",RALEWAY,7.5,DIM); y+=18
    line(y,"\xa9 MathRelaxing  \xb7  For personal use only. Not for redistribution or commercial use.",RALEWAY,6.0,DIMMER)


# ══════════════════════════════════════════════════════════════════════════════
# PORTADA FRONTAL (verde casa + mandala dorado)
# ══════════════════════════════════════════════════════════════════════════════

def build_cover():
    print("Portada...")
    doc=fitz.open(); pg=doc.new_page(width=PW,height=PH)
    pg.draw_rect(pg.rect,color=None,fill=C_BG)
    # 2 circulos guia muy sutiles
    sh=pg.new_shape()
    for rad in (188,168): sh.draw_circle((PW/2,PH*0.47),rad)
    sh.finish(color=C_DIMGREEN,width=0.4); sh.commit()
    # mandala dorado hero
    _voronoi_motif(pg,PW/2,PH*0.47,C_GOLD,seed=3)
    # titulo (cajas altas)
    T(pg, 30, PH*0.085,    PW-60, TITLE_1, CINZEL, 48, C_WHITE, align=1)
    T(pg, 30, PH*0.085+58, PW-60, TITLE_2, CINZEL, 48, C_GOLD,  align=1)
    # subtitulos abajo
    T(pg, 50, PH*0.76, PW-100, SUB_ITALIC, RALEWAY_IT, 16, C_WHITE, align=1)
    T(pg, 50, PH*0.815, PW-100, SUB_SMALL, RALEWAY, 12, C_GOLD, align=1)
    # logo + url
    lw,lh=96,70; lt=PH*0.875
    pg.insert_image(fitz.Rect(PW/2-lw/2,lt,PW/2+lw/2,lt+lh),filename=LOGO,keep_proportion=True)
    T(pg, 30, PH*0.955, PW-60, "mathrelaxing.store", CINZEL, 11, C_GOLD, align=1)
    out=f"{OUT}/{NAME}_cover.pdf"; doc.save(out); doc.close()
    print(f"  {out}")
    return out


# ══════════════════════════════════════════════════════════════════════════════
# INTERIOR (frontmatter + 50 disenos)
# ══════════════════════════════════════════════════════════════════════════════

def build_interior():
    print("Interior (3 frontmatter + 50 disenos)...")
    doc=fitz.open()
    page_title(doc); page_about(doc); page_math(doc)
    for i,cfg in enumerate(DESIGNS):
        pg=doc.new_page(width=PW,height=PH)
        draw_design(pg, cfg, i+1, seed=1000+i*7)
        if (i+1)%10==0: print(f"  diseno {i+1}/50")
    out=f"{OUT}/{NAME}_interior.pdf"
    doc.save(out,deflate=True,garbage=4); doc.close()
    print(f"  {out} ({os.path.getsize(out)/1024/1024:.1f} MB, {3+50} pags)")
    return out

def build_digital():
    print("PDF digital (cover + interior + CTA)...")
    cover=fitz.open(f"{OUT}/{NAME}_cover.pdf")
    interior=fitz.open(f"{OUT}/{NAME}_interior.pdf")
    final=fitz.open()
    final.insert_pdf(cover); final.insert_pdf(interior)
    page_cta(final)   # CTA como ultima pagina del mismo doc
    out=f"{OUT}/{NAME}_digital.pdf"
    final.save(out,deflate=True,garbage=4); final.close()
    print(f"  {out} ({os.path.getsize(out)/1024/1024:.1f} MB)")
    return out


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRO EN BOOKS + bundle iPad / previews / video (via kit)
# ══════════════════════════════════════════════════════════════════════════════

def register_book():
    BOOKS[SLUG]={
        "cover":f"{OUT}/{NAME}_cover.pdf",
        "interior":f"{OUT}/{NAME}_interior.pdf",
        "audio":f"{DL}/fractal-flora-coloring-book/promo.mp4",
        "title":TITLE,"subtitle":SUB_SMALL,"motif":"geometric",
        "design_from":3,"design_to":52,   # saltar las 3 frontmatter
        "fix_isbn":False,"out_dir":OUT,"name":NAME,"type":"low_poly",
    }

# paginas ricas para video/previews (indices 0-based en interior: 3+n)
VID1, VID2 = 3+22, 3+0      # Sunflower Lattice, Sixfold Bloom

def build_ipad():
    register_book(); print("Bundle iPad...")
    build_hyperlinked_pdf(SLUG)
    build_transparent_pngs(SLUG,dpi=300)
    build_swatches(VORONOI_PALETTE,SLUG)
    build_guide(SLUG,
        goodnotes_text=("Open the PDF and tap any thumbnail in the index to jump straight to that "
            "design. Colour directly on top of the Voronoi cells with any brush. Each cell is a "
            "closed region, so fill them one at a time for a luminous stained-glass effect."),
        procreate_text=("Import a transparent PNG onto a new canvas. The cell outlines sit on their "
            "own layer, so paint underneath and every stroke stays within the lines. Load the "
            "included 30-colour palette for tones that harmonise across all fifty designs."),
        note_text=("A Voronoi cell holds every point closer to its own seed than to any other \xb7 "
            "the quiet rule behind honeycombs, leaves and cracked earth. No two designs repeat. "
            "Colour as slowly as you like."))
    build_packages(SLUG)
    print("  iPad OK")

def build_previews():
    register_book(); print("Previews...")
    make_preview_hero(SLUG, VID1, PAL_WARM)
    make_preview_included(SLUG,[
        "50 unique Voronoi mandala & cell designs",
        "Hyperlinked PDF index for GoodNotes & Notability",
        "50 transparent PNGs (300 dpi) for Procreate",
        "Procreate palette  \xb7  30 curated swatches",
        "'How to use on iPad' quick guide",
        "Instant download  \xb7  personal use",
    ])
    make_preview_twoways(SLUG, VID2, PAL_COOL)
    print("  previews OK")

def build_video():
    register_book(); print("Video...")
    animate_coloring_video(SLUG,
        designs=[(VID1,PAL_WARM,"low_poly"),(VID2,PAL_COOL,"low_poly")],
        out_path=f"{OUT}/{NAME}_iPad_promo.mp4")


# ══════════════════════════════════════════════════════════════════════════════
# SAMPLE (preview rapido antes de generar todo)
# ══════════════════════════════════════════════════════════════════════════════

def build_sample():
    """Genera portada + 3 frontmatter + 4 disenos variados -> /tmp/vor_sample/*.png"""
    import tempfile
    sd="/tmp/vor_sample"; os.makedirs(sd,exist_ok=True)
    print("SAMPLE -> /tmp/vor_sample/")
    # cover
    build_cover()
    def render(pdf,idx,name,zoom=1.5):
        d=fitz.open(pdf); p=d[idx]
        p.get_pixmap(matrix=fitz.Matrix(zoom,zoom)).save(f"{sd}/{name}.png"); d.close()
    render(f"{OUT}/{NAME}_cover.pdf",0,"00_cover")
    # frontmatter
    doc=fitz.open(); page_title(doc); page_about(doc); page_math(doc)
    doc.save(f"{sd}/_fm.pdf"); doc.close()
    render(f"{sd}/_fm.pdf",0,"01_title")
    render(f"{sd}/_fm.pdf",1,"02_about")
    render(f"{sd}/_fm.pdf",2,"03_math")
    # 4 disenos variados: mandala, rosewindow, phyllotaxis, organic
    picks=[(0,"04_mandala"),(14,"05_rosewindow"),(22,"06_phyllotaxis"),(38,"07_organic")]
    for di,(idx,nm) in enumerate(picks):
        doc=fitz.open(); pg=doc.new_page(width=PW,height=PH)
        draw_design(pg,DESIGNS[idx],idx+1,seed=1000+idx*7)
        doc.save(f"{sd}/_d.pdf"); doc.close()
        render(f"{sd}/_d.pdf",0,nm)
        print(f"  {nm}: {DESIGNS[idx]['name']}")
    print("Sample listo.")


if __name__=="__main__":
    cmd=sys.argv[1] if len(sys.argv)>1 else "sample"
    if cmd=="sample":   build_sample()
    elif cmd=="interior": build_interior()
    elif cmd=="cover":    build_cover()
    elif cmd=="digital":  build_interior(); build_cover(); build_digital()
    elif cmd=="ipad":     build_ipad()
    elif cmd=="previews": build_previews()
    elif cmd=="video":    build_video()
    elif cmd=="all":
        build_interior(); build_cover(); build_digital()
        build_ipad(); build_previews(); build_video()
    print("Done.")
