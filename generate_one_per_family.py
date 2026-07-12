"""
Generate 1 representative page per family, full v7 treatment.
Outputs: 5 × 2 = 10 PNGs + 5 PDFs (uncolored is the printable one).

Reuses the v7 framework as a callable function so the same code can
later batch-render 50 pages.
"""

import math
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import LineString, Point, box as shp_box
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree


# =========================================================================
#  PAGE LAYOUT — Lulu US Letter (8.5 x 11) edge-to-edge
# -------------------------------------------------------------------------
#  Printed page = trim 8.5 x 11 in + 0.125" bleed on all sides = 8.75 x 11.25.
#  Axis unit = 0.5 in, so the data box maps 1:1 onto the bleed page when the
#  axes fill the whole figure with set_aspect("equal") (ratio 17.5:22.5 ==
#  8.75:11.25 == 7:9, so no letterboxing).
#      bleed edge   : x = +-8.75  y = +-11.25   (= +-4.375 / +-5.625 in)
#      trim line    : x = +-8.50  y = +-11.00   (= +-4.25  / +-5.50  in)
#      safety (0.5"): x = +-7.50  y = +-10.00   (= +-3.75  / +-5.00  in)
# =========================================================================
FIG_W_IN, FIG_H_IN = 8.75, 11.25
AX_X = (-8.75, 8.75)
AX_Y = (-11.25, 11.25)
DRAW_X_MIN, DRAW_X_MAX = -7.4, 7.4
DRAW_Y_MIN, DRAW_Y_MAX = -9.5, 9.5
SAFE_BOX = shp_box(DRAW_X_MIN, DRAW_Y_MIN, DRAW_X_MAX, DRAW_Y_MAX)


# =========================================================================
#  CURVES
# =========================================================================
def _close(pts): return np.vstack([pts, pts[0:1]])

def circle_curve(radius, points=600):
    t = np.linspace(0, 2*np.pi, points)
    return _close(np.column_stack([radius*np.cos(t), radius*np.sin(t)]))

def rose(k, a, rotation=0.0, points=3000):
    th = np.linspace(0, 2*np.pi, points)
    r = a*np.cos(k*th)
    return _close(np.column_stack([r*np.cos(th+rotation), r*np.sin(th+rotation)]))

def hypotrochoid(R, r, d, n_turns=None, points_per_turn=1500):
    if n_turns is None:
        n_turns = int(r/math.gcd(int(R), int(r))) if r==int(r) else 5
    t = np.linspace(0, 2*np.pi*n_turns, points_per_turn*n_turns)
    x = (R-r)*np.cos(t) + d*np.cos((R-r)/r*t)
    y = (R-r)*np.sin(t) - d*np.sin((R-r)/r*t)
    return _close(np.column_stack([x, y]))

def lissajous(A, B, a, b, delta, points=3500):
    t = np.linspace(0, 2*np.pi, points)
    return _close(np.column_stack([A*np.sin(a*t+delta), B*np.sin(b*t)]))

def epicycloid(R, r, n_turns=None, points_per_turn=1500):
    if n_turns is None:
        n_turns = int(r/math.gcd(int(R), int(r)))
    t = np.linspace(0, 2*np.pi*n_turns, points_per_turn*n_turns)
    x = (R+r)*np.cos(t) - r*np.cos((R+r)/r*t)
    y = (R+r)*np.sin(t) - r*np.sin((R+r)/r*t)
    return _close(np.column_stack([x, y]))

def hypocycloid(R, r, n_turns=None, points_per_turn=1500):
    if n_turns is None:
        n_turns = int(r/math.gcd(int(R), int(r)))
    t = np.linspace(0, 2*np.pi*n_turns, points_per_turn*n_turns)
    x = (R-r)*np.cos(t) + r*np.cos((R-r)/r*t)
    y = (R-r)*np.sin(t) - r*np.sin((R-r)/r*t)
    return _close(np.column_stack([x, y]))

def butterfly_curve(scale=1.0, points=4500):
    t = np.linspace(0, 12*np.pi, points)
    r = np.exp(np.cos(t)) - 2*np.cos(4*t) - np.sin(t/12)**5
    return _close(np.column_stack([scale*r*np.cos(t), scale*r*np.sin(t)]))

def lemniscate_bernoulli(a, rotation=0, cx=0.0, cy=0.0, points=2200):
    t = np.linspace(0, 2*np.pi, points)
    cos2t = np.cos(2*t)
    r = np.where(cos2t >= 0, a*np.sqrt(np.abs(cos2t)), 0)
    c, s = math.cos(rotation), math.sin(rotation)
    x = r*np.cos(t); y = r*np.sin(t)
    return _close(np.column_stack([cx + c*x - s*y, cy + s*x + c*y]))


