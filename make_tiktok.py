#!/usr/bin/env python3
"""Generate a TikTok compilation video: 5 clips, crossfade transitions, 1080x1920."""
import subprocess, os, sys

VIDEOS_DIR = "/var/www/mathrelaxing.store/static/videos"
OUT_DIR    = "/var/www/mathrelaxing.store/static"
TMP_DIR    = "/tmp/tiktok_clips"
OUT_FILE   = f"{OUT_DIR}/tiktok_compilation.mp4"

os.makedirs(TMP_DIR, exist_ok=True)

# (filename, start_sec, duration_sec)
clips = [
    ("lorenz_drift_1080p60.mp4",    8,  6),  # classic lorenz
    ("clifford_nebula_1080p60.mp4",  5,  6),  # clifford colors
    ("particle_nebula_1080p30.mp4",  5,  6),  # particle nebula
    ("julia_zoom2_1080p30.mp4",      8,  6),  # julia zoom
    ("particle_storm_1080p30.mp4",   4,  6),  # storm finale
]

W, H = 1080, 1920
TRANS = 1  # crossfade duration seconds

def to_9x16(src, dst, start, dur):
    """Scale to 9:16 with blurred background, trim to dur seconds."""
    print(f"  Processing {os.path.basename(src)} [{start}s +{dur}s] → {os.path.basename(dst)}")
    # fg: scale to fit within 1080x1920, keeping aspect
    # bg: scale to cover 1080x1920 + blur
    filtergraph = (
        f"[0:v]trim=start={start}:duration={dur},setpts=PTS-STARTPTS,split[orig][blursrc];"
        f"[blursrc]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},gblur=sigma=30[bg];"
        f"[orig]scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[out]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", src,
        "-filter_complex", filtergraph,
        "-map", "[out]",
        "-r", "30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-an",
        dst
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("ERROR:", r.stderr[-800:])
        sys.exit(1)

# Step 1: process each clip
tmp_files = []
for i, (fname, start, dur) in enumerate(clips):
    src = f"{VIDEOS_DIR}/{fname}"
    dst = f"{TMP_DIR}/clip{i:02d}.mp4"
    to_9x16(src, dst, start, dur)
    tmp_files.append(dst)

print(f"\nAll {len(tmp_files)} clips processed. Building final video with xfade transitions...")

# Step 2: concat with xfade
# For N clips each of duration D with transition T:
# xfade offsets: D-T, 2*(D-T), 3*(D-T), ...
D = 6
T = TRANS
n = len(tmp_files)

inputs = []
for f in tmp_files:
    inputs += ["-i", f]

# Build filter: chain xfades
# [0][1] -> xfade(offset=5) -> [v01]
# [v01][2] -> xfade(offset=10) -> [v012]
# etc.
fc_parts = []
prev = "[0:v]"
for i in range(1, n):
    label = f"[v{i:02d}]"
    offset = (D - T) * i
    fc_parts.append(f"{prev}[{i}:v]xfade=transition=fade:duration={T}:offset={offset}{label}")
    prev = label

filter_complex = ";".join(fc_parts)
final_label = f"[v{n-1:02d}]"

cmd = [
    "ffmpeg", "-y",
    *inputs,
    "-filter_complex", filter_complex,
    "-map", final_label,
    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    OUT_FILE
]

print("Running final concat...")
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print("ERROR:", r.stderr[-1200:])
    sys.exit(1)

size = os.path.getsize(OUT_FILE) / 1024 / 1024
print(f"\nDone! → {OUT_FILE}  ({size:.1f} MB)")
print(f"Download: https://mathrelaxing.store/static/tiktok_compilation.mp4")
