"""
Audit eBay listing galleries for preview quality issues:
- too few images
- mostly black / mostly white frames
- GoodNotes TOC pages ("TAP A DESIGN", jump grids)
- how-to instruction pages as gallery fillers
- tiny file sizes
"""
from __future__ import annotations

import asyncio
import os
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from PIL import Image, ImageStat

ROOT = Path("/var/www/mathrelaxing.store")
load_dotenv(ROOT / ".env")
os.chdir(ROOT)

import services.ebay as ebay  # noqa: E402

TOC_HINTS = (
    "tap a design",
    "jump to it",
    "how to use",
    "goodnotes",
    "notability",
    "contents",
    "table of contents",
    "instruction",
)


def local_path_from_url(url: str) -> Path | None:
    if "mathrelaxing.store/" not in url:
        return None
    rel = url.split("mathrelaxing.store/", 1)[1].split("?", 1)[0]
    p = ROOT / rel
    return p if p.is_file() else None


def analyze_image(path: Path) -> dict:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    # downscale for stats / OCR-ish text check via pixel stats only
    thumb = im.resize((96, 96))
    stat = ImageStat.Stat(thumb)
    mean = sum(stat.mean) / 3
    # stddev approx
    std = sum(stat.stddev) / 3
    # dark ratio
    px = list(thumb.getdata())
    dark = sum(1 for r, g, b in px if (r + g + b) / 3 < 25) / len(px)
    bright = sum(1 for r, g, b in px if (r + g + b) / 3 > 245) / len(px)
    # corner content: if only top-left has variance and rest black → broken crop
    corners = {
        "tl": ImageStat.Stat(im.crop((0, 0, max(1, w // 4), max(1, h // 4))).resize((32, 32))).stddev,
        "br": ImageStat.Stat(
            im.crop((3 * w // 4, 3 * h // 4, w, h)).resize((32, 32))
        ).stddev,
    }
    tl_var = sum(corners["tl"]) / 3
    br_var = sum(corners["br"]) / 3
    size_kb = path.stat().st_size / 1024
    name = path.name.lower()
    issues = []
    if size_kb < 8:
        issues.append("tiny_file")
    if mean < 20 and dark > 0.75:
        issues.append("mostly_black")
    if mean > 248 and bright > 0.9 and std < 8:
        issues.append("mostly_blank_white")
    if dark > 0.7 and tl_var > 15 and br_var < 5:
        issues.append("broken_crop_black")
    if w < 400 or h < 400:
        issues.append("low_resolution")
    # filename heuristics
    if name.startswith("page-") and size_kb < 40 and mean > 200:
        # could be sparse TOC — flag soft
        issues.append("possible_sparse_page")
    return {
        "path": str(path),
        "name": path.name,
        "w": w,
        "h": h,
        "kb": round(size_kb, 1),
        "mean": round(mean, 1),
        "std": round(std, 1),
        "dark": round(dark, 2),
        "bright": round(bright, 2),
        "tl_var": round(tl_var, 1),
        "br_var": round(br_var, 1),
        "issues": issues,
    }


def looks_like_toc_filename(url: str) -> bool:
    u = url.lower()
    return any(x in u for x in ("how_to", "howto", "instruction", "readme"))


async def main():
    inv = await ebay._get("/sell/inventory/v1/inventory_item", {"limit": "100"})
    items = inv.get("inventoryItems") or []
    print(f"inventory_items={len(items)}\n")

    report = []
    for it in items:
        sku = it.get("sku") or ""
        offers = await ebay.get_offers_for_sku(sku)
        if not offers or offers[0].get("status") != "PUBLISHED":
            continue
        lid = offers[0].get("listingId") or (offers[0].get("listing") or {}).get(
            "listingId"
        )
        # refresh inventory for image list
        try:
            full = await ebay._get(f"/sell/inventory/v1/inventory_item/{sku}")
        except Exception:
            full = it
        urls = (full.get("product") or {}).get("imageUrls") or []
        title = ((full.get("product") or {}).get("title") or "")[:60]
        analyses = []
        listing_issues = []
        if len(urls) < 3:
            listing_issues.append(f"few_images:{len(urls)}")
        for u in urls:
            if looks_like_toc_filename(u):
                listing_issues.append("howto_filename")
            lp = local_path_from_url(u)
            if not lp:
                listing_issues.append("remote_or_missing:" + u[-40:])
                continue
            try:
                a = analyze_image(lp)
                a["url"] = u
                analyses.append(a)
                for iss in a["issues"]:
                    listing_issues.append(f"{iss}:{lp.name}")
            except Exception as e:
                listing_issues.append(f"read_fail:{lp.name}:{e}")

        # detect TOC-like pages: many white cards on dark navy (high dark + high bright structure)
        toc_pages = []
        for a in analyses:
            # navy background + white tiles pattern often: mean mid-low, dark ~0.4-0.7, bright ~0.2-0.4
            if (
                a["name"].startswith("page-")
                and 40 < a["mean"] < 160
                and a["dark"] > 0.25
                and a["bright"] > 0.15
                and a["kb"] > 50
            ):
                toc_pages.append(a["name"])
            # also check via simple heuristic: page-01/02 from goodnotes often TOC
            if a["name"] in ("page-01.jpg", "page-02.jpg") and a["kb"] > 70 and a["dark"] > 0.3:
                if a["name"] not in toc_pages:
                    toc_pages.append(a["name"] + "?")

        # broken designs
        broken = [a["name"] for a in analyses if "broken_crop_black" in a["issues"] or "mostly_black" in a["issues"]]
        tiny = [a["name"] for a in analyses if "tiny_file" in a["issues"]]

        severity = 0
        flags = []
        if len(urls) < 4:
            severity += 2
            flags.append(f"few_images({len(urls)})")
        if toc_pages:
            severity += 3
            flags.append(f"likely_toc_pages:{','.join(toc_pages[:4])}")
        if broken:
            severity += 3
            flags.append(f"black_broken:{','.join(broken[:4])}")
        if tiny:
            severity += 1
            flags.append(f"tiny:{','.join(tiny[:4])}")
        if any("howto" in (a["name"].lower()) for a in analyses):
            severity += 2
            flags.append("howto_in_gallery")

        # product family hints
        slug = sku.replace("mr-", "")
        is_coloring = any(
            x in slug
            for x in (
                "coloring",
                "ipad",
                "interactive",
                "gardens",
                "tangle",
                "harmonics",
                "flora",
                "geometry",
                "tilings",
                "celtic",
                "neural",
                "islamic",
                "hyperbolic",
                "sacred",
                "spiral",
                "voronoi",
            )
        )

        entry = {
            "sku": sku,
            "slug": slug,
            "listing_id": lid,
            "title": title,
            "n_images": len(urls),
            "severity": severity,
            "flags": flags,
            "is_coloring_family": is_coloring,
            "analyses": analyses,
        }
        report.append(entry)

    report.sort(key=lambda x: (-x["severity"], x["slug"]))

    print("=== PROBLEMS (severity > 0) ===")
    problems = [r for r in report if r["severity"] > 0]
    if not problems:
        print("(none)")
    for r in problems:
        print(
            f"\n[{r['severity']}] {r['slug']}  imgs={r['n_images']}  "
            f"https://www.ebay.com/itm/{r['listing_id']}"
        )
        print(f"  title: {r['title']}")
        print(f"  flags: {r['flags']}")
        for a in r["analyses"]:
            if a["issues"] or a["name"].startswith("page-") or a["name"].startswith("design-"):
                print(
                    f"    {a['name']}: {a['w']}x{a['h']} {a['kb']}KB "
                    f"mean={a['mean']} dark={a['dark']} bright={a['bright']} "
                    f"issues={a['issues']}"
                )

    print("\n=== COLORING / iPAD FAMILY SUMMARY ===")
    for r in sorted(report, key=lambda x: x["slug"]):
        if not r["is_coloring_family"]:
            continue
        status = "OK" if r["severity"] == 0 else f"ISSUE:{r['severity']}"
        print(f"  {status:10} {r['n_images']:2d} imgs  {r['slug']}  {r['flags']}")

    print("\n=== ALL PUBLISHED COUNTS ===")
    print(f"published={len(report)} problems={len(problems)}")
    # also list math-art with only 1 image
    single = [r for r in report if r["n_images"] <= 2]
    if single:
        print("\n=== LOW IMAGE COUNT (≤2) ===")
        for r in single:
            print(f"  {r['n_images']}  {r['slug']}  https://www.ebay.com/itm/{r['listing_id']}")


if __name__ == "__main__":
    asyncio.run(main())
