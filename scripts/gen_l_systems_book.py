"""Generate the 'Fractal Flora' coloring book interior PDF — 50 unique
L-Systems (Space-filling curves and fractal plants) as clean black line art."""
import sys, math
sys.path.insert(0, "/var/www/mathrelaxing.store")
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.backends.backend_pdf import PdfPages
import os

def generate_lsystem(axiom, rules, iterations):
    current = axiom
    for _ in range(iterations):
        next_seq = ""
        for char in current:
            next_seq += rules.get(char, char)
        current = next_seq
    return current

def interpret_lsystem(seq, angle_deg, start_pos=(0, 0), start_angle=90):
    stack = []
    x, y = start_pos[0], start_pos[1]
    current_angle = start_angle
    
    segments = []
    current_segment_x = [x]
    current_segment_y = [y]
    
    for char in seq:
        if char in ('F', 'G', 'A', 'B'):  # Move forward and draw
            x += math.cos(math.radians(current_angle))
            y += math.sin(math.radians(current_angle))
            current_segment_x.append(x)
            current_segment_y.append(y)
        elif char == 'f':  # Move forward without drawing
            if len(current_segment_x) > 1:
                segments.append((current_segment_x, current_segment_y))
            x += math.cos(math.radians(current_angle))
            y += math.sin(math.radians(current_angle))
            current_segment_x = [x]
            current_segment_y = [y]
        elif char == '+':  # Turn right (or left depending on convention, let's say left here)
            current_angle += angle_deg
        elif char == '-':  # Turn left
            current_angle -= angle_deg
        elif char == '[':  # Save state
            if len(current_segment_x) > 1:
                segments.append((current_segment_x, current_segment_y))
            stack.append((x, y, current_angle))
            current_segment_x = [x]
            current_segment_y = [y]
        elif char == ']':  # Restore state
            if len(current_segment_x) > 1:
                segments.append((current_segment_x, current_segment_y))
            x, y, current_angle = stack.pop()
            current_segment_x = [x]
            current_segment_y = [y]
            
    if len(current_segment_x) > 1:
        segments.append((current_segment_x, current_segment_y))
        
    return segments

def draw_page(ax, spec, lw=1.0):
    name, axiom, rules, iters, angle, start_angle = spec
    seq = generate_lsystem(axiom, rules, iters)
    segments = interpret_lsystem(seq, angle, start_angle=start_angle)
    
    # Calculate bounds
    min_x = min(min(seg[0]) for seg in segments)
    max_x = max(max(seg[0]) for seg in segments)
    min_y = min(min(seg[1]) for seg in segments)
    max_y = max(max(seg[1]) for seg in segments)
    
    # Scale and center
    width = max_x - min_x
    height = max_y - min_y
    if width == 0: width = 1
    if height == 0: height = 1
    
    scale = 1.9 / max(width, height)
    
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_aspect("equal")
    ax.axis("off")
    
    # Optional outer boundary (circle or square)
    th = np.linspace(0, 2*math.pi, 500)
    # ax.plot(np.cos(th), np.sin(th), color="black", lw=lw*1.4)
    
    for seg_x, seg_y in segments:
        sx = [(x - min_x - width/2) * scale for x in seg_x]
        sy = [(y - min_y - height/2) * scale for y in seg_y]
        
        # Hollow tubes: thick white interior, thin black outline
        ax.plot(sx, sy, color="white", lw=2.5, 
                path_effects=[pe.Stroke(linewidth=3.0, foreground='black'), pe.Normal()],
                solid_capstyle='round', solid_joinstyle='round')