# =========================================================================
#  PATTERNS
# =========================================================================
def _to_segments(geom):
    if geom.is_empty: return []
    gt = geom.geom_type
    if gt == "LineString": return [list(geom.coords)]
    if gt == "MultiLineString": return [list(ls.coords) for ls in geom.geoms]
    if gt == "GeometryCollection":
        out = []
        for g in geom.geoms: out.extend(_to_segments(g))
        return out
    return []

def pattern_hatching(poly, spacing, angle_deg):
    angle = math.radians(angle_deg)
    dx, dy = math.cos(angle), math.sin(angle)
    px, py = -math.sin(angle), math.cos(angle)
    xmin, ymin, xmax, ymax = poly.bounds
    cx, cy = (xmin+xmax)/2, (ymin+ymax)/2
    diag = math.hypot(xmax-xmin, ymax-ymin) * 0.6
    n = int(2*diag/spacing) + 2
    segs = []
    for k in range(-n, n+1):
        off = k*spacing
        a = (cx + off*px - diag*dx, cy + off*py - diag*dy)
        b = (cx + off*px + diag*dx, cy + off*py + diag*dy)
        segs.extend(_to_segments(poly.intersection(LineString([a, b]))))
    return segs

def pattern_crosshatch(poly, spacing, angle_deg):
    return pattern_hatching(poly, spacing, angle_deg) + pattern_hatching(poly, spacing, angle_deg+90)

def pattern_dots(poly, spacing, dot_r=0.05):
    xmin, ymin, xmax, ymax = poly.bounds
    segs = []
    y = ymin; row = 0
    while y <= ymax:
        offset = (spacing/2) if (row % 2) else 0
        x = xmin + offset
        while x <= xmax:
            if poly.contains(Point(x, y)):
                th = np.linspace(0, 2*np.pi, 16)
                segs.append(list(zip(x + dot_r*np.cos(th), y + dot_r*np.sin(th))))
            x += spacing
        y += spacing*0.85; row += 1
    return segs

def pattern_scales(poly, spacing, radius):
    xmin, ymin, xmax, ymax = poly.bounds
    segs = []
    y = ymin; row = 0
    while y <= ymax + radius:
        offset = (spacing/2) if (row % 2) else 0
        x = xmin + offset - spacing
        while x <= xmax + spacing:
            th = np.linspace(np.pi, 2*np.pi, 28)
            ax = x + radius*np.cos(th); ay = y + radius*np.sin(th)
            segs.extend(_to_segments(poly.intersection(LineString(list(zip(ax, ay))))))
            x += spacing
        y += spacing*0.55; row += 1
    return segs

def pattern_waves(poly, spacing, amp=0.10, freq=1.4):
    xmin, ymin, xmax, ymax = poly.bounds
    segs = []
    y = ymin
    while y <= ymax:
        xs = np.linspace(xmin-0.5, xmax+0.5, 260)
        ys = y + amp*np.sin(freq*np.pi*xs)
        segs.extend(_to_segments(poly.intersection(LineString(list(zip(xs, ys))))))
        y += spacing
    return segs

def pattern_radial(poly, n_spokes):
    pt = poly.representative_point(); c = (pt.x, pt.y)
    xmin, ymin, xmax, ymax = poly.bounds
    diag = math.hypot(xmax-xmin, ymax-ymin)
    segs = []
    for k in range(n_spokes):
        ang = 2*math.pi*k/n_spokes
        a = (c[0] + diag*math.cos(ang), c[1] + diag*math.sin(ang))
        segs.extend(_to_segments(poly.intersection(LineString([c, a]))))
    return segs

def pattern_spiral(poly, max_turns):
    pt = poly.representative_point(); cx, cy = pt.x, pt.y
    xmin, ymin, xmax, ymax = poly.bounds
    rmax = max(xmax-xmin, ymax-ymin) * 0.6
    t = np.linspace(0, max_turns*2*np.pi, 600)
    r = rmax * t / (max_turns*2*np.pi)
    return _to_segments(poly.intersection(
        LineString(list(zip(cx + r*np.cos(t), cy + r*np.sin(t))))))

