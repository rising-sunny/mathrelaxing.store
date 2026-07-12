import io
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from sklearn.cluster import KMeans

LP_PAGE_MARGIN_PX = 100
SWATCH_SIZE = 38
LEGEND_PADDING = 10
LEGEND_TEXT_PAD = 8

PAGE_FORMATS = {
    "a4-portrait":         (2480, 3508),   # A4 @ 300 DPI
    "a4-landscape":        (3508, 2480),
    "letter-portrait":     (2550, 3300),   # US Letter @ 300 DPI
    "letter-landscape":    (3300, 2550),
}

OUTPUT_DPI = {
    "auto":            150,
    "a4-portrait":     300,
    "a4-landscape":    300,
    "letter-portrait": 300,
    "letter-landscape":300,
}


def _quantize_colors(image, num_colors):
    if image.mode != "RGB":
        image = image.convert("RGB")
    w, h = image.size
    max_dim = 400
    if w > max_dim or h > max_dim:
        if w > h:
            nw, nh = max_dim, int(h * (max_dim / w))
        else:
            nh, nw = max_dim, int(w * (max_dim / h))
        small = image.resize((nw, nh), Image.Resampling.LANCZOS)
    else:
        small = image
    arr = np.array(small).reshape((-1, 3))
    km = KMeans(n_clusters=num_colors, random_state=42, n_init="auto", algorithm="lloyd")
    km.fit(arr)
    palette = km.cluster_centers_.astype(int)
    full_arr = np.array(image).reshape((-1, 3))
    labels = km.predict(full_arr)
    ih, iw = image.size[1], image.size[0]
    quantized = Image.fromarray(
        palette[labels].reshape((ih, iw, 3)).astype(np.uint8), "RGB"
    )
    return quantized, palette


def _find_closest_color_number(color, color_map):
    if color in color_map:
        return color_map[color]
    min_dist = float("inf")
    closest = None
    for map_c, num in color_map.items():
        dist = sum((a - b) ** 2 for a, b in zip(color, map_c))
        if dist < min_dist:
            min_dist = dist
            closest = num
    return closest


