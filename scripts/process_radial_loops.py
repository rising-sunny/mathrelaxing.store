import sys
import os
import subprocess
import json

sys.path.insert(0, "/var/www/mathrelaxing.store")
from database import SessionLocal
from models.product import DigitalProduct

out_dir = "/var/www/mathrelaxing.store/static/videos"
slug = "radial-symmetry-loop-pack"

items = [
    "rose_spin",
    "superformula_spin",
    "superformula_hue",
]

for key in items:
    in_video = os.path.join(out_dir, f"{key}_1080p30.mp4")
    out_video = os.path.join(out_dir, f"{key}_preview.mp4")
    
    if not os.path.exists(in_video):
        print(f"Skipping {key}, missing {in_video}")
        continue
    
    print(f"\nCompressing {key}...")
    subprocess.run([
        "ffmpeg", "-y", "-i", in_video,
        "-vf", "scale=-2:720",
        "-c:v", "libx264", "-crf", "30", "-preset", "fast",
        "-an",
        out_video
    ], check=True)
    
    in_size = os.path.getsize(in_video) / 1024 / 1024
    out_size = os.path.getsize(out_video) / 1024 / 1024
    print(f"Compressed {key}: {in_size:.1f}MB -> {out_size:.1f}MB")

db = SessionLocal()
product = db.query(DigitalProduct).filter_by(slug=slug).first()
if product:
    contents = json.loads(product.contents_json)
    changed = False
    for item in contents:
        k = item.get("animation_key")
        if k in items:
            item["preview_url"] = f"/static/videos/{k}_preview.mp4"
            item["download_url"] = f"/static/videos/{k}_1080p30.mp4"
            changed = True
    if changed:
        product.contents_json = json.dumps(contents)
        db.commit()
        print(f"\nUpdated DB contents_json for {slug}")