def pattern_concentric(poly, spacing):
    pt = poly.representative_point()
    cx, cy = pt.x, pt.y
    boundary = np.asarray(poly.exterior.coords)
    segs = []
    for k in range(1, 6):
        s = 1 - k*(spacing/2.0)
        if s <= 0.05: break
        ring = (boundary - np.array([cx, cy])) * s + np.array([cx, cy])
        segs.append([tuple(p) for p in ring])
    return segs

def insc(p): return p.representative_point().distance(p.boundary)

def choose_pattern(poly, poly_idx):
    xmin, ymin, xmax, ymax = poly.bounds
    w, h = xmax-xmin, ymax-ymin
    aspect = w/h if h > 0 else 1.0
    area = poly.area
    r_insc = insc(poly)
    spacing = max(0.18, min(0.55, 0.18 + r_insc*0.35))
    if aspect > 2.2 or aspect < 0.45:
        return pattern_hatching(poly, spacing, angle_deg=(90 if aspect<1 else 0)+90)
    if area > 6.0 and r_insc > 1.1:
        pid = poly_idx % 4
        if pid==0: return pattern_spiral(poly, max_turns=5)
        if pid==1: return pattern_concentric(poly, spacing=0.18)
        if pid==2: return pattern_radial(poly, n_spokes=28)
        return pattern_scales(poly, spacing=0.50, radius=0.30)
    if area > 2.5:
        pid = poly_idx % 4
        if pid==0: return pattern_scales(poly, spacing=spacing+0.15, radius=spacing*0.7)
        if pid==1: return pattern_waves(poly, spacing=spacing+0.08, amp=spacing*0.4, freq=1.5)
        if pid==2: return pattern_dots(poly, spacing=spacing+0.05)
        return pattern_crosshatch(poly, spacing=spacing+0.10, angle_deg=(poly_idx*23)%90)
    pid = poly_idx % 3
    if pid==0: return pattern_hatching(poly, spacing*0.8, angle_deg=(poly_idx*37)%180)
    if pid==1: return pattern_dots(poly, spacing*0.9, dot_r=0.04)
    return pattern_crosshatch(poly, spacing*0.9, angle_deg=(poly_idx*53)%90)


PASTEL = [
    "#F7B7A3", "#FFD6A5", "#FDFFB6", "#CAFFBF",
    "#9BF6FF", "#A0C4FF", "#BDB2FF", "#FFC6FF",
]


