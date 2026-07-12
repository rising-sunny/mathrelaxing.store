"""
Thomas attractor — static preview images for the Etsy listing (2000x2000).
Reuses the simulation + LUT from make_thomas_loop, renders at high res with
more points for density, then composes title / specs / loop-badge overlays.
"""
import os, math
import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image, ImageDraw, ImageFont
import make_thomas_loop as base

OUT_DIR  = "/var/www/mathrelaxing.store/static/downloads/digital"
FONT_DIR = "/var/www/mathrelaxing.store/static/fonts"
CINZEL     = FONT_DIR + "/Cinzel.ttf"
RALEWAY    = FONT_DIR + "/Raleway.ttf"
RALEWAY_IT = FONT_DIR + "/Raleway-Italic.ttf"
LOGO       = "/var/www/mathrelaxing.store/static/img/logo.png"

SIZE = 2000
GOLD   = (216, 180, 120)
AQUA   = (140, 220, 200)
WHITE  = (245, 247, 245)
DIM    = (150, 160, 175)


def render_attractor(xs, ys, zs, angle_deg, size, half, sigma=1.5):
    a = math.radians(angle_deg); ca, sa = math.cos(a), math.sin(a)
    xr = xs * ca - ys * sa
    depth = xs * sa + ys * ca
    rng = [[-half, half], [-half, half]]
    dens, _, _ = np.histogram2d(zs, xr, bins=(size, size), range=rng)
    dnorm = (depth - depth.min()) / (np.ptp(depth) + 1e-9)
    depthw, _, _ = np.histogram2d(zs, xr, bins=(size, size), range=rng, weights=dnorm)
    dens = gaussian_filter(dens, sigma); depthw = gaussian_filter(depthw, sigma)
    inten = np.log1p(dens); inten /= (inten.max() + 1e-9)
    avg = np.divide(depthw, dens, out=np.zeros_like(dens), where=dens > 0)
    inten = np.clip(inten * (0.78 + 0.30 * avg), 0, 1)
    rgb = base.LUT[(inten * 255).astype(np.int32)]
    return Image.fromarray(np.flipud(rgb).astype(np.uint8), "RGB")


def font(path, size):
    return ImageFont.truetype(path, size)

def ctext(draw, cx, y_top, text, fnt, fill):
    """Draw horizontally centered; y_top is the top of the text."""
    b = draw.textbbox((0, 0), text, font=fnt)
    w = b[2] - b[0]
    draw.text((cx - w/2, y_top), text, font=fnt, fill=fill)

def grad_band(img, y0, y1, top_alpha, bot_alpha):
    """Darken a horizontal band (for text legibility), alpha ramps y0->y1."""
    band = img.crop((0, y0, img.width, y1)).convert("RGB")
    arr = np.asarray(band).astype(np.float32)
    h = y1 - y0
    a = np.linspace(top_alpha, bot_alpha, h)[:, None, None]
    arr *= (1 - a)
    img.paste(Image.fromarray(arr.astype(np.uint8)), (0, y0))

def paste_logo(img, scale=0.16, margin=46, alpha=0.92):
    logo = Image.open(LOGO).convert("RGBA")
    lw = int(img.width * scale); lh = int(logo.height * lw / logo.width)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    if alpha < 1:
        r, g, b, al = logo.split(); al = al.point(lambda p: int(p*alpha))
        logo = Image.merge("RGBA", (r, g, b, al))
    img.paste(logo, ((img.width - lw)//2, img.height - lh - margin), logo)


def main():
    print("Simulating Thomas (1.2M pts) for high-res density...")
    xs, ys, zs = base.simulate_thomas(n_steps=1_200_000)
    R = float(np.sqrt(xs**2 + ys**2).max())
    half = max(R, abs(float(zs.min())), abs(float(zs.max()))) * 1.03
    print(f"  half={half:.2f}")

    # ── Preview 1: clean hero ───────────────────────────────────────────────
    print("Preview 1: hero")
    hero = render_attractor(xs, ys, zs, 23, SIZE, half)
    h1 = hero.copy()
    paste_logo(h1, scale=0.13, margin=40, alpha=0.85)
    h1.save(f"{OUT_DIR}/thomas_preview_1_hero.jpg", "JPEG", quality=92)

    # ── Preview 2: title + specs ────────────────────────────────────────────
    print("Preview 2: titled")
    img2 = render_attractor(xs, ys, zs, 0, SIZE, half)
    grad_band(img2, 0, 470, 0.85, 0.0)                # top darken
    grad_band(img2, SIZE-360, SIZE, 0.0, 0.88)        # bottom darken
    d = ImageDraw.Draw(img2)
    ctext(d, SIZE/2, 110, "THOMAS ATTRACTOR", font(CINZEL, 104), WHITE)
    ctext(d, SIZE/2, 250, "Seamless 60 fps Animation Loop", font(RALEWAY_IT, 50), GOLD)
    # specs bar
    ctext(d, SIZE/2, SIZE-250, "1080 × 1080   ·   60 FPS   ·   12s PERFECT LOOP", font(RALEWAY, 46), AQUA)
    ctext(d, SIZE/2, SIZE-180, "Instant MP4 Digital Download", font(RALEWAY, 40), DIM)
    img2.save(f"{OUT_DIR}/thomas_preview_2_titled.jpg", "JPEG", quality=92)

    # ── Preview 3: loop badge ───────────────────────────────────────────────
    print("Preview 3: loop badge")
    img3 = render_attractor(xs, ys, zs, 46, SIZE, half)
    grad_band(img3, SIZE-430, SIZE, 0.0, 0.9)
    d = ImageDraw.Draw(img3)
    # infinity symbol drawn as two tangent rings (avoids missing font glyph)
    yb = SIZE - 330; r = 56; lw = 12
    for sign in (-1, 1):
        cxr = SIZE/2 + sign * r
        d.ellipse([cxr - r, yb - r, cxr + r, yb + r], outline=GOLD, width=lw)
    ctext(d, SIZE/2, SIZE-210, "Plays forever — no visible seam", font(RALEWAY_IT, 52), WHITE)
    img3.save(f"{OUT_DIR}/thomas_preview_3_loop.jpg", "JPEG", quality=92)

    print("Done: 3 previews saved.")


if __name__ == "__main__":
    main()
