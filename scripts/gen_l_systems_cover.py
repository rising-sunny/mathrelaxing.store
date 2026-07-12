"""Generate the Lulu wraparound cover (1255x810 pt = 17.43x11.25") for
Fractal Flora, plus a square web cover image of the front."""
import sys
sys.path.insert(0,"/var/www/mathrelaxing.store")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.image as mpimg
from matplotlib.backends.backend_pdf import PdfPages
import os
from scripts.gen_l_systems_book import draw_page, SPECS

# Emerald and Gold aesthetic for "Flora"
BG="#11221D"; GOLD="#C8A96E"; CREAM="#EDE6D6"; FAINT="#2B4037"; BAND="#000000"
LOGO_PATH="/var/www/mathrelaxing.store/static/img/logo.png"
_LOGO=mpimg.imread(LOGO_PATH)

def place_logo(fig, rect):
    ax=fig.add_axes(rect); ax.axis("off"); ax.imshow(_LOGO, aspect="equal")

def build_cover():
    W,H=1255/72.0, 810/72.0
    fig=plt.figure(figsize=(W,H))
    bg=fig.add_axes([0,0,1,1]); bg.axis("off"); bg.add_patch(plt.Rectangle((0,0),1,1,color=BG))
    # fractions
    fb=9/1255.0; front_l=634/1255.0; front_r=1246/1255.0; spine_l=621/1255.0; spine_r=634/1255.0
    
    # FRONT motif (Fractal Plant 1: SPECS[0])
    axm=fig.add_axes([front_l+0.055, 0.43, (front_r-front_l)-0.11, 0.32])
    # The draw_page function from gen_l_systems_book.py uses color="black", we need to adapt it 
    # to draw with GOLD. We can monkeypatch it or just implement a custom draw here.
    # To be safe, I'll copy interpret_lsystem and generate_lsystem logic for the cover.
    from scripts.gen_l_systems_book import generate_lsystem, interpret_lsystem
    def draw_spec_color(ax, spec, color, lw):
        name, axiom, rules, iters, angle, start_angle = spec
        seq = generate_lsystem(axiom, rules, iters)
        segments = interpret_lsystem(seq, angle, start_angle=start_angle)
        min_x = min(min(seg[0]) for seg in segments)
        max_x = max(max(seg[0]) for seg in segments)
        min_y = min(min(seg[1]) for seg in segments)
        max_y = max(max(seg[1]) for seg in segments)
        width, height = max_x - min_x, max_y - min_y
        if width == 0: width = 1
        if height == 0: height = 1
        scale = 1.9 / max(width, height)
        ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05); ax.set_aspect("equal"); ax.axis("off")
        for seg_x, seg_y in segments:
            sx = [(x - min_x - width/2) * scale for x in seg_x]
            sy = [(y - min_y - height/2) * scale for y in seg_y]
            ax.plot(sx, sy, color=color, lw=3.0, 
                    path_effects=[pe.Stroke(linewidth=3.8, foreground='black'), pe.Normal()],
                    solid_capstyle='round', solid_joinstyle='round')

    draw_spec_color(axm, SPECS[0], GOLD, 1.0)
    
    fig.text((front_l+front_r)/2, 0.86, "FRACTAL", ha="center", va="center", fontsize=38, family="serif", color=CREAM, weight="light")
    fig.text((front_l+front_r)/2, 0.805, "FLORA", ha="center", va="center", fontsize=38, family="serif", color=GOLD, weight="light")
    fig.text((front_l+front_r)/2, 0.36, "A Coloring Book of Algorithmic Growth", ha="center", fontsize=14, family="serif", style="italic", color=CREAM)
    fig.text((front_l+front_r)/2, 0.255, "50 space-filling and fractal plant designs", ha="center", fontsize=11, family="serif", color=GOLD)
    
    # FRONT — black band + MathRelaxing logo
    band_h=0.155
    bg.add_patch(plt.Rectangle((front_l,0),1-front_l,band_h,color=BAND,zorder=5))
    fc=(front_l+front_r)/2
    place_logo(fig,[fc-0.085,0.018,0.17,band_h*0.74])
    
    # SPINE
    fig.text((spine_l+spine_r)/2, 0.5, "FRACTAL FLORA   ·   MATHRELAXING", rotation=90, ha="center", va="center", fontsize=8.5, family="serif", color=CREAM)
    
    # BACK (Dragon Curve: SPECS[14])
    back_c=(fb+spine_l)/2
    axb=fig.add_axes([0.06, 0.46, 0.22, 0.30])
    draw_spec_color(axb, SPECS[14], FAINT, 0.8)
    
    blurb=("Step into the forest of mathematics. Every page in this book\n"
           "was generated using Lindenmayer systems (L-systems), a formal\n"
           "grammar that models the growth processes of plants.\n\n"
           "50 unique algorithmic gardens, from space-filling curves like\n"
           "the Dragon Curve to perfectly symmetrical fractal ferns, drawn\n"
           "as clean line art, ready for your colour.\n\n"
           "Perfect-bound · 8.5 x 11 in · matte cover · printed on demand.")
    fig.text(0.06, 0.40, blurb, ha="left", va="top", fontsize=9.5, family="serif", color=CREAM, linespacing=1.5)
    fig.text(back_c, 0.07, "mathrelaxing.store", ha="center", fontsize=9, family="serif", color=GOLD)
    
    out_dir = "/var/www/mathrelaxing.store/static/downloads/fractal-flora-coloring-book"
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "cover.pdf")
    with PdfPages(out) as pdf: pdf.savefig(fig)
    plt.close(fig); print("cover ->", out)

