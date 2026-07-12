"""Generate the Lulu wraparound cover (1255x810 pt = 17.43x11.25") for
Hyperbolic Gardens, plus a square web cover image of the front."""
import sys, math
sys.path.insert(0,"/var/www/mathrelaxing.store")
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.backends.backend_pdf import PdfPages
from scripts.gen_hyperbolic_book import tiling_polys, _arc_pts

BG="#1F1834"; GOLD="#C8A96E"; CREAM="#EDE6D6"; FAINT="#3A3052"; BAND="#000000"
LOGO_PATH="/var/www/mathrelaxing.store/static/img/logo.png"
_LOGO=mpimg.imread(LOGO_PATH)

def place_logo(fig, rect):
    """Drop the MathRelaxing logo, centred, inside the given figure-fraction box.
    imshow keeps the image aspect ratio (no distortion); it letterboxes/centres
    within the box."""
    ax=fig.add_axes(rect); ax.axis("off"); ax.imshow(_LOGO, aspect="equal")

def draw_tiling(ax, p, q, color, lw, max_polys=200):
    ax.set_xlim(-1.03,1.03); ax.set_ylim(-1.03,1.03); ax.set_aspect("equal"); ax.axis("off")
    th=np.linspace(0,2*math.pi,400); ax.plot(np.cos(th),np.sin(th),color=color,lw=lw*1.3)
    drawn=set()
    for poly in tiling_polys(p,q,max_polys):
        for i in range(len(poly)):
            a,b=poly[i],poly[(i+1)%len(poly)]
            ek=tuple(sorted([(round(a.real,3),round(a.imag,3)),(round(b.real,3),round(b.imag,3))]))
            if ek in drawn: continue
            drawn.add(ek); xs,ys=_arc_pts(a,b); ax.plot(xs,ys,color=color,lw=lw)

def build_cover():
    W,H=1255/72.0, 810/72.0
    fig=plt.figure(figsize=(W,H))
    bg=fig.add_axes([0,0,1,1]); bg.axis("off"); bg.add_patch(plt.Rectangle((0,0),1,1,color=BG))
    # fractions
    fb=9/1255.0; front_l=634/1255.0; front_r=1246/1255.0; spine_l=621/1255.0; spine_r=634/1255.0
    # FRONT motif
    axm=fig.add_axes([front_l+0.055, 0.43, (front_r-front_l)-0.11, 0.32]); draw_tiling(axm,7,3,GOLD,1.0)
    fig.text((front_l+front_r)/2, 0.86, "HYPERBOLIC", ha="center", va="center", fontsize=34, family="serif", color=CREAM, weight="light")
    fig.text((front_l+front_r)/2, 0.805, "GARDENS", ha="center", va="center", fontsize=34, family="serif", color=GOLD, weight="light")
    fig.text((front_l+front_r)/2, 0.36, "A Coloring Book of Infinite Tilings", ha="center", fontsize=14, family="serif", style="italic", color=CREAM)
    fig.text((front_l+front_r)/2, 0.255, "50 hand-finishable hyperbolic designs", ha="center", fontsize=11, family="serif", color=GOLD)
    # FRONT — black band + MathRelaxing logo across the bottom of the front panel
    band_h=0.155
    bg.add_patch(plt.Rectangle((front_l,0),1-front_l,band_h,color=BAND,zorder=5))
    fc=(front_l+front_r)/2
    place_logo(fig,[fc-0.085,0.018,0.17,band_h*0.74])
    # SPINE
    fig.text((spine_l+spine_r)/2, 0.5, "HYPERBOLIC GARDENS   ·   MATHRELAXING", rotation=90, ha="center", va="center", fontsize=8.5, family="serif", color=CREAM)
    # BACK
    back_c=(fb+spine_l)/2
    axb=fig.add_axes([0.06, 0.46, 0.22, 0.30]); draw_tiling(axb,5,4,FAINT,0.8,max_polys=120)
    blurb=("Step into the infinite. Every page in this book is a tiling of the\n"
           "hyperbolic plane, rendered in the Poincare disk — the geometry that\n"
           "inspired M.C. Escher's Circle Limit prints. Regular polygons repeat\n"
           "forever, shrinking toward an edge they can never reach.\n\n"
           "50 unique {p,q} tessellations, generated from real hyperbolic\n"
           "geometry and drawn as clean line art, ready for your colour.\n\n"
           "Perfect-bound · 8.5 x 11 in · matte cover · printed on demand.")
    fig.text(0.06, 0.40, blurb, ha="left", va="top", fontsize=9.5, family="serif", color=CREAM, linespacing=1.5)
    fig.text(back_c, 0.07, "mathrelaxing.store", ha="center", fontsize=9, family="serif", color=GOLD)
    out="/var/www/mathrelaxing.store/static/downloads/hyperbolic-gardens/cover.pdf"
    with PdfPages(out) as pdf: pdf.savefig(fig)
    plt.close(fig); print("cover ->", out)

def build_web_cover():
    # square-ish front cover image for the product page / promo
    fig=plt.figure(figsize=(10,12.5))
    bg=fig.add_axes([0,0,1,1]); bg.axis("off"); bg.add_patch(plt.Rectangle((0,0),1,1,color=BG))
    axm=fig.add_axes([0.13,0.40,0.74,0.38]); draw_tiling(axm,7,3,GOLD,1.4)
    fig.text(0.5,0.88,"HYPERBOLIC",ha="center",fontsize=40,family="serif",color=CREAM,weight="light")
    fig.text(0.5,0.825,"GARDENS",ha="center",fontsize=40,family="serif",color=GOLD,weight="light")
    fig.text(0.5,0.31,"A Coloring Book of Infinite Tilings",ha="center",fontsize=15,family="serif",style="italic",color=CREAM)
    fig.text(0.5,0.225,"50 hyperbolic designs",ha="center",fontsize=11,family="serif",color=GOLD)
    # black band + MathRelaxing logo across the bottom
    band_h=0.135
    bg.add_patch(plt.Rectangle((0,0),1,band_h,color=BAND,zorder=5))
    place_logo(fig,[0.385,0.02,0.23,band_h*0.74])
    out="/var/www/mathrelaxing.store/static/img/hyperbolic_gardens_cover.png"
    fig.savefig(out,facecolor=BG,dpi=100); plt.close(fig); print("web cover ->", out)

if __name__=="__main__":
    build_cover(); build_web_cover()
