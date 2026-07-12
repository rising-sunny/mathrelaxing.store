"""
Desk-mat specific design renderer.

Generates premium horizontal compositions designed for mouse pad / gaming mouse
pad products. Independent from services/renderer.py — uses Pillow + NumPy
directly for a tight pixel pipeline, no Matplotlib.

Design families implemented:
  - deskmat-topographic          (contour + circuit-trace surface)
  - deskmat-aurora-interface     (luminous wave bands + technical overlays)
  - deskmat-textile              (computational woven field, halftone)
  - deskmat-guilloche            (banknote-grade radial security curves)
  - deskmat-celestial            (orbital arcs + faint coordinate ticks)

Public API:
  render_deskmat_design(design_type, params, width, height) -> bytes (PNG)

All designs are aspect-ratio adaptive, full-bleed, with intentionally denser
detail along the edges (so rounded-corner crops still feel composed) and
asymmetric horizontal weight (left side denser for the keyboard area, right
side calmer for the mouse path).
"""

from __future__ import annotations

import io
import math
import random
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


# ──────────────────────────────────────────────────────────
# Palette catalogue — named, hand-picked color stops.
# Each palette is a list of hex strings from dark → light.
# ──────────────────────────────────────────────────────────

PALETTES: dict[str, list[str]] = {
    "cyan-gold-ink":      ["#06121f", "#0e2238", "#1d4675", "#d4a04a", "#f4d491"],
    "graphite-emerald":   ["#070a0c", "#11181d", "#1c3a30", "#37936a", "#9fe6ba"],
    "ink-magenta":        ["#080414", "#1a0c2c", "#3a1a4c", "#a13983", "#f4a4d2"],
    "carbon-cyan":        ["#040608", "#0b1820", "#16404f", "#3aa2bd", "#9fe1ea"],
    "amber-noir":         ["#070503", "#160e07", "#3a2210", "#a86926", "#f0c275"],
    "violet-mist":        ["#06051a", "#160e3a", "#3a247f", "#7d62cf", "#cfbeef"],
    "rose-graphite":      ["#0a0709", "#1b1116", "#4a1f30", "#c25775", "#f2c4d2"],
    "azure-bronze":       ["#040810", "#0a1828", "#173a5e", "#c9923a", "#f0d68a"],
    "obsidian-jade":      ["#060708", "#0c1216", "#1d3635", "#4ea38f", "#aae0d0"],
    "ink-lava":           ["#060306", "#1a070a", "#591818", "#d04a2c", "#f5b88a"],
    # Premium stops tuned for the harmonograph / spirograph guilloché families.
    "gold-black":         ["#050505", "#0e0b06", "#2e2008", "#b07d1e", "#f6d98a", "#fff4d0"],
    "rose-noir":          ["#0a0509", "#1c0a14", "#4a1230", "#c23a70", "#f07aa8", "#ffd8e6"],
    "cyan-abyss":         ["#02060a", "#04141e", "#0a3a4a", "#1f8fa8", "#7fe3f0", "#eaffff"],
    "violet-gold":        ["#070518", "#140f34", "#2e2a66", "#8a6fd0", "#e0c060", "#fff0c0"],
    "emerald-ink":        ["#030605", "#06140e", "#0d3a28", "#2f9e63", "#8ff0b6", "#eafff2"],
}


def _palette_for(name: str | None) -> list[str]:
    if not name or name not in PALETTES:
        return PALETTES["cyan-gold-ink"]
    return PALETTES[name]


# ──────────────────────────────────────────────────────────
# Color helpers
# ──────────────────────────────────────────────────────────

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _palette_to_lut(palette: list[str], n: int = 256) -> np.ndarray:
    """Linear interpolation across a list of hex stops → (n, 3) uint8 LUT."""
    rgbs = [_hex_to_rgb(c) for c in palette]
    lut = np.zeros((n, 3), dtype=np.uint8)
    segs = len(rgbs) - 1
    for i in range(n):
        t = i / (n - 1)
        seg_pos = t * segs
        idx = min(int(seg_pos), segs - 1)
        frac = seg_pos - idx
        c1 = rgbs[idx]
        c2 = rgbs[idx + 1]
        lut[i] = [int(c1[k] + (c2[k] - c1[k]) * frac) for k in range(3)]
    return lut


