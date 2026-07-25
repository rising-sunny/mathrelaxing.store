"""Render interactive HTML CBN pages to JPG and push to eBay listings."""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path("/var/www/mathrelaxing.store")
load_dotenv(ROOT / ".env")
os.chdir(ROOT)

from database import SessionLocal  # noqa: E402
from models.product import DigitalProduct  # noqa: E402
import services.ebay as ebay  # noqa: E402

SLUGS = {
    "geometric-cbn-ipad-interactive": "static/downloads/geometric-cbn-ipad-interactive.zip",
    "sacred-geometry-svg-ipad-interactive": "static/downloads/sacred-geometry-svg-ipad-interactive.zip",
    "spiral-tilings-ipad-interactive": "static/downloads/spiral-tilings-ipad-interactive.zip",
    "voronoi-gardens-ipad-interactive": "static/downloads/voronoi-gardens-ipad-interactive.zip",
}


def html_to_jpg(html_bytes: bytes, out_jpg: Path) -> bool:
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    text = html_bytes.decode("utf-8", errors="ignore")
    svgs = re.findall(r"(<svg[\s\S]*?</svg>)", text, re.I)
    if not svgs:
        return False
    svg = max(svgs, key=len)
    # Ensure size for ImageMagick
    head = svg[:300]
    if "width=" not in head:
        svg = svg.replace("<svg", '<svg width="900" height="1100"', 1)
    if "viewBox" not in head and "viewbox" not in head.lower():
        # try inject a generic viewBox after <svg ...>
        svg = re.sub(
            r"<svg(\s[^>]*)?>",
            r'<svg\1 viewBox="0 0 900 1100">',
            svg,
            count=1,
            flags=re.I,
        )
    with tempfile.TemporaryDirectory() as td:
        svg_path = Path(td) / "page.svg"
        png_path = Path(td) / "page.png"
        svg_path.write_text(svg, encoding="utf-8")
        # Try cairosvg via python if available, else convert
        try:
            import cairosvg  # type: ignore

            cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_width=900)
        except Exception:
            # ImageMagick with density
            r = subprocess.run(
                [
                    "convert",
                    "-density",
                    "150",
                    "-background",
                    "white",
                    "-flatten",
                    str(svg_path),
                    str(png_path),
                ],
                capture_output=True,
                text=True,
            )
            if r.returncode != 0 or not png_path.exists():
                # last resort: chromium screenshot of a minimal html wrapper
                wrap = Path(td) / "wrap.html"
                wrap.write_text(
                    "<!doctype html><html><body style='margin:0;background:#fff'>"
                    + svg
                    + "</body></html>",
                    encoding="utf-8",
                )
                shot = Path(td) / "shot.png"
                # write under store static so snap chromium can access
                work = ROOT / "static" / "ebay" / "_chrome_work"
                work.mkdir(parents=True, exist_ok=True)
                whtml = work / "wrap.html"
                wshot = work / "shot.png"
                whtml.write_text(wrap.read_text(encoding="utf-8"), encoding="utf-8")
                wshot.unlink(missing_ok=True)
                subprocess.run(
                    [
                        "chromium-browser",
                        "--headless=new",
                        "--disable-gpu",
                        "--no-sandbox",
                        "--virtual-time-budget=8000",
                        "--window-size=900,1100",
                        f"--screenshot={wshot}",
                        f"file://{whtml.resolve()}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=50,
                )
                if wshot.exists() and wshot.stat().st_size > 2000:
                    shutil.copy2(wshot, png_path)
                else:
                    print("    convert/chrome failed", (r.stderr or "")[:180])
                    return False
        if not png_path.exists() or png_path.stat().st_size < 2000:
            return False
        subprocess.run(
            ["convert", str(png_path), "-quality", "88", str(out_jpg)],
            check=False,
            capture_output=True,
        )
        return out_jpg.exists() and out_jpg.stat().st_size > 2000


async def push(product, urls):
    sku = f"mr-{product.slug}"
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
                "imageUrls": urls,
            },
            "condition": "NEW",
            "availability": {"shipToLocationAvailability": {"quantity": 1}},
        },
    )
    inv2 = await ebay._get(f"/sell/inventory/v1/inventory_item/{sku}")
    return len((inv2.get("product") or {}).get("imageUrls") or [])


async def main():
    # try install cairosvg if missing (optional)
    try:
        import cairosvg  # noqa: F401
    except Exception:
        subprocess.run(
            [str(ROOT / ".venv" / "bin" / "pip"), "install", "cairosvg", "-q"],
            check=False,
        )

    db = SessionLocal()
    for slug, zrel in SLUGS.items():
        print("===", slug)
        p = db.query(DigitalProduct).filter(DigitalProduct.slug == slug).first()
        zpath = ROOT / zrel
        out = ROOT / "static" / "ebay" / slug
        out.mkdir(parents=True, exist_ok=True)
        urls = []
        for rel in (
            f"static/bonanza/{slug}.jpg",
            f"static/previews/{slug}.jpg",
            f"static/img/{slug}_cover.jpg",
            f"static/previews/{slug}_clean.jpg",
        ):
            fp = ROOT / rel
            if fp.is_file():
                dest = out / fp.name
                if not dest.exists():
                    shutil.copy2(fp, dest)
                urls.append(f"https://mathrelaxing.store/static/ebay/{slug}/{dest.name}")

        with zipfile.ZipFile(zpath) as zf:
            htmls = sorted(
                n
                for n in zf.namelist()
                if n.lower().endswith(".html") and not n.startswith("__")
            )[:8]
            print(" htmls", len(htmls))
            for i, n in enumerate(htmls, 1):
                jpg = out / f"design-{i:02d}.jpg"
                ok = html_to_jpg(zf.read(n), jpg)
                print(f"  {n} -> {ok} {jpg.stat().st_size if ok else 0}")
                if ok:
                    urls.append(f"https://mathrelaxing.store/static/ebay/{slug}/{jpg.name}")

        seen = set()
        uu = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                uu.append(u)
        uu = uu[:12]
        nimg = await push(p, uu)
        st = await ebay.get_listing_status(p)
        print(f" pushed {nimg} https://www.ebay.com/itm/{st.get('listing_id')}")
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
