"""Generate the 'Hyperbolic Gardens' coloring book interior PDF — 50 unique
Poincaré-disk {p,q} tilings (Escher Circle Limit style) as clean black line art."""
import sys, math
sys.path.insert(0, "/var/www/mathrelaxing.store")
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

def _ortho(p1, p2):
    a1,b1,c1 = 2*p1.real, 2*p1.imag, abs(p1)**2+1
    a2,b2,c2 = 2*p2.real, 2*p2.imag, abs(p2)**2+1
    det = a1*b2 - a2*b1
    if abs(det) < 1e-9: return None
    c = complex((c1*b2-c2*b1)/det, (a1*c2-a2*c1)/det); R2 = abs(c)**2-1
    return (c, math.sqrt(R2)) if R2 > 1e-9 else None

def _reflect(z, p1, p2):
    oc = _ortho(p1,p2)
    if oc is None:
        d=p2-p1; th=math.atan2(d.imag,d.real)
        return complex(math.cos(2*th),math.sin(2*th))*np.conj(z)
    c,R = oc; return c + R*R*(z-c)/(abs(z-c)**2)

def _interior_angle(r,p):
    V0=complex(r,0); V1=r*np.exp(1j*2*math.pi/p); Vm=r*np.exp(-1j*2*math.pi/p)
    def tang(a,b):
        oc=_ortho(a,b)
        if oc is None: return (b-a)/abs(b-a)
        c,R=oc; t=1j*(a-c)
        if (t.real*(b-a).real+t.imag*(b-a).imag)<0: t=-t
        return t/abs(t)
    t1=tang(V0,V1); t2=tang(V0,Vm)
    return math.acos(max(-1,min(1,t1.real*t2.real+t1.imag*t2.imag)))

def _vr(p,q):
    tgt=2*math.pi/q; lo,hi=1e-3,0.999
    for _ in range(80):
        m=(lo+hi)/2
        if _interior_angle(m,p)>tgt: lo=m
        else: hi=m
    return (lo+hi)/2

def _arc_pts(a,b,n=48):
    oc=_ortho(a,b)
    if oc is None: return np.array([a.real,b.real]), np.array([a.imag,b.imag])
    c,R=oc
    a1=math.atan2(a.imag-c.imag,a.real-c.real); a2=math.atan2(b.imag-c.imag,b.real-c.real)
    if a2-a1>math.pi: a2-=2*math.pi
    if a1-a2>math.pi: a1-=2*math.pi
    t=np.linspace(a1,a2,n); return c.real+R*np.cos(t), c.imag+R*np.sin(t)

def tiling_polys(p,q,max_polys):
    r0=_vr(p,q); v0=tuple(r0*np.exp(1j*2*math.pi*k/p) for k in range(p))
    key=lambda P:(round((sum(P)/len(P)).real,4),round((sum(P)/len(P)).imag,4))
    seen={key(v0)}; polys=[v0]; queue=[v0]
    while queue and len(polys)<max_polys:
        poly=queue.pop(0)
        for i in range(len(poly)):
            a,b=poly[i],poly[(i+1)%len(poly)]
            npoly=tuple(_reflect(v,a,b) for v in poly); k=key(npoly)
            if k in seen: continue
            seen.add(k); polys.append(npoly); queue.append(npoly)
    return polys

