import fitz
import os

OUT_DIR = "static/downloads/digital"
os.makedirs(OUT_DIR, exist_ok=True)

PRINT_LINE = "Perfect-bound · 8.5 x 11 in · matte cover · printed on demand."
DIGITAL_LINE = "Digital Edition · Printable PDF · mathrelaxing.store"

def get_span_info(page, search_text):
    """Find bbox, font, size, color of a span containing search_text."""
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                if search_text in span["text"]:
                    return span
    return None

def fix_cover(src_path, search=PRINT_LINE, replace=DIGITAL_LINE):
    doc = fitz.open(src_path)
    page = doc[0]
    span = get_span_info(page, search)
    if span:
        bbox = fitz.Rect(span["bbox"])
        # Redact old text (fill with page background — white)
        page.add_redact_annot(bbox, fill=(1, 1, 1))
        page.apply_redactions()
        # Insert new text at same position
        color_int = span["color"]
        r = ((color_int >> 16) & 0xFF) / 255
        g = ((color_int >> 8) & 0xFF) / 255
        b_val = (color_int & 0xFF) / 255
        page.insert_text(
            (bbox.x0, bbox.y1 - 1),
            replace,
            fontname="helv",
            fontsize=span["size"],
            color=(r, g, b_val),
        )
        print(f"  ✓ Cover text replaced in {src_path}")
    else:
        print(f"  — Text not found in {src_path}, skipping")
    return doc

def fix_isbn(src_path):
    doc = fitz.open(src_path)
    page = doc[1]  # page 2 (index 1)
    span = get_span_info(page, "ISBN")
    if span:
        # Redact the whole line area
        bbox = fitz.Rect(span["bbox"])
        # Also find the full block to wipe ISBN lines
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            block_text = " ".join(
                sp["text"] for ln in b["lines"] for sp in ln["spans"]
            )
            if "ISBN" in block_text:
                # Redact the whole block
                page.add_redact_annot(fitz.Rect(b["bbox"]), fill=(1, 1, 1))
        page.apply_redactions()
        print(f"  ✓ ISBN removed from {src_path}")
    else:
        print(f"  — ISBN not found in {src_path}")
    return doc

def make_cta_page(book_title, template_page):
    """Create a CTA last page matching the interior style."""
    doc = fitz.open()
    page = doc.new_page(width=template_page.rect.width, height=template_page.rect.height)
    w, h = page.rect.width, page.rect.height

    # White background
    page.draw_rect(page.rect, color=None, fill=(1, 1, 1))

    cx = w / 2

    page.insert_text(
        (cx - 80, h * 0.38),
        "Thank you for coloring!",
        fontname="helv",
        fontsize=16,
        color=(0.2, 0.2, 0.2),
    )
    page.insert_text(
        (cx - 120, h * 0.46),
        "Discover more mathematical art at:",
        fontname="helv",
        fontsize=11,
        color=(0.4, 0.4, 0.4),
    )
    page.insert_text(
        (cx - 80, h * 0.52),
        "mathrelaxing.store",
        fontname="helv",
        fontsize=14,
        color=(0.2, 0.5, 0.8),
    )
    page.insert_text(
        (cx - 100, h * 0.60),
        "Find us on Etsy: themathrelaxing",
        fontname="helv",
        fontsize=11,
        color=(0.4, 0.4, 0.4),
    )
    page.insert_text(
        (cx - 110, h * 0.68),
        "YouTube · Pinterest · TikTok: @MathRelaxing",
        fontname="helv",
        fontsize=10,
        color=(0.5, 0.5, 0.5),
    )
    page.insert_text(
        (cx - 150, h * 0.82),
        "© MathRelaxing — For personal use only. Not for redistribution.",
        fontname="helv",
        fontsize=8,
        color=(0.6, 0.6, 0.6),
    )
    return doc

def merge_and_save(book_name, cover_doc, interior_path, out_path):
    interior = fitz.open(interior_path)
    # CTA page based on interior page size
    cta = make_cta_page(book_name, interior[0])

    final = fitz.open()
    final.insert_pdf(cover_doc)
    final.insert_pdf(interior)
    final.insert_pdf(cta)
    final.save(out_path, deflate=True, garbage=4)
    print(f"  ✓ Saved → {out_path} ({final.page_count} pages)")
    final.close()
    interior.close()
    cta.close()
    cover_doc.close()

# ── Book definitions ──────────────────────────────────────────────────────────

books = [
    {
        "name": "Fractal Flora",
        "cover": "static/downloads/fractal-flora-coloring-book/cover.pdf",
        "interior": "static/downloads/fractal-flora-coloring-book/interior.pdf",
        "out": f"{OUT_DIR}/fractal_flora_digital.pdf",
        "fix_cover": True,
        "fix_isbn": False,
    },
    {
        "name": "Hyperbolic Gardens",
        "cover": "static/downloads/hyperbolic-gardens/cover.pdf",
        "interior": "static/downloads/hyperbolic-gardens/interior.pdf",
        "out": f"{OUT_DIR}/hyperbolic_gardens_digital.pdf",
        "fix_cover": True,
        "fix_isbn": False,
    },
    {
        "name": "Sacred Geometry",
        "cover": "static/downloads/sacred-math-coloring-book/cover.pdf",
        "interior": "static/downloads/sacred-math-coloring-book/interior.pdf",
        "out": f"{OUT_DIR}/sacred_geometry_digital.pdf",
        "fix_cover": True,
        "fix_isbn": False,
    },
    {
        "name": "Mathematical Tangle Art",
        "cover": "static/downloads/book/cover.pdf",
        "interior": "static/downloads/book/interior.pdf",
        "out": f"{OUT_DIR}/mathematical_tangle_art_digital.pdf",
        "fix_cover": False,
        "fix_isbn": True,
    },
    {
        "name": "Sacred Harmonics",
        "cover": None,
        "interior": "static/downloads/Sacred_Harmonics_Book.pdf",
        "out": f"{OUT_DIR}/sacred_harmonics_digital.pdf",
        "fix_cover": False,
        "fix_isbn": False,
    },
]

for book in books:
    print(f"\n── {book['name']} ──")

    if book["fix_isbn"]:
        interior_doc = fix_isbn(book["interior"])
        # Save fixed interior to temp
        tmp = f"/tmp/{book['name'].replace(' ','_')}_interior_fixed.pdf"
        interior_doc.save(tmp)
        interior_doc.close()
        interior_path = tmp
    else:
        interior_path = book["interior"]

    if book["cover"]:
        if book["fix_cover"]:
            cover_doc = fix_cover(book["cover"])
        else:
            cover_doc = fitz.open(book["cover"])
        merge_and_save(book["name"], cover_doc, interior_path, book["out"])
    else:
        # No cover — just add CTA to interior
        interior = fitz.open(interior_path)
        cta = make_cta_page(book["name"], interior[0])
        final = fitz.open()
        final.insert_pdf(interior)
        final.insert_pdf(cta)
        final.save(book["out"], deflate=True, garbage=4)
        print(f"  ✓ Saved → {book['out']} ({final.page_count} pages)")
        final.close()
        interior.close()
        cta.close()

print("\n✅ All done!")
