#!/usr/bin/env python3
"""Fractal Flora promo video v2 — flood-fill coloring animation.

For each page:
  1. Line art reveals via circle wipe
  2. Enclosed regions are flood-filled one by one with different colors
  3. Hold the fully coloured page

Uses PIL floodfill to detect and paint interior regions.
"""
import math, os, shutil, subprocess, sys, random
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, "/var/www/mathrelaxing.store")
from scripts.gen_l_systems_book import SPECS, generate_lsystem, interpret_lsystem

OUT_MP4 = "/var/www/mathrelaxing.store/static/downloads/fractal-flora-coloring-book/promo.mp4"
FRAMES  = Path("/tmp/fractal_flora_promo_frames")
AUDIO   = "/tmp/bgm.mp3"
FPS     = 24
W, H    = 1080, 1920

CARD_H  = 980
CARD_W  = round(CARD_H * 8.5 / 11)
CARD_X  = (W - CARD_W) // 2
CARD_Y  = 380
CARD_RAD = 24

BG_TOP  = (17, 34, 29)
BG_BOT  = (8,  18, 14)
GOLD    = (200, 169, 110)
CREAM   = (237, 230, 214)
WHITE   = (255, 255, 255)

# Vibrant coloring palette (like colored pencils)
FILL_COLORS = [
    (126, 207, 179),  # teal
    (232, 93, 117),   # coral
    (168, 85, 247),   # purple
    (245, 158, 11),   # amber
    (6, 182, 212),    # cyan
    (236, 72, 153),   # pink
    (52, 211, 153),   # emerald
    (139, 92, 246),   # violet
    (251, 191, 36),   # yellow
    (239, 68, 68),    # red
    (59, 130, 246),   # blue
    (16, 185, 129),   # green
    (244, 114, 182),  # light pink
    (167, 139, 250),  # lavender
    (253, 224, 71),   # lemon
    (248, 113, 113),  # salmon
    (96, 165, 250),   # sky blue
    (74, 222, 128),   # lime
]

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)

def make_background():
    top = np.array(BG_TOP, float); bot = np.array(BG_BOT, float)
    col = top[None, :] + (bot - top)[None, :] * (np.arange(H)[:, None] / (H - 1))
    return Image.fromarray(np.repeat(col[:, None, :], W, axis=1).astype(np.uint8), "RGB")

def card_mask():
    m = Image.new("L", (CARD_W, CARD_H), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, CARD_W-1, CARD_H-1], radius=CARD_RAD, fill=255)
    return m

def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)

def draw_text_centered(canvas, y, text, f, color, alpha=1.0):
    d = ImageDraw.Draw(canvas, "RGBA")
    c = (*color, int(255 * alpha))
    d.text((W / 2, y), text, font=f, fill=c, anchor="mm")

# ── Render L-system as line art ────────────────────────────────────────
def render_lsystem_pil(spec, w, h, line_color="black", bg_color="white", lw=3):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import io

    name, axiom, rules, iters, angle, start_angle = spec
    seq = generate_lsystem(axiom, rules, iters)
    segments = interpret_lsystem(seq, angle, start_angle=start_angle)

    if not segments:
        return Image.new("RGB", (w, h), bg_color)

    min_x = min(min(seg[0]) for seg in segments)
    max_x = max(max(seg[0]) for seg in segments)
    min_y = min(min(seg[1]) for seg in segments)
    max_y = max(max(seg[1]) for seg in segments)
    width_ = max(max_x - min_x, 1)
    height_ = max(max_y - min_y, 1)
    scale = 1.85 / max(width_, height_)

    dpi = 100
    fig = plt.figure(figsize=(w/dpi, h/dpi), dpi=dpi)
    ax = fig.add_axes([0.05, 0.05, 0.9, 0.9])
    ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05)
    ax.set_aspect("equal"); ax.axis("off")
    fig.set_facecolor(bg_color)

    for seg_x, seg_y in segments:
        sx = [(x - min_x - width_/2) * scale for x in seg_x]
        sy = [(y - min_y - height_/2) * scale for y in seg_y]
        ax.plot(sx, sy, color=line_color, lw=lw,
                solid_capstyle='round', solid_joinstyle='round')

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=bg_color)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB").resize((w, h), Image.LANCZOS)

# ── Flood-fill to find and color enclosed regions ──────────────────────
def find_fill_regions(line_img, min_area=60, max_area_ratio=0.35):
    """Find enclosed white regions using scipy connected-components (fast)."""
    from scipy import ndimage
    arr = np.array(line_img.convert("L"))
    # White pixels (>240) = fillable area
    binary = (arr > 240).astype(np.int32)
    labeled, n_features = ndimage.label(binary)

    w, h = line_img.size
    max_area = int(w * h * max_area_ratio)
    regions = []

    for label_id in range(1, n_features + 1):
        coords = np.argwhere(labeled == label_id)
        area = len(coords)
        if min_area <= area <= max_area:
            cy, cx = coords.mean(axis=0).astype(int)
            # Make sure the seed pixel is actually in the region
            if labeled[cy, cx] == label_id:
                regions.append((cx, cy, area))
            else:
                # Fallback: use any pixel in the region
                regions.append((int(coords[0, 1]), int(coords[0, 0]), area))

    regions.sort(key=lambda r: r[2])
    return [(r[0], r[1]) for r in regions]