# =========================================================================
#  MAIN RENDER PIPELINE
# =========================================================================
def render_full_page(raw_curves, family_name, page_id, out_dir):
    """Full v7-style A4 rendering. Writes uncolored + colored PNGs + uncolored PDF."""

    # fit
    all_pts = np.vstack(raw_curves)
    xmin, ymin = all_pts.min(axis=0); xmax, ymax = all_pts.max(axis=0)
    cx0, cy0 = (xmin+xmax)/2, (ymin+ymax)/2
    bw = DRAW_X_MAX - DRAW_X_MIN; bh = DRAW_Y_MAX - DRAW_Y_MIN
    bcx = (DRAW_X_MIN+DRAW_X_MAX)/2; bcy = (DRAW_Y_MIN+DRAW_Y_MAX)/2
    PAD = 0.94
    sx = (bw/(xmax-xmin))*PAD; sy = (bh/(ymax-ymin))*PAD
    def fit(pts):
        out = np.empty_like(pts)
        out[:,0] = (pts[:,0]-cx0)*sx + bcx
        out[:,1] = (pts[:,1]-cy0)*sy + bcy
        return out
    curves = [fit(c) for c in raw_curves]

    # polygonize
    merged = unary_union([LineString(c) for c in curves])
    all_polys = list(polygonize(merged))
    tangle_polys = [(i, p) for i, p in enumerate(all_polys)
                    if p.area >= 0.35 and insc(p) >= 0.22]

    # Dense-region mask: only polygons that are BOTH tiny AND part of a
    # cluster of tiny neighbors. This avoids clipping isolated thin
    # slivers (which weren't a problem) while still removing genuine
    # "macro lines piled on top of each other" zones.
    TINY_AREA = 0.07
    TINY_INSC = 0.09
    CLUSTER_NEIGHBORS = 4
    CLUSTER_RADIUS = 0.30
    tiny = [p for p in all_polys if p.area < TINY_AREA or insc(p) < TINY_INSC]
    if tiny:
        tiny_tree = STRtree(tiny)
        truly_dense = []
        for p in tiny:
            nearby = list(tiny_tree.query(p.buffer(CLUSTER_RADIUS)))
            if len(nearby) >= CLUSTER_NEIGHBORS:
                truly_dense.append(p)
        dense_mask = unary_union(truly_dense).buffer(0.008) if truly_dense else None
        if dense_mask is not None and dense_mask.is_empty:
            dense_mask = None
    else:
        dense_mask = None

    # tangle segments
    tangle_segs = {}
    for poly_idx, poly in tangle_polys:
        tangle_segs[poly_idx] = choose_pattern(poly, poly_idx)

    # exterior dots
    interior = unary_union(all_polys) if all_polys else None
    ext_dot_spacing = 0.42; ext_dot_r = 0.035
    ext_dots = []
    y = DRAW_Y_MIN; row = 0
    while y <= DRAW_Y_MAX:
        offset = (ext_dot_spacing/2) if (row % 2) else 0
        x = DRAW_X_MIN + offset
        while x <= DRAW_X_MAX:
            p = Point(x, y)
            if SAFE_BOX.contains(p) and (interior is None or not interior.intersects(p.buffer(0.01))):
                ext_dots.append((x, y))
            x += ext_dot_spacing
        y += ext_dot_spacing*0.9; row += 1

    # wavy frame
    def frame_wave():
        inset = 0.35
        xmin_, ymin_ = DRAW_X_MIN + inset, DRAW_Y_MIN + inset
        xmax_, ymax_ = DRAW_X_MAX - inset, DRAW_Y_MAX - inset
        amp, freq = 0.10, 14
        segs = []
        xs = np.linspace(xmin_, xmax_, 800)
        segs.append(list(zip(xs, ymax_ + amp*np.sin(np.linspace(0, freq*np.pi, 800)))))
        segs.append(list(zip(xs, ymin_ - amp*np.sin(np.linspace(0, freq*np.pi, 800)))))
        ys = np.linspace(ymin_, ymax_, 1000)
        segs.append(list(zip(xmax_ + amp*np.sin(np.linspace(0, freq*np.pi, 1000)), ys)))
        segs.append(list(zip(xmin_ - amp*np.sin(np.linspace(0, freq*np.pi, 1000)), ys)))
        return segs
    frame_segs = frame_wave()

    # graph color
    N = len(all_polys)
    adj = [set() for _ in range(N)]
    if N:
        tree = STRtree(all_polys)
        for i, p in enumerate(all_polys):
            for j in tree.query(p.buffer(0.05)):
                j = int(j)
                if j <= i: continue
                inter = p.boundary.intersection(all_polys[j].boundary)
                try: ln = inter.length
                except Exception: ln = 0.0
                if not inter.is_empty and ln > 1e-3:
                    adj[i].add(j); adj[j].add(i)
    usage = [0]*len(PASTEL); color_idx = [-1]*N
    order = sorted(range(N), key=lambda i: -len(adj[i]))
    for i in order:
        forb = {color_idx[j] for j in adj[i] if color_idx[j] >= 0}
        allow = [c for c in range(len(PASTEL)) if c not in forb] or list(range(len(PASTEL)))
        chosen = min(allow, key=lambda c: (usage[c], c))
        color_idx[i] = chosen; usage[chosen] += 1

    def setup_axes():
        fig, ax = plt.subplots(figsize=(FIG_W_IN, FIG_H_IN))
        ax.set_xlim(*AX_X); ax.set_ylim(*AX_Y)
        ax.set_aspect("equal"); ax.axis("off")
        return fig, ax

    def draw_brand(ax):
        # Decorative frame sits inside the trim (+-8.5 / +-11) with margin;
        # all text stays within the 0.5" safety box (+-7.5 / +-10).
        bx = [-7.85, 7.85, 7.85, -7.85, -7.85]
        by = [-10.4, -10.4, 10.4, 10.4, -10.4]
        ax.plot(bx, by, color="black", lw=0.5)
        ax.text(0, 9.98, "m a t h r e l a x i n g",
                ha="center", va="center",
                fontsize=10, color="#333333", family="serif", weight="bold")
        ax.text(0, 9.62, "MATHEMATICAL TANGLE ART",
                ha="center", va="center",
                fontsize=6, color="#777777", family="sans-serif")
        ax.text(0, -9.95,
                f"{family_name}   |   page {page_id}",
                ha="center", va="center",
                fontsize=6, color="#999999", family="serif", style="italic")

    def draw_linework(ax):
        # exterior dots
        for x, y in ext_dots:
            th = np.linspace(0, 2*np.pi, 14)
            ax.fill(x + ext_dot_r*np.cos(th), y + ext_dot_r*np.sin(th), color="#555")
        # frame
        for seg in frame_segs:
            seg = np.asarray(seg)
            ax.plot(seg[:,0], seg[:,1], color="#1a1a1a", lw=0.6)
        # tangles
        for poly_idx, segs in tangle_segs.items():
            for seg in segs:
                if len(seg) < 2: continue
                seg = np.asarray(seg)
                ax.plot(seg[:,0], seg[:,1], color="#1a1a1a", lw=0.5, solid_capstyle="round")
        # Macro curves — two-pass so region boundaries are ALWAYS visible:
        #   1) Hairline pass: every macro curve at lw=0.35 — always drawn
        #      so the contour between colored regions is never lost, even
        #      inside dense-clipped zones.
        #   2) Bold pass: lw=1.3, but skipped through dense_mask zones so
        #      those areas don't become a black mass.
        for c in curves:
            ax.plot(c[:,0], c[:,1], color="#1a1a1a", lw=0.35, alpha=0.9,
                    solid_capstyle="round", solid_joinstyle="round")
        for c in curves:
            if dense_mask is None:
                ax.plot(c[:,0], c[:,1], color="black", lw=1.3,
                        solid_capstyle="round", solid_joinstyle="round")
            else:
                clipped = LineString(c).difference(dense_mask)
                for seg in _to_segments(clipped):
                    if len(seg) < 2: continue
                    seg = np.asarray(seg)
                    ax.plot(seg[:,0], seg[:,1], color="black", lw=1.3,
                            solid_capstyle="round", solid_joinstyle="round")

    # uncolored — saved at the EXACT 8.75 x 11.25 bleed page size (no tight
    # crop) so the artwork drops 1:1 into the Lulu interior, edge-to-edge.
    fig, ax = setup_axes()
    draw_linework(ax); draw_brand(ax)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    base = os.path.join(out_dir, f"page_{page_id}_{family_name.replace(' ','_').replace('+','plus')}")
    fig.savefig(base + ".png", dpi=300, facecolor="white")
    with PdfPages(base + ".pdf") as pdf:
        pdf.savefig(fig, facecolor="white")
    plt.close(fig)

    # colored
    fig, ax = setup_axes()
    for i, p in enumerate(all_polys):
        if p.geom_type != "Polygon": continue
        ax.add_patch(MplPolygon(list(p.exterior.coords), closed=True,
                                facecolor=PASTEL[color_idx[i]], edgecolor="none"))
    draw_linework(ax); draw_brand(ax)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(base + "_colored.png", dpi=300, facecolor="white")
    plt.close(fig)

    print(f"[{family_name}] tangles={len(tangle_polys)}  polys={N}  -> {base}.*")


