"""
Stylized, self-generated lifestyle scenes for stickers.

Printful's Kiss-Cut Sticker product only returns one flat mockup, so we build
our own scenes by compositing a sticker sprite (the design + a white kiss-cut
border + a drop shadow) onto a generated background:

  * "laptop" — the sticker placed on a space-gray laptop/device lid
  * "peel"   — the sticker on a surface with a curled, lifted corner

Pure Pillow; no stock photos. Returned as JPEG bytes.
"""
import io
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CANVAS = 1100

# Realistic laptop scene: a royalty-free closed-laptop photo (Unsplash, free for
# commercial use) with the sticker perspective-warped onto the lid.
LAPTOP_PHOTO = "/var/www/mathrelaxing.store/static/stickers/scenes/laptop.jpg"
# Sticker placement quad on the lid (TL, TR, BR, BL) in the photo's pixel coords.
LAPTOP_QUAD = [(360, 470), (700, 405), (742, 735), (402, 800)]
# Set to True to draw the quad outline for tuning.
LAPTOP_DEBUG = os.getenv("STICKER_SCENE_DEBUG") == "1"


def _find_coeffs(dest, src):
    """Perspective coeffs that map output `dest` quad pixels back to `src` rect."""
    matrix = []
    for (dx, dy), (sx, sy) in zip(dest, src):
        matrix.append([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy])
        matrix.append([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy])
    A = np.array(matrix, dtype=np.float64)
    B = np.array(src, dtype=np.float64).reshape(8)
    res = np.linalg.solve(A, B)
    return res.tolist()


def _gradient(size, top, bottom):
    w, h = size
    col = Image.new("RGB", (1, h))
    px = col.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return col.resize(size).convert("RGBA")


def _sprite(design_path, target, border_passes=4):
    """Design + white kiss-cut border, transparent outside. Square `target` px."""
    d = Image.open(design_path).convert("RGBA").resize((target, target), Image.LANCZOS)
    dil = d.split()[3]
    for _ in range(border_passes):
        dil = dil.filter(ImageFilter.MaxFilter(9))
    sprite = Image.new("RGBA", d.size, (255, 255, 255, 0))
    sprite.putalpha(dil)
    white = Image.new("RGBA", d.size, (255, 255, 255, 255))
    white.putalpha(dil)
    sprite = white
    sprite.alpha_composite(d)
    return sprite


def _shadow(sprite, blur, offset, opacity):
    a = sprite.split()[3]
    layer = Image.new("RGBA", sprite.size, (0, 0, 0, 0))
    black = Image.new("RGBA", sprite.size, (0, 0, 0, opacity))
    layer.paste(black, (0, 0), a)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new("RGBA", (sprite.size[0] + 80, sprite.size[1] + 80), (0, 0, 0, 0))
    out.alpha_composite(layer, (40 + offset[0], 40 + offset[1]))
    return out


def _paste_center(base, layer, cx, cy):
    base.alpha_composite(layer, (int(cx - layer.size[0] / 2), int(cy - layer.size[1] / 2)))


def _laptop_stylized(design_path):
    W = H = CANVAS
    base = _gradient((W, H), (240, 237, 231), (212, 208, 199))

    # landscape lid in laptop proportions (~1.8:1)
    x0, y0, x1, y1 = 120, 320, 980, 800
    r = 40

    # floor shadow under the device
    fs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(fs).rounded_rectangle([x0 - 8, y0 + 44, x1 + 8, y1 + 74], radius=r, fill=(0, 0, 0, 85))
    base.alpha_composite(fs.filter(ImageFilter.GaussianBlur(36)))

    # body thickness (darker slab offset down) → reads as a real 3D device
    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(body).rounded_rectangle([x0, y0 + 26, x1, y1 + 26], radius=r, fill=(39, 42, 47, 255))
    base.alpha_composite(body)

    # lid top surface
    lid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(lid)
    dr.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=(62, 66, 73, 255))
    dr.rounded_rectangle([x0, y0, x1, y1], radius=r, outline=(88, 92, 100, 255), width=2)
    dr.rounded_rectangle([x0 + 18, y0 + 10, x1 - 18, y0 + 20], radius=5, fill=(86, 90, 98, 150))
    base.alpha_composite(lid)

    # sticker on the lid (center-left), slightly rotated
    sp = _sprite(design_path, target=300)
    rot = -6
    sh = _shadow(sp, blur=16, offset=(6, 12), opacity=115).rotate(rot, expand=True, resample=Image.BICUBIC)
    spr = sp.rotate(rot, expand=True, resample=Image.BICUBIC)
    cx, cy = W * 0.40, (y0 + y1) / 2
    _paste_center(base, sh, cx, cy + 4)
    _paste_center(base, spr, cx, cy)
    return base