def make_colored_version(line_img, seed=42):
    """Create a fully colored version by flood-filling all enclosed regions."""
    colored = line_img.copy()
    regions = find_fill_regions(colored)
    rng = random.Random(seed)
    palette = FILL_COLORS[:]
    rng.shuffle(palette)

    for i, (x, y) in enumerate(regions):
        color = palette[i % len(palette)]
        try:
            ImageDraw.floodfill(colored, (x, y), color, thresh=20)
        except Exception:
            pass
    return colored, regions

def make_partially_colored(line_img, regions, n_filled, seed=42):
    """Create a version with only the first n_filled regions colored."""
    colored = line_img.copy()
    rng = random.Random(seed)
    palette = FILL_COLORS[:]
    rng.shuffle(palette)

    for i in range(min(n_filled, len(regions))):
        x, y = regions[i]
        color = palette[i % len(palette)]
        try:
            ImageDraw.floodfill(colored, (x, y), color, thresh=20)
        except Exception:
            pass
    return colored

# ── Scene renderer ─────────────────────────────────────────────────────
def render_scene(line_img, regions, title_top, title_bot, fidx,
                 frames_draw, frames_paint, frames_hold, seed=42):
    cmask = card_mask()
    bg = make_background()

    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [CARD_X, CARD_Y + 12, CARD_X + CARD_W, CARD_Y + CARD_H + 24],
        radius=CARD_RAD, fill=(0, 0, 0, 140))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    bg_sh = Image.alpha_composite(bg.convert("RGBA"), shadow).convert("RGB")

    f_top = font("DejaVuSans-Bold.ttf", 42)
    f_bot = font("DejaVuSerif-Italic.ttf", 34)
    white_card = Image.new("RGB", (CARD_W, CARD_H), (255, 255, 255))

    def paste_card(card_rgb, text_alpha):
        frame = bg_sh.copy()
        frame.paste(card_rgb, (CARD_X, CARD_Y), cmask)
        draw_text_centered(frame, 200, title_top, f_top, GOLD, text_alpha)
        draw_text_centered(frame, 260, title_bot, f_bot, CREAM, text_alpha)
        return frame

    max_r = math.hypot(CARD_W/2, CARD_H/2)

    # Phase 1: line-art reveal
    for f in range(frames_draw):
        prog = smoothstep((f + 1) / frames_draw)
        mask = Image.new("L", (CARD_W, CARD_H), 0)
        mdraw = ImageDraw.Draw(mask)
        r = prog * max_r
        mdraw.ellipse([CARD_W/2-r, CARD_H/2-r, CARD_W/2+r, CARD_H/2+r], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(12))
        card = Image.composite(line_img, white_card, mask)
        frame = paste_card(card, text_alpha=prog)
        frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1

    # Phase 2: progressive flood-fill coloring (region by region)
    n_regions = len(regions)
    if n_regions > 0:
        # Distribute regions across frames
        for f in range(frames_paint):
            prog = (f + 1) / frames_paint
            n_filled = int(prog * n_regions)
            card = make_partially_colored(line_img, regions, n_filled, seed=seed)
            frame = paste_card(card, text_alpha=1.0)
            frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1
    else:
        # Fallback: no regions found, just show line art
        for f in range(frames_paint):
            frame = paste_card(line_img, text_alpha=1.0)
            frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1

    # Phase 3: hold fully coloured
    full_colored = make_partially_colored(line_img, regions, n_regions, seed=seed)
    hold = paste_card(full_colored, text_alpha=1.0)
    for f in range(frames_hold):
        hold.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1

    # Fade out text
    for f in range(12):
        prog = smoothstep((f + 1) / 12)
        frame = paste_card(full_colored, text_alpha=1.0 - prog)
        frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1

    return fidx

