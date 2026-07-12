"""
make_stem_notebook.py — MathRelaxing STEM Notebook (GoodNotes hyperlinked)
==========================================================================
Cuaderno digital para iPad (GoodNotes/Notability): landscape 4:3, con pestañas
laterales hipervinculadas (GOTO) y grids que la audiencia STEM realmente usa:
dot, graph, hexagonal (química), isométrico (ingeniería), Cornell, polar, rayado.

Estrategia: dibujar el grid a sangre completa y luego TAPAR márgenes/cabecera/
pestañas con blanco — evita recortar líneas a mano.

Uso:
  python3 make_stem_notebook.py sample   # portada+índice+grids -> /tmp/stem_sample/
  python3 make_stem_notebook.py full     # cuaderno completo (varias págs por sección)
"""
import sys, os, math
sys.path.insert(0, "/var/www/mathrelaxing.store")
from mathrelaxing_kit import put_text, CINZEL, RALEWAY, RALEWAY_IT, LOGO
import fitz

OUT = "/var/www/mathrelaxing.store/static/downloads/digital/stem_notebook"
os.makedirs(OUT, exist_ok=True)

# ── Lienzo landscape 4:3 (estándar GoodNotes) ─────────────────────────────────
W, H = 1280, 960
TOP = 76                      # banda cabecera
BOT = 44
LEFT = 54
TABW = 116                    # ancho franja de pestañas (derecha)
X0, Y0, X1, Y1 = LEFT, TOP, W-TABW-16, H-BOT     # área de contenido (grid)

# ── Colores (fitz floats) ─────────────────────────────────────────────────────
NAVY=(0.07,0.09,0.18); GOLD=(0.83,0.66,0.30); INK=(0.13,0.13,0.16)
GRID=(0.80,0.83,0.88); GRIDB=(0.64,0.69,0.78)
TABBG=(0.14,0.18,0.31); TABTXT=(0.80,0.84,0.92); ACT=(0.83,0.66,0.30); ACTTXT=(0.07,0.09,0.18)
WHITE=(1,1,1); TEAL=(0.30,0.62,0.62); DIM=(0.55,0.58,0.66)

def T(pg,x,y,w,t,f,s,c,align=0,h=None):
    put_text(pg, fitz.Rect(x,y,x+w,y+(h or s*2.2)), t, f, s, c, align=align, lineheight=1.0)

def rect(pg,x0,y0,x1,y1,fill,color=None,width=0):
    sh=pg.new_shape(); sh.draw_rect(fitz.Rect(x0,y0,x1,y1))
    sh.finish(color=color,fill=fill,width=width); sh.commit()

def chevron(pg,x,y,s,color):
    """Chevron '›' dibujado (Raleway no tiene la flecha →)."""
    sh=pg.new_shape()
    sh.draw_line((x,y-s),(x+s*0.75,y)); sh.draw_line((x+s*0.75,y),(x,y+s))
    sh.finish(color=color,width=1.4); sh.commit()

# ── Secciones del cuaderno (label corto pestaña, nombre, tipo de grid) ─────────
SECTIONS = [
    ("Index",   "Contents",              "index"),
    ("Dot",     "Dot Grid",              "dot"),
    ("Graph",   "Graph \xb7 Quad Ruled", "graph"),
    ("Hex",     "Hexagonal \xb7 Chemistry","hex"),
    ("Iso",     "Isometric \xb7 3D",     "iso"),
    ("Cornell", "Cornell Notes",         "cornell"),
    ("Polar",   "Polar Grid",            "polar"),
    ("Lined",   "Lined \xb7 Ruled",      "lined"),
]

# ── Grids (dibujan a sangre; luego se enmascara) ──────────────────────────────
def g_dot(pg, s=26):
    sh=pg.new_shape()
    y=0
    while y<H+s:
        x=0
        while x<W+s:
            sh.draw_circle(fitz.Point(x,y),1.4); x+=s
        y+=s
    sh.finish(color=None, fill=GRID, width=0)
    sh.commit()

