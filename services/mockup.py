import io
import os
import json
import hashlib
import numpy as np
from PIL import Image, ImageFilter
from services.renderer import render_equation
from services.printful import FORMATS

MOCKUP_CACHE_DIR = "/tmp/mathrelaxing_mockups"
PRINT_CACHE_DIR  = "/tmp/mathrelaxing_print"
os.makedirs(MOCKUP_CACHE_DIR, exist_ok=True)
os.makedirs(PRINT_CACHE_DIR, exist_ok=True)

# Fast mockup resolution: 2400×3000 is sufficient for web display
# (mockups are shown at ~800px on screen, this gives 3x oversampling)
_MOCKUP_SPEC = {"width_px": 2400, "height_px": 3000, "dpi": 150}

# ── PSD template definitions ──────────────────────────────────────────────────
# psd_type determines which PSD loading branch to use (and is used as cache key).
# art_style (optional) applies a post-processing effect to the artwork before pasting.
PSD_TEMPLATES = [
    {
        "id":       "studio",
        "path":     "/root/canvas_mockup/PSD 001 3x4.psd",
        "art_l": 1662, "art_t": 716, "art_w": 1177, "art_h": 1569,
        "scale":    0.5,
        "psd_type": "studio",
    },
    {
        "id":       "room",
        "path":     "/root/canvas_mockup/vertical wall poster mockup.psd",
        "art_l": 1049, "art_t": 481, "art_w": 1111, "art_h": 1573,
        "scale":    0.5,
        "psd_type": "room",
    },
    {
        # Framed poster: same room scene, artwork gets black-frame + cream-mat treatment
        "id":       "framed",
        "path":     "/root/canvas_mockup/vertical wall poster mockup.psd",
        "art_l": 1049, "art_t": 481, "art_w": 1111, "art_h": 1573,
        "scale":    0.5,
        "psd_type": "room",
        "art_style": "framed",
    },
    {
        # Acrylic standoff print. Art slot from PSD "Change This" smart object layer.
        "id":       "acrylic",
        "path":     "/root/acrylic_mockup/Print-mockup.psd",
        "art_l": 2223, "art_t": 1163, "art_w": 1484, "art_h": 2109,
        "scale":    0.5,
        "psd_type": "acrylic-standoff",
    },
    {
        # New: dual-canvas studio scene (Canvas Left smartobject).
        # Coords from PlLd Trnf block: top-left=(1397,387), size=1185x1552.
        "id":       "free-canvas-left",
        "path":     "/var/www/mathrelaxing.store/static/psd-mockups/free-canvas-mockup.psd",
        "art_l": 1397, "art_t": 387, "art_w": 1185, "art_h": 1552,
        "scale":    0.5,
        "psd_type": "free-canvas",
    },
    {
        # New: single canvas on wall — best e-commerce scene.
        # Coords from COLOR→Canvas layer bounds: [2452,505,3543,1933].
        "id":       "free-vertical-canvas",
        "path":     "/var/www/mathrelaxing.store/static/psd-mockups/free-vertical-wall-canvas.psd",
        "art_l": 2452, "art_t": 505, "art_w": 1091, "art_h": 1428,
        "scale":    0.5,
        "psd_type": "free-vertical-canvas",
    },
    {
        # New: framed poster on wall. Art slot from smartobject bounds [532,321,679x965].
        "id":       "free-framed-poster",
        "path":     "/var/www/mathrelaxing.store/static/psd-mockups/free-framed-poster-wall.psd",
        "art_l": 532, "art_t": 321, "art_w": 679, "art_h": 965,
        "scale":    1.0,
        "psd_type": "free-framed-poster",
    },
    {
        # Unframed art print / poster hanging on wall with two binder clips.
        # Smart object "Change This" Trnf corners: (1854,616)→(4114,3814), size 2260×3198.
        "id":       "free-hanging-poster",
        "path":     "/var/www/mathrelaxing.store/static/psd-mockups/free-hanging-poster.psd",
        "art_l": 1854, "art_t": 616, "art_w": 2260, "art_h": 3198,
        "scale":    0.5,
        "psd_type": "free-hanging-poster",
    },
    {
        # Aluminum metal panel: studio with gray background + floating shadow
        "id":       "aluminum-studio",
        "path":     "/var/www/mathrelaxing.store/static/psd-mockups/free-vertical-wall-canvas.psd",
        "art_l": 1397, "art_t": 387, "art_w": 1185, "art_h": 1552,
        "scale":    0.5,
        "psd_type": "aluminum-studio",
        "art_style": "aluminum",
    },
    {
        # AI generated notebook mockup
        "id":       "spiral_notebook",
        "path":     "/var/www/mathrelaxing.store/static/psd-mockups/notebook_mockup_bg.png",
        "art_l": 180, "art_t": 150, "art_w": 580, "art_h": 740,
        "scale":    1.0,
        "psd_type": "spiral_notebook",
    },
]

# ── Per-psd_type lazy cache ───────────────────────────────────────────────────
_psd_cache: dict = {}   # psd_type → (bg: Image, overlays: dict | None)


