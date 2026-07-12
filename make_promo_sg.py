"""
Sacred Geometry & Topology — Etsy promo video
Low-poly color-by-number: facets fill in one by one with 3D-shaded palette,
simulating completing the color-by-number model. ~15s, 1080x1920, 30fps.
"""

import fitz
import numpy as np
import subprocess, os, shutil, math, random
from PIL import Image
from scipy.ndimage import label, binary_dilation

INTERIOR = "/var/www/mathrelaxing.store/static/downloads/sacred-math-coloring-book/interior.pdf"
LOGO     = "/var/www/mathrelaxing.store/static/img/logo.png"
AUDIO_SRC= "/var/www/mathrelaxing.store/static/downloads/fractal-flora-coloring-book/promo.mp4"
OUT      = "/var/www/mathrelaxing.store/static/downloads/digital/sacred_geometry_promo_etsy.mp4"
FRAMES   = "/tmp/sg_frames"

W, H = 1080, 1920
FPS  = 30
random.seed(11); np.random.seed(11)

# Pages: variety of shapes (torus, knot, complex, sphere)
PAGE_INDICES = [5, 20, 36, 48]

# 3D-shaded palettes (light -> dark for gradient shading)
PALETTES = [
    [(216,234,247),(150,196,224),(74,123,168),(26,61,107),(13,35,71)],     # ocean
    [(255,226,150),(255,168,88),(230,96,68),(150,48,82),(70,28,66)],        # sunset
    [(214,242,220),(140,210,170),(64,158,128),(28,98,88),(14,54,52)],       # emerald
    [(232,216,246),(190,158,226),(138,98,190),(88,52,138),(48,28,84)],      # amethyst
]

os.makedirs(FRAMES, exist_ok=True)
fidx = [0]
def save(img):
    img.convert("RGB").save(os.path.join(FRAMES, f"f_{fidx[0]:05d}.png"))
    fidx[0] += 1

def ease_out(t): return 1 - (1-t)**2.2
def ease_io(t):  return t*t*(3-2*t)

def render(doc, idx, tw=900):
    p = doc[idx]
    s = tw / p.rect.width
    pix = p.get_pixmap(matrix=fitz.Matrix(s, s), colorspace=fitz.csRGB, alpha=False)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).copy()

def design_bbox(arr):
    """Bounding box of the wireframe design, excluding bottom legend strip."""
    gray = arr.mean(axis=2)
    h, w = gray.shape
    region = gray[: int(h*0.83), :]            # exclude legend/title strip
    dark = region < 120
    ys, xs = np.where(dark)
    if len(xs) == 0:
        return 0, 0, w, h
    pad = int(0.04 * max(w, h))
    x0 = max(0, xs.min()-pad); x1 = min(w, xs.max()+pad)
    y0 = max(0, ys.min()-pad); y1 = min(int(h*0.83), ys.max()+pad)
    return x0, y0, x1, y1

def find_regions(arr):
    """Label closed facets (complement of black wireframe lines)."""
    gray  = arr.mean(axis=2)
    lines = binary_dilation(gray < 120, iterations=1)
    lbl, n = label(~lines)
    h, w = gray.shape
    # background = label touching the border with largest area
    border_labels = set(lbl[0,:]) | set(lbl[-1,:]) | set(lbl[:,0]) | set(lbl[:,-1])
    regions = []
    for i in range(1, n+1):
        if i in border_labels:
            continue
        mask = lbl == i
        a = mask.sum()
        if a < 60:
            continue
        ys, xs = np.where(mask)
        regions.append((mask, xs.mean(), ys.mean(), a))
    return regions

def shade_color(palette, t, jitter=0.10):
    """Map t in [0,1] to an interpolated palette color, with slight jitter."""
    t = min(max(t + random.uniform(-jitter, jitter), 0), 1)
    pos = t * (len(palette)-1)
    i = int(pos); f = pos - i
    if i >= len(palette)-1:
        return palette[-1]
    a, b = palette[i], palette[i+1]
    return tuple(a[c]*(1-f) + b[c]*f for c in range(3))

