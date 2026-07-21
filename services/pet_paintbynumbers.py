"""
pet_paintbynumbers.py — turn ONE customer pet photo into a multi-size
paint-by-numbers download bundle (a ZIP the buyer receives).

The photo is processed as-is (no background removal). One design is rendered at
several standard print sizes so the buyer can print on whatever paper they have.

Design rules baked in:
  * Orientation follows the photo. A landscape photo -> landscape pages, a
    portrait photo -> portrait pages, a square photo -> square sizes. The
    subject fills the sheet instead of sitting tiny inside big margins.
  * Grid density is measured on the LONG edge, so every square keeps the same
    physical size regardless of photo shape.
  * Same cell COUNT at every size => it is one picture scaled, not several
    different designs. Bigger paper = bigger, easier-to-paint squares.
  * Only sizes whose squares stay >= ~4 mm (paintable) are offered; A4 and the
    small US sizes are intentionally excluded for the default dense grid.

This wraps services.low_poly_engine.generate_low_poly (unchanged).

CLI:
    python -m services.pet_paintbynumbers <photo.jpg> [out_dir]
"""
import io
import os
import zipfile

from PIL import Image

from services.low_poly_engine import generate_low_poly

# matches LP_PAGE_MARGIN_PX in low_poly_engine
_MARGIN = 100

# same DejaVu path the low-poly web route uses, with fallbacks
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
)

# rectangular sizes as (long_edge_px, short_edge_px) @ 300 DPI
SIZES_RECT = {
    "A3_29.7x42cm":   (4961, 3508),
    "A2_42x59.4cm":   (7016, 4961),
    "A1_59.4x84.1cm": (9933, 7016),
    "US_14x11in":     (4200, 3300),
    "US_20x16in":     (6000, 4800),
    "US_24x18in":     (7200, 5400),
}
# square sizes as side_px @ 300 DPI (for square photos)
SIZES_SQUARE = {
    "40x40cm": 4724,
    "50x50cm": 5906,
    "60x60cm": 7087,
}

DEFAULT_NUM_COLORS = 16
DEFAULT_CELLS_LONG = 85    # squares along the long edge (grid density)
MIN_CELL_MM = 4.0          # a size is skipped if its squares fall below this


def _resolve_font(font_path=None):
    for p in ((font_path,) if font_path else ()) + _FONT_CANDIDATES:
        if p and os.path.exists(p):
            return p
    raise FileNotFoundError("No DejaVuSans.ttf found; pass font_path explicitly.")


def _orientation(w, h, tol=0.05):
    if abs(w - h) <= max(w, h) * tol:
        return "square"
    return "landscape" if w > h else "portrait"


def _pages_for(orient):
    """Yield (name, page_w_px, page_h_px), the page turned to match the photo."""
    if orient == "square":
        for name, side in SIZES_SQUARE.items():
            yield f"{name}_square", side, side
    else:
        for name, (lo, sh) in SIZES_RECT.items():
            yield ((f"{name}_landscape", lo, sh) if orient == "landscape"
                   else (f"{name}_portrait", sh, lo))


def _cell_mm(long_px, cells_long):
    """Physical square size in mm (300 DPI, minus page margins on the long edge)."""
    return (long_px / 300.0 * 25.4 - 2 * _MARGIN / 300.0 * 25.4) / cells_long


def build_bundle(image_bytes, out_dir, num_colors=DEFAULT_NUM_COLORS,
                 base_cells_long=DEFAULT_CELLS_LONG, font_path=None,
                 min_cell_mm=MIN_CELL_MM):
    """Render the paint-by-numbers bundle and return the path to the ZIP.

    For every included print size, writes a numbered sheet and a color
    reference (both 300 DPI PNG), plus HOW-TO-PRINT.txt, then zips them.
    """
    os.makedirs(out_dir, exist_ok=True)
    font_path = _resolve_font(font_path)
    w, h = Image.open(io.BytesIO(image_bytes)).size
    orient = _orientation(w, h)

    made = []
    for name, pw, ph in _pages_for(orient):
        long_px = max(pw, ph)
        if _cell_mm(long_px, base_cells_long) < min_cell_mm:
            continue  # squares would be too small to paint at this size
        side = max(8, round((long_px - 2 * _MARGIN) / base_cells_long))
        legend_font = max(16, round(16 * pw / 3508))
        col, colored = generate_low_poly(
            image_bytes=image_bytes, filename="pet.jpg", font_path=font_path,
            num_colors=num_colors, polygon_type="square", polygon_size=side,
            legend_font_size=legend_font, output_width=pw, output_height=ph)
        cpath = os.path.join(out_dir, f"paint-by-numbers_{name}_NUMBERED.png")
        rpath = os.path.join(out_dir, f"color-reference_{name}.png")
        with open(cpath, "wb") as f:
            f.write(col)
        with open(rpath, "wb") as f:
            f.write(colored)
        made += [cpath, rpath]

    if not made:
        raise RuntimeError("No print size met the minimum paintable cell size.")

    guide = os.path.join(out_dir, "HOW-TO-PRINT.txt")
    with open(guide, "w") as f:
        f.write(
            "YOUR CUSTOM PET PAINT-BY-NUMBERS\n"
            "================================\n\n"
            "Two files per size:\n"
            "  * ..._NUMBERED.png       -> the paint-by-numbers sheet you paint on\n"
            "  * color-reference_...png -> the finished-look guide\n\n"
            "All files are 300 DPI. Print at 100% / 'Actual size' (NOT 'fit to page').\n"
            "It is the SAME picture at every size. Bigger paper = bigger squares =\n"
            "easier to paint. Pick the size you like and print that one. For the\n"
            "clearest numbers we recommend the larger sizes.\n")
    made.append(guide)

    zpath = os.path.join(out_dir, "pet_paintbynumbers_bundle.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in made:
            z.write(p, os.path.basename(p))
    return zpath


def _main(argv):
    if not argv:
        print("usage: python -m services.pet_paintbynumbers <photo> [out_dir]")
        return 1
    photo = argv[0]
    out_dir = argv[1] if len(argv) > 1 else os.path.splitext(photo)[0] + "_bundle"
    with open(photo, "rb") as f:
        image_bytes = f.read()
    w, h = Image.open(io.BytesIO(image_bytes)).size
    print(f"photo {photo} {w}x{h} -> {_orientation(w, h)}")
    zpath = build_bundle(image_bytes, out_dir)
    print(f"bundle: {zpath} ({os.path.getsize(zpath) // 1024} KB)")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv[1:]))