def _load_template(tpl: dict):
    psd_type = tpl.get("psd_type", tpl["id"])
    if psd_type in _psd_cache:
        return _psd_cache[psd_type]

    if tpl["path"].lower().endswith(('.png', '.jpg', '.jpeg')):
        scene = Image.open(tpl["path"]).convert('RGB')
        overlays = {}
        _psd_cache[psd_type] = (scene, overlays)
        return scene, overlays

    from psd_tools import PSDImage
    psd  = PSDImage.open(tpl["path"])
    W, H = psd.width, psd.height

    def topil(layer):
        img = layer.topil()
        return img.convert('RGBA') if img else None

    if psd_type == "studio":
        bg_group   = next(l for l in psd if l.name == 'Background')
        mockup_grp = next(l for l in psd if l.name == 'Mockup')
        mc = {l.name: l for l in mockup_grp}

        scene = bg_group.composite().convert('RGB').resize((W, H))
        canvas_raw = topil(mc['Canvas'])
        cx, cy = mc['Canvas'].left, mc['Canvas'].top
        scene.paste(canvas_raw.convert('RGB'), (cx, cy), canvas_raw.split()[3])

        overlays = {
            'texture':  (topil(mc['Texture']),    mc['Texture'].left,    mc['Texture'].top,    0.18),
            'light':    (topil(mc['Light']),      mc['Light'].left,      mc['Light'].top,      0.12),
            'reflect':  (topil(mc['Reflection']), mc['Reflection'].left, mc['Reflection'].top, 0.35),
            'specular': (topil(mc['Scpecular']),  mc['Scpecular'].left,  mc['Scpecular'].top,  0.50),
        }

    elif psd_type == "room":
        files_grp = next(l for l in psd if l.name == 'files')
        photo = next(l for l in files_grp if l.kind == 'pixel')
        scene = photo.topil().convert('RGB').resize((W, H))

        effects = next(l for l in files_grp if l.name == 'effects')
        overlays = {
            'effects': (topil(effects), effects.left, effects.top, 54 / 255),
        }

    elif psd_type == "acrylic-standoff":
        # Layer 0 already contains the wall, acrylic sheet, standoffs, and shadows.
        # We only replace the inner poster area; the PSD gloss layer uses a blend mode
        # that is not reproduced faithfully here and washes out the print.
        layers = list(psd)
        scene = layers[0].topil().convert('RGB')
        overlays = {}

    elif psd_type == "free-canvas":
        bg_layer     = next(l for l in psd if l.name == 'Background')
        scene        = bg_layer.topil().convert('RGB')
        shadows_l    = next(l for l in psd if l.name == 'Shadows')
        highlights_l = next(l for l in psd if l.name == 'Highlights')
        overlays = {
            'shadows':    (topil(shadows_l),    shadows_l.left,    shadows_l.top,    1.0),
            'highlights': (topil(highlights_l), highlights_l.left, highlights_l.top, 1.0),
        }

    elif psd_type == "free-vertical-canvas":
        bg_layer     = next(l for l in psd if l.name == 'Background')
        scene        = bg_layer.topil().convert('RGB')
        shadows_l    = next(l for l in psd if l.name == 'Sahdows')   # typo preserved from PSD
        highlights_l = next(l for l in psd if l.name == 'Highlights')
        overlays = {
            'shadows':    (topil(shadows_l),    shadows_l.left,    shadows_l.top,    1.0),
            'highlights': (topil(highlights_l), highlights_l.left, highlights_l.top, 1.0),
        }

    elif psd_type == "free-framed-poster":
        outer_grp  = next(l for l in psd if 'sachanati' in l.name.lower())
        photo      = next(l for l in outer_grp if l.kind == 'pixel')
        scene      = Image.new('RGB', (W, H), (200, 200, 200))
        scene.paste(photo.topil().convert('RGB'), (photo.left, photo.top))
        fx_grp     = next(l for l in psd if l.name == 'Lighting FX')
        shadow_l   = next(l for l in fx_grp if l.name == 'Shadow')
        lighting_l = next(l for l in fx_grp if l.name == 'Lighting')
        overlays = {
            'shadow':   (topil(shadow_l),   shadow_l.left,   shadow_l.top,   1.0),
            'lighting': (topil(lighting_l), lighting_l.left, lighting_l.top, 38 / 255),
        }

    elif psd_type == "free-hanging-poster":
        bg_layer = next(l for l in psd if l.name == 'Change Color')
        scene    = bg_layer.topil().convert('RGB')
        shadow_layers   = [l for l in psd if l.name == 'Shadow']
        full_shadow_l   = next(l for l in shadow_layers if l.width == W)
        poster_shadow_l = next(l for l in shadow_layers if l.width != W)
        reflections_l   = next(l for l in psd if l.name == 'Reflections')
        ropes_l         = next(l for l in psd if l.name == 'Ropes')
        # Pre-bake the full-canvas shadow into the wall background so it never
        # darkens the artwork (artwork is pasted after this cached background is copied).
        full_shadow_img = topil(full_shadow_l)
        bg_arr  = np.array(scene, dtype=np.float32) / 255
        shd_arr = np.array(full_shadow_img.convert('RGB'), dtype=np.float32) / 255
        shd_a   = np.array(full_shadow_img.split()[3], dtype=np.float32) / 255
        burned  = np.clip(bg_arr + shd_arr - 1, 0, 1)
        bg_arr  = burned * shd_a[:, :, np.newaxis] + bg_arr * (1 - shd_a[:, :, np.newaxis])
        scene   = Image.fromarray((bg_arr * 255).clip(0, 255).astype(np.uint8))
        overlays = {
            'poster_shadow': (topil(poster_shadow_l), poster_shadow_l.left, poster_shadow_l.top, 1.0),
            'reflections':   (topil(reflections_l),   reflections_l.left,   reflections_l.top,   1.0),
            'ropes':         (topil(ropes_l),         ropes_l.left,         ropes_l.top,         1.0),
        }

    elif psd_type == "aluminum-studio":
        # Create virtual gray studio background (matches Gelato's product photos)
        # Medium gray gradient background
        scene = Image.new('RGB', (W, H), (235, 235, 235))
        # Add subtle gradient from center
        bg_arr = np.array(scene, dtype=np.float32)
        center_y, center_x = H // 2, W // 2
        y_coords, x_coords = np.ogrid[:H, :W]
        dist_from_center = np.sqrt((x_coords - center_x)**2 + (y_coords - center_y)**2)
        max_dist = np.sqrt(center_x**2 + center_y**2)
        # Lighten towards center
        lighten = 1 + 0.05 * (1 - dist_from_center / max_dist)
        bg_arr = (bg_arr * lighten[:, :, np.newaxis]).clip(0, 255)
        scene = Image.fromarray(bg_arr.astype(np.uint8))

        # Create floating shadow overlay (panel shadow on wall)
        shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        shadow_draw = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        # Shadow will be applied relative to art position in generate_mockup
        overlays = {
            'floating_shadow': (shadow, 0, 0, 0.3),  # 30% opacity shadow
        }

    _psd_cache[psd_type] = (scene, overlays)
    return scene, overlays


