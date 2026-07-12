#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/var/www/mathrelaxing.store")
VIDEOS = ROOT / "static" / "videos"
OUT_DIR = ROOT / "static" / "social"
TMP = Path("/tmp/mathrelaxing_tiktok_20260602")
OUT = OUT_DIR / "mathrelaxing_tiktok_20260602.mp4"

W, H = 1080, 1920
D = 4
T = 0.45
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

CLIPS = [
    ("particle_vortex_1080p30.mp4", 5, "90,000 particles", "one equation in motion"),
    ("dejong_morph_1080p30.mp4", 6, "Attractors that morph", "generative math loops"),
    ("turing_shift1_1080p30.mp4", 3, "Patterns that drift", "Turing systems, animated"),
    ("julia_zoom1_1080p30.mp4", 8, "Fractal zooms", "self-similar worlds"),
    ("ff_flame_aurora_1080p30.mp4", 2, "Seamless 4K loops", "for screens and creators"),
    ("mobius_spin_1080p30.mp4", 5, "Explore the packs", "mathrelaxing.store"),
]


def q(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode:
        print(proc.stderr[-2000:])
        sys.exit(proc.returncode)


def make_clip(idx, filename, start, headline, subline):
    src = VIDEOS / filename
    dst = TMP / f"clip_{idx:02d}.mp4"
    if not src.exists():
        raise FileNotFoundError(src)

    top_text = q(headline.upper())
    bottom_text = q(subline)
    url_text = q("mathrelaxing.store")
    fg = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black"
    )
    bg = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},gblur=sigma=24,eq=brightness=-0.12:saturation=1.18"
    )
    filters = (
        f"[0:v]trim=start={start}:duration={D},setpts=PTS-STARTPTS,split[main][blur];"
        f"[blur]{bg}[bg];"
        f"[main]{fg}[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v0];"
        f"[v0]drawbox=x=0:y=0:w={W}:h=260:color=black@0.38:t=fill,"
        f"drawbox=x=0:y={H-330}:w={W}:h=330:color=black@0.45:t=fill,"
        f"drawtext=fontfile={FONT}:text='{top_text}':x=(w-text_w)/2:y=82:"
        f"fontsize=64:fontcolor=white:borderw=2:bordercolor=black@0.65,"
        f"drawtext=fontfile={FONT}:text='{bottom_text}':x=(w-text_w)/2:y={H-268}:"
        f"fontsize=43:fontcolor=white:borderw=2:bordercolor=black@0.65,"
        f"drawtext=fontfile={FONT}:text='{url_text}':x=(w-text_w)/2:y={H-144}:"
        f"fontsize=50:fontcolor=#FBBF24:borderw=2:bordercolor=black@0.7"
        f"[out]"
    )

    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-filter_complex", filters,
        "-map", "[out]",
        "-r", "30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "19",
        "-pix_fmt", "yuv420p",
        "-an",
        str(dst),
    ]
    print(f"clip {idx + 1}: {filename}")
    run(cmd)
    return dst


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)

    clips = [make_clip(i, *clip) for i, clip in enumerate(CLIPS)]

    inputs = []
    for clip in clips:
        inputs += ["-i", str(clip)]

    prev = "[0:v]"
    parts = []
    for i in range(1, len(clips)):
        label = f"[v{i}]"
        offset = (D - T) * i
        parts.append(
            f"{prev}[{i}:v]xfade=transition=fade:duration={T}:offset={offset}{label}"
        )
        prev = label

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(parts),
        "-map", prev,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(OUT),
    ]
    print("building final...")
    run(cmd)

    size = OUT.stat().st_size / (1024 * 1024)
    print(f"DONE {OUT} {size:.1f} MB")
    print("URL https://mathrelaxing.store/static/social/mathrelaxing_tiktok_20260602.mp4")


if __name__ == "__main__":
    main()