def draw_page(ax, p, q, decoration="plain", max_polys=240, lw=1.6):
    ax.set_xlim(-1.04,1.04); ax.set_ylim(-1.04,1.04); ax.set_aspect("equal"); ax.axis("off")
    th=np.linspace(0,2*math.pi,500); ax.plot(np.cos(th),np.sin(th),color="black",lw=lw*1.4)
    polys=tiling_polys(p,q,max_polys)
    drawn=set()
    for poly in polys:
        for i in range(len(poly)):
            a,b=poly[i],poly[(i+1)%len(poly)]
            ek=tuple(sorted([(round(a.real,3),round(a.imag,3)),(round(b.real,3),round(b.imag,3))]))
            if ek in drawn: continue
            drawn.add(ek); xs,ys=_arc_pts(a,b); ax.plot(xs,ys,color="black",lw=lw)
        if decoration=="nested" and len(poly)>=3:
            mids=[]
            for i in range(len(poly)):
                xs,ys=_arc_pts(poly[i],poly[(i+1)%len(poly)]); mids.append(complex(xs[len(xs)//2],ys[len(ys)//2]))
            for i in range(len(mids)):
                xs,ys=_arc_pts(mids[i],mids[(i+1)%len(mids)]); ax.plot(xs,ys,color="black",lw=lw*0.85)

# 50 distinct (p,q,decoration) specs
BASE=[(7,3),(8,3),(9,3),(10,3),(12,3),(5,4),(6,4),(7,4),(8,4),(4,5),
      (5,5),(6,5),(4,6),(5,6),(4,7),(3,7),(3,8),(3,9),(3,10),(3,12),
      (4,8),(5,7),(6,6),(7,5),(8,5)]
SPECS=[(p,q,"plain") for (p,q) in BASE] + [(p,q,"nested") for (p,q) in BASE]  # 50

PNAME={3:"triangles",4:"squares",5:"pentagons",6:"hexagons",7:"heptagons",
       8:"octagons",9:"nonagons",10:"decagons",11:"hendecagons",12:"dodecagons"}

def _caption(fig, p, q, dec, idx, total):
    """Elegant math caption beneath each design: Schlafli symbol, plain-language
    description, the hyperbolic condition, and the tile's circumradius."""
    s   = 1.0/p + 1.0/q
    cR  = math.cos(math.pi/q)/math.sin(math.pi/p)          # cosh R (circumradius)
    sym = r"$\{%d,\,%d\}$" % (p,q) + ("   $·$   nested" if dec=="nested" else "")
    fig.text(0.5,0.092, sym, ha="center", fontsize=16, family="serif", color="#222")
    fig.text(0.5,0.066, f"Regular {PNAME.get(p,f'{p}-gons')} · {q} meeting at every vertex",
             ha="center", fontsize=10.5, family="serif", style="italic", color="#555")
    fig.text(0.5,0.038,
             r"$\frac{1}{%d}+\frac{1}{%d}\approx%.3f<\frac{1}{2}$        "
             r"$\cosh R=\dfrac{\cos(\pi/%d)}{\sin(\pi/%d)}\approx%.2f$" % (p,q,s,q,p,cR),
             ha="center", fontsize=10.5, color="#666")
    fig.text(0.93,0.022, f"{idx}", ha="center", fontsize=9, color="#aaa")

PAGE_W, PAGE_H = 8.75, 11.25  # trim 8.5x11 + 0.125" bleed all sides (matches Lulu)

def _blank(pdf):
    fig=plt.figure(figsize=(PAGE_W,PAGE_H)); fig.add_axes([0,0,1,1]).axis("off")
    pdf.savefig(fig); plt.close(fig)

def _title_page(pdf):
    fig=plt.figure(figsize=(PAGE_W,PAGE_H)); ax=fig.add_axes([0,0,1,1]); ax.axis("off")
    ax.text(0.5,0.62,"HYPERBOLIC\nGARDENS",ha="center",va="center",fontsize=46,family="serif",weight="light")
    ax.text(0.5,0.45,"A Coloring Book of Infinite Tilings",ha="center",fontsize=18,family="serif",style="italic",color="#444")
    ax.text(0.5,0.40,"50 Poincare-disk {p,q} tessellations \u00b7 MathRelaxing",ha="center",fontsize=11,family="serif",color="#777")
    pdf.savefig(fig); plt.close(fig)

def _intro_page(pdf):
    fig=plt.figure(figsize=(PAGE_W,PAGE_H)); ax=fig.add_axes([0.12,0.1,0.76,0.82]); ax.axis("off")
    ax.text(0.0,0.97,"About this book",ha="left",va="top",fontsize=22,family="serif",color="#222")
    intro=("Every design in these pages is a tiling of the hyperbolic plane \u2014 a\n"
           "world where space curves away from itself so steeply that infinitely\n"
           "many identical shapes fit inside a single circle. They are drawn in\n"
           "the Poincare disk, the same model of hyperbolic geometry that inspired\n"
           "M.C. Escher's famous Circle Limit woodcuts.\n\n"
           "Each pattern is named by its Schlafli symbol {p, q}: it is built from\n"
           "regular p-sided polygons, with exactly q of them meeting around every\n"
           "corner. The tiles appear to shrink toward the rim, but in hyperbolic\n"
           "space they are all exactly the same size \u2014 the pattern truly continues\n"
           "forever, never reaching the edge.\n\n"
           "The next page explains the geometry behind the drawings. After that,\n"
           "50 unique tilings await your colour.\n\n\n"
           "How to colour:\n"
           "   -  Any pens, pencils or markers work on the matte paper.\n"
           "   -  Try colouring by ring, by tile size, or by symmetry \u2014 each\n"
           "      choice reveals a different hidden structure.\n"
           "   -  Slip a spare sheet behind the page if you use wet markers.\n\n"
           "Enjoy the infinite.")
    ax.text(0.0,0.88,intro,ha="left",va="top",fontsize=12.5,family="serif",color="#333",linespacing=1.5)
    pdf.savefig(fig); plt.close(fig)

def _math_page(pdf):
    fig=plt.figure(figsize=(PAGE_W,PAGE_H)); ax=fig.add_axes([0.12,0.1,0.76,0.82]); ax.axis("off")
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    ax.text(0.0,0.99,"The mathematics",ha="left",va="top",fontsize=22,family="serif",color="#222")
    y=0.905
    def para(txt, fs=12.5, gap=0.026, color="#333"):
        nonlocal y
        ax.text(0.0,y,txt,ha="left",va="top",fontsize=fs,family="serif",color=color,linespacing=1.5)
        y-=(txt.count("\n")+1)*0.0305 + gap
    def formula(expr, fs=15, gap=0.030):
        nonlocal y
        ax.text(0.5,y,expr,ha="center",va="top",fontsize=fs,color="#222")
        y-=0.060 + gap

    para("The Poincare disk.  Every design lives inside one circle \u2014 a map of the\n"
         "entire hyperbolic plane. The straight lines of this world, its geodesics,\n"
         "appear as arcs of circles that meet the boundary at right angles. That is\n"
         "why every edge in these tilings curves so gracefully.")
    para("The Schlafli symbol.  Each tiling is described by two numbers: regular\n"
         "p-sided polygons, with q of them meeting at every vertex.")
    formula(r"$\{\,p,\ q\,\}$")
    para("When is it hyperbolic?  A regular tiling is spherical, flat, or hyperbolic\n"
         "depending only on p and q. It curves into the hyperbolic plane exactly when")
    formula(r"$\dfrac{1}{p}+\dfrac{1}{q}<\dfrac{1}{2}$")
    para("If the sum is greater than one half the tiling closes up on a sphere (only\n"
         "five exist); if it equals one half the tiling is flat (only three). Below\n"
         "one half there are infinitely many \u2014 and every one of them lives here.")
    para("The size of a tile.  In the disk each polygon has the same hyperbolic\n"
         "circumradius R, fixed by p and q through")
    formula(r"$\cosh R=\dfrac{\cos(\pi/q)}{\sin(\pi/p)}$")
    para("Building the pattern.  Starting from a single tile, we reflect it across\n"
         "its edges again and again. These reflections form a hyperbolic symmetry\n"
         "group, and their orbit fills the disk with the endless garden you colour.")
    pdf.savefig(fig); plt.close(fig)

def main(test=False):
    out="/var/www/mathrelaxing.store/static/downloads/hyperbolic-gardens/interior.pdf"
    specs = SPECS[:3] if test else SPECS
    if test: out="/tmp/hyp_test.pdf"
    with PdfPages(out) as pdf:
        _title_page(pdf)
        _intro_page(pdf)
        _math_page(pdf)
        for idx,(p,q,dec) in enumerate(specs,1):
            fig=plt.figure(figsize=(PAGE_W,PAGE_H))
            ax=fig.add_axes([0.12,0.13,0.76,0.74])
            draw_page(ax,p,q,dec)
            _caption(fig,p,q,dec,idx,len(specs))
            pdf.savefig(fig); plt.close(fig)
            print(f"page {idx}/{len(specs)} {{{p},{q}}} {dec}",flush=True)
        if not test:
            _blank(pdf)   # single trailing blank \u2192 title+intro+math+50+1 = 54 pages
    print("DONE ->",out)

if __name__=="__main__":
    main(test=("--test" in sys.argv))