def _estimate_legend_height(num_colors, legend_font_size, available_width):
    max_text_w = int(legend_font_size * 1.4)
    item_w = SWATCH_SIZE + LEGEND_TEXT_PAD + max_text_w + LEGEND_PADDING
    items_per_row = max(1, int(available_width // item_w))
    n_rows = math.ceil(num_colors / items_per_row)
    return n_rows * (SWATCH_SIZE + LEGEND_PADDING) + LEGEND_PADDING * 4


def _draw_centered_text(draw, text, rect_coords, side, text_color, font_path):
    try:
        font_size = max(7, int(side * 0.65))
        font = ImageFont.truetype(font_path, font_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        limit = side - 4
        if tw > limit or th > limit:
            scale = min(limit / max(tw, 1), limit / max(th, 1))
            font_size = max(5, int(font_size * scale))
            font = ImageFont.truetype(font_path, font_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        cx = (rect_coords[0] + rect_coords[2]) / 2
        cy = (rect_coords[1] + rect_coords[3]) / 2
        draw.text((cx - tw / 2, cy - th / 2), text, fill=text_color, font=font)
    except (IOError, OSError):
        font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        cx = (rect_coords[0] + rect_coords[2]) / 2
        cy = (rect_coords[1] + rect_coords[3]) / 2
        draw.text((cx - tw / 2, cy - th / 2), text, fill=text_color, font=font)


def _draw_legend(draw, number_to_color_map, x, y, max_width, font):
    items = sorted(number_to_color_map.items())
    max_text_w = max(draw.textbbox((0, 0), str(k), font=font)[2] for k, _ in items)
    item_full_w = SWATCH_SIZE + LEGEND_TEXT_PAD + max_text_w + LEGEND_PADDING
    items_per_row = max(1, int(max_width // item_full_w))
    cx, cy = x, y
    for i, (number, color) in enumerate(items):
        if i > 0 and i % items_per_row == 0:
            cx = x
            cy += SWATCH_SIZE + LEGEND_PADDING
        draw.rectangle(
            [cx, cy, cx + SWATCH_SIZE, cy + SWATCH_SIZE],
            fill=color,
            outline=(80, 80, 80),
        )
        th = draw.textbbox((0, 0), str(number), font=font)[3]
        draw.text(
            (cx + SWATCH_SIZE + LEGEND_TEXT_PAD, cy + (SWATCH_SIZE - th) / 2),
            str(number),
            fill=(50, 50, 50),
            font=font,
        )
        cx += item_full_w


def generate_low_poly(
    image_bytes: bytes,
    filename: str,
    font_path: str,
    num_colors: int = 16,
    polygon_type: str = "square",
    polygon_size: int = 30,
    grid_opacity: int = 200,
    number_opacity: int = 80,
    legend_font_size: int = 16,
    page_format: str = "auto",
    output_width: int | None = None,
    output_height: int | None = None,
) -> tuple[bytes, bytes]:
    """Returns (coloring_png_bytes, colored_png_bytes)."""
    try:
        original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"No se pudo abrir la imagen: {e}")

    poly_type = polygon_type.lower()
    side = polygon_size

    try:
        quantized, palette = _quantize_colors(original, num_colors)
    except Exception as e:
        raise RuntimeError(f"Error en cuantizacion: {e}") from e

    color_map = {tuple(int(c) for c in col): i + 1 for i, col in enumerate(palette)}
    num_to_color = {i + 1: tuple(int(c) for c in col) for i, col in enumerate(palette)}

    img_w, img_h = original.size

    if poly_type == "square":
        art_w = max((img_w // side) * side, side)
        art_h = max((img_h // side) * side, side)
    elif poly_type == "hexagonal":
        hex_w = math.sqrt(3) * side
        art_w = max(int((img_w // hex_w) * hex_w), side)
        art_h = img_h
    else:
        raise ValueError(f"Tipo de poligono no soportado: {polygon_type}")

    if page_format in PAGE_FORMATS:
        output_width, output_height = PAGE_FORMATS[page_format]

    margin = LP_PAGE_MARGIN_PX
    legend_gap = int(margin * 0.6)

    def _compute_layout(aw, ah, ow, oh):
        if ow and oh:
            lw = ow - 2 * margin
            lh = _estimate_legend_height(num_colors, legend_font_size, lw)
            max_aw = ow - 2 * margin
            max_ah = oh - lh - legend_gap - 2 * margin
            # Always scale to fill the page (up or down)
            sc = min(max_aw / aw, max_ah / ah)
            aw, ah = max(int(aw * sc), side), max(int(ah * sc), side)
            return (ow, oh), aw, ah
        elif ow:
            max_aw = ow - 2 * margin
            sc = max_aw / aw   # scale up or down to fill width
            aw, ah = max(int(aw * sc), side), max(int(ah * sc), side)
            lh = _estimate_legend_height(num_colors, legend_font_size, ow - 2 * margin)
            ps = (ow, margin + ah + legend_gap + lh + margin)
            return ps, aw, ah
        elif oh:
            lh = _estimate_legend_height(num_colors, legend_font_size, aw)
            max_ah = oh - lh - legend_gap - 2 * margin
            sc = max_ah / ah   # scale up or down to fill height
            aw, ah = max(int(aw * sc), side), max(int(ah * sc), side)
            lh = _estimate_legend_height(num_colors, legend_font_size, aw)
            ps = (aw + 2 * margin, oh)
            return ps, aw, ah
        else:
            lh = _estimate_legend_height(num_colors, legend_font_size, aw)
            ps = (aw + 2 * margin, margin + ah + legend_gap + lh + margin)
            return ps, aw, ah

    page_size, art_w, art_h = _compute_layout(art_w, art_h, output_width, output_height)
    art_w = max(art_w, 1)
    art_h = max(art_h, 1)

    quantized_resized = quantized.resize((art_w, art_h), Image.Resampling.LANCZOS)

    coloring_img = Image.new("RGB", page_size, (255, 255, 255))
    draw = ImageDraw.Draw(coloring_img)
    colored_img = Image.new("RGB", page_size, (255, 255, 255))
    draw_c = ImageDraw.Draw(colored_img)

    offset_x = (page_size[0] - art_w) // 2
    offset_y = margin

    grid_gray = int(255 * (1 - grid_opacity / 255.0))
    num_gray = int(255 * (1 - number_opacity / 255.0))
    grid_color = (grid_gray, grid_gray, grid_gray)
    text_color = (num_gray, num_gray, num_gray)

    if poly_type == "square":
        for y in range(0, art_h, side):
            for x in range(0, art_w, side):
                box = (x, y, min(x + side, art_w), min(y + side, art_h))
                tile = quantized_resized.crop(box)
                avg = tuple(int(v) for v in np.array(tile).mean(axis=(0, 1)))
                num = _find_closest_color_number(avg, color_map)
                if num is None:
                    continue
                rc = (offset_x + x, offset_y + y, offset_x + x + side, offset_y + y + side)
                draw.rectangle(rc, fill=(255, 255, 255), outline=grid_color)
                _draw_centered_text(draw, str(num), rc, side, text_color, font_path)
                draw_c.rectangle(rc, fill=avg, outline=None)

    elif poly_type == "hexagonal":
        s = side
        horiz_dist = math.sqrt(3) * s
        vert_dist = s * 3 / 2
        for r in range(math.ceil(art_h / vert_dist) + 1):
            for q in range(math.ceil(art_w / horiz_dist) + 1):
                cx = q * horiz_dist + ((horiz_dist / 2) if r % 2 != 0 else 0)
                cy = r * vert_dist
                avg = quantized_resized.getpixel(
                    (max(0, min(art_w - 1, int(cx))), max(0, min(art_h - 1, int(cy))))
                )
                num = _find_closest_color_number(avg, color_map)
                if num is None:
                    continue
                lp = [
                    (cx + s * math.cos(math.radians(30 + 60 * i)),
                     cy + s * math.sin(math.radians(30 + 60 * i)))
                    for i in range(6)
                ]
                if not (
                    min(p[0] for p in lp) >= 0 and max(p[0] for p in lp) <= art_w
                    and min(p[1] for p in lp) >= 0 and max(p[1] for p in lp) <= art_h
                ):
                    continue
                fp = [(offset_x + p[0], offset_y + p[1]) for p in lp]
                draw.polygon(fp, fill=(255, 255, 255), outline=grid_color)
                draw_c.polygon(fp, fill=avg, outline=None)
                pcx = offset_x + cx
                pcy = offset_y + cy
                _draw_centered_text(draw, str(num), (pcx - s, pcy - s, pcx + s, pcy + s), s, text_color, font_path)

    # Legend
    legend_y = offset_y + art_h + legend_gap
    legend_max_w = page_size[0] - 2 * margin
    try:
        leg_font = ImageFont.truetype(font_path, legend_font_size)
    except (IOError, OSError):
        leg_font = ImageFont.load_default()
    _draw_legend(draw, num_to_color, margin, legend_y, legend_max_w, leg_font)
    _draw_legend(draw_c, num_to_color, margin, legend_y, legend_max_w, leg_font)

    dpi = OUTPUT_DPI.get(page_format, 300)
    coloring_buf = io.BytesIO()
    coloring_img.save(coloring_buf, format="PNG", dpi=(dpi, dpi))
    colored_buf = io.BytesIO()
    colored_img.save(colored_buf, format="PNG", dpi=(dpi, dpi))

    return coloring_buf.getvalue(), colored_buf.getvalue()