# =========================================================================
#  5 REPRESENTATIVE PAGES (one per family) — demo only, runs when this file
#  is executed directly. Skipped on import (regenerate_all.py imports it).
# =========================================================================
_DEMO_PAGES = [
    ("Lissajous", [
        lissajous(7.5, 9.5, 1, 1, np.pi/2),
        lissajous(7.0, 8.5, 5, 4, np.pi/2),
        lissajous(6.0, 7.5, 5, 4, np.pi/4),
        circle_curve(2.0),
    ]),
    ("Rosa + spirograph", [
        circle_curve(8.0),
        rose(k=5, a=6.8),
        hypotrochoid(R=7, r=3, d=5),
        hypotrochoid(R=8, r=5, d=4),
        circle_curve(2.6),
    ]),
    ("Epicicloides", [
        circle_curve(8.0),
        epicycloid(R=7, r=1),
        epicycloid(R=5, r=2),
        circle_curve(2.5),
    ]),
    ("Hipocicloides", [
        circle_curve(8.0),
        hypocycloid(R=5, r=2),
        hypocycloid(R=8, r=3),
        rose(k=5, a=4.0),
        circle_curve(2.0),
    ]),
    ("Exoticas", [
        circle_curve(8.0),
        lemniscate_bernoulli(a=7.0, rotation=0),
        lemniscate_bernoulli(a=7.0, rotation=np.pi/3),
        lemniscate_bernoulli(a=7.0, rotation=2*np.pi/3),
        rose(k=6, a=3.0),
    ]),
]

if __name__ == "__main__":
    OUT_DIR = "/root/coloring_prototype/by_family"
    os.makedirs(OUT_DIR, exist_ok=True)
    for i, (fam, curves) in enumerate(_DEMO_PAGES, 1):
        render_full_page(curves, fam, page_id=f"{i:02d}", out_dir=OUT_DIR)
    print("\nDone. Files in:", OUT_DIR)
