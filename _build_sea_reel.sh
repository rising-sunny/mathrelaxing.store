#!/usr/bin/env bash
# Build SEA multi-product Meta ad reel (square 1080x1080, ~25s).
set -euo pipefail

ROOT=/var/www/mathrelaxing.store
WORKDIR=/tmp/sea_reel_build
OUTDIR=$ROOT/static/ads
mkdir -p "$WORKDIR" "$OUTDIR"
rm -rf "$WORKDIR"/*
cd "$WORKDIR"

FONT=$ROOT/static/fonts/Cinzel.ttf
FONT2=$ROOT/static/fonts/Raleway.ttf
LOGO=$ROOT/static/img/logo.png

# Segment length (seconds) per product clip
SEG=3.2
FPS=30
SIZE=1080

normalize() {
  local in="$1"
  local out="$2"
  local start="${3:-0}"
  # Scale to cover 1080x1080, center crop, fixed fps, silent
  ffmpeg -y -ss "$start" -t "$SEG" -i "$in" \
    -vf "scale=${SIZE}:${SIZE}:force_original_aspect_ratio=increase,crop=${SIZE}:${SIZE},fps=${FPS},format=yuv420p" \
    -an -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
    "$out" </dev/null 2>/tmp/ff_norm.log
}

echo "=== Normalizing clips ==="
# Order: hypnotic open → variety → product promo → close loop
normalize "$ROOT/static/video/thomas_attractor_loop.mp4"              01_thomas.mp4 0
normalize "$ROOT/static/digital/julia-set-loop/00_preview.mp4"        02_julia.mp4 0
normalize "$ROOT/static/digital/voronoi-cell-garden-loop/00_preview.mp4" 03_voronoi.mp4 0
normalize "$ROOT/static/dejong_loop_1080.mp4"                         04_dejong.mp4 0
normalize "$ROOT/static/examples/lorenz_flow_1080p30.mp4"             05_lorenz.mp4 0
normalize "$ROOT/static/examples/clifford_spiral_1080p60.mp4"         06_clifford.mp4 0
normalize "$ROOT/static/video/fb_chladni.mp4"                         07_chladni.mp4 0
# Fractal flora is vertical promo — take a mid section if long enough
normalize "$ROOT/static/video/fractal_flora_promo.mp4"                08_flora.mp4 4

# Labels (subtle bottom caption) — optional short title cards between clips? 
# Keep clean: no mid titles, just end card.

echo "=== End card ==="
# 3.5s end card: navy bg, gold accents, logo, headline, CTA
# Generate with ffmpeg lavfi + drawtext
ffmpeg -y -f lavfi -i "color=c=0x0B1220:s=${SIZE}x${SIZE}:d=3.5:r=${FPS}" \
  -i "$LOGO" \
  -filter_complex "\
    [1:v]scale=220:-1,format=rgba[logo]; \
    [0:v][logo]overlay=(W-w)/2:160[v1]; \
    [v1]drawtext=fontfile=${FONT}:text='MathRelaxing':fontcolor=0xC8A96E:fontsize=64:x=(w-text_w)/2:y=420,\
drawtext=fontfile=${FONT2}:text='Math that feels like art':fontcolor=0xE8E4DC:fontsize=36:x=(w-text_w)/2:y=510,\
drawtext=fontfile=${FONT2}:text='Digital downloads  ·  Print or iPad':fontcolor=0xA8A29A:fontsize=28:x=(w-text_w)/2:y=580,\
drawtext=fontfile=${FONT2}:text='SHOP NOW':fontcolor=0x0B1220:fontsize=40:box=1:boxcolor=0xC8A96E@1:boxborderw=18:x=(w-text_w)/2:y=700,\
drawtext=fontfile=${FONT2}:text='mathrelaxing.store':fontcolor=0xC8A96E:fontsize=26:x=(w-text_w)/2:y=820,\
drawtext=fontfile=${FONT2}:text='India  ·  Thailand  ·  Malaysia':fontcolor=0x6B6560:fontsize=22:x=(w-text_w)/2:y=900\
  " \
  -t 3.5 -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -an \
  09_endcard.mp4 </dev/null 2>/tmp/ff_end.log

echo "=== Concat ==="
# Build concat list
cat > list.txt <<EOF
file '01_thomas.mp4'
file '02_julia.mp4'
file '03_voronoi.mp4'
file '04_dejong.mp4'
file '05_lorenz.mp4'
file '06_clifford.mp4'
file '07_chladni.mp4'
file '08_flora.mp4'
file '09_endcard.mp4'
EOF

ffmpeg -y -f concat -safe 0 -i list.txt -c:v libx264 -preset slow -crf 19 -pix_fmt yuv420p -movflags +faststart -an \
  sea_in_th_my_reel.mp4 </dev/null 2>/tmp/ff_concat.log

# Also make a shorter 15s cut (first 4 clips + end) for Reels testing
cat > list_short.txt <<EOF
file '01_thomas.mp4'
file '02_julia.mp4'
file '03_voronoi.mp4'
file '04_dejong.mp4'
file '09_endcard.mp4'
EOF
ffmpeg -y -f concat -safe 0 -i list_short.txt -c:v libx264 -preset slow -crf 19 -pix_fmt yuv420p -movflags +faststart -an \
  sea_in_th_my_reel_15s.mp4 </dev/null 2>/tmp/ff_short.log

# Poster frame for Meta thumbnail
ffmpeg -y -ss 1 -i sea_in_th_my_reel.mp4 -frames:v 1 -q:v 2 sea_in_th_my_reel_poster.jpg </dev/null 2>/tmp/ff_poster.log

cp -v sea_in_th_my_reel.mp4 sea_in_th_my_reel_15s.mp4 sea_in_th_my_reel_poster.jpg "$OUTDIR/"
chmod 644 "$OUTDIR"/sea_in_th_my_reel*

echo "=== DONE ==="
ls -lah "$OUTDIR"/sea_in_th_my_reel*
ffprobe -v error -show_entries format=duration -show_entries stream=width,height -of default=noprint_wrappers=1 \
  "$OUTDIR/sea_in_th_my_reel.mp4"
echo "URL: https://mathrelaxing.store/static/ads/sea_in_th_my_reel.mp4"
echo "URL15: https://mathrelaxing.store/static/ads/sea_in_th_my_reel_15s.mp4"
echo "POSTER: https://mathrelaxing.store/static/ads/sea_in_th_my_reel_poster.jpg"