def g_graph(pg, s=26):
    sh=pg.new_shape(); x=0
    while x<W+s: sh.draw_line((x,0),(x,H)); x+=s
    y=0
    while y<H+s: sh.draw_line((0,y),(W,y)); y+=s
    sh.finish(color=GRID,width=0.6); sh.commit()
    # líneas guía cada 5
    sh=pg.new_shape(); x=0; i=0
    while x<W+s:
        if i%5==0: sh.draw_line((x,0),(x,H))
        x+=s; i+=1
    y=0; i=0
    while y<H+s:
        if i%5==0: sh.draw_line((0,y),(W,y))
        y+=s; i+=1
    sh.finish(color=GRIDB,width=0.8); sh.commit()

def g_lined(pg, s=30):
    sh=pg.new_shape(); y=0
    while y<H+s: sh.draw_line((0,y),(W,y)); y+=s
    sh.finish(color=GRID,width=0.7); sh.commit()

def g_hex(pg, size=22):
    # hexágonos flat-top a sangre
    dx=1.5*size; dy=math.sqrt(3)*size
    sh=pg.new_shape(); col=0; x=-size
    while x<W+size:
        yoff=0 if col%2==0 else dy/2
        y=-size+yoff
        while y<H+size:
            pts=[(x+size*math.cos(math.radians(60*k)), y+size*math.sin(math.radians(60*k))) for k in range(6)]
            sh.draw_polyline([fitz.Point(*p) for p in pts]+[fitz.Point(*pts[0])])
            y+=dy
        x+=dx; col+=1
    sh.finish(color=GRID,width=0.7,closePath=False); sh.commit()

def g_iso(pg, s=30):
    # tres familias: vertical, +30°, -30°
    sh=pg.new_shape()
    x=0
    while x<W+s: sh.draw_line((x,0),(x,H)); x+=s   # verticales
    sh.finish(color=GRID,width=0.5); sh.commit()
    t30=math.tan(math.radians(30)); span=s/math.cos(math.radians(30))
    sh=pg.new_shape()
    # +30°: y = t30*x + b
    b=-W*t30
    while b<H+W*t30:
        sh.draw_line((0,b),(W, b+W*t30)); b+=span
    sh.finish(color=GRID,width=0.5); sh.commit()
    sh=pg.new_shape()
    b=0
    while b<H+W*t30:
        sh.draw_line((0,b),(W, b-W*t30)); b+=span
    sh.finish(color=GRID,width=0.5); sh.commit()

def g_polar(pg):
    cx,cy=(X0+X1)/2,(Y0+Y1)/2; R=min(X1-X0,Y1-Y0)/2-6
    sh=pg.new_shape()
    r=R; rings=10
    for i in range(1,rings+1): sh.draw_circle(fitz.Point(cx,cy),R*i/rings)
    sh.finish(color=GRID,width=0.6); sh.commit()
    sh=pg.new_shape()
    for a in range(0,360,15):
        sh.draw_line((cx,cy),(cx+R*math.cos(math.radians(a)), cy+R*math.sin(math.radians(a))))
    sh.finish(color=GRID,width=0.5); sh.commit()

def g_cornell(pg):
    cue=X0+(X1-X0)*0.24; summ=Y1-(Y1-Y0)*0.16
    # rayado en zona de notas
    sh=pg.new_shape(); y=Y0+34
    while y<summ:
        sh.draw_line((X0,y),(X1,y)); y+=30
    sh.finish(color=GRID,width=0.6); sh.commit()
    sh=pg.new_shape()
    sh.draw_line((cue,Y0),(cue,summ))          # columna cue
    sh.draw_line((X0,summ),(X1,summ))          # línea resumen
    sh.finish(color=GRIDB,width=1.0); sh.commit()
    put_text(pg, fitz.Rect(X0+6,Y0+6,cue-6,Y0+24),"CUE",RALEWAY,9,DIM,align=0)
    put_text(pg, fitz.Rect(X0+6,summ+6,X1,summ+24),"SUMMARY",RALEWAY,9,DIM,align=0)

GRIDS={"dot":g_dot,"graph":g_graph,"hex":g_hex,"iso":g_iso,"polar":g_polar,
       "cornell":g_cornell,"lined":g_lined}

