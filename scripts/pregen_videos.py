#!/usr/bin/env python3
"""Pre-generate seamless loop videos for all animation packs.

Generates videos at multiple FPS (30 and 60) and resolutions (1080p and 4K).
Stores them in static/videos/ for serving via the download endpoint.
"""
import os, sys, json, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.product import DigitalProduct
from services.video_renderer import ANIMATION_GENERATORS

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "static", "videos")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Video format presets: (label, fps, width, height)
FORMATS = [
    ("1080p30", 30, 1920, 1080),
    ("1080p60", 60, 1920, 1080),
    ("4k30",    30, 3840, 2160),
    ("4k60",    60, 3840, 2160),
]

# Color palettes per animation
PALETTES = {
    "lorenz_flow":     ("#c8a96e", "#7ecfb3", "#080808"),
    "clifford_spin":   ("#e85d75", "#6ec8cf", "#0a0a14"),
    "clifford_nebula": ("#e85d75", "#6ec8cf", "#0a0a14"),
    "clifford_spiral": ("#f59e0b", "#8b5cf6", "#0c0a1a"),
    "clifford_bloom":  ("#ec4899", "#06b6d4", "#0a0a0a"),
    "aizawa_dance":    ("#a855f7", "#38bdf8", "#0c0a1a"),
    "attractor_morph": ("#f59e0b", "#8b5cf6", "#0a0a0a"),
    "lorenz_drift":    ("#c8a96e", "#7ecfb3", "#080808"),
}


def get_animation_items():
    """Get all animation items from the database."""
    db = SessionLocal()
    dp = db.query(DigitalProduct).filter(
        DigitalProduct.product_type == "animation_pack"
    ).first()
    db.close()

    if not dp:
        print("No animation_pack products found in DB.")
        return []

    items = json.loads(dp.contents_json or "[]")
    # Map item titles to animation generator keys
    title_to_key = {
        "Lorenz Flow": "lorenz_flow",
        "Clifford Spin": "clifford_spin",
        "Clifford Nebula": "clifford_nebula",
        "Clifford Spiral": "clifford_spiral",
        "Clifford Bloom": "clifford_bloom",
        "Aizawa Dance": "aizawa_dance",
        "Attractor Morph": "attractor_morph",
        "Lorenz Drift": "lorenz_drift",
    }

    result = []
    for item in items:
        key = title_to_key.get(item.get("title", ""))
        if key and key in ANIMATION_GENERATORS:
            result.append({
                "key": key,
                "title": item["title"],
                "duration": item.get("duration_secs",
                                     ANIMATION_GENERATORS[key]["default_duration"]),
                "params": ANIMATION_GENERATORS[key]["default_params"],
            })
    return result


def generate_all(formats=None, keys=None, force=False):
    """Generate videos for all animation items in specified formats."""
    items = get_animation_items()
    if not items:
        return

    if keys:
        items = [i for i in items if i["key"] in keys]

    fmt_list = FORMATS if formats is None else [f for f in FORMATS if f[0] in formats]

    total = len(items) * len(fmt_list)
    done = 0

    for item in items:
        key = item["key"]
        gen_info = ANIMATION_GENERATORS[key]
        cs, ce, bg = PALETTES.get(key, ("#c8a96e", "#7ecfb3", "#080808"))

        for fmt_label, fps, w, h in fmt_list:
            out_name = f"{key}_{fmt_label}.mp4"
            out_path = os.path.join(OUTPUT_DIR, out_name)

            if not force and os.path.exists(out_path):
                size_mb = os.path.getsize(out_path) / 1024 / 1024
                print(f"  [SKIP] {out_name} ({size_mb:.1f}MB) — already exists")
                done += 1
                continue

            print(f"\n[{done+1}/{total}] {item['title']} — {fmt_label} ({w}x{h} @ {fps}fps)")
            t0 = time.time()

            try:
                gen_info["fn"](
                    output_path=out_path,
                    fps=fps,
                    duration_secs=item["duration"],
                    width=w,
                    height=h,
                    color_start=cs,
                    color_end=ce,
                    bg=bg,
                    **item["params"],
                )
                elapsed = time.time() - t0
                size_mb = os.path.getsize(out_path) / 1024 / 1024
                print(f"  [OK] {out_name} — {size_mb:.1f}MB — {elapsed:.0f}s")
            except Exception as e:
                print(f"  [ERROR] {out_name}: {e}")

            done += 1

    print(f"\nDone. {done}/{total} videos in {OUTPUT_DIR}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Regenerate existing videos")
    parser.add_argument("--formats", nargs="*", help="Only these formats (1080p30, 1080p60, 4k30, 4k60)")
    parser.add_argument("--keys", nargs="*", help="Only these animation keys")
    args = parser.parse_args()

    generate_all(formats=args.formats, keys=args.keys, force=args.force)