# ── Blend helpers ─────────────────────────────────────────────────────────────
def _screen(base_arr, over, opacity):
    o = np.array(over.convert('RGB'), dtype=np.float32) / 255
    a = np.array(over.split()[3],     dtype=np.float32) / 255 * opacity
    r = 1 - (1 - base_arr) * (1 - o)
    return r * a[:, :, np.newaxis] + base_arr * (1 - a[:, :, np.newaxis])


def _overlay_blend(base_arr, over, opacity):
    o = np.array(over.convert('RGB'), dtype=np.float32) / 255
    a = np.array(over.split()[3],     dtype=np.float32) / 255 * opacity
    dark  = 2 * base_arr * o
    light = 1 - 2 * (1 - base_arr) * (1 - o)
    r = np.where(base_arr >= 0.5, light, dark)
    return r * a[:, :, np.newaxis] + base_arr * (1 - a[:, :, np.newaxis])


def _linear_burn(base_arr, over, opacity):
    o = np.array(over.convert('RGB'), dtype=np.float32) / 255
    a = np.array(over.split()[3],     dtype=np.float32) / 255 * opacity
    r = np.clip(base_arr + o - 1, 0, 1)
    return r * a[:, :, np.newaxis] + base_arr * (1 - a[:, :, np.newaxis])


def _multiply(base_arr, over, opacity):
    o = np.array(over.convert('RGB'), dtype=np.float32) / 255
    a = np.array(over.split()[3],     dtype=np.float32) / 255 * opacity
    r = base_arr * o
    return r * a[:, :, np.newaxis] + base_arr * (1 - a[:, :, np.newaxis])


def _hard_light(base_arr, over, opacity):
    o = np.array(over.convert('RGB'), dtype=np.float32) / 255
    a = np.array(over.split()[3],     dtype=np.float32) / 255 * opacity
    dark  = 2 * base_arr * o
    light = 1 - 2 * (1 - base_arr) * (1 - o)
    r = np.where(o >= 0.5, light, dark)
    return r * a[:, :, np.newaxis] + base_arr * (1 - a[:, :, np.newaxis])


def _apply_overlays(scene, overlays, psd_type):
    if not overlays:
        return

    if psd_type == "studio":
        art_w = next(t["art_w"] for t in PSD_TEMPLATES if t["psd_type"] == "studio" and t["id"] == "studio")
        art_h = next(t["art_h"] for t in PSD_TEMPLATES if t["psd_type"] == "studio" and t["id"] == "studio")
        tex_img, tx, ty, t_op = overlays['texture']
        zone = np.array(scene.crop((tx, ty, tx + art_w, ty + art_h)), dtype=np.float32) / 255
        blended = _overlay_blend(zone, tex_img, t_op)
        scene.paste(Image.fromarray((blended * 255).clip(0, 255).astype(np.uint8)), (tx, ty))
        for key in ('light', 'reflect', 'specular'):
            img, lx, ly, op = overlays[key]
            lw, lh = img.size
            zone = np.array(scene.crop((lx, ly, lx + lw, ly + lh)), dtype=np.float32) / 255
            blended = _screen(zone, img, op)
            scene.paste(Image.fromarray((blended * 255).clip(0, 255).astype(np.uint8)), (lx, ly))

    elif psd_type == "room":
        img, lx, ly, op = overlays['effects']
        lw, lh = img.size
        zone = np.array(scene.crop((lx, ly, lx + lw, ly + lh)), dtype=np.float32) / 255
        blended = _screen(zone, img, op)
        scene.paste(Image.fromarray((blended * 255).clip(0, 255).astype(np.uint8)), (lx, ly))

    elif psd_type in ("free-canvas", "free-vertical-canvas"):
        img, lx, ly, _ = overlays['shadows']
        lw, lh = img.size
        zone = np.array(scene.crop((lx, ly, lx + lw, ly + lh)), dtype=np.float32) / 255
        blended = _linear_burn(zone, img, 1.0)
        scene.paste(Image.fromarray((blended * 255).clip(0, 255).astype(np.uint8)), (lx, ly))
        img, lx, ly, _ = overlays['highlights']
        lw, lh = img.size
        zone = np.array(scene.crop((lx, ly, lx + lw, ly + lh)), dtype=np.float32) / 255
        blended = _screen(zone, img, 1.0)
        scene.paste(Image.fromarray((blended * 255).clip(0, 255).astype(np.uint8)), (lx, ly))

    elif psd_type == "free-framed-poster":
        img, lx, ly, _ = overlays['shadow']
        lw, lh = img.size
        zone = np.array(scene.crop((lx, ly, lx + lw, ly + lh)), dtype=np.float32) / 255
        blended = _multiply(zone, img, 1.0)
        scene.paste(Image.fromarray((blended * 255).clip(0, 255).astype(np.uint8)), (lx, ly))
        img, lx, ly, op = overlays['lighting']
        lw, lh = img.size
        zone = np.array(scene.crop((lx, ly, lx + lw, ly + lh)), dtype=np.float32) / 255
        blended = _hard_light(zone, img, op)
        scene.paste(Image.fromarray((blended * 255).clip(0, 255).astype(np.uint8)), (lx, ly))

    elif psd_type == "free-hanging-poster":
        # Poster edge shadow (LINEAR_BURN — adds subtle darkening at poster edges)
        img, lx, ly, _ = overlays['poster_shadow']
        lw, lh = img.size
        zone = np.array(scene.crop((lx, ly, lx + lw, ly + lh)), dtype=np.float32) / 255
        blended = _linear_burn(zone, img, 0.35)
        scene.paste(Image.fromarray((blended * 255).clip(0, 255).astype(np.uint8)), (lx, ly))
        # Reflections (SCREEN — paper surface sheen)
        img, lx, ly, _ = overlays['reflections']
        lw, lh = img.size
        zone = np.array(scene.crop((lx, ly, lx + lw, ly + lh)), dtype=np.float32) / 255
        blended = _screen(zone, img, 0.25)
        scene.paste(Image.fromarray((blended * 255).clip(0, 255).astype(np.uint8)), (lx, ly))
        # Ropes (NORMAL alpha-composite on top of everything)
        img, lx, ly, _ = overlays['ropes']
        scene.paste(img.convert('RGB'), (lx, ly), img.split()[3])