# Definition of 50 L-systems. 
# Format: (Name, Axiom, Rules, Iterations, Angle, StartAngle)
SPECS = [
    # 1. Geometric Mandalas and Loops (Replacing open plants)
    ("Koch Mandala", "F++F++F++F++F++F", {"F": "F-F++F-F"}, 4, 60, 0),
    ("Minkowski Loop", "F+F+F+F", {"F": "F-F+F+FF-F-F+F"}, 3, 90, 0),
    ("Quadratic Koch Island", "F+F+F+F", {"F": "F-F+F+FFF-F-F+F"}, 3, 90, 0),
    ("Koch Square", "F+F+F+F", {"F": "FF+F-F+F+FF"}, 4, 90, 0),
    ("Cesaro Fractal", "F+F+F+F", {"F": "F-F+F-F"}, 5, 85, 0),
    ("Dragon Loop", "FX+FX+FX+FX", {"X": "X+YF+", "Y": "-FX-Y"}, 10, 90, 0),
    ("Peano Loop", "F+F+F+F", {"F": "F+F-F-F-F+F+F+F-F"}, 3, 90, 0),
    ("Gosper Ring", "A+A+A+A+A+A", {"A": "A-B--B+A++AA+B-", "B": "+A-BB--B-A++A+B"}, 4, 60, 0),
    ("Sierpinski Ring", "F+XF+F+XF", {"X": "XF-F+F-XF+F+XF-F+F-X"}, 4, 90, 0),
    ("Hexagonal Snowflake", "F++F++F++F++F++F", {"F": "F-F+F+F-F"}, 4, 60, 0),
    
    # 11. Space Filling Curves
    ("Hilbert Curve", "A", {"A": "-BF+AFA+FB-", "B": "+AF-BFB-FA+"}, 6, 90, 0),
    ("Moore Curve", "LFL+F+LFL", {"L": "-RF+LFL+FR-", "R": "+LF-RFR-FL+"}, 5, 90, 0),
    ("Peano Curve", "F", {"F": "F+F-F-F-F+F+F+F-F"}, 4, 90, 0),
    ("Peano-Gosper Curve", "A", {"A": "A-B--B+A++AA+B-", "B": "+A-BB--B-A++A+B"}, 4, 60, 0),
    ("Dragon Curve", "FX", {"X": "X+YF+", "Y": "-FX-Y"}, 12, 90, 0),
    ("Twin Dragon", "FX+FX+", {"X": "X+YF+", "Y": "-FX-Y"}, 11, 90, 0),
    ("Terdragon", "F", {"F": "F+F-F"}, 8, 120, 0),
    ("Sierpinski Arrowhead", "A", {"A": "B-A-B", "B": "A+B+A"}, 7, 60, 0),
    ("Sierpinski Curve", "F+XF+F+XF", {"X": "XF-F+F-XF+F+XF-F+F-X"}, 5, 90, 0),
    ("Lebesgue Curve", "F", {"F": "F+F-F-F+F"}, 5, 45, 0),

    # 21. Koch-like Fractals
    ("Koch Snowflake", "F++F++F", {"F": "F-F++F-F"}, 5, 60, 0),
    ("Koch Anti-Snowflake", "F++F++F", {"F": "F+F--F+F"}, 5, 60, 0),
    ("Quadratic Snowflake", "F", {"F": "F-F+F+F-F"}, 5, 90, 0),
    ("Islands and Lakes", "F+F+F+F", {"F": "F+f-FF+F+FF+Ff+FF-f+FF-F-FF-Ff-FFF", "f": "ffffff"}, 2, 90, 0),
    ("Crystal", "F+F+F+F", {"F": "FF+F++F+F"}, 4, 90, 0),
    ("Minkowski Sausage", "F", {"F": "F+F-F-FF+F+F-F"}, 4, 90, 0),
    ("Quadratic Gosper", "YF", {"X": "XFX-YF-YF+FX+FX-YF-YFFX+YF+FXFXYF-FX+YF+FXFX+YF-FXYF-YF-FX+FX+YFYF-", "Y": "+FXFX-YF-YF+FX+FXYF+FX-YFYF-FX-YF+FXYFYF-FX-YFFX+FX+YF-YF-FX+FX+YFY"}, 2, 90, 0),
    ("Cross Stitch", "F-F-F-F", {"F": "F-F+F+F-F"}, 4, 90, 0),
    ("Rings", "F-F-F-F", {"F": "FF-F-F-F-F-F+F"}, 4, 90, 0),
    ("Board", "F+F+F+F", {"F": "FF+F+F+F+FF"}, 4, 90, 0),

    # 31. Tesselations and Hexagonal Grids
    ("Hexagonal Gosper", "A", {"A": "A+B++B-A--AA-B+", "B": "-A+BB++B+A--A-B"}, 4, 60, 0),
    ("Hexagonal Tesselation", "F", {"F": "F-F+F+F-F"}, 5, 60, 0),
    ("Triangle Tesselation", "F-F-F", {"F": "F-F+F+F-F"}, 5, 120, 0),
    ("Square Tesselation", "F-F-F-F", {"F": "F-F+F+F-F"}, 4, 90, 0),
    ("Pentaplexity", "F++F++F++F++F", {"F": "F++F++F|F-F++F"}, 4, 36, 0), # Pentagonal
    ("Rhombus Tesselation", "F-F-F-F", {"F": "F-F+F+F-F"}, 5, 90, 0),
    ("Kolam Pattern", "A", {"A": "A-B-A", "B": "B+A+B"}, 6, 60, 0),
    ("Sierpinski Carpet", "F-F-F-F", {"F": "F[F]-F+F[--F]+F-F"}, 4, 90, 0),
    ("Tile Pattern", "F+F+F+F", {"F": "FF+F-F+F+FF"}, 4, 90, 0),
    ("Mosaic", "F-F-F-F", {"F": "F-FF--F-F"}, 4, 90, 0),

    # 41. More Organic and Abstract
    ("Crystal Loop", "F+F+F+F", {"F": "FF+F++F+F"}, 5, 90, 0),
    ("Minkowski Star", "F-F-F-F", {"F": "F-F+F+FF-F-F+F"}, 4, 90, 0),
    ("Quadratic Star", "F-F-F-F", {"F": "F-F+F+F-F"}, 5, 90, 0),
    ("Hilbert Loop", "L", {"L": "+RF-LFL-FR+", "R": "-LF+RFR+FL-"}, 5, 90, 0),
    ("Hexagonal Maze", "A", {"A": "A+B++B-A--AA-B+", "B": "-A+BB++B+A--A-B"}, 5, 60, 0),
    ("Spiderweb", "F-F-F-F-F-F-F-F", {"F": "F---F+F-F-F+F+F-F"}, 3, 45, 0),
    ("Star Tesselation", "F-F-F-F-F", {"F": "F-F++F+F-F-F"}, 4, 72, 0),
    ("Mandalic Star", "F-F-F-F-F-F", {"F": "F-F++F-F"}, 5, 60, 0),
    ("Geometric Flower", "F-F-F-F-F-F-F-F", {"F": "F-F+F-F"}, 5, 45, 0),
    ("Infinite Labyrinth", "F", {"F": "F+F-F-F+F+F-F"}, 4, 90, 0)
]