# ── Main ───────────────────────────────────────────────────────────────
def main():
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)

    bg = make_background()
    f_intro1 = font("DejaVuSans-Bold.ttf", 56)
    f_intro2 = font("DejaVuSerif-Italic.ttf", 40)
    fidx = 0

    # ── Intro ────────────────────────────────────────────────────────
    print("Rendering intro...")
    for f in range(int(2.5 * FPS)):
        prog = smoothstep(f / (1.0 * FPS)) if f < FPS else 1.0
        frame = bg.copy()
        draw_text_centered(frame, H/2 - 80, "Discover Fractal Flora", f_intro1, GOLD, prog)
        draw_text_centered(frame, H/2 + 10, "A Coloring Book of", f_intro2, CREAM, prog)
        draw_text_centered(frame, H/2 + 60, "Algorithmic Growth", f_intro2, CREAM, prog)
        frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1

    for f in range(12):
        prog = smoothstep((f+1) / 12)
        frame = bg.copy()
        draw_text_centered(frame, H/2 - 80, "Discover Fractal Flora", f_intro1, GOLD, 1.0 - prog)
        draw_text_centered(frame, H/2 + 10, "A Coloring Book of", f_intro2, CREAM, 1.0 - prog)
        draw_text_centered(frame, H/2 + 60, "Algorithmic Growth", f_intro2, CREAM, 1.0 - prog)
        frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1

    # ── Pages — designs with enclosed areas (tessellations) ──────────
    pages = [
        (SPECS[23], "Islands & Lakes",         "Watch the colors fill in"),   # Islands and Lakes
        (SPECS[29], "Board Pattern",            "50 unique geometric designs"),# Board
        (SPECS[37], "Sierpinski Carpet",       "Perfect lines for coloring"), # Sierpinski Carpet
        (SPECS[39], "Mosaic",                  "Relax and colour"),           # Mosaic
    ]

    for i, (spec, t_top, t_bot) in enumerate(pages):
        print(f"Rendering page {i+1}/{len(pages)}: {spec[0]}...")
        line_img = render_lsystem_pil(spec, CARD_W, CARD_H, "black", "white", lw=2.5)

        print(f"  Finding regions...")
        _, regions = make_colored_version(line_img, seed=42 + i)
        print(f"  Found {len(regions)} fill regions")

        fidx = render_scene(
            line_img, regions, t_top, t_bot, fidx,
            frames_draw=int(1.5 * FPS),
            frames_paint=int(3.0 * FPS),  # longer paint phase to enjoy the coloring
            frames_hold=int(1.5 * FPS),
            seed=42 + i,
        )

    # ── Outro ────────────────────────────────────────────────────────
    print("Rendering outro...")
    cover_path = "/var/www/mathrelaxing.store/static/img/fractal_flora_cover.png"
    cover = Image.open(cover_path).convert("RGB")
    cr = min(CARD_W / cover.width, CARD_H / cover.height)
    nw, nh = int(cover.width * cr), int(cover.height * cr)
    cover = cover.resize((nw, nh), Image.LANCZOS)
    cover_card = Image.new("RGB", (CARD_W, CARD_H), (255, 255, 255))
    cover_card.paste(cover, ((CARD_W - nw)//2, (CARD_H - nh)//2))

    cmask = card_mask()
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [CARD_X, CARD_Y + 12, CARD_X + CARD_W, CARD_Y + CARD_H + 24],
        radius=CARD_RAD, fill=(0, 0, 0, 140))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    bg_sh = Image.alpha_composite(bg.convert("RGBA"), shadow).convert("RGB")

    f_out1 = font("DejaVuSans-Bold.ttf", 52)
    f_out2 = font("DejaVuSans-Bold.ttf", 36)
    f_out3 = font("DejaVuSans.ttf", 28)

    for f in range(3 * FPS):
        prog = smoothstep(min(1.0, f / (1.2 * FPS)))
        frame = bg_sh.copy()
        y_off = int((1.0 - prog) * 200)
        frame.paste(cover_card, (CARD_X, CARD_Y + y_off), cmask)
        draw_text_centered(frame, 120, "FRACTAL FLORA", f_out1, GOLD, prog)
        draw_text_centered(frame, 185, "Coloring Book", f_out2, CREAM, prog)
        a = int(255 * prog)
        pill_w, pill_h = 580, 60
        px0 = (W - pill_w) / 2; py0 = H - 520
        pd = ImageDraw.Draw(frame, "RGBA")
        pd.rounded_rectangle(
            [px0, py0, px0 + pill_w, py0 + pill_h],
            radius=pill_h / 2, fill=(255, 255, 255, a))
        pd.text(
            (W / 2, py0 + pill_h / 2), "$14.99  ·  FREE SHIPPING",
            font=f_out2, fill=(17, 34, 29, a), anchor="mm")
        draw_text_centered(frame, H - 400, "mathrelaxing.store", f_out3, CREAM, prog)
        frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1

    total_duration = fidx / FPS
    print(f"Total frames: {fidx}, duration: {total_duration:.1f}s")

    # ── Encode ───────────────────────────────────────────────────────
    silent = "/tmp/fractal_flora_silent.mp4"
    print("Encoding silent video...")
    subprocess.run([
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(FRAMES / "f_%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-crf", "18",
        "-movflags", "+faststart", silent,
    ], check=True)

    if os.path.exists(AUDIO):
        print("Merging audio...")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", silent, "-i", AUDIO,
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", OUT_MP4,
        ], check=True)
    else:
        shutil.copy(silent, OUT_MP4)

    size_mb = os.path.getsize(OUT_MP4) / (1024 * 1024)
    print(f"DONE → {OUT_MP4} ({size_mb:.1f} MB)")

if __name__ == "__main__":
    main()