# ── Enmascarar márgenes + cabecera + franja pestañas ──────────────────────────
def mask(pg):
    rect(pg,0,0,W,TOP,WHITE)               # cabecera
    rect(pg,X1+1,0,W,H,WHITE)              # franja derecha (pestañas)
    rect(pg,0,Y1+1,W,H,WHITE)             # pie
    rect(pg,0,0,X0-1,H,WHITE)             # margen izq
    # marco sutil del área
    rect(pg,X0,Y0,X1,Y1,None,color=(0.85,0.87,0.91),width=1.0)

# ── Cabecera ──────────────────────────────────────────────────────────────────
def header(pg, title):
    lw=64; lh=int(lw*575/800)    # logo pequeño que cabe en la banda de cabecera
    pg.insert_image(fitz.Rect(LEFT,14,LEFT+lw,14+lh),filename=LOGO,keep_proportion=True)
    T(pg, LEFT+lw+14, 24, 500, title, CINZEL, 17, INK, align=0)
    put_text(pg, fitz.Rect(X1-260,28,X1,46),"mathrelaxing.store",RALEWAY,9,DIM,align=2)
    sh=pg.new_shape(); sh.draw_line((LEFT,TOP-10),(X1,TOP-10)); sh.finish(color=GOLD,width=0.8); sh.commit()

# ── Pestañas laterales con links GOTO ─────────────────────────────────────────
def tabs(pg, active_idx, targets):
    n=len(SECTIONS); pad=TOP; av=H-TOP-BOT
    th=av/n
    tx0=X1+22; tx1=W-14
    for i,(label,_,_) in enumerate(SECTIONS):
        ty0=pad+i*th+4; ty1=pad+(i+1)*th-4
        on = (i==active_idx)
        sh=pg.new_shape(); sh.draw_rect(fitz.Rect(tx0,ty0,tx1+6,ty1))
        sh.finish(color=None, fill=ACT if on else TABBG, width=0); sh.commit()
        put_text(pg, fitz.Rect(tx0,(ty0+ty1)/2-8,tx1,(ty0+ty1)/2+10), label,
                 RALEWAY, 11, ACTTXT if on else TABTXT, align=1)
        # link a la primera página de esa sección
        pg.insert_link({"kind":fitz.LINK_GOTO,"from":fitz.Rect(tx0,ty0,tx1+6,ty1),
                        "page":targets[i],"to":fitz.Point(0,0)})

# ── Páginas especiales ────────────────────────────────────────────────────────
def page_cover(pg):
    rect(pg,0,0,W,H,NAVY)
    # puntos sutiles
    sh=pg.new_shape()
    for x in range(0,W,40):
        for y in range(0,H,40): sh.draw_circle(fitz.Point(x,y),1.0)
    sh.finish(color=None,fill=(0.11,0.14,0.24),width=0); sh.commit()
    # hex motif dorado a la derecha
    sh=pg.new_shape(); cx,cy,size=W*0.74,H*0.5,40
    for ring in range(4):
        for k in range(6):
            ang=math.radians(60*k); rx=cx+ring*1.5*size*math.cos(ang); ry=cy+ring*math.sqrt(3)*size*math.sin(ang)
            pts=[(rx+size*math.cos(math.radians(60*j)),ry+size*math.sin(math.radians(60*j))) for j in range(6)]
            sh.draw_polyline([fitz.Point(*p) for p in pts]+[fitz.Point(*pts[0])])
    sh.finish(color=GOLD,width=0.8,closePath=False); sh.commit()
    T(pg, 90, H*0.30, 620, "STEM", CINZEL, 64, WHITE, align=0)
    T(pg, 90, H*0.30+78, 620, "NOTEBOOK", CINZEL, 64, GOLD, align=0)
    T(pg, 92, H*0.56, 640, "Hyperlinked digital notebook for GoodNotes & Notability",
      RALEWAY_IT, 18, (0.80,0.84,0.92), align=0)
    T(pg, 92, H*0.62, 640, "Dot \xb7 Graph \xb7 Hexagonal \xb7 Isometric \xb7 Cornell \xb7 Polar \xb7 Lined",
      RALEWAY, 13, TEAL, align=0)
    lw=150; lh=int(lw*575/800)
    pg.insert_image(fitz.Rect(90,H-120,90+lh,H-120+lh),filename=LOGO,keep_proportion=True)
    T(pg, 90+lh+10, H-92, 400, "mathrelaxing.store", CINZEL, 13, GOLD, align=0)