def build_web_cover():
    fig=plt.figure(figsize=(10,12.5))
    bg=fig.add_axes([0,0,1,1]); bg.axis("off"); bg.add_patch(plt.Rectangle((0,0),1,1,color=BG))
    axm=fig.add_axes([0.13,0.40,0.74,0.38])
    
    from scripts.gen_l_systems_book import generate_lsystem, interpret_lsystem
    def draw_spec_color(ax, spec, color, lw):
        name, axiom, rules, iters, angle, start_angle = spec
        seq = generate_lsystem(axiom, rules, iters)
        segments = interpret_lsystem(seq, angle, start_angle=start_angle)
        min_x = min(min(seg[0]) for seg in segments)
        max_x = max(max(seg[0]) for seg in segments)
        min_y = min(min(seg[1]) for seg in segments)
        max_y = max(max(seg[1]) for seg in segments)
        width, height = max_x - min_x, max_y - min_y
        if width == 0: width = 1
        if height == 0: height = 1
        scale = 1.9 / max(width, height)
        ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05); ax.set_aspect("equal"); ax.axis("off")
        for seg_x, seg_y in segments:
            sx = [(x - min_x - width/2) * scale for x in seg_x]
            sy = [(y - min_y - height/2) * scale for y in seg_y]
            ax.plot(sx, sy, color=color, lw=3.0, 
                    path_effects=[pe.Stroke(linewidth=3.8, foreground='black'), pe.Normal()],
                    solid_capstyle='round', solid_joinstyle='round')
            
    draw_spec_color(axm, SPECS[0], GOLD, 1.4)
    
    fig.text(0.5,0.88,"FRACTAL",ha="center",fontsize=44,family="serif",color=CREAM,weight="light")
    fig.text(0.5,0.825,"FLORA",ha="center",fontsize=44,family="serif",color=GOLD,weight="light")
    fig.text(0.5,0.31,"A Coloring Book of Algorithmic Growth",ha="center",fontsize=15,family="serif",style="italic",color=CREAM)
    fig.text(0.5,0.225,"50 algorithmic designs",ha="center",fontsize=11,family="serif",color=GOLD)
    
    band_h=0.135
    bg.add_patch(plt.Rectangle((0,0),1,band_h,color=BAND,zorder=5))
    place_logo(fig,[0.385,0.02,0.23,band_h*0.74])
    
    out="/var/www/mathrelaxing.store/static/img/fractal_flora_cover.png"
    fig.savefig(out,facecolor=BG,dpi=100); plt.close(fig); print("web cover ->", out)

if __name__=="__main__":
    build_cover(); build_web_cover()
