"""
Fix eBay listings with broken gallery previews (black SVG crops, TOC PDF pages).

Targets from audit:
- geometric-cbn-ipad-interactive (pure black design-*.jpg)
- spiral-tilings-ipad-interactive (pure black)
- sacred-geometry-svg-ipad-interactive (black broken crop)
- Plus re-check other iPad coloring packs for GoodNotes TOC pages / nested PNG packs
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw

ROOT = Path("/var/www/mathrelaxing.store")
load_dotenv(ROOT / ".env")
os.chdir(ROOT)

from database import SessionLocal  # noqa: E402
from models.product import DigitalProduct  # noqa: E402
import services.ebay as ebay  # noqa: E402

PUBLIC = "https://mathrelaxing.store"
MAX = 10

# sibling sources: interactive slug -> zip paths that may contain real art PNGs/PDFs
PRODUCT_ZIPS = {
    "geometric-cbn-ipad-interactive": [
        ROOT / "static/downloads/geometric-cbn-ipad-interactive.zip",
    ],
    "spiral-tilings-ipad-interactive": [
        ROOT / "static/downloads/spiral-tilings-ipad-interactive.zip",
        ROOT / "static/downloads/spiral_tilings_digital.pdf",
        ROOT / "private_downloads/spiral-tilings-coloring-book-digital.pdf",
        ROOT / "static/downloads/spiral-tilings-coloring-book-digital.zip",
    ],
    "sacred-geometry-svg-ipad-interactive": [
        ROOT / "static/downloads/sacred-geometry-svg-ipad-interactive.zip",
        ROOT / "private_downloads/sacred-geometry-ipad-coloring.zip",
        ROOT / "private_downloads/sacred-geometry-coloring-book-digital.pdf",
        ROOT / "static/downloads/sacred_geometry_digital.pdf",
    ],
    "fractal-flora-ipad-coloring": [
        ROOT / "private_downloads/fractal-flora-ipad-coloring.zip",
        ROOT / "private_downloads/fractal-flora-coloring-book-digital.pdf",
    ],
    "sacred-geometry-ipad-coloring": [
        ROOT / "private_downloads/sacred-geometry-ipad-coloring.zip",
        ROOT / "private_downloads/sacred-geometry-coloring-book-digital.pdf",
    ],
}


def copy_heroes(slug: str, out: Path) -> list[str]:
    urls = []
    for rel in (
        f"static/bonanza/{slug}.jpg",
        f"static/previews/{slug}.jpg",
        f"static/img/{slug}_cover.jpg",
        f"static/previews/{slug}_clean.jpg",
    ):
        p = ROOT / rel
        if p.is_file() and p.stat().st_size > 4000:
            dest = out / p.name
            shutil.copy2(p, dest)
            urls.append(f"{PUBLIC}/static/ebay/{slug}/{dest.name}")
    # numbered static previews
    prev = ROOT / "static" / "previews"
    numbered = {}
    for p in sorted(prev.glob(f"{slug}_*")):
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        key = p.stem.replace("_clean", "")
        if key in (slug,):
            continue
        if key not in numbered or "_clean" in p.stem:
            numbered[key] = p
    for k in sorted(numbered):
        dest = out / numbered[k].name
        shutil.copy2(numbered[k], dest)
        urls.append(f"{PUBLIC}/static/ebay/{slug}/{dest.name}")
        if len(urls) >= 12:
            break
    return urls


def image_ok(path: Path) -> bool:
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return False
    w, h = im.size
    if w < 300 or h < 300:
        return False
    thumb = im.resize((48, 48))
    px = list(thumb.getdata())
    mean = sum(sum(c) / 3 for c in px) / len(px)
    var = sum((sum(c) / 3 - mean) ** 2 for c in px) / len(px)
    if mean < 12 and var < 40:
        return False  # pure black
    if mean > 252 and var < 20:
        return False
    if path.stat().st_size < 8000 and mean < 30:
        return False
    return True


def png_to_jpg(src: Path, dest: Path, long_edge: int = 1400) -> bool:
    try:
        im = Image.open(src).convert("RGB")
    except Exception:
        return False
    w, h = im.size
    if max(w, h) > long_edge:
        s = long_edge / max(w, h)
        im = im.resize((int(w * s), int(h * s)), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=90, optimize=True)
    return image_ok(dest)


def extract_pngs_from_zip(zpath: Path, work: Path) -> list[Path]:
    work.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    with zipfile.ZipFile(zpath) as zf:
        # nested procreate / png zips
        nested = [n for n in zf.namelist() if n.lower().endswith(".zip")]
        for n in nested:
            part = work / Path(n).name
            part.write_bytes(zf.read(n))
            try:
                with zipfile.ZipFile(part) as inner:
                    for name in sorted(inner.namelist()):
                        if name.lower().endswith(".png") and not name.startswith("__"):
                            dest = work / f"{part.stem}__{Path(name).name}"
                            dest.write_bytes(inner.read(name))
                            out.append(dest)
            except zipfile.BadZipFile:
                pass
        for n in sorted(zf.namelist()):
            if n.lower().endswith((".png", ".jpg", ".jpeg")) and not n.startswith("__"):
                dest = work / Path(n).name
                dest.write_bytes(zf.read(n))
                out.append(dest)
    return sorted(out, key=lambda p: p.name.lower())


def render_pdf_pages(pdf: Path, out_dir: Path, prefix: str, max_pages: int = 12) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(f"{prefix}-*.jpg"):
        old.unlink(missing_ok=True)
    subprocess.run(
        [
            "pdftoppm",
            "-jpeg",
            "-r",
            "130",
            "-f",
            "1",
            "-l",
            str(max_pages),
            str(pdf),
            str(out_dir / prefix),
        ],
        check=True,
        capture_output=True,
        timeout=180,
    )
    pages = sorted(out_dir.glob(f"{prefix}-*.jpg"))
    # drop likely TOC: high dark navy + many bright cards, or filename early pages with dark>0.3
    good = []
    for p in pages:
        if not image_ok(p):
            print("  drop bad page", p.name)
            continue
        im = Image.open(p).convert("RGB")
        thumb = im.resize((96, 96))
        px = list(thumb.getdata())
        mean = sum(sum(c) / 3 for c in px) / len(px)
        dark = sum(1 for r, g, b in px if (r + g + b) / 3 < 40) / len(px)
        bright = sum(1 for r, g, b in px if (r + g + b) / 3 > 240) / len(px)
        # TOC pattern: navy bg (~dark 0.3-0.6) + white tiles (bright 0.15+)
        if dark > 0.28 and bright > 0.18 and 30 < mean < 170:
            print(f"  drop TOC-like {p.name} mean={mean:.0f} dark={dark:.2f} bright={bright:.2f}")
            continue
        good.append(p)
    return good


def render_html_svg_fixed(zpath: Path, out: Path) -> list[Path]:
    """Render SVG from HTML with explicit output size so cairosvg doesn't fail."""
    try:
        import cairosvg
    except Exception:
        subprocess.run(
            [str(ROOT / ".venv" / "bin" / "pip"), "install", "cairosvg", "-q"],
            check=False,
        )
        import cairosvg

    rendered: list[Path] = []
    with zipfile.ZipFile(zpath) as zf:
        htmls = sorted(
            n
            for n in zf.namelist()
            if n.lower().endswith(".html") and not n.startswith("__")
        )[:MAX]
        for i, name in enumerate(htmls, 1):
            html = zf.read(name).decode("utf-8", errors="ignore")
            m = re.search(r"(<svg[\s\S]*?</svg>)", html, re.I)
            if not m:
                continue
            inner_svg = m.group(1)
            if "xmlns=" not in inner_svg[:300]:
                inner_svg = inner_svg.replace(
                    "<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1
                )
            # Outer fixed canvas always — avoids "SVG size is undefined"
            outer = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1200" '
                'viewBox="0 0 1200 1200">'
                '<rect width="1200" height="1200" fill="white"/>'
                '<g transform="translate(60,60)">'
                f"{inner_svg}"
                "</g></svg>"
            )
            png = out / f"_t{i}.png"
            jpg = out / f"design-{i:02d}.jpg"
            try:
                cairosvg.svg2png(
                    bytestring=outer.encode("utf-8"),
                    write_to=str(png),
                    output_width=1200,
                    background_color="white",
                )
            except Exception as e:
                print(f"  svg fail {name}: {e}")
                continue
            if not png.exists():
                continue
            im = Image.open(png).convert("RGB")
            # crop content
            mask = im.point(lambda x: 0 if x > 248 else 255)
            # use any channel
            gray = im.convert("L")
            bw = gray.point(lambda x: 0 if x > 248 else 255)
            bbox = bw.getbbox()
            if bbox:
                x0, y0, x1, y1 = bbox
                pad = 50
                x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
                x1, y1 = min(im.width, x1 + pad), min(im.height, y1 + pad)
                cropped = im.crop((x0, y0, x1, y1))
                side = max(cropped.size) + 100
                canvas = Image.new("RGB", (side, side), "white")
                canvas.paste(
                    cropped,
                    ((side - cropped.size[0]) // 2, (side - cropped.size[1]) // 2),
                )
                im = canvas
            im.save(jpg, "JPEG", quality=90, optimize=True)
            png.unlink(missing_ok=True)
            t = im.resize((48, 48))
            px = list(t.getdata())
            mean = sum(sum(c) / 3 for c in px) / len(px)
            if mean < 30 or jpg.stat().st_size < 12000:
                print(f"  reject {jpg.name} mean={mean:.0f} size={jpg.stat().st_size}")
                jpg.unlink(missing_ok=True)
                continue
            rendered.append(jpg)
            print(f"  + svg {jpg.name} {jpg.stat().st_size//1024}KB mean={mean:.0f}")
    return rendered


def find_pdf_candidates(paths: list[Path]) -> list[Path]:
    found = []
    for p in paths:
        if not p.exists():
            continue
        if p.suffix.lower() == ".pdf":
            found.append(p)
        elif p.suffix.lower() == ".zip":
            # extract pdfs from zip to work
            work = ROOT / "static" / "ebay" / "_pdf_extract" / p.stem
            work.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(p) as zf:
                    for n in zf.namelist():
                        nl = n.lower()
                        if not nl.endswith(".pdf"):
                            continue
                        if "how_to" in nl or "howto" in nl or "readme" in nl:
                            continue
                        dest = work / Path(n).name
                        dest.write_bytes(zf.read(n))
                        found.append(dest)
            except zipfile.BadZipFile:
                pass
    return found


async def push(slug: str, urls: list[str]) -> None:
    db = SessionLocal()
    product = db.query(DigitalProduct).filter(DigitalProduct.slug == slug).first()
    if not product:
        print("missing product", slug)
        db.close()
        return
    sku = f"mr-{slug}"
    inv = await ebay._get(f"/sell/inventory/v1/inventory_item/{sku}")
    pb = inv.get("product") or {}
    await ebay._put(
        f"/sell/inventory/v1/inventory_item/{sku}",
        {
            "product": {
                "title": pb.get("title") or ebay._safe_title(product),
                "description": pb.get("description") or ebay._product_description(product),
                "aspects": pb.get("aspects")
                or {
                    "Format": ["Digital Download"],
                    "File Type": ["PDF/ZIP/JPG"],
                    "Subject": ["Mathematical Art"],
                    "Style": ["Abstract"],
                },
                "imageUrls": urls[:12],
            },
            "condition": "NEW",
            "availability": {"shipToLocationAvailability": {"quantity": 1}},
        },
    )
    inv2 = await ebay._get(f"/sell/inventory/v1/inventory_item/{sku}")
    got = (inv2.get("product") or {}).get("imageUrls") or []
    st = await ebay.get_listing_status(product)
    print(f"  PUSHED {len(got)} → https://www.ebay.com/itm/{st.get('listing_id')}")
    for u in got:
        print("   ", u)
    db.close()


def build_gallery(slug: str) -> list[str]:
    out = ROOT / "static" / "ebay" / slug
    out.mkdir(parents=True, exist_ok=True)
    # clear broken designs
    for p in list(out.glob("design-*.jpg")) + list(out.glob("page-*.jpg")):
        if not image_ok(p) or p.stat().st_size < 10000:
            p.unlink(missing_ok=True)

    urls = copy_heroes(slug, out)
    sources = PRODUCT_ZIPS.get(slug, [])

    # 1) PNG packs from zips
    work = ROOT / "static" / "ebay" / f"_work_{slug}"
    if work.exists():
        shutil.rmtree(work)
    pngs: list[Path] = []
    for src in sources:
        if src.suffix.lower() == ".zip" and src.is_file():
            pngs.extend(extract_pngs_from_zip(src, work))
    print(f"  pngs found: {len(pngs)}")
    n = 0
    for src in pngs:
        dest = out / f"design-{n+1:02d}.jpg"
        if png_to_jpg(src, dest) and image_ok(dest):
            urls.append(f"{PUBLIC}/static/ebay/{slug}/{dest.name}")
            n += 1
            print(f"  + png {dest.name}")
        if n >= MAX:
            break

    # 2) if still few, try HTML SVG render
    good_designs = [u for u in urls if "/design-" in u]
    if len(good_designs) < 4:
        html_zip = next((s for s in sources if s.suffix.lower() == ".zip" and s.is_file()), None)
        if html_zip:
            print("  trying SVG render from HTML zip")
            for p in out.glob("design-*.jpg"):
                if p.stat().st_size < 15000:
                    p.unlink(missing_ok=True)
            rendered = render_html_svg_fixed(html_zip, out)
            urls = copy_heroes(slug, out)
            for p in sorted(rendered):
                urls.append(f"{PUBLIC}/static/ebay/{slug}/{p.name}")

    # 3) PDF pages (skip TOC)
    good_designs = [u for u in urls if "/design-" in u or re.search(r"/\d+_", u)]
    if len([u for u in urls if "design-" in u or "page-" in u or re.search(r"_\d", u)]) < 5:
        pdfs = find_pdf_candidates(sources)
        print(f"  pdf candidates: {[p.name for p in pdfs]}")
        for pdf in pdfs[:2]:
            pages = render_pdf_pages(pdf, out, "page", max_pages=14)
            # skip first pages if still too few after filter — take middle pages
            if len(pages) >= 3:
                # prefer pages after first 2 (often cover/TOC)
                pick = pages[2:2+MAX] if len(pages) > 5 else pages
                for p in pick:
                    urls.append(f"{PUBLIC}/static/ebay/{slug}/{p.name}")
                break

    # dedupe
    seen = set()
    out_urls = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out_urls.append(u)
    return out_urls[:12]


async def main():
    # Broken from audit + related iPad packs that used GoodNotes PDF renders
    targets = [
        "geometric-cbn-ipad-interactive",
        "spiral-tilings-ipad-interactive",
        "sacred-geometry-svg-ipad-interactive",
        "fractal-flora-ipad-coloring",
        "sacred-geometry-ipad-coloring",
    ]
    for slug in targets:
        print(f"\n=== {slug} ===")
        try:
            urls = build_gallery(slug)
            print(f"  gallery={len(urls)}")
            if len(urls) < 2:
                print("  WARN still too few images")
            await push(slug, urls)
        except Exception as e:
            print("  ERROR", e)
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
