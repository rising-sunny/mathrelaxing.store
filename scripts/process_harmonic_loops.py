import os
import subprocess
import sys
import json

sys.path.insert(0, "/var/www/mathrelaxing.store")
from database import SessionLocal
from models.product import DigitalProduct

out_dir = "/var/www/mathrelaxing.store/static/videos"
slug = "harmonic-geometry-loop-pack"

items = [
    "harmonic_hue1",
    "harmonic_hue2",
    "harmonic_hue3",
]

for key in items:
    in_video = os.path.join(out_dir, f"{key}_1080p30.mp4")
    out_video = os.path.join(out_dir, f"{key}_preview.mp4")
    
    if not os.path.exists(in_video):
        print(f"Skipping {key}, missing {in_video}")
        continue
        
    print(f"\nCompressing {key}...")
    cmd = [
        "ffmpeg", "-y", "-i", in_video,
        "-vf", "scale=-2:720",
        "-c:v", "libx264", "-crf", "30", "-preset", "medium",
        "-an", out_video
    ]
    subprocess.run(cmd, check=True)
    
    in_size = os.path.getsize(in_video) / (1024*1024)
    out_size = os.path.getsize(out_video) / (1024*1024)
    print(f"Compressed {key}: {in_size:.1f}MB -> {out_size:.1f}MB")

# Update DB
db = SessionLocal()
try:
    product = db.query(DigitalProduct).filter_by(slug=slug).first()
    if product:
        contents = json.loads(product.contents_json)
        for item in contents:
            k = item.get("animation_key")
            if k in items:
                item["thumbnail_url"] = f"/static/videos/{k}_preview.mp4"
        product.contents_json = json.dumps(contents)
        db.commit()
        print(f"\nUpdated DB contents_json for {slug}")
finally:
    db.close()