def page_index(pg, targets):
    rect(pg,0,0,W,H,WHITE)
    header(pg,"Contents")
    rows=SECTIONS[1:]   # excluye Index
    y=TOP+26; rh=(Y1-y)/len(rows)
    for j,(label,name,_) in enumerate(rows):
        ry=y+j*rh
        sh=pg.new_shape(); sh.draw_rect(fitz.Rect(X0,ry+6,X1,ry+rh-6))
        sh.finish(color=None,fill=(0.97,0.97,0.98),width=0); sh.commit()
        # número dorado
        sh=pg.new_shape(); sh.draw_circle(fitz.Point(X0+30,ry+rh/2),14); sh.finish(color=None,fill=GOLD,width=0); sh.commit()
        put_text(pg, fitz.Rect(X0+16,ry+rh/2-9,X0+44,ry+rh/2+9),str(j+1),RALEWAY,12,NAVY,align=1)
        T(pg, X0+60, ry+rh/2-12, 400, name, CINZEL, 16, INK, align=0)
        put_text(pg, fitz.Rect(X1-120,ry+rh/2-9,X1-30,ry+rh/2+9),"open",RALEWAY,10,TEAL,align=2)
        chevron(pg, X1-22, ry+rh/2, 4.5, TEAL)
        pg.insert_link({"kind":fitz.LINK_GOTO,"from":fitz.Rect(X0,ry+6,X1,ry+rh-6),
                        "page":targets[j+1],"to":fitz.Point(0,0)})
    tabs(pg, 0, targets)

def page_grid(pg, sec_idx, targets):
    label,name,kind=SECTIONS[sec_idx]
    rect(pg,0,0,W,H,WHITE)
    if kind in GRIDS: GRIDS[kind](pg)
    mask(pg); header(pg,name); tabs(pg, sec_idx, targets)
    return pg

# ── Build ─────────────────────────────────────────────────────────────────────
def build(pages_per_section=1, out_name="STEM_Notebook_sample"):
    doc=fitz.open()
    # page index destino de cada sección (0=cover, 1=index, luego grids)
    targets=[]; idx=1
    for si,(label,name,kind) in enumerate(SECTIONS):
        targets.append(idx)
        idx += 1 if si==0 else pages_per_section
    total = 2 + (len(SECTIONS)-1)*pages_per_section   # cover + index + grids
    for _ in range(total): doc.new_page(width=W,height=H)
    # rellenar (todas las páginas ya existen -> los links GOTO son válidos)
    page_cover(doc[0])
    page_index(doc[1], targets)
    pi=2
    for si in range(1,len(SECTIONS)):
        for _ in range(pages_per_section):
            page_grid(doc[pi], si, targets); pi+=1
    out=f"{OUT}/{out_name}.pdf"
    doc.save(out, deflate=True, garbage=4); doc.close()
    print(f"  {out} ({os.path.getsize(out)/1024/1024:.1f} MB, {total} págs)")
    return out

def build_sample():
    print("Sample STEM Notebook...")
    pdf=build(pages_per_section=1, out_name="STEM_Notebook_sample")
    sd="/tmp/stem_sample"; os.makedirs(sd,exist_ok=True)
    d=fitz.open(pdf)
    for i in range(len(d)):
        d[i].get_pixmap(matrix=fitz.Matrix(1.1,1.1)).save(f"{sd}/p{i:02d}.png")
    d.close()
    print(f"  render -> {sd} ({i+1} págs)")

if __name__=="__main__":
    cmd=sys.argv[1] if len(sys.argv)>1 else "sample"
    if cmd=="sample": build_sample()
    elif cmd=="full": build(pages_per_section=20, out_name="STEM_Notebook")
    print("Done.")
