"""
Fractal Flora — Etsy promo video
Coloring animation via brush-stroke zones that expand progressively,
simulating someone coloring area by area with colored pencils.
"""

import fitz
import numpy as np
import subprocess, os, shutil, random, math
from PIL import Image
from scipy.ndimage import gaussian_filter

PDF_PATH   = "/var/www/mathrelaxing.store/static/downloads/fractal-flora-coloring-book/interior.pdf"
LOGO_PATH  = "/var/www/mathrelaxing.store/static/img/logo.png"
AUDIO_SRC  = "/var/www/mathrelaxing.store/static/downloads/fractal-flora-coloring-book/promo.mp4"
OUT_PATH   = "/var/www/mathrelaxing.store/static/downloads/digital/fractal_flora_promo_etsy.mp4"
FRAMES_DIR = "/tmp/ff_frames"

W, H  = 1080, 1920
FPS   = 30

random.seed(7)
np.random.seed(7)

PAGE_INDICES = [3, 9, 16, 24, 33]

PALETTES = [
    [(255,170,150),(150,200,255),(165,240,175),(255,225,130),(215,165,255),(255,190,120)],
    [(195,162,255),(255,182,132),(140,225,210),(255,162,188),(170,230,152),(255,210,148)],
    [(162,230,188),(255,192,152),(188,178,255),(138,218,235),(255,178,178),(192,240,164)],
    [(255,178,178),(178,220,255),(198,252,188),(255,224,138),(188,168,255),(152,225,205)],
    [(188,198,255),(255,185,158),(162,238,205),(255,196,212),(178,245,195),(255,218,132)],
]

os.makedirs(FRAMES_DIR, exist_ok=True)
frame_idx = [0]

def save_frame(img):
    path = os.path.join(FRAMES_DIR, f"frame_{frame_idx[0]:05d}.png")
    img.convert("RGB").save(path)
    frame_idx[0] += 1

def ease_out(t):
    return 1 - (1 - t) ** 2.2

def ease_in_out(t):
    return t * t * (3 - 2 * t)

# ── Render page ──────────────────────────────────────────────────────────────

def render_page(doc, idx, target_w=820):
    page = doc[idx]
    mat  = fitz.Matrix(target_w / page.rect.width, target_w / page.rect.width)
    pix  = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

# ── Build zone-colored version ───────────────────────────────────────────────

def make_zone_colored(img, palette):
    """Smooth Voronoi color zones — watercolor wash effect on white areas."""
    arr = np.array(img).astype(np.float32)
    h, w = arr.shape[:2]

    # Color zone centers (relative positions)
    rel_centers = [
        (0.25, 0.20), (0.75, 0.18), (0.50, 0.50),
        (0.20, 0.78), (0.80, 0.75), (0.50, 0.88),
    ]
    centers = [(cx * w, cy * h) for cx, cy in rel_centers]
    colors  = [palette[i % len(palette)] for i in range(len(centers))]

    ys, xs = np.mgrid[0:h, 0:w]
    color_field = np.zeros((h, w, 3), dtype=np.float32)
    weight_sum  = np.zeros((h, w),    dtype=np.float32)

    for (cx, cy), col in zip(centers, colors):
        dist   = np.sqrt((xs - cx)**2 + (ys - cy)**2)
        weight = 1.0 / (dist + 60) ** 1.8
        for c, v in enumerate(col):
            color_field[:, :, c] += weight * v
        weight_sum += weight

    for c in range(3):
        color_field[:, :, c] /= weight_sum

    # Slightly blur for watercolor feel
    for c in range(3):
        color_field[:, :, c] = gaussian_filter(color_field[:, :, c], sigma=12)

    # Apply only on light (non-line) areas
    brightness = arr.mean(axis=2)
    strength   = np.clip((brightness - 140) / 100, 0, 1)  # 0 on lines, 1 on white

    colored = arr.copy()
    for c in range(3):
        colored[:, :, c] = (
            arr[:, :, c] * (1 - strength * 0.82) +
            color_field[:, :, c] * strength * 0.82
        )
    return Image.fromarray(np.clip(colored, 0, 255).astype(np.uint8))

# ── Brush stroke mask ────────────────────────────────────────────────────────