def _peel(design_path):
    W = H = CANVAS
    # mid-tone surface so BOTH light (cream) and dark sticker designs keep contrast
    base = _gradient((W, H), (201, 194, 182), (168, 160, 148))

    sp = _sprite(design_path, target=620)
    rot = -4
    sh = _shadow(sp, blur=24, offset=(6, 22), opacity=130).rotate(rot, expand=True, resample=Image.BICUBIC)
    spr = sp.rotate(rot, expand=True, resample=Image.BICUBIC)
    _paste_center(base, sh, W * 0.5, H * 0.52 + 10)
    _paste_center(base, spr, W * 0.5, H * 0.5)

    # curled top-right corner: a shadow wedge on the sticker + a light "vinyl back" flap
    ox = int(W * 0.5 - spr.size[0] / 2)
    oy = int(H * 0.5 - spr.size[1] / 2)
    sw, sh2 = spr.size
    cs = int(sw * 0.26)  # corner size
    # shadow cast by the lifted corner onto the sticker face
    wedge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wedge)
    tipx, tipy = ox + sw - 6, oy + 8
    wd.polygon([(tipx - cs, tipy), (tipx, tipy + cs), (tipx - cs * 0.5, tipy + cs * 0.5)], fill=(0, 0, 0, 90))
    base.alpha_composite(wedge.filter(ImageFilter.GaussianBlur(9)))
    # the curled flap (back of the vinyl: white→light grey), flipped to point outward
    flap = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(flap)
    fd.polygon(
        [(tipx - cs, tipy), (tipx + cs * 0.30, tipy - cs * 0.30), (tipx + 6, tipy + cs)],
        fill=(245, 244, 240, 255),
    )
    fd.line([(tipx - cs, tipy), (tipx + 6, tipy + cs)], fill=(208, 205, 198, 255), width=4)
    fsh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(fsh).polygon(
        [(tipx - cs + 8, tipy + 8), (tipx + cs * 0.30 + 8, tipy - cs * 0.30 + 10), (tipx + 12, tipy + cs + 8)],
        fill=(0, 0, 0, 70),
    )
    base.alpha_composite(fsh.filter(ImageFilter.GaussianBlur(7)))
    base.alpha_composite(flap)
    return base


def _laptop_photo(design_path):
    photo = Image.open(LAPTOP_PHOTO).convert("RGBA")
    W, H = photo.size
    sp = _sprite(design_path, target=520, border_passes=3)
    src_rect = [(0, 0), (sp.width, 0), (sp.width, sp.height), (0, sp.height)]
    coeffs = _find_coeffs(LAPTOP_QUAD, src_rect)
    warped = sp.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC)

    # tight contact shadow (sticker lies flush on the lid; light from upper-left)
    a = warped.split()[3]
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh.paste(Image.new("RGBA", (W, H), (0, 0, 0, 95)), (0, 0), a)
    sh = sh.filter(ImageFilter.GaussianBlur(7))
    off = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    off.alpha_composite(sh, (5, 8))

    out = photo.copy()
    out.alpha_composite(off)
    out.alpha_composite(warped)
    if LAPTOP_DEBUG:
        ImageDraw.Draw(out).polygon(LAPTOP_QUAD, outline=(255, 0, 0, 255))
    return out


def _laptop(design_path):
    if os.path.exists(LAPTOP_PHOTO):
        return _laptop_photo(design_path)
    return _laptop_stylized(design_path)


SCENES = {"laptop": _laptop, "peel": _peel}


def render_scene(design_path: str, scene: str) -> bytes:
    if scene not in SCENES or not os.path.exists(design_path):
        raise ValueError(f"Unknown sticker scene or missing design: {scene}")
    img = SCENES[scene](design_path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()
