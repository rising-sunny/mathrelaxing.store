"""
Generates Pinterest-optimized vertical pin images (1000x1500 = 2:3 aspect).

Pinterest's algorithm strongly favors tall vertical pins. Each call returns
a JPEG composed from:
  - the existing product preview (centered, ~65% of canvas)
  - a top strip with the product name and "Mathematical Art" tagline
  - a bottom strip with price and brand mark

Variants 0, 1, 2 swap layout/colors so the same product gets multiple distinct
pins that won't look identical when boosted by Pinterest's "more like this".
"""
import io
import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

PIN_W, PIN_H = 1000, 1500
CACHE_DIR = "/tmp/mathrelaxing_pinterest"
os.makedirs(CACHE_DIR, exist_ok=True)

# Three visual variants — different color tones + layouts.
VARIANTS = [
    {  # 0: warm cream, classic layout (image up top, text strip below)
        "bg": (242, 235, 224),
        "ink": (38, 34, 28),
        "accent": (200, 169, 110),
        "subtle": (120, 110, 95),
        "layout": "classic",
    },
    {  # 1: dark plum, framed (centered image with thick frame)
        "bg": (28, 20, 32),
        "ink": (240, 234, 226),
        "accent": (200, 169, 110),
        "subtle": (160, 150, 140),
        "layout": "framed",
    },
    {  # 2: muted blue, magazine style (image top + bold typographic bottom)
        "bg": (24, 32, 44),
        "ink": (240, 238, 232),
        "accent": (140, 180, 220),
        "subtle": (160, 170, 180),
        "layout": "magazine",
    },
]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold
         else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
         else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                   y: int, color, max_width: int) -> int:
    """Draw text centered horizontally, wrapping if needed. Returns y after the text block."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = (cur + " " + w).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] > max_width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = candidate
    if cur:
        lines.append(cur)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (PIN_W - w) // 2
        draw.text((x, y), line, font=font, fill=color)
        y += h + 6
    return y


def _load_static(slug: str) -> Optional[Image.Image]:
    base = "/var/www/mathrelaxing.store/static/previews"
    candidates = [f"{slug}_clean.jpg", f"{slug}.jpg"]
    if slug == "sacred-harmonics-coloring-book":
        candidates.append("../img/sacred_harmonics_cover.png")
    elif slug == "mathematical-tangle-art-coloring-book":
        candidates.append("../img/book_cover.png")
        
    for candidate in candidates:
        path = os.path.normpath(os.path.join(base, candidate))
        if os.path.exists(path):
            try:
                return Image.open(path).convert("RGB")
            except Exception:
                continue
    return None


def _render_from_equation(equation_type: str, params: dict, collection: str) -> Optional[Image.Image]:
    """Sync render using the existing equation/desk-mat engines.
    No DB lookup, no recursion — pure rendering from already-known params."""
    try:
        if collection == "desk-mats":
            from services.deskmat_renderer import render_deskmat_design
            png_bytes = render_deskmat_design(equation_type, params, 1600, 800)
        else:
            from services.renderer import render_equation
            png_bytes = render_equation(equation_type, params, 1200, 1200)
        return Image.open(io.BytesIO(png_bytes)).convert("RGB")
    except Exception:
        return None


def _render_dynamic(product_slug: str) -> Optional[Image.Image]:
    """Generate a preview image by calling the same renderers used by
    /api/render/preview — directly in-process, no HTTP. This avoids
    deadlocking the single uvicorn worker when render_pin is itself
    handling a /api/render/pinterest request."""
    import json as _json
    try:
        from database import SessionLocal
        from models.product import DigitalProduct, Product

        db = SessionLocal()
        try:
            item = (db.query(DigitalProduct).filter(DigitalProduct.slug == product_slug).first()
                    or db.query(Product).filter(Product.slug == product_slug).first())
            if not item:
                return None
            collection = getattr(item, "collection", "") or ""
            equation_type = getattr(item, "equation_type", None)
            params_json = getattr(item, "params_json", None)
            contents_json = getattr(item, "contents_json", None)
        finally:
            db.close()

        # Bundle / loop-pack products have no equation params of their own.
        # Cover-image fallback chain:
        #   a) first item's slug or animation_key in /static/previews
        #   b) the pack's own indexed thumbnails ({slug}_0.jpg etc.)
        #   c) any sibling product in the same collection that does have a preview
        if not equation_type or not params_json:
            if contents_json:
                try:
                    contents = _json.loads(contents_json)
                    if isinstance(contents, list) and contents:
                        first = contents[0]
                        candidates_keys = []
                        if isinstance(first, dict):
                            for k in ("slug", "id", "animation_key"):
                                v = first.get(k)
                                if v:
                                    candidates_keys.append(str(v))
                        elif isinstance(first, str):
                            candidates_keys.append(first)
                        for key in candidates_keys:
                            cover = _load_static(key)
                            if cover is not None:
                                return cover
                except Exception:
                    pass
            # (b) indexed thumbnails of the pack itself
            for i in range(0, 6):
                cover = _load_static(f"{product_slug}_{i}")
                if cover is not None:
                    return cover
            # (c) any sibling in the same collection — try static first, then
            #     fall back to dynamic equation render. Physical products almost
            #     always have equation_type+params_json even when no static
            #     preview was pre-generated.
            if collection:
                try:
                    db2 = SessionLocal()
                    try:
                        sib_digital = db2.query(DigitalProduct).filter(
                            DigitalProduct.collection == collection,
                            DigitalProduct.slug != product_slug,
                            DigitalProduct.active == True,
                        ).all()
                        sib_physical = db2.query(Product).filter(
                            Product.collection == collection,
                            Product.slug != product_slug,
                            Product.active == True,
                        ).all()
                    finally:
                        db2.close()
                    siblings = list(sib_digital) + list(sib_physical)
                    for s in siblings:
                        cover = _load_static(s.slug)
                        if cover is not None:
                            return cover
                    # No siblings had a static preview — try rendering a
                    # sibling that has equation_type + params_json.
                    for s in siblings:
                        s_eq = getattr(s, "equation_type", None)
                        s_pj = getattr(s, "params_json", None)
                        s_col = getattr(s, "collection", "") or ""
                        if s_eq and s_pj:
                            try:
                                cover = _render_from_equation(s_eq, _json.loads(s_pj), s_col)
                                if cover is not None:
                                    return cover
                            except Exception:
                                continue
                except Exception:
                    pass
            return None

        return _render_from_equation(equation_type, _json.loads(params_json), collection)
    except Exception:
        return None


def _load_preview(product_slug: str) -> Optional[Image.Image]:
    """Load product preview. Order:
      1) /static/previews/{slug}_clean.jpg  (no watermark — preferred)
      2) /static/previews/{slug}.jpg        (with watermark)
      3) render dynamically via in-process engines (desk-mats, dynamic eqs)
      4) for bundles/loop-packs without equation: cover from first item
    """
    img = _load_static(product_slug)
    if img is not None:
        return img
    return _render_dynamic(product_slug)


def _fit_image(src: Image.Image, target_w: int, target_h: int,
               bg: tuple) -> Image.Image:
    """Letterbox the source image into target dimensions, preserving aspect ratio."""
    sw, sh = src.size
    ratio = min(target_w / sw, target_h / sh)
    new_w = max(1, int(sw * ratio))
    new_h = max(1, int(sh * ratio))
    resized = src.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), bg)
    canvas.paste(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
    return canvas


def render_pin(*, product_slug: str, name: str, price_usd: float,
               collection: str = "", variant: int = 0,
               product_label: str = "Digital Download") -> bytes:
    """Render a Pinterest-optimized vertical pin. Returns JPEG bytes."""
    variant = max(0, min(variant, len(VARIANTS) - 1))
    v = VARIANTS[variant]

    label_key = "".join(ch.lower() if ch.isalnum() else "-" for ch in product_label).strip("-")
    cache_key = f"{product_slug}__v{variant}__label-{label_key or 'product'}.jpg"
    cache_path = os.path.join(CACHE_DIR, cache_key)
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as fh:
            return fh.read()

    canvas = Image.new("RGB", (PIN_W, PIN_H), v["bg"])
    draw = ImageDraw.Draw(canvas)

    src = _load_preview(product_slug)
    # Track whether we have a real product image so we can skip caching
    # garbage renders (canvas with only text and no product visual).
    has_image = src is not None
    # Build the image area depending on layout
    if v["layout"] == "classic":
        img_area_top, img_area_h = 80, 950
        img_box_w, img_box_h = PIN_W - 120, img_area_h
        if src:
            fitted = _fit_image(src, img_box_w, img_box_h, v["bg"])
            canvas.paste(fitted, ((PIN_W - img_box_w) // 2, img_area_top))
        text_top = img_area_top + img_area_h + 60

        f_tag = _font(38, bold=False)
        f_title = _font(58, bold=True)
        f_price = _font(64, bold=True)
        f_brand = _font(26, bold=False)
        y = text_top
        y = _draw_centered(draw, product_label, f_tag, y, v["subtle"], PIN_W - 120)
        y += 14
        y = _draw_centered(draw, name, f_title, y, v["ink"], PIN_W - 120)
        y += 24
        y = _draw_centered(draw, f"From ${int(price_usd)}", f_price, y, v["accent"], PIN_W - 120)
        # Bottom brand
        bbox = draw.textbbox((0, 0), "mathrelaxing.store", font=f_brand)
        draw.text(((PIN_W - (bbox[2] - bbox[0])) // 2, PIN_H - 60), "mathrelaxing.store",
                  font=f_brand, fill=v["subtle"])

    elif v["layout"] == "framed":
        # Solid border, centered image, text bottom
        pad = 70
        inner_top = 200
        inner_h = 900
        if src:
            fitted = _fit_image(src, PIN_W - 2 * pad, inner_h, v["bg"])
            canvas.paste(fitted, (pad, inner_top))
        # Outline frame
        draw.rectangle((pad - 6, inner_top - 6, PIN_W - pad + 6, inner_top + inner_h + 6),
                       outline=v["accent"], width=4)

        f_tag = _font(30, bold=False)
        f_title = _font(54, bold=True)
        f_price = _font(40, bold=True)
        y = 60
        bbox = draw.textbbox((0, 0), "MATHRELAXING", font=f_tag)
        draw.text(((PIN_W - (bbox[2] - bbox[0])) // 2, y),
                  "MATHRELAXING", font=f_tag, fill=v["accent"])
        y = inner_top + inner_h + 60
        y = _draw_centered(draw, name, f_title, y, v["ink"], PIN_W - 100)
        y += 20
        y = _draw_centered(draw, f"{product_label}  ·  From ${int(price_usd)}",
                           f_price, y, v["subtle"], PIN_W - 100)

    else:  # magazine
        # Image up top (60%), big typographic block in lower 40%
        img_h = 900
        if src:
            fitted = _fit_image(src, PIN_W, img_h, v["bg"])
            canvas.paste(fitted, (0, 0))
        # Color band over image bottom for legibility
        band = Image.new("RGBA", (PIN_W, 100), (*v["bg"], 200))
        canvas.paste(band, (0, img_h - 50), band)

        f_kicker = _font(28, bold=False)
        f_title = _font(72, bold=True)
        f_meta = _font(32, bold=False)
        f_cta = _font(34, bold=True)
        y = img_h + 50
        y = _draw_centered(draw, "MATHRELAXING", f_kicker, y, v["accent"], PIN_W - 80)
        y += 18
        y = _draw_centered(draw, name, f_title, y, v["ink"], PIN_W - 80)
        y += 22
        y = _draw_centered(draw, f"{product_label} · From ${int(price_usd)}",
                           f_meta, y, v["subtle"], PIN_W - 80)
        y += 14
        y = _draw_centered(draw, "mathrelaxing.store →", f_cta, y, v["accent"], PIN_W - 80)

    # Encode
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=88, optimize=True)
    data = buf.getvalue()
    # Only cache if the product image actually loaded — otherwise we'd be
    # persisting a render with only fonts on a blank background and serve
    # that bad version to Pinterest forever (Pinterest never re-fetches).
    if has_image:
        try:
            with open(cache_path, "wb") as fh:
                fh.write(data)
        except Exception:
            pass
    return data


def render_etsy_pin(*, listing_id: str, image_bytes: bytes, title: str,
                    label: str = "Digital Download", variant: int = 0) -> Optional[bytes]:
    """Render a 2:3 pin from an Etsy listing image. Returns JPEG bytes, or None
    if the source image cannot be decoded.

    Etsy listing images are square or 4:5; Pinterest favours 1000x1500, so the
    listing image is letterboxed into a branded vertical canvas instead of being
    pinned raw. `variant` rotates colour/layout so re-pins of the same listing
    do not look identical."""
    variant = max(0, min(variant, len(VARIANTS) - 1))
    v = VARIANTS[variant]

    cache_path = os.path.join(CACHE_DIR, f"etsy-{listing_id}__v{variant}.jpg")
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as fh:
            return fh.read()

    try:
        src = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None

    canvas = Image.new("RGB", (PIN_W, PIN_H), v["bg"])
    draw = ImageDraw.Draw(canvas)

    if v["layout"] == "framed":
        pad, inner_top, inner_h = 70, 190, 920
        canvas.paste(_fit_image(src, PIN_W - 2 * pad, inner_h, v["bg"]), (pad, inner_top))
        draw.rectangle((pad - 6, inner_top - 6, PIN_W - pad + 6, inner_top + inner_h + 6),
                       outline=v["accent"], width=4)
        f_kicker, f_title, f_cta = _font(30), _font(52, bold=True), _font(32, bold=True)
        bbox = draw.textbbox((0, 0), "MATHRELAXING", font=f_kicker)
        draw.text(((PIN_W - (bbox[2] - bbox[0])) // 2, 60), "MATHRELAXING",
                  font=f_kicker, fill=v["accent"])
        y = inner_top + inner_h + 50
        y = _draw_centered(draw, title, f_title, y, v["ink"], PIN_W - 100)
        y += 20
        _draw_centered(draw, f"{label}  ·  on Etsy", f_cta, y, v["subtle"], PIN_W - 100)

    else:  # classic / magazine share one clean vertical composition
        img_top, img_h = 90, 960
        canvas.paste(_fit_image(src, PIN_W - 120, img_h, v["bg"]), (60, img_top))
        f_kicker, f_title, f_cta = _font(30), _font(56, bold=True), _font(34, bold=True)
        y = img_top + img_h + 55
        y = _draw_centered(draw, label.upper(), f_kicker, y, v["subtle"], PIN_W - 120)
        y += 16
        y = _draw_centered(draw, title, f_title, y, v["ink"], PIN_W - 120)
        y += 22
        # Plain ASCII only — the font falls back to PIL's default when DejaVu is
        # missing, and a glyph like "→" would render as tofu on the pin.
        _draw_centered(draw, "Shop on Etsy", f_cta, y, v["accent"], PIN_W - 120)

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=88, optimize=True)
    data = buf.getvalue()
    try:
        with open(cache_path, "wb") as fh:
            fh.write(data)
    except Exception:
        pass
    return data


def invalidate_cache(product_slug: Optional[str] = None) -> int:
    """Remove cached pin images. If slug given, only that product's pins."""
    n = 0
    for f in os.listdir(CACHE_DIR):
        if product_slug and not f.startswith(product_slug + "__"):
            continue
        try:
            os.remove(os.path.join(CACHE_DIR, f))
            n += 1
        except OSError:
            pass
    return n