def stroke_mask(h, w, cx, cy, rx, ry, angle=0.0):
    """Soft elliptical mask centered at (cx, cy)."""
    ys, xs = np.mgrid[0:h, 0:w]
    cos_a  = math.cos(angle)
    sin_a  = math.sin(angle)
    dx     = (xs - cx) * cos_a + (ys - cy) * sin_a
    dy     = -(xs - cx) * sin_a + (ys - cy) * cos_a
    dist   = np.sqrt((dx / rx) ** 2 + (dy / ry) ** 2)
    # Smooth edge
    mask   = np.clip(1.0 - (dist - 0.75) / 0.35, 0.0, 1.0)
    return mask.astype(np.float32)

# ── Canvas helpers ───────────────────────────────────────────────────────────

def make_canvas(page_arr):
    img    = Image.fromarray(np.clip(page_arr, 0, 255).astype(np.uint8))
    canvas = Image.new("RGB", (W, H), (18, 23, 46))
    margin = 50
    tw     = W - margin * 2
    ratio  = tw / img.width
    th     = int(img.height * ratio)
    img_r  = img.resize((tw, th), Image.LANCZOS)
    yo     = (H - th) // 2
    canvas.paste(img_r, (margin, yo))
    return canvas

def add_logo(canvas, alpha=1.0):
    logo = Image.open(LOGO_PATH).convert("RGBA")
    lw   = 200
    lh   = int(logo.height * lw / logo.width)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    if alpha < 1.0:
        r, g, b, a = logo.split()
        a = a.point(lambda p: int(p * alpha))
        logo = Image.merge("RGBA", (r, g, b, a))
    out  = canvas.copy().convert("RGBA")
    out.paste(logo, ((W - lw) // 2, H - lh - 70), logo)
    return out.convert("RGB")

def lerp_canvas(ca, cb, t):
    a = np.array(ca).astype(np.float32)
    b = np.array(cb).astype(np.float32)
    return Image.fromarray(np.clip(a*(1-t)+b*t, 0, 255).astype(np.uint8))

# ── Define strokes per page ──────────────────────────────────────────────────
# Each stroke: (cx_rel, cy_rel, rx_rel, ry_rel, angle_deg)
# Coordinates relative to page image size

STROKE_SETS = [
    # Page 0 — sweep diagonally top-left to bottom-right
    [(0.25,0.20,0.32,0.28, 15),(0.70,0.25,0.30,0.25,-10),
     (0.45,0.52,0.35,0.30,  5),(0.22,0.78,0.28,0.32,-15),
     (0.75,0.80,0.30,0.28, 10)],
    # Page 1 — horizontal sweep
    [(0.20,0.30,0.28,0.35,  0),(0.75,0.28,0.28,0.32,  5),
     (0.50,0.55,0.40,0.28,-5),(0.18,0.80,0.30,0.28, 10),
     (0.80,0.78,0.28,0.32,-8)],
    # Page 2 — radial from center
    [(0.50,0.50,0.42,0.38,  0),(0.20,0.22,0.30,0.28, 12),
     (0.80,0.20,0.28,0.30,-12),(0.18,0.80,0.30,0.28,  8),
     (0.80,0.80,0.28,0.30, -8)],
    # Page 3 — zigzag
    [(0.22,0.25,0.32,0.28,-10),(0.72,0.35,0.30,0.28,  8),
     (0.30,0.60,0.35,0.30,-5),(0.70,0.72,0.32,0.28, 10),
     (0.45,0.88,0.35,0.25,  0)],
    # Page 4 — spiral-ish
    [(0.50,0.30,0.38,0.28,  0),(0.78,0.55,0.28,0.32,-10),
     (0.50,0.70,0.38,0.28,  5),(0.22,0.48,0.28,0.32, 10),
     (0.50,0.50,0.22,0.22,  0)],
]

STROKE_EXPAND  = 7    # frames to expand a stroke (quick fill)
STROKE_HOLD    = 3    # frames to hold after stroke
CROSS_FRAMES   = int(0.32 * FPS)
HOLD_BW        = int(0.38 * FPS)
COLORED_HOLD   = int(0.28 * FPS)
LOGO_FRAMES    = int(0.65 * FPS)
FADE_FRAMES    = int(0.48 * FPS)

# ── Main ─────────────────────────────────────────────────────────────────────

doc = fitz.open(PDF_PATH)

print("Rendering pages...")
pages    = [render_page(doc, i) for i in PAGE_INDICES]
colored  = [make_zone_colored(p, PALETTES[i]) for i, p in enumerate(pages)]
page_arrs   = [np.array(p).astype(np.float32) for p in pages]
col_arrs    = [np.array(c).astype(np.float32) for c in colored]

print("Generating frames...")

full_canvas = None

for pi in range(len(PAGE_INDICES)):
    line_arr  = page_arrs[pi]
    col_arr   = col_arrs[pi]
    ph, pw    = line_arr.shape[:2]
    strokes   = STROKE_SETS[pi]

    # Start: pure line art
    current = line_arr.copy()

    # Hold B&W
    bw_canvas = make_canvas(current)
    for _ in range(HOLD_BW):
        save_frame(bw_canvas)

    # Stroke by stroke
    for si, (cxr, cyr, rxr, ryr, ang_deg) in enumerate(strokes):
        cx  = cxr * pw
        cy  = cyr * ph
        rx  = rxr * pw
        ry  = ryr * ph
        ang = math.radians(ang_deg)

        # Expand stroke over STROKE_EXPAND frames
        for f in range(STROKE_EXPAND):
            t    = ease_out((f + 1) / STROKE_EXPAND)
            mask = stroke_mask(ph, pw, cx, cy, rx * t, ry * t, ang)
            blended = current.copy()
            for c in range(3):
                blended[:, :, c] = (
                    current[:, :, c] * (1 - mask) +
                    col_arr[:, :, c] * mask
                )
            save_frame(make_canvas(blended))

        # Update current state with full stroke
        full_mask = stroke_mask(ph, pw, cx, cy, rx, ry, ang)
        for c in range(3):
            current[:, :, c] = (
                current[:, :, c] * (1 - full_mask) +
                col_arr[:, :, c] * full_mask
            )

        # Brief hold
        cv = make_canvas(current)
        for _ in range(STROKE_HOLD):
            save_frame(cv)

    # Hold fully colored
    full_canvas = make_canvas(current)
    for _ in range(COLORED_HOLD):
        save_frame(full_canvas)

    # Crossfade to next page
    if pi < len(PAGE_INDICES) - 1:
        next_bw = make_canvas(page_arrs[pi + 1])
        for f in range(CROSS_FRAMES):
            t = ease_in_out(f / max(CROSS_FRAMES - 1, 1))
            save_frame(lerp_canvas(full_canvas, next_bw, t))

# Logo fade-in
for f in range(LOGO_FRAMES):
    t = ease_out(f / max(LOGO_FRAMES - 1, 1))
    save_frame(add_logo(full_canvas, alpha=t))
for _ in range(int(0.22 * FPS)):
    save_frame(add_logo(full_canvas))

# Fade to black
black      = Image.new("RGB", (W, H), (0, 0, 0))
logo_final = add_logo(full_canvas)
for f in range(FADE_FRAMES):
    t = ease_in_out(f / max(FADE_FRAMES - 1, 1))
    save_frame(lerp_canvas(logo_final, black, t))

total = frame_idx[0]
print(f"Frames: {total} ({total/FPS:.1f}s) — trimming to 15s")

# ── Compile ──────────────────────────────────────────────────────────────────
print("Compiling...")

audio_tmp = "/tmp/ff_audio.aac"
subprocess.run([
    "ffmpeg", "-y", "-i", AUDIO_SRC,
    "-t", "15", "-vn", "-acodec", "aac", "-b:a", "128k", audio_tmp
], capture_output=True)
has_audio = os.path.exists(audio_tmp) and os.path.getsize(audio_tmp) > 1000

cmd = ["ffmpeg", "-y", "-framerate", str(FPS),
       "-i", os.path.join(FRAMES_DIR, "frame_%05d.png")]
if has_audio:
    cmd += ["-i", audio_tmp]
cmd += ["-t", "15", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
if has_audio:
    cmd += ["-c:a", "aac", "-shortest"]
cmd.append(OUT_PATH)

r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode == 0:
    mb = os.path.getsize(OUT_PATH) / 1024 / 1024
    print(f"Done! {mb:.1f} MB  →  {OUT_PATH}")
else:
    print("Error:", r.stderr[-500:])

shutil.rmtree(FRAMES_DIR)
print("Cleaned up.")