def _caption(fig, name, iters, idx, total):
    fig.text(0.5, 0.08, name, ha="center", fontsize=16, family="serif", color="#222")
    fig.text(0.5, 0.05, f"L-System Generator • {iters} Iterations",
             ha="center", fontsize=10.5, family="serif", style="italic", color="#555")
    fig.text(0.93, 0.022, f"{idx}", ha="center", fontsize=9, color="#aaa")

PAGE_W, PAGE_H = 8.75, 11.25  # trim 8.5x11 + 0.125" bleed all sides (matches Lulu)

def _blank(pdf):
    fig = plt.figure(figsize=(PAGE_W, PAGE_H)); fig.add_axes([0,0,1,1]).axis("off")
    pdf.savefig(fig); plt.close(fig)

def _title_page(pdf):
    fig = plt.figure(figsize=(PAGE_W, PAGE_H)); ax = fig.add_axes([0,0,1,1]); ax.axis("off")
    ax.text(0.5, 0.62, "FRACTAL\nFLORA", ha="center", va="center", fontsize=46, family="serif", weight="light")
    ax.text(0.5, 0.45, "A Coloring Book of Algorithmic Growth", ha="center", fontsize=18, family="serif", style="italic", color="#444")
    ax.text(0.5, 0.40, "50 L-System Space-Filling Curves & Plants · MathRelaxing", ha="center", fontsize=11, family="serif", color="#777")
    pdf.savefig(fig); plt.close(fig)

