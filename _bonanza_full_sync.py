"""
Full Bonanza sync:
1) Ensure listing images for all active digital products
2) Publish/revise every active digital
3) End + drop orphan map entries (not in active catalog)
4) Revise/republish all POD map entries that still exist in DB
5) Write summary report
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from dotenv import load_dotenv

load_dotenv(".env")

from database import SessionLocal
from models.product import DigitalProduct, Product
from services import bonanza as B

ROOT = Path("/var/www/mathrelaxing.store")
BONANZA_IMG = ROOT / "static" / "bonanza"
REPORT = ROOT / "meta_drafts" / f"bonanza_full_sync_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
# reuse meta_drafts dir or write to root
REPORT.parent.mkdir(parents=True, exist_ok=True)

SLEEP = 0.35  # polite API pacing


def _local_path(url_or_path: str | None) -> Path | None:
    if not url_or_path:
        return None
    p = url_or_path
    if p.startswith("http://") or p.startswith("https://"):
        # only local site assets
        for prefix in (
            "https://mathrelaxing.store/",
            "http://mathrelaxing.store/",
            "https://www.mathrelaxing.store/",
        ):
            if p.startswith(prefix):
                p = "/" + p[len(prefix) :]
                break
        else:
            return None
    p = p.split("?", 1)[0]
    if p.startswith("/"):
        candidate = ROOT / p.lstrip("/")
    else:
        candidate = ROOT / p
    return candidate if candidate.is_file() else None


def ensure_digital_image(product) -> tuple[bool, str]:
    """Copy/convert cover or thumb into static/bonanza/{slug}.jpg. Returns (ok, note)."""
    BONANZA_IMG.mkdir(parents=True, exist_ok=True)
    dest = BONANZA_IMG / f"{product.slug}.jpg"
    if dest.is_file() and dest.stat().st_size > 1000:
        return True, f"exists:{dest.name}"

    candidates = [
        _local_path(getattr(product, "cover_image", None)),
        _local_path(getattr(product, "thumbnail_url", None)),
        ROOT / "static" / "previews" / f"{product.slug}.jpg",
        ROOT / "static" / "img" / f"{product.slug}_cover.jpg",
        ROOT / "static" / "img" / f"{product.slug}_cover.png",
        ROOT / "static" / "covers" / f"{product.slug}.jpg",
    ]
    # special known covers
    special = {
        "hyperbolic-gardens-digital": [
            ROOT / "static" / "img" / "hyperbolic_gardens_cover.png",
            ROOT / "static" / "previews" / "hyperbolic-gardens-digital.jpg",
        ],
        "fractal-flora-coloring-book-digital": [
            ROOT / "static" / "img" / "fractal_flora_cover.jpg",
            ROOT / "static" / "img" / "fractal_flora_cover.png",
        ],
        "sacred-harmonics-digital": [
            ROOT / "static" / "img" / "sacred_harmonics_cover.png",
            ROOT / "static" / "previews" / "sacred-harmonics-digital.jpg",
        ],
        "mathematical-tangle-art-digital": [
            ROOT / "static" / "img" / "book_cover.png",
            ROOT / "static" / "previews" / "mathematical-tangle-art-digital.jpg",
        ],
        "sacred-geometry-coloring-book-digital": [
            ROOT / "static" / "previews" / "sacred-geometry-coloring-book-digital.jpg",
        ],
        "thomas-attractor-loop": [
            ROOT / "static" / "previews" / "thomas-attractor-loop.jpg",
        ],
    }
    for extra in special.get(product.slug, []):
        candidates.insert(0, extra)

    src = next((c for c in candidates if c and Path(c).is_file()), None)
    if not src:
        # last resort: public preview endpoint can't be copied offline easily
        return False, "no_local_image"

    src = Path(src)
    try:
        if src.suffix.lower() in {".jpg", ".jpeg"}:
            shutil.copy2(src, dest)
            return True, f"copied:{src.name}"
        # convert png/webp via PIL
        from PIL import Image

        im = Image.open(src).convert("RGB")
        # Bonanza likes reasonable size; keep aspect, max edge 1600
        im.thumbnail((1600, 1600))
        im.save(dest, "JPEG", quality=88, optimize=True)
        return True, f"converted:{src.name}"
    except Exception as e:
        return False, f"image_err:{e}"


async def end_item(item_id: str) -> tuple[bool, str]:
    try:
        await B._request(
            "endFixedPriceItemRequest",
            {
                "requesterCredentials": B._credentials(),
                "itemID": int(item_id),
            },
        )
        return True, "ended"
    except Exception as e:
        msg = str(e)
        # already ended / not found is fine for cleanup
        low = msg.lower()
        if any(x in low for x in ("already", "ended", "not found", "invalid", "cannot")):
            return True, f"end_soft:{msg[:120]}"
        return False, msg[:200]


async def main():
    if not B.is_configured():
        raise SystemExit("Bonanza not configured")

    report: dict = {
        "started": datetime.now(timezone.utc).isoformat(),
        "token_ok": None,
        "images": {},
        "digital_publish": [],
        "orphans_cleaned": [],
        "pod_publish": [],
        "final_status": {},
        "errors": [],
    }

    try:
        tok = await B.get_token_status()
        report["token_ok"] = tok.get("verified") == "true" or tok.get("verified") is True
        print("token:", tok)
    except Exception as e:
        report["errors"].append(f"token:{e}")
        print("TOKEN FAIL", e)
        raise

    db = SessionLocal()
    active_digital = (
        db.query(DigitalProduct)
        .filter(DigitalProduct.active == True)
        .order_by(DigitalProduct.slug)
        .all()
    )
    active_slugs = {p.slug for p in active_digital}
    print(f"active_digital={len(active_digital)}")

    # ── 1) images ──────────────────────────────────────────────────────────
    print("\n=== IMAGES ===")
    for p in active_digital:
        ok, note = ensure_digital_image(p)
        report["images"][p.slug] = {"ok": ok, "note": note}
        print(f"  image {p.slug}: {ok} {note}")

    # ── 2) publish all active digitals ─────────────────────────────────────
    print("\n=== PUBLISH DIGITALS ===")
    for i, p in enumerate(active_digital, 1):
        row = {"slug": p.slug, "ok": False}
        try:
            if not report["images"].get(p.slug, {}).get("ok"):
                # still try — _listing_image_url may fall back to cover URL
                print(f"  [{i}/{len(active_digital)}] {p.slug}: warning no local image, trying anyway")
            result = await B.publish_product(p)
            row.update({"ok": True, **{k: result.get(k) for k in ("item_id", "selling_state", "listing_url", "category_id")}})
            print(f"  [{i}/{len(active_digital)}] {p.slug}: OK {result.get('selling_state')} {result.get('item_id')}")
        except Exception as e:
            row["error"] = str(e)[:300]
            report["errors"].append(f"digital:{p.slug}:{e}")
            print(f"  [{i}/{len(active_digital)}] {p.slug}: FAIL {e}")
        report["digital_publish"].append(row)
        await asyncio.sleep(SLEEP)

    # ── 3) orphan cleanup ──────────────────────────────────────────────────
    print("\n=== ORPHAN CLEANUP ===")
    dig_map = B._load_map()
    orphans = [slug for slug in list(dig_map.keys()) if slug not in active_slugs]
    print(f"orphans={len(orphans)}")
    for slug in orphans:
        meta = dig_map.get(slug) or {}
        item_id = meta.get("item_id")
        row = {"slug": slug, "item_id": item_id}
        if item_id:
            ok, note = await end_item(str(item_id))
            row["end_ok"] = ok
            row["end_note"] = note
            print(f"  end {slug} ({item_id}): {ok} {note}")
            await asyncio.sleep(SLEEP)
        dig_map.pop(slug, None)
        row["removed_from_map"] = True
        report["orphans_cleaned"].append(row)
    B._save_map(dig_map)
    print(f"digital map now {len(B._load_map())} entries")

    # ── 4) POD republish ───────────────────────────────────────────────────
    print("\n=== POD REPUBLISH ===")
    pod_map = B._load_pod_map()
    for key, meta in sorted(pod_map.items()):
        row = {"key": key, "ok": False, "item_id": meta.get("item_id")}
        slug = meta.get("slug") or key.split(":")[0]
        format_id = meta.get("format_id") or (key.split(":")[1] if ":" in key else None)
        product = db.query(Product).filter(Product.slug == slug).first()
        if not product:
            row["error"] = "product_not_in_db"
            # try end listing
            if meta.get("item_id"):
                ok, note = await end_item(str(meta["item_id"]))
                row["end_ok"] = ok
                row["end_note"] = note
            report["pod_publish"].append(row)
            print(f"  POD {key}: missing product, end attempt")
            await asyncio.sleep(SLEEP)
            continue
        try:
            if format_id == "book" or format_id == getattr(B, "BOOK_FORMAT_ID", "book"):
                result = await B.publish_book(product)
            else:
                result = await B.publish_pod_product(product, format_id)
            row.update(
                {
                    "ok": True,
                    "selling_state": result.get("selling_state"),
                    "listing_url": result.get("listing_url"),
                    "item_id": result.get("item_id"),
                    "price_usd": result.get("price_usd"),
                }
            )
            print(f"  POD {key}: OK {result.get('selling_state')} {result.get('item_id')}")
        except Exception as e:
            row["error"] = str(e)[:300]
            report["errors"].append(f"pod:{key}:{e}")
            print(f"  POD {key}: FAIL {e}")
        report["pod_publish"].append(row)
        await asyncio.sleep(SLEEP)

    # ── 5) final live status ───────────────────────────────────────────────
    print("\n=== FINAL DIGITAL STATUS ===")
    dig_counts: dict[str, int] = {}
    for p in active_digital:
        try:
            st = await B.get_listing_status(p)
            s = st.get("status") or "unknown"
            dig_counts[s] = dig_counts.get(s, 0) + 1
            if s not in ("active", "ready_for_sale"):
                print(f"  ! {p.slug}: {s} {st}")
        except Exception as e:
            dig_counts["error"] = dig_counts.get("error", 0) + 1
            print(f"  ! {p.slug}: err {e}")
        await asyncio.sleep(0.15)
    report["final_status"]["digital_counts"] = dig_counts
    report["final_status"]["digital_map_size"] = len(B._load_map())
    report["final_status"]["pod_map_size"] = len(B._load_pod_map())

    print("\n=== FINAL POD STATUS ===")
    pod_counts: dict[str, int] = {}
    pod_map = B._load_pod_map()
    for key, meta in sorted(pod_map.items()):
        item_id = meta.get("item_id")
        if not item_id:
            pod_counts["no_id"] = pod_counts.get("no_id", 0) + 1
            continue
        try:
            data = await B._request(
                "getUnlistedItemRequest",
                {"requesterCredentials": B._credentials(), "itemId": str(item_id)},
            )
            item = data.get("getUnlistedItemResponse", {}).get("item", {})
            state = item.get("listingStatus") or "empty"
            pics = item.get("pictureURL") or []
            pod_counts[str(state)] = pod_counts.get(str(state), 0) + 1
            # refresh map selling_state
            meta["selling_state"] = state
            meta["listing_url"] = item.get("viewItemURL") or meta.get("listing_url")
            pod_map[key] = meta
            if state not in ("Active", "Ready for sale"):
                print(f"  ! {key}: {state} pics={len(pics) if isinstance(pics, list) else pics}")
        except Exception as e:
            pod_counts["error"] = pod_counts.get("error", 0) + 1
            print(f"  ! {key}: err {e}")
        await asyncio.sleep(0.15)
    B._save_pod_map(pod_map)
    report["final_status"]["pod_counts"] = pod_counts

    # hyperbolic check
    try:
        hyp = next(p for p in active_digital if p.slug == "hyperbolic-gardens-digital")
        st = await B.get_listing_status(hyp)
        report["final_status"]["hyperbolic"] = st
        print("hyperbolic final:", st)
    except Exception as e:
        report["final_status"]["hyperbolic"] = {"error": str(e)}

    report["finished"] = datetime.now(timezone.utc).isoformat()
    ok_d = sum(1 for r in report["digital_publish"] if r.get("ok"))
    ok_p = sum(1 for r in report["pod_publish"] if r.get("ok"))
    print(
        f"\nSUMMARY digital_ok={ok_d}/{len(report['digital_publish'])} "
        f"pod_ok={ok_p}/{len(report['pod_publish'])} "
        f"orphans={len(report['orphans_cleaned'])} "
        f"errors={len(report['errors'])}"
    )
    print("digital_counts", dig_counts)
    print("pod_counts", pod_counts)

    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    latest = ROOT / "meta_drafts" / "bonanza_full_sync_latest.json"
    latest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("WROTE", REPORT, latest)
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