def make_canvas(arr):
    img = Image.fromarray(np.clip(arr,0,255).astype(np.uint8))
    canvas = Image.new("RGB", (W, H), (16, 20, 40))
    margin = 70
    tw = W - margin*2
    ratio = tw / img.width
    th = int(img.height * ratio)
    if th > H - 360:                            # keep room top/bottom
        th = H - 360; tw = int(img.width * th / img.height)
        ratio = th / img.height
    img_r = img.resize((tw, th), Image.LANCZOS)
    canvas.paste(img_r, ((W-tw)//2, (H-th)//2))
    return canvas

def add_logo(canvas, alpha=1.0):
    logo = Image.open(LOGO).convert("RGBA")
    lw = 200; lh = int(logo.height*lw/logo.width)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    if alpha < 1:
        r,g,b,a = logo.split(); a = a.point(lambda p:int(p*alpha))
        logo = Image.merge("RGBA",(r,g,b,a))
    out = canvas.copy().convert("RGBA")
    out.paste(logo, ((W-lw)//2, H-lh-90), logo)
    return out.convert("RGB")

def lerp(ca, cb, t):
    a = np.array(ca,np.float32); b = np.array(cb,np.float32)
    return Image.fromarray(np.clip(a*(1-t)+b*t,0,255).astype(np.uint8))

# ── Build ────────────────────────────────────────────────────────────────────
doc = fitz.open(INTERIOR)
print("Preparing pages...")

prepared = []
for pi, pidx in enumerate(PAGE_INDICES):
    full = render(doc, pidx, tw=900)
    x0,y0,x1,y1 = design_bbox(full)
    crop = full[y0:y1, x0:x1].copy()
    regions = find_regions(crop)
    # order facets along a diagonal wave for organic fill
    diag = [(r[1]+r[2]) for r in regions]
    order = np.argsort(diag)
    regions = [regions[i] for i in order]
    # precompute shaded target colors (gradient along diagonal => 3D look)
    if regions:
        dvals = np.array([regions[i][1]+regions[i][2] for i in range(len(regions))], np.float32)
        dmin, dmax = dvals.min(), dvals.max()+1e-6
    pal = PALETTES[pi % len(PALETTES)]
    colors = []
    for (mask, cx, cy, a) in regions:
        t = (cx+cy - dmin)/(dmax-dmin)
        colors.append(shade_color(pal, t))
    prepared.append((crop.astype(np.float32), regions, colors))
    print(f"  page {pidx}: {len(regions)} facets")

print("Rendering frames...")
HOLD_BW    = int(0.40*FPS)   # line-art hold before coloring
FILL_FRAMES= int(2.5*FPS)    # fixed frames to fill ANY page (deterministic)
CROSS      = int(0.34*FPS)
COL_HOLD   = int(0.45*FPS)   # hold on completed page
LOGO_F     = int(0.65*FPS)
FADE_F     = int(0.5*FPS)

last_full = None
for pi, (line_arr, regions, colors) in enumerate(prepared):
    current = line_arr.copy()
    n = len(regions)

    bw = make_canvas(current)
    for _ in range(HOLD_BW if pi==0 else HOLD_BW//2):
        save(bw)

    # Fill facets over a FIXED number of frames regardless of facet count.
    # Reveal `per_step` facets each frame -> always ~FILL_FRAMES frames.
    per_step = max(1, math.ceil(n / FILL_FRAMES))
    i = 0
    while i < n:
        for (mask,_,_,_), col in zip(regions[i:i+per_step], colors[i:i+per_step]):
            for c in range(3):
                current[:,:,c][mask] = col[c]
        save(make_canvas(current))
        i += per_step

    full = make_canvas(current)
    for _ in range(COL_HOLD):
        save(full)
    last_full = full

    if pi < len(prepared)-1:
        nxt = make_canvas(prepared[pi+1][0])
        for f in range(CROSS):
            save(lerp(full, nxt, ease_io(f/max(CROSS-1,1))))

# logo + fade
for f in range(LOGO_F):
    save(add_logo(last_full, ease_out(f/max(LOGO_F-1,1))))
for _ in range(int(0.25*FPS)):
    save(add_logo(last_full))
black = Image.new("RGB",(W,H),(0,0,0)); lf = add_logo(last_full)
for f in range(FADE_F):
    save(lerp(lf, black, ease_io(f/max(FADE_F-1,1))))

print(f"Frames: {fidx[0]} ({fidx[0]/FPS:.1f}s)")

# ── Compile ──────────────────────────────────────────────────────────────────
print("Compiling...")
audio = "/tmp/sg_audio.aac"
subprocess.run(["ffmpeg","-y","-i",AUDIO_SRC,"-map","0:a:0","-t","15","-vn",
                "-acodec","aac","-b:a","160k",audio], capture_output=True)
has_a = os.path.exists(audio) and os.path.getsize(audio) > 1000

cmd = ["ffmpeg","-y","-framerate",str(FPS),"-i",os.path.join(FRAMES,"f_%05d.png")]
if has_a: cmd += ["-i",audio]
cmd += ["-t","15","-c:v","libx264","-preset","slow","-crf","18",
        "-pix_fmt","yuv420p","-movflags","+faststart"]
if has_a: cmd += ["-c:a","aac","-shortest"]
cmd.append(OUT)
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode==0:
    print(f"Done! {os.path.getsize(OUT)/1024/1024:.1f} MB -> {OUT}")
else:
    print("ERR:", r.stderr[-600:])
shutil.rmtree(FRAMES)
print("Cleaned.")