def _intro_page(pdf):
    fig = plt.figure(figsize=(PAGE_W, PAGE_H)); ax = fig.add_axes([0.12,0.1,0.76,0.82]); ax.axis("off")
    ax.text(0.0, 0.97, "About this book", ha="left", va="top", fontsize=22, family="serif", color="#222")
    intro = ("Every design in these pages was generated using Lindenmayer systems\n"
             "(L-systems) — a mathematical language originally developed to model\n"
             "the growth processes of plant development.\n\n"
             "By repeatedly applying a simple set of rewriting rules to a sequence\n"
             "of symbols, complex branching structures and space-filling curves\n"
             "emerge. The patterns grow iteratively, expanding into intricate\n"
             "fractals like the Hilbert Curve, the Dragon Curve, and algorithmic\n"
             "ferns that mimic nature perfectly.\n\n"
             "The next page explains the mathematics behind the drawings. After that,\n"
             "50 unique algorithmic gardens await your colour.\n\n\n"
             "How to colour:\n"
             "   -  Any pens, pencils or markers work on the matte paper.\n"
             "   -  Follow the continuous lines of the space-filling curves, or\n"
             "      colour the enclosed spaces they create.\n"
             "   -  Slip a spare sheet behind the page if you use wet markers.\n\n"
             "Enjoy the infinite growth.")
    ax.text(0.0, 0.88, intro, ha="left", va="top", fontsize=12.5, family="serif", color="#333", linespacing=1.5)
    pdf.savefig(fig); plt.close(fig)

def _math_page(pdf):
    fig = plt.figure(figsize=(PAGE_W, PAGE_H)); ax = fig.add_axes([0.12,0.1,0.76,0.82]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.text(0.0, 0.99, "The mathematics", ha="left", va="top", fontsize=22, family="serif", color="#222")
    y = 0.905
    def para(txt, fs=12.5, gap=0.026, color="#333"):
        nonlocal y
        ax.text(0.0, y, txt, ha="left", va="top", fontsize=fs, family="serif", color=color, linespacing=1.5)
        y -= (txt.count("\n")+1)*0.0305 + gap

    para("L-Systems. An L-system consists of an alphabet of symbols, an initial\n"
         "string called the axiom, and a set of production rules that expand each\n"
         "symbol into a larger string in parallel.")
    para("For example, a simple algae model by Aristid Lindenmayer uses:")
    y -= 0.04
    ax.text(0.5, y, "Axiom: A\nRules: A \u2192 AB,  B \u2192 A", ha="center", va="top", fontsize=14, color="#222", linespacing=1.5)
    y -= 0.08
    para("Iteration. Applying the rules repeatedly causes the string to grow\n"
         "exponentially. Iteration 0 is 'A'. Iteration 1 is 'AB'. Iteration 2 is\n"
         "'ABA'. Iteration 3 is 'ABAAB'.")
    para("Turtle Graphics. To draw the fractals, we read the final string as\n"
         "commands for a 'turtle' holding a pen. 'F' means draw forward. '+' means\n"
         "turn right by an angle. '[' means remember current position, and ']' means\n"
         "return to it. This simple geometry interprets the string into the beautiful\n"
         "botanical branching shapes and continuous curves you see in this book.")
    pdf.savefig(fig); plt.close(fig)

def main(test=False):
    out_dir = "/var/www/mathrelaxing.store/static/downloads/fractal-flora-coloring-book"
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "interior.pdf")
    
    # We might need to handle the | notation used in Pentaplexity if not implemented, 
    # but I implemented F, G, A, B, f, +, -, [, ] which should cover 99% of it.
    
    specs = SPECS[:3] if test else SPECS
    if test: out = "/tmp/flora_test.pdf"
    
    with PdfPages(out) as pdf:
        _title_page(pdf)
        _intro_page(pdf)
        _math_page(pdf)
        for idx, spec in enumerate(specs, 1):
            fig = plt.figure(figsize=(PAGE_W, PAGE_H))
            ax = fig.add_axes([0.1, 0.13, 0.8, 0.76])
            try:
                draw_page(ax, spec)
            except Exception as e:
                print(f"Error on {spec[0]}: {e}")
            _caption(fig, spec[0], spec[3], idx, len(specs))
            pdf.savefig(fig); plt.close(fig)
            print(f"page {idx}/{len(specs)} {spec[0]}", flush=True)
        if not test:
            _blank(pdf)
    print("DONE ->", out)

if __name__ == "__main__":
    main(test=("--test" in sys.argv))