# ── Art style treatments ──────────────────────────────────────────────────────
def _add_frame_border(art: Image.Image, target_w: int, target_h: int,
                      bg_color: tuple = (8, 8, 8)) -> Image.Image:
    """Fit artwork inside a black wood frame with cream mat, sized to target dimensions."""
    mat_px   = int(target_w * 0.048)   # cream mat border
    frame_px = int(target_w * 0.026)   # black wood frame border
    inner_w  = target_w - 2 * (mat_px + frame_px)
    inner_h  = target_h - 2 * (mat_px + frame_px)

    art_w, art_h = art.size
    scale = min(inner_w / art_w, inner_h / art_h)
    scaled_w, scaled_h = int(art_w * scale), int(art_h * scale)
    art_scaled = art.resize((scaled_w, scaled_h), Image.LANCZOS)
    art_inner = Image.new('RGB', (inner_w, inner_h), bg_color)
    art_inner.paste(art_scaled, ((inner_w - scaled_w) // 2, (inner_h - scaled_h) // 2))

    # Black wood frame background
    result = Image.new('RGB', (target_w, target_h), (24, 18, 14))

    # Subtle wood grain via a faint noise layer
    rng = np.random.default_rng(0)
    grain = rng.integers(0, 18, (target_h, target_w, 3), dtype=np.uint8)
    frame_arr = np.array(result, dtype=np.int16) + grain - 9
    result = Image.fromarray(np.clip(frame_arr, 0, 255).astype(np.uint8))

    # Cream mat
    mat_w = inner_w + 2 * mat_px
    mat_h = inner_h + 2 * mat_px
    mat = Image.new('RGB', (mat_w, mat_h), (244, 240, 230))
    # Soft inner-shadow on mat (4-px gradient toward art edge)
    mat_arr = np.array(mat, dtype=np.float32) / 255
    shadow_px = 6
    for i in range(shadow_px):
        f = 1 - (shadow_px - i) / shadow_px * 0.18
        mat_arr[mat_px - shadow_px + i, :] *= f
        mat_arr[mat_h - mat_px + i, :]      *= f
        mat_arr[:, mat_px - shadow_px + i] *= f
        mat_arr[:, mat_w - mat_px + i]      *= f
    mat = Image.fromarray((mat_arr * 255).clip(0, 255).astype(np.uint8))

    result.paste(mat, (frame_px, frame_px))
    result.paste(art_inner, (frame_px + mat_px, frame_px + mat_px))
    return result


def _detect_bg_color(img: Image.Image) -> tuple:
    """Sample the artwork background color from the four corners."""
    arr = np.array(img.convert('RGB'), dtype=np.float32)
    corners = [arr[:12, :12], arr[:12, -12:], arr[-12:, :12], arr[-12:, -12:]]
    mean = np.concatenate([c.reshape(-1, 3) for c in corners]).mean(axis=0)
    return tuple(int(v) for v in mean)


def _draw_standoff(scene: Image.Image, cx: int, cy: int, r: int = 58) -> None:
    """Draw a chrome standoff cap at (cx, cy) with radius r (PSD coords)."""
    size = r * 2
    y_g, x_g = np.ogrid[:size, :size]
    dist = np.sqrt((x_g - r) ** 2 + (y_g - r) ** 2).astype(np.float32)
    mask = dist < r
    nx = (x_g - r) / r
    ny = (y_g - r) / r
    base = np.clip(0.52 + 0.32 * (1 - dist / r), 0, 1)
    highlight = np.exp(-((nx + 0.32) ** 2 + (ny + 0.32) ** 2) / 0.09) * 0.58
    edge_fade = np.clip((r - dist) / (r * 0.14), 0, 1)
    val = np.clip(base + highlight, 0, 1) * edge_fade
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    arr[:, :, 0] = (val * 195 * mask).astype(np.uint8)
    arr[:, :, 1] = (val * 200 * mask).astype(np.uint8)
    arr[:, :, 2] = (val * 210 * mask).astype(np.uint8)
    arr[:, :, 3] = (mask * 248).astype(np.uint8)
    cap = Image.fromarray(arr, 'RGBA')
    scene.paste(cap.convert('RGB'), (cx - r, cy - r), cap.split()[3])


def _apply_acrylic_glass_overlay(scene: Image.Image,
                                  pl: int, pt: int, pr: int, pb: int) -> None:
    """Apply a realistic glass/gloss reflection over the acrylic panel area in-place."""
    panel = np.array(scene.crop((pl, pt, pr, pb)), dtype=np.float32) / 255.0
    h, w = panel.shape[:2]

    # Diagonal gloss streak: simulates studio light hitting the acrylic surface
    yp = np.linspace(0, 1, h, dtype=np.float32)[:, np.newaxis]
    xp = np.linspace(0, 1, w, dtype=np.float32)[np.newaxis, :]
    d = (xp + yp) * 0.5
    gloss = np.where(
        (d > 0.03) & (d < 0.22),
        np.sin((d - 0.03) / 0.19 * np.pi) * 0.10,
        0.0,
    ).astype(np.float32)
    panel = np.clip(panel + gloss[:, :, np.newaxis], 0, 1)

    # Edge highlights: screen blend toward white on all 4 panel borders
    edge_px = 28
    for i in range(edge_px):
        v = (1 - i / edge_px) * 0.18
        for col in [i, w - 1 - i]:
            panel[:, col] = np.clip(1 - (1 - panel[:, col]) * (1 - v), 0, 1)
        for row in [i, h - 1 - i]:
            panel[row, :] = np.clip(1 - (1 - panel[row, :]) * (1 - v), 0, 1)

    # Subtle overall sheen (+2% screen blend toward white)
    panel = np.clip(1 - (1 - panel) * 0.98, 0, 1)

    scene.paste(Image.fromarray((panel * 255).astype(np.uint8)), (pl, pt))


def _add_acrylic_effect(art: Image.Image) -> Image.Image:
    """Add edge-lit highlight and diagonal gloss streak typical of acrylic prints."""
    arr = np.array(art, dtype=np.float32) / 255.0
    h, w = arr.shape[:2]

    # Edge highlight: white glow on all four edges, fading inward
    edge_px = max(int(w * 0.014), 10)
    lin     = np.linspace(1.0, 0.0, edge_px, dtype=np.float32)
    mask    = np.zeros((h, w), dtype=np.float32)
    for i, v in enumerate(lin):
        mask[:, i]             = np.maximum(mask[:, i],         v)
        mask[:, w - 1 - i]    = np.maximum(mask[:, w - 1 - i], v)
        mask[i, :]             = np.maximum(mask[i, :],         v)
        mask[h - 1 - i, :]    = np.maximum(mask[h - 1 - i, :], v)

    edge_op = 0.65
    a = (mask * edge_op)[:, :, np.newaxis]
    # Screen blend toward white on edges
    result = 1 - (1 - arr) * (1 - np.ones_like(arr))  # full screen = 1
    result = result * a + arr * (1 - a)

    # Diagonal gloss streak (top-left to center, like studio light hitting glass)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, np.newaxis]
    xx = np.linspace(0, 1, w, dtype=np.float32)[np.newaxis, :]
    d  = (xx + yy) * 0.5
    gloss = np.where(
        (d > 0.04) & (d < 0.22),
        np.sin((d - 0.04) / 0.18 * np.pi) * 0.09,
        0.0,
    ).astype(np.float32)

    result = np.clip(result + gloss[:, :, np.newaxis], 0, 1)
    return Image.fromarray((result * 255).astype(np.uint8))


def _add_aluminum_effect(art: Image.Image) -> Image.Image:
    """Add brushed metallic texture typical of aluminum prints.
    Matches Gelato's metallic_400x500-mm product: brushed finish, 3mm panel look."""
    arr = np.array(art, dtype=np.float32) / 255.0
    h, w = arr.shape[:2]

    # Brushed texture: subtle horizontal lines with noise
    np.random.seed(42)
    brush_lines = np.zeros((h, w), dtype=np.float32)
    line_spacing = 3  # pixels between brush lines
    for y in range(0, h, line_spacing):
        intensity = 0.015 * (0.8 + 0.4 * np.random.random())
        brush_lines[y:y+1, :] = intensity
    # Subtle blur for brush realism using PIL
    brush_img = Image.fromarray((brush_lines * 255).astype(np.uint8))
    brush_img = brush_img.filter(ImageFilter.GaussianBlur(radius=0.5))
    brush_lines = np.array(brush_img, dtype=np.float32) / 255.0

    # Add subtle grain/noise for realism
    grain = np.random.normal(0, 0.008, (h, w)).astype(np.float32)
    brushed_texture = brush_lines + grain

    # Apply brushed texture (subtle luminance modulation)
    arr_brushed = arr * (1 + brushed_texture[:, :, np.newaxis])
    arr_brushed = np.clip(arr_brushed, 0, 1)

    # Metallic edge: thin border simulating 3mm aluminum edge
    edge_px = max(int(w * 0.025), 15)
    lin = np.linspace(1.0, 0.0, edge_px, dtype=np.float32)
    edge_mask = np.zeros((h, w), dtype=np.float32)
    for i, v in enumerate(lin):
        edge_mask[:, i] = np.maximum(edge_mask[:, i], v)
        edge_mask[:, w - 1 - i] = np.maximum(edge_mask[:, w - 1 - i], v)
        edge_mask[i, :] = np.maximum(edge_mask[i, :], v)
        edge_mask[h - 1 - i, :] = np.maximum(edge_mask[h - 1 - i, :], v)

    # Edge highlight: cool gray metallic (not glossy)
    edge_op = 0.70
    a = (edge_mask * edge_op)[:, :, np.newaxis]
    # Brushed aluminum color: cool gray with slight blue
    metal_gray = np.array([0.94, 0.95, 0.97], dtype=np.float32)
    result = metal_gray * a + arr_brushed * (1 - a)

    # Very subtle vignette for depth (not glossy reflection)
    center_y, center_x = h // 2, w // 2
    y_coords, x_coords = np.ogrid[:h, :w]
    dist_from_center = np.sqrt((x_coords - center_x)**2 + (y_coords - center_y)**2)
    max_dist = np.sqrt(center_x**2 + center_y**2)
    vignette = 1 - 0.03 * (dist_from_center / max_dist)
    result = result * vignette[:, :, np.newaxis]

    # Slight contrast boost for metallic pop
    result = np.clip((result - 0.5) * 1.05 + 0.5, 0, 1)

    return Image.fromarray((result * 255).astype(np.uint8))


# ── Mockup master (fast resolution for web display) ─────────────────────────
def _get_art_master(equation_type, params, variant=None):
    # Use fast mockup resolution (2400×3000) instead of full print resolution
    # This is 4x faster to render while still looking sharp on screen
    specs = _MOCKUP_SPEC
    pw, ph = specs["width_px"], specs["height_px"]

    if variant == "spiral_notebook":
        # Match Printful's notebook print file ratio (1650x2550) so scaling perfectly matches the flat product shot
        pw, ph = 1650, 2550

    cache_key  = hashlib.md5(
        json.dumps({"eq": equation_type, "params": params, "w": pw, "h": ph, "type": "mockup_v3"},
                   sort_keys=True).encode()
    ).hexdigest()
    cache_path = os.path.join(MOCKUP_CACHE_DIR, f"master_{cache_key}.png")

    if os.path.exists(cache_path):
        return Image.open(cache_path).convert('RGB')

    art_bytes  = render_equation(equation_type, params, width=pw, height=ph, hq=True)
    art_master = Image.open(io.BytesIO(art_bytes)).convert('RGB')
    art_master.save(cache_path, format="PNG")
    return art_master


def _get_art_master_rgba(equation_type, params, target_w: int, target_h: int) -> Image.Image:
    """Render art with transparent background for acrylic see-through effect.
    The background color is detected from corner pixels and made transparent."""
    # Use fast mockup resolution
    specs = _MOCKUP_SPEC
    pw, ph = specs["width_px"], specs["height_px"]

    art_bytes = render_equation(equation_type, params, width=pw, height=ph, hq=True)
    art = Image.open(io.BytesIO(art_bytes)).convert('RGBA')

    # Sample background color from the four corners (3x3 area)
    arr = np.array(art, dtype=np.float32)
    corners = [arr[:8, :8, :3], arr[:8, -8:, :3],
               arr[-8:, :8, :3], arr[-8:, -8:, :3]]
    bg_color = np.concatenate([c.reshape(-1, 3) for c in corners]).mean(axis=0)

    # Build alpha mask: pixels far from bg_color are opaque, close are transparent
    rgb = arr[:, :, :3]
    dist = np.sqrt(((rgb - bg_color) ** 2).sum(axis=2))
    # Threshold: within 30 units of bg_color = transparent
    alpha = np.clip((dist - 20) / 40, 0, 1) * 255
    result = arr.copy()
    result[:, :, 3] = alpha.astype(np.uint8)

    return Image.fromarray(result.astype(np.uint8)).resize(
        (target_w, target_h), Image.LANCZOS
    )


# ── Public API ────────────────────────────────────────────────────────────────
def generate_mockup(equation_type: str, params: dict, variant: str = "studio", art_style: str = None, product_slug: str = None) -> bytes:
    tpl = next((t for t in PSD_TEMPLATES if t["id"] == variant), PSD_TEMPLATES[0])

    # Combine template art_style with passed art_style (passed takes precedence)
    template_art_style = tpl.get("art_style")
    effective_art_style = art_style or template_art_style

    cache_key  = hashlib.md5(
        json.dumps({
            "eq": equation_type,
            "params": params,
            "v": tpl["id"],
            "rv": tpl.get("cache_rev", 1),
            "style": effective_art_style,
            "product": product_slug,
        },
                   sort_keys=True).encode()
    ).hexdigest()
    cache_path = os.path.join(MOCKUP_CACHE_DIR, f"{cache_key}.jpg")

    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return f.read()

    bg, overlays = _load_template(tpl)
    scene = bg.copy()

    raw = _get_art_master(equation_type, params, variant=variant)
    
    if variant == "spiral_notebook" and product_slug:
        from services.watermark import add_elegant_equation
        eq_map = {
            "lorenz": ("LORENZ ATTRACTOR", "dx/dt = σ(y - x)"),
            "clifford": ("CLIFFORD ATTRACTOR", "x_{n+1} = sin(a y_n) + c cos(a x_n)"),
            "aizawa": ("AIZAWA ATTRACTOR", "dz/dt = c + a*z - z^3/3 - (x^2+y^2)(1+e*z) + f*z*x^3"),
            "julia": ("JULIA SET", "z_{n+1} = z_n^2 + c"),
            "mandelbrot": ("MANDELBROT SET", "z_{n+1} = z_n^2 + c"),
            "rose": ("POLAR ROSE", "r = a cos(kθ)"),
            "joukowski": ("JOUKOWSKI TRANSFORM", "w = z + 1/z"),
            "mobius-grid": ("MÖBIUS TRANSFORM", "f(z) = (az + b)/(cz + d)"),
            "superformula": ("SUPERFORMULA", "r = ( |cos(mθ/4)/a|^n_2 + |sin(mθ/4)/b|^n_3 )^{-1/n_1}"),
            "chladni": ("CHLADNI RESONANCE", "cos(nπx/L)cos(mπy/L) - cos(mπx/L)cos(nπy/L) = 0"),
            "turing": ("TURING PATTERN", "∂u/∂t = D_u ∇²u + f(u,v)"),
            "gray-scott": ("REACTION DIFFUSION", "∂v/∂t = D_v ∇²v - uv² - (F+k)v"),
            "voronoi": ("VORONOI TESSELLATION", "R_k = { x | d(x, P_k) ≤ d(x, P_j) }"),
            "flow-field": ("VECTOR FLOW", "v(x, y) = ∇ × A(x, y)"),
            "fractal-flame": ("FRACTAL FLAME", "F(x) = Σ p_i f_i(x)"),
            "de_jong": ("DE JONG ATTRACTOR", "x_{n+1} = sin(a y_n) - cos(b x_n)"),
        }
        title, eq_text = eq_map.get(equation_type, ("MATHEMATICAL PATTERN", "f(x, y) = 0"))
        raw = add_elegant_equation(raw, title, eq_text)

    bg_color = _detect_bg_color(raw)
    tw, th = tpl["art_w"], tpl["art_h"]

    if effective_art_style == "framed":
        art = _add_frame_border(raw, tw, th, bg_color)
    elif effective_art_style == "acrylic":
        art = raw.resize((tw, th), Image.LANCZOS)
        art = _add_acrylic_effect(art)
    elif effective_art_style == "aluminum":
        art = raw.resize((tw, th), Image.LANCZOS)
        art = _add_aluminum_effect(art)
    elif variant == "spiral_notebook":
        # FIT mode for notebooks: preserve aspect ratio, pad with background color
        # so circular patterns don't get squished into the rectangular cover.
        from PIL import ImageOps
        art = ImageOps.contain(raw, (tw, th), Image.LANCZOS)
        # Center the fitted art on a background-colored canvas
        padded = Image.new("RGB", (tw, th), tuple(int(c) for c in bg_color))
        offset_x = (tw - art.width) // 2
        offset_y = (th - art.height) // 2
        padded.paste(art, (offset_x, offset_y))
        art = padded
        
        # Apply a subtle burn on the left edge to simulate the shadow of the spiral binding
        arr = np.array(art, dtype=np.float32) / 255.0
        edge_w = int(tw * 0.08)
        lin = np.linspace(0.4, 1.0, edge_w, dtype=np.float32)
        shadow_mask = np.ones((th, tw), dtype=np.float32)
        shadow_mask[:, :edge_w] = lin
        arr = arr * shadow_mask[:, :, np.newaxis]
        art = Image.fromarray((arr * 255).astype(np.uint8))
    else:
        # Canvas, room, acrylic-standoff: scale to FILL (crop) ensuring no letterbox bands.
        art_w, art_h = raw.size
        scale = max(tw / art_w, th / art_h)
        scaled = raw.resize((int(art_w * scale), int(art_h * scale)), Image.LANCZOS)
        offset_x = (scaled.width - tw) // 2
        offset_y = (scaled.height - th) // 2
        art = scaled.crop((offset_x, offset_y, offset_x + tw, offset_y + th))


    if tpl.get("psd_type") == "acrylic-standoff" and params.get("transparent_bg"):
        art_rgba = _get_art_master_rgba(equation_type, params, tpl["art_w"], tpl["art_h"])
        scene.paste(art_rgba.convert('RGB'), (tpl["art_l"], tpl["art_t"]), art_rgba.split()[3])
    else:
        if variant == "spiral_notebook":
            bg_crop = scene.crop((tpl["art_l"], tpl["art_t"], tpl["art_l"] + tw, tpl["art_t"] + th))
            bg_arr = np.array(bg_crop, dtype=np.float32)
            art_arr = np.array(art.convert('RGB'), dtype=np.float32)
            
            # Mask out the left side (spiral area) so the math lines don't draw over the spiral rings.
            # Spiral takes about the first 75 pixels on the left.
            spiral_w = 75
            fade_w = 15
            art_alpha = np.ones((th, tw, 3), dtype=np.float32)
            art_alpha[:, :spiral_w, :] = 0.0
            
            # Fade transition
            fade = np.linspace(0.0, 1.0, fade_w, dtype=np.float32)
            art_alpha[:, spiral_w:spiral_w+fade_w, 0] = fade
            art_alpha[:, spiral_w:spiral_w+fade_w, 1] = fade
            art_alpha[:, spiral_w:spiral_w+fade_w, 2] = fade
            
            # Apply alpha mask and burn the left edge slightly for spiral shadow
            masked_art = art_arr * art_alpha
            shadow_mask = np.ones((th, tw, 3), dtype=np.float32)
            fade_shadow = np.linspace(0.6, 1.0, spiral_w+60, dtype=np.float32)
            shadow_mask[:, :spiral_w+60, 0] = fade_shadow
            shadow_mask[:, :spiral_w+60, 1] = fade_shadow
            shadow_mask[:, :spiral_w+60, 2] = fade_shadow
            masked_art = masked_art * shadow_mask
            
            # Lighten blend mode preserves the realistic notebook texture while printing the bright math lines
            blended = np.maximum(bg_arr, masked_art)
            blended_img = Image.fromarray(blended.astype(np.uint8))
            scene.paste(blended_img, (tpl["art_l"], tpl["art_t"]))
        else:
            scene.paste(art, (tpl["art_l"], tpl["art_t"]))

    psd_type  = tpl.get("psd_type", tpl["id"])
    out_scale = tpl["scale"]

    if psd_type in ("free-canvas", "free-hanging-poster"):
        # Shadow layers span the full canvas — apply numpy blends at output resolution
        # to avoid 300+ MB peak allocations at full PSD size.
        W, H = scene.size
        scene = scene.resize((int(W * out_scale), int(H * out_scale)), Image.LANCZOS)
        scaled_overlays = {
            k: (
                v[0].resize(
                    (max(1, int(v[0].width * out_scale)),
                     max(1, int(v[0].height * out_scale))),
                    Image.LANCZOS,
                ),
                int(v[1] * out_scale), int(v[2] * out_scale), v[3],
            )
            for k, v in overlays.items()
        }
        _apply_overlays(scene, scaled_overlays, psd_type)
        result_img = scene
    else:
        _apply_overlays(scene, overlays, psd_type)

        if psd_type == "acrylic-standoff":
            for cx, cy in [(2120, 960), (3775, 1010), (2120, 3425), (3770, 3360)]:
                _draw_standoff(scene, cx, cy, r=58)
            _apply_acrylic_glass_overlay(scene, pl=1940, pt=780, pr=3960, pb=3560)

        W, H = scene.size
        result_img = scene.resize((int(W * out_scale), int(H * out_scale)), Image.LANCZOS)

    out = io.BytesIO()
    result_img.save(out, format="JPEG", quality=92, optimize=True)
    result = out.getvalue()

    with open(cache_path, "wb") as f:
        f.write(result)

    return result


def available_variants() -> list[str]:
    return [t["id"] for t in PSD_TEMPLATES]


# ── Flat poster compositor ─────────────────────────────────────────────────────
# Generates a clean poster: art centered on white/cream background with a
# subtle drop shadow. This image is BOTH the web preview AND the Printful
# print file — what the customer sees on screen is exactly what gets printed.

_FLAT_POSTER_MOCKUP_CACHE = "/tmp/mathrelaxing_flat_poster"
os.makedirs(_FLAT_POSTER_MOCKUP_CACHE, exist_ok=True)


def generate_flat_poster(
    equation_type: str,
    params: dict,
    width: int = 1200,
    height: int = 1600,
    bg_color: tuple = (252, 251, 249),   # ignored — bg auto-detected from art corners
    margin_pct: float = 0.0,
    shadow: bool = False,
) -> bytes:
    """
    Art letterboxed on a background matching the art's own bg color — no margins,
    no shadow. Width/height controls resolution: small for web, large (e.g. 5400×7200)
    for the Printful print file. Returns PNG bytes.
    """
    cache_key = hashlib.md5(
        json.dumps(
            {"eq": equation_type, "params": params,
             "w": width, "h": height, "v": "no_margin_v4"},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    cache_path = os.path.join(_FLAT_POSTER_MOCKUP_CACHE, f"{cache_key}.png")

    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return f.read()

    from routers.render import _ASPECT_MAP
    ratio = _ASPECT_MAP.get(equation_type, "portrait")

    if ratio == "square":
        # Renderers for grid-based simulations (Chladni, Turing, Voronoi, etc.) produce
        # a centered square pattern with solid background bands at the edges.
        # Render square, auto-detect the content bounds, zoom to fill the poster.
        sq = max(width, height)
        art_bytes = render_equation(equation_type, params,
                                    width=sq, height=sq, hq=True)
        art = Image.open(io.BytesIO(art_bytes)).convert("RGB")
        art_arr = np.array(art)

        # Find rows/cols that contain pattern (variance above noise floor)
        row_var = art_arr.var(axis=(1, 2))
        col_var = art_arr.var(axis=(0, 2))
        threshold = max(row_var.max() * 0.02, 50)
        content_rows = np.where(row_var > threshold)[0]
        content_cols = np.where(col_var > threshold)[0]

        if len(content_rows) > 4 and len(content_cols) > 4:
            top_b  = max(0, int(content_rows[0]) - 4)
            bot_b  = min(sq, int(content_rows[-1]) + 5)
            left_b = max(0, int(content_cols[0]) - 4)
            rgt_b  = min(sq, int(content_cols[-1]) + 5)
            art = art.crop((left_b, top_b, rgt_b, bot_b))

        # Scale to cover poster (no bands), then center-crop to poster size
        scale = max(width / art.width, height / art.height)
        new_w = int(art.width * scale)
        new_h = int(art.height * scale)
        art = art.resize((new_w, new_h), Image.LANCZOS)
        lft = (new_w - width)  // 2
        top = (new_h - height) // 2
        canvas = art.crop((lft, top, lft + width, top + height))
    else:
        # Attractor / fractal types have a natural aspect ratio — render at that
        # ratio and letterbox; gaps use the art's own bg color so they're invisible.
        if ratio == "landscape":
            nat_w = width
            nat_h = int(width * 4 / 5)
        else:  # portrait 4:5
            nat_w = width
            nat_h = int(width * 5 / 4)

        art_bytes = render_equation(equation_type, params,
                                    width=nat_w, height=nat_h, hq=True)
        art = Image.open(io.BytesIO(art_bytes)).convert("RGB")

        # Detect bg from corners for the letterbox fill color
        art_arr = np.array(art)
        corners = [art_arr[:10, :10], art_arr[:10, -10:],
                   art_arr[-10:, :10], art_arr[-10:, -10:]]
        canvas_bg = tuple(
            int(v) for v in np.concatenate([c.reshape(-1, 3) for c in corners]).mean(axis=0)
        )

        art_w, art_h = art.size
        scale = min(width / art_w, height / art_h)
        fit_w, fit_h = int(art_w * scale), int(art_h * scale)
        art = art.resize((fit_w, fit_h), Image.LANCZOS)

        canvas = Image.new("RGB", (width, height), canvas_bg)
        paste_x = (width  - fit_w) // 2
        paste_y = (height - fit_h) // 2
        canvas.paste(art, (paste_x, paste_y))

    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    result = out.getvalue()

    with open(cache_path, "wb") as f:
        f.write(result)

    return result