def _apply_lut(values: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """values: 2D float [0,1] → (H, W, 3) uint8 via LUT lookup."""
    idx = np.clip((values * (len(lut) - 1)).astype(np.int32), 0, len(lut) - 1)
    return lut[idx]


# ──────────────────────────────────────────────────────────
# Noise: bilinear-upscaled value noise via Pillow
# Fast and good enough for soft surface textures.
# ──────────────────────────────────────────────────────────

def _value_noise(width: int, height: int, scale: float,
                 octaves: int, seed: int, persistence: float = 0.5) -> np.ndarray:
    """fBm-style value noise normalized to [0, 1]."""
    rng = np.random.RandomState(seed)
    out = np.zeros((height, width), dtype=np.float32)
    amp = 1.0
    max_amp = 0.0
    freq = 1.0
    for o in range(octaves):
        nw = max(2, int(width * scale * freq))
        nh = max(2, int(height * scale * freq))
        grid = (rng.rand(nh, nw) * 255).astype(np.uint8)
        img = Image.fromarray(grid).resize((width, height), Image.BILINEAR)
        layer = np.asarray(img, dtype=np.float32) / 255.0
        out += layer * amp
        max_amp += amp
        amp *= persistence
        freq *= 2.0
    out /= max_amp
    return out


# ──────────────────────────────────────────────────────────
# Asymmetric weight mask: denser left (keyboard) than right (mouse)
# ──────────────────────────────────────────────────────────

def _asymmetric_weight(width: int, height: int,
                       left_strength: float = 0.7,
                       edge_boost: float = 0.5) -> np.ndarray:
    """
    Returns (H, W) float in [0, 1]:
      - higher on the left, lower on the right (asymmetric horizontal density)
      - boosted near top/bottom edges (so contour detail survives rounded crops)
    """
    x = np.linspace(0, 1, width)
    y = np.linspace(0, 1, height)
    # Horizontal: cosine ramp from 1.0 left → ~0.3 right
    h_weight = (1.0 - left_strength) + left_strength * (0.5 + 0.5 * np.cos(np.pi * x))
    # Vertical: small boost near top/bottom edges
    v_boost = 1.0 + edge_boost * (np.abs(y - 0.5) * 2.0) ** 2
    return (h_weight[None, :] * v_boost[:, None]).astype(np.float32)


# ──────────────────────────────────────────────────────────
# DESIGN FAMILY 1 — Topographic Circuit Maps
#   Layered contour lines forming a faux-topography surface,
#   with circuit-trace highlights along contour edges.
# ──────────────────────────────────────────────────────────

def _design_topographic(width: int, height: int, params: dict,
                        palette_lut: np.ndarray, bg_rgb: tuple) -> Image.Image:
    seed = int((params.get("seed") or {"value": 1207}).get("value", 1207))
    rng = np.random.RandomState(seed)

    # 1. Smooth elevation field
    elevation = _value_noise(
        width, height,
        scale=0.0009, octaves=5, seed=seed, persistence=0.55,
    )

    # 2. Asymmetric weighting (denser left)
    weight = _asymmetric_weight(width, height, left_strength=0.55, edge_boost=0.35)
    elevation = elevation * (0.6 + 0.4 * weight)
    # Normalize
    e_min, e_max = elevation.min(), elevation.max()
    elevation = (elevation - e_min) / max(1e-6, (e_max - e_min))

    # 3. Quantize into contour bands and compute edges
    n_bands = 18
    bands = (elevation * n_bands) % 1.0
    # Gradient of band gives contour line strength
    gy = np.diff(bands, axis=0, prepend=bands[:1])
    gx = np.diff(bands, axis=1, prepend=bands[:, :1])
    edge = np.sqrt(gx * gx + gy * gy)
    edge = np.clip(edge * 4.0, 0, 1)

    # 4. Base shaded surface from elevation
    img = _apply_lut(elevation, palette_lut).astype(np.float32)

    # 5. Add contour highlights (bright stop) on edges
    highlight = palette_lut[-1].astype(np.float32)
    edge3 = edge[:, :, None]
    img = img * (1.0 - 0.65 * edge3) + highlight[None, None, :] * (0.65 * edge3)

    # 6. Sprinkle circuit-trace dots at noise peaks (left half emphasis)
    pim = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(pim, "RGBA")
    n_traces = int(min(width, height) * 0.30)
    for _ in range(n_traces):
        # Bias toward left half
        cx = int(rng.beta(2.0, 3.5) * width)
        cy = int(rng.uniform(0, height))
        r = int(rng.uniform(2, 6))
        a = int(rng.uniform(120, 200))
        c = tuple(highlight.astype(int).tolist())
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*c, a))

    # 7. Subtle scanline darkening every N rows (technical feel)
    arr = np.asarray(pim).astype(np.float32)
    step = max(40, height // 90)
    arr[::step, :, :] *= 0.93
    pim = Image.fromarray(arr.clip(0, 255).astype(np.uint8))

    return pim


# ──────────────────────────────────────────────────────────
# DESIGN FAMILY 2 — Aurora Interface Fields
#   Horizontal luminous wave ribbons + fine technical
#   measurement ticks/grid. Reads left-to-right for mouse path.
# ──────────────────────────────────────────────────────────

def _design_aurora_interface(width: int, height: int, params: dict,
                             palette_lut: np.ndarray, bg_rgb: tuple) -> Image.Image:
    seed = int((params.get("seed") or {"value": 1207}).get("value", 1207))
    rng = np.random.RandomState(seed)

    # 1. Base: deep gradient (palette dark → dark-mid) as background
    y = np.linspace(0, 1, height)[:, None]
    base_grad = np.tile(y, (1, width))
    img = _apply_lut(base_grad * 0.35, palette_lut).astype(np.float32)

    # 2. Stack of horizontal aurora ribbons (sin waves with noise modulation)
    n_ribbons = 7
    accent = palette_lut[-1].astype(np.float32)
    mid = palette_lut[int(len(palette_lut) * 0.7)].astype(np.float32)

    x = np.arange(width, dtype=np.float32)
    for i in range(n_ribbons):
        # Each ribbon at a different y, with a unique wave profile
        base_y = (i + 0.5) * (height / n_ribbons) + rng.uniform(-30, 30)
        freq = rng.uniform(1.5, 3.5) * math.pi / width
        phase = rng.uniform(0, 2 * math.pi)
        amp = rng.uniform(height * 0.04, height * 0.08)
        # Add a low-frequency noise modulation horizontally
        ribbon_noise = _value_noise(width, 1, 0.004, 3, seed + i * 17)[0]
        ribbon_y = base_y + amp * np.sin(freq * x + phase) + (ribbon_noise - 0.5) * height * 0.05

        # Thickness varies — thicker on left (keyboard), thinner on right
        thickness = (rng.uniform(8, 16) * (1.0 + 0.6 * (1.0 - x / width))).astype(np.float32)
        color = (accent if i % 2 == 0 else mid).astype(np.float32)
        intensity = rng.uniform(0.55, 0.95)

        # Paint the ribbon with vertical Gaussian falloff
        rows = np.arange(height, dtype=np.float32)[:, None]  # (H, 1)
        rib_y_2d = ribbon_y[None, :]  # (1, W)
        thick_2d = thickness[None, :]
        falloff = np.exp(-0.5 * ((rows - rib_y_2d) / thick_2d) ** 2)  # (H, W)
        falloff *= intensity
        img = img * (1.0 - falloff[:, :, None]) + color[None, None, :] * falloff[:, :, None]

    # 3. Technical grid overlay — fine ticks every step px, only on edges
    pim = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(pim, "RGBA")
    tick_color = (*accent.astype(int).tolist(), 60)
    tick_spacing = max(50, width // 80)
    tick_len = max(6, height // 120)
    # Top + bottom edge ticks
    for tx in range(0, width, tick_spacing):
        major = (tx // tick_spacing) % 5 == 0
        tl = tick_len * (2 if major else 1)
        a = 100 if major else 50
        col = (*accent.astype(int).tolist(), a)
        draw.line([(tx, 0), (tx, tl)], fill=col, width=1)
        draw.line([(tx, height - tl), (tx, height - 1)], fill=col, width=1)
    # Left + right edge ticks
    for ty in range(0, height, tick_spacing):
        major = (ty // tick_spacing) % 5 == 0
        tl = tick_len * (2 if major else 1)
        a = 100 if major else 50
        col = (*accent.astype(int).tolist(), a)
        draw.line([(0, ty), (tl, ty)], fill=col, width=1)
        draw.line([(width - tl, ty), (width - 1, ty)], fill=col, width=1)

    # 4. A few measurement crosshairs sparsely on top + bottom edges
    n_marks = max(3, width // 1400)
    for _ in range(n_marks):
        cx = int(rng.uniform(width * 0.1, width * 0.9))
        cy_choices = [int(height * 0.06), int(height * 0.94)]
        cy = cy_choices[rng.randint(2)]
        size = max(8, height // 80)
        col = (*accent.astype(int).tolist(), 120)
        draw.line([(cx - size, cy), (cx + size, cy)], fill=col, width=2)
        draw.line([(cx, cy - size), (cx, cy + size)], fill=col, width=2)
        draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), outline=col, width=1)

    return pim


# ──────────────────────────────────────────────────────────
# DESIGN FAMILY 3 — Computational Textile
#   Woven horizontal line field with halftone density modulation.
#   Looks like fabric weave but generated mathematically.
# ──────────────────────────────────────────────────────────

def _design_textile(width: int, height: int, params: dict,
                    palette_lut: np.ndarray, bg_rgb: tuple) -> Image.Image:
    seed = int((params.get("seed") or {"value": 1207}).get("value", 1207))
    rng = np.random.RandomState(seed)

    # 1. Background as a dark mid stop, very subtle vertical gradient
    y = np.linspace(0, 1, height)[:, None]
    bg_field = np.tile(y * 0.25 + 0.1, (1, width))
    img = _apply_lut(bg_field, palette_lut).astype(np.float32)

    # 2. Density modulation field (where weave is thicker / thinner)
    # Asymmetric — denser left
    density = _value_noise(width, height, scale=0.0006, octaves=4, seed=seed)
    weight = _asymmetric_weight(width, height, left_strength=0.6, edge_boost=0.4)
    density = density * weight
    density = (density - density.min()) / max(1e-6, density.max() - density.min())

    # 3. Horizontal weave: paint horizontal lines every step, line intensity
    #    modulated by density field at that location.
    accent = palette_lut[-1].astype(np.float32)
    midbright = palette_lut[int(len(palette_lut) * 0.6)].astype(np.float32)

    step_h = max(3, height // 280)
    for row in range(0, height, step_h):
        # Sample density at this row
        d_row = density[row, :]  # (W,)
        # Color modulation: lerp between dark midbright and bright accent based on density
        d3 = d_row[:, None]  # (W, 1)
        line_color = midbright[None, :] * (1 - d3) + accent[None, :] * d3  # (W, 3)
        # Apply with varying alpha (intensity)
        alpha = (0.20 + 0.45 * d_row)[:, None]  # (W, 1)
        img[row, :, :] = img[row, :, :] * (1 - alpha) + line_color * alpha

    # 4. Vertical "warp" lines every wider step (textile cross-weave)
    step_v = max(6, width // 200)
    for col in range(0, width, step_v):
        d_col = density[:, col]  # (H,)
        d3 = d_col[:, None]
        col_color = midbright[None, :] * (1 - d3) + accent[None, :] * d3
        alpha = (0.10 + 0.30 * d_col)[:, None]
        img[:, col, :] = img[:, col, :] * (1 - alpha) + col_color * alpha

    # 5. Halftone dot pattern across high-density regions (sparse)
    pim = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(pim, "RGBA")
    cell = max(10, width // 220)
    for cy in range(cell // 2, height, cell):
        for cx in range(cell // 2, width, cell):
            d = float(density[cy, cx])
            if d < 0.55:
                continue
            r = max(1, int((d - 0.55) * cell * 0.9))
            a = int(70 + d * 100)
            c = tuple(accent.astype(int).tolist())
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*c, a))

    return pim


# ──────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────

def _design_from_equation(eq_type: str):
    """Build a desk-mat design that renders a full-bleed math pattern (flow field,
    Voronoi, reaction-diffusion, …) at the exact landscape resolution. These
    space-filling patterns are ideal for a wide workspace surface."""
    def _fn(width, height, params, palette_lut, bg_rgb):
        from services.renderer import render_equation
        png = render_equation(eq_type, params, width=width, height=height, hq=True)
        im = Image.open(io.BytesIO(png)).convert("RGB")
        if im.size != (width, height):
            im = im.resize((width, height), Image.LANCZOS)
        return im
    return _fn


# ──────────────────────────────────────────────────────────
# DESIGN FAMILY — Harmonograph (damped-sine guilloché)
# DESIGN FAMILY — Spirograph  (hypotrochoid guilloché rosettes)
# Density-accumulation line art, colored through the palette LUT.
# ──────────────────────────────────────────────────────────

def _seed_of(params: dict) -> int:
    try:
        return int((params.get("seed") or {}).get("value", 7))
    except Exception:
        return 7


def _finish_density(acc: np.ndarray, palette_lut: np.ndarray, width: int,
                    gamma: float, glow_div: int, blend: float) -> Image.Image:
    g = np.log1p(acc)
    g = g / (g.max() + 1e-9)
    g = g ** gamma
    im = Image.fromarray(_apply_lut(g, palette_lut).astype(np.uint8), "RGB")
    glow = im.filter(ImageFilter.GaussianBlur(max(2, width // glow_div)))
    return Image.blend(im, glow, blend)


def _design_harmonograph(width, height, params, palette_lut, bg_rgb) -> Image.Image:
    rng = np.random.default_rng(_seed_of(params))
    acc = np.zeros((height, width), dtype=np.float32)
    npts = min(1_400_000, max(120_000, width * 170))
    t = np.linspace(0, 60 * np.pi, npts)
    for _ in range(5):
        f = rng.uniform(1.0, 4.0, 4); ph = rng.uniform(0, 2 * np.pi, 4)
        dm = rng.uniform(0.002, 0.02, 4)
        x = np.sin(f[0]*t+ph[0])*np.exp(-dm[0]*t) + np.sin(f[1]*t+ph[1])*np.exp(-dm[1]*t)
        y = np.sin(f[2]*t+ph[2])*np.exp(-dm[2]*t) + np.sin(f[3]*t+ph[3])*np.exp(-dm[3]*t)
        px = ((x/2.2*0.9*(width/height)/2 + 0.5) * width).astype(np.int32)
        py = ((y/2.2*0.9 + 0.5) * height).astype(np.int32)
        m = (px >= 0) & (px < width) & (py >= 0) & (py < height)
        np.add.at(acc, (py[m], px[m]), 1.0)
    return _finish_density(acc, palette_lut, width, gamma=0.6, glow_div=500, blend=0.40)


# Curated hypotrochoid (R, r, d) layer sets — coprime-ish for dense rosettes.
_SPIRO_SETS = [
    [(200, 79, 118), (200, 79, 150)],
    [(210, 83, 132), (150, 61, 96)],
    [(190, 71, 140), (190, 71, 90)],
    [(220, 89, 150)],
    [(200, 57, 140)],
]


def _design_spirograph(width, height, params, palette_lut, bg_rgb) -> Image.Image:
    layers = _SPIRO_SETS[_seed_of(params) % len(_SPIRO_SETS)]
    acc = np.zeros((height, width), dtype=np.float32)
    npts = min(1_800_000, max(200_000, width * 240))
    t = np.linspace(0, 300 * np.pi, npts)
    curves = []
    for Rr, rr, dd in layers:
        k = (Rr - rr) / rr
        curves.append(((Rr-rr)*np.cos(t) + dd*np.cos(k*t),
                       (Rr-rr)*np.sin(t) - dd*np.sin(k*t)))
    s = max(max(abs(x).max() for x, _ in curves),
            max(abs(y).max() for _, y in curves)) * 1.06
    for x, y in curves:
        PX = ((x/s*0.47*(height/width) + 0.5) * width).astype(np.int32)
        PY = ((y/s*0.47 + 0.5) * height).astype(np.int32)
        m = (PX >= 0) & (PX < width) & (PY >= 0) & (PY < height)
        np.add.at(acc, (PY[m], PX[m]), 1.0)
    return _finish_density(acc, palette_lut, width, gamma=0.5, glow_div=600, blend=0.38)


# LaTeX (mathtext) of the generating equation, shown as an elegant corner signature.
_DESIGN_EQUATIONS = {
    "deskmat-harmonograph": r"$x=\sum_i A_i\,\sin(f_i t+\phi_i)\,e^{-d_i t}$",
    "deskmat-spirograph":   r"$x=(R-r)\cos t + d\cos\dfrac{(R-r)\,t}{r}$",
}


def _add_equation_overlay(im: Image.Image, eq: str, palette_lut: np.ndarray,
                          width_frac: float = 0.34, alpha: float = 0.5,
                          pad_frac: float = 0.03) -> Image.Image:
    """Composite the generating equation as a subtle, tinted signature in the
    bottom-left corner, with a soft shadow for legibility on busy designs."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    W, H = im.size
    tint = palette_lut[-1]
    color = (float(tint[0])/255, float(tint[1])/255, float(tint[2])/255)
    fig = plt.figure(figsize=(8, 2), dpi=200); fig.patch.set_alpha(0)
    fig.text(0.5, 0.5, eq, color=color, fontsize=28, ha="center", va="center",
             math_fontfamily="cm")
    buf = io.BytesIO()
    fig.savefig(buf, transparent=True, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig); buf.seek(0)
    eqimg = Image.open(buf).convert("RGBA")
    target_w = int(W * width_frac)
    sc = target_w / eqimg.width
    eqimg = eqimg.resize((target_w, int(eqimg.height * sc)), Image.LANCZOS)
    r, g, b, a = eqimg.split()
    eqimg.putalpha(a.point(lambda v: int(v * alpha)))

    pad = int(W * pad_frac)
    x0, y0 = pad, H - eqimg.height - pad
    base = im.convert("RGBA")
    # soft shadow
    shadow = Image.new("RGBA", eqimg.size, (0, 0, 0, 0))
    shadow.putalpha(eqimg.split()[3].point(lambda v: int(v * 0.85)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(2, eqimg.width // 90)))
    base.alpha_composite(shadow, (x0 + 3, y0 + 3))
    base.alpha_composite(eqimg, (x0, y0))
    return base.convert("RGB")


DESIGNS = {
    "deskmat-harmonograph":     _design_harmonograph,
    "deskmat-spirograph":       _design_spirograph,
    "deskmat-topographic":      _design_topographic,
    "deskmat-topographic-circuit": _design_topographic,  # alias
    "deskmat-aurora-interface": _design_aurora_interface,
    "deskmat-textile":          _design_textile,
    "deskmat-computational-textile": _design_textile,  # alias
    "deskmat-flowfield":        _design_from_equation("flow-field"),
    "deskmat-voronoi":          _design_from_equation("voronoi"),
    "deskmat-reactiondiff":     _design_from_equation("gray-scott"),
}


def render_deskmat_design(design_type: str, params: dict[str, Any],
                          width: int, height: int) -> bytes:
    """
    Render a desk-mat design at the requested resolution.

    Args:
      design_type: one of the keys in DESIGNS. Falls back to topographic.
      params: dict with keys design_family / palette / background_color / seed
        — values are dicts of the form {"value": ...}.
      width, height: output pixel dims (should match Printful spec).

    Returns:
      PNG bytes.
    """
    # Extract params
    palette_name = (params.get("palette") or {}).get("value")
    bg_hex = (params.get("background_color") or {}).get("value", "#070b13")
    bg_rgb = _hex_to_rgb(bg_hex)
    palette = _palette_for(palette_name)
    palette_lut = _palette_to_lut(palette)

    renderer = DESIGNS.get(design_type, _design_topographic)

    # Cap internal render res to prevent OOM on full 7200x3600.
    # Use bilinear upscale: soft designs survive it perfectly, big speed gain.
    MAX_DIM = 4000
    if max(width, height) > MAX_DIM:
        scale = MAX_DIM / max(width, height)
        rw = max(64, int(width * scale))
        rh = max(64, int(height * scale))
        im = renderer(rw, rh, params, palette_lut, bg_rgb)
        # Smooth upscale — extra Lanczos blur to hide any noise aliasing
        im = im.resize((width, height), Image.LANCZOS)
    else:
        im = renderer(width, height, params, palette_lut, bg_rgb)

    # Elegant generating-equation signature (harmonograph / spirograph).
    eq = _DESIGN_EQUATIONS.get(design_type)
    show_eq = (params.get("show_equation") or {}).get("value", True)
    if eq and show_eq:
        try:
            im = _add_equation_overlay(im, eq, palette_lut)
        except Exception:
            pass  # never fail the whole render over the caption

    # Force full-bleed RGB (no alpha leaks)
    if im.mode != "RGB":
        im = im.convert("RGB")

    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=False, compress_level=3)
    return buf.getvalue()
