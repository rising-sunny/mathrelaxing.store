#!/usr/bin/env bash
# SEA Meta ad SHORT reel (~20–25s): hooks + best recent products + end card.
set -euo pipefail

ROOT=/var/www/mathrelaxing.store
WORKDIR=/tmp/sea_reel_short
OUTDIR=$ROOT/static/ads
mkdir -p "$WORKDIR" "$OUTDIR"
rm -rf "$WORKDIR"/*
cd "$WORKDIR"

FONT=$ROOT/static/fonts/Cinzel.ttf
FONT2=$ROOT/static/fonts/Raleway.ttf
LOGO=$ROOT/static/img/logo.png
SIZE=1080
FPS=30
SEG_LOOP=2.4
SEG_PRODUCT=2.2

: >/tmp/ff_short_build.log

still_to_clip() {
  local img="$1" out="$2" label="$3"
  [[ -f "$img" ]] || return 1
  ffmpeg -y -loop 1 -i "$img" -t "$SEG_PRODUCT" \
    -vf "scale=${SIZE}:${SIZE}:force_original_aspect_ratio=increase,crop=${SIZE}:${SIZE},fps=${FPS},\
drawbox=x=0:y=ih-100:w=iw:h=100:color=0x0B1220@0.75:t=fill,\
drawtext=fontfile=${FONT2}:text='${label}':fontcolor=0xE8E4DC:fontsize=30:\
x=(w-text_w)/2:y=h-64,format=yuv420p" \
    -an -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
    "$out" </dev/null 2>>/tmp/ff_short_build.log
}

video_to_clip() {
  local in="$1" out="$2" start="${3:-0}" dur="${4:-$SEG_LOOP}" label="${5:-}"
  [[ -f "$in" ]] || return 1
  local vf="scale=${SIZE}:${SIZE}:force_original_aspect_ratio=increase,crop=${SIZE}:${SIZE},fps=${FPS},format=yuv420p"
  if [[ -n "$label" ]]; then
    vf="${vf},drawbox=x=0:y=ih-100:w=iw:h=100:color=0x0B1220@0.75:t=fill,drawtext=fontfile=${FONT2}:text='${label}':fontcolor=0xE8E4DC:fontsize=30:x=(w-text_w)/2:y=h-64"
  fi
  ffmpeg -y -ss "$start" -t "$dur" -i "$in" \
    -vf "$vf" -an -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
    "$out" </dev/null 2>>/tmp/ff_short_build.log
}

pick_hero() {
  local slug="$1"
  for p in \
    "$ROOT/static/digital/${slug}/01_hero.jpg" \
    "$ROOT/static/img/${slug}_cover.jpg" \
    "$ROOT/static/previews/${slug}.jpg"
  do
    if [[ -f "$p" ]]; then echo "$p"; return 0; fi
  done
  echo ""
}

n=0
: > list.txt

add_video() {
  n=$((n + 1))
  local f; f=$(printf "%02d.mp4" "$n")
  if video_to_clip "$1" "$f" "${2:-0}" "${3:-$SEG_LOOP}" "${4:-}"; then
    echo "file '$f'" >> list.txt
    echo "OK $f — $4"
  else
    n=$((n - 1)); echo "FAIL video $1"
  fi
}

add_still() {
  local slug="$1" label="$2"
  local img; img=$(pick_hero "$slug")
  n=$((n + 1))
  local f; f=$(printf "%02d.mp4" "$n")
  if [[ -n "$img" ]] && still_to_clip "$img" "$f" "$label"; then
    echo "file '$f'" >> list.txt
    echo "OK $f — $label"
  else
    n=$((n - 1)); echo "FAIL still $slug"
  fi
}

echo "=== SHORT reel segments ==="
# 2 hooks (~4.8s)
add_video "$ROOT/static/video/thomas_attractor_loop.mp4" 0 "$SEG_LOOP" "Thomas Attractor"
add_video "$ROOT/static/digital/julia-set-loop/00_preview.mp4" 0 "$SEG_LOOP" "Julia Set Loop"

# 6 recent bestsellers / visual hits (~13.2s)
add_still "happy-chemicals-print-set" "Happy Chemicals"
add_still "computer-science-poster-set" "CS Poster Set"
add_still "unit-circle-poster" "Unit Circle"
add_still "bauhaus-print-set" "Bauhaus Prints"
add_still "beautiful-equations-print-set" "Beautiful Equations"
add_still "newton-fractal-print-set" "Newton Fractal"

# 1 motion close (~2.4s)
add_video "$ROOT/static/dejong_loop_1080.mp4" 0 "$SEG_LOOP" "De Jong Loop"

# End card (~3s) → total ~23s
n=$((n + 1))
f=$(printf "%02d.mp4" "$n")
ffmpeg -y -f lavfi -i "color=c=0x0B1220:s=${SIZE}x${SIZE}:d=3.0:r=${FPS}" \
  -i "$LOGO" \
  -filter_complex "\
    [1:v]scale=180:-1,format=rgba[logo]; \
    [0:v][logo]overlay=(W-w)/2:150[v1]; \
    [v1]drawtext=fontfile=${FONT}:text='MathRelaxing':fontcolor=0xC8A96E:fontsize=58:x=(w-text_w)/2:y=380,\
drawtext=fontfile=${FONT2}:text='Math that feels like art':fontcolor=0xE8E4DC:fontsize=32:x=(w-text_w)/2:y=470,\
drawtext=fontfile=${FONT2}:text='Instant digital download':fontcolor=0xA8A29A:fontsize=26:x=(w-text_w)/2:y=530,\
drawtext=fontfile=${FONT2}:text='SHOP NOW':fontcolor=0x0B1220:fontsize=40:box=1:boxcolor=0xC8A96E@1:boxborderw=16:x=(w-text_w)/2:y=640,\
drawtext=fontfile=${FONT2}:text='mathrelaxing.store':fontcolor=0xC8A96E:fontsize=24:x=(w-text_w)/2:y=760,\
drawtext=fontfile=${FONT2}:text='IN  ·  TH  ·  MY':fontcolor=0x6B6560:fontsize=22:x=(w-text_w)/2:y=860\
  " \
  -t 3.0 -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -an \
  "$f" </dev/null 2>>/tmp/ff_short_build.log
echo "file '$f'" >> list.txt
echo "OK endcard $f"

echo "=== Concat ==="
cat list.txt
ffmpeg -y -f concat -safe 0 -i list.txt -c:v libx264 -preset slow -crf 19 \
  -pix_fmt yuv420p -movflags +faststart -an \
  sea_short.mp4 </dev/null 2>>/tmp/ff_short_build.log

ffmpeg -y -ss 1.5 -i sea_short.mp4 -frames:v 1 -q:v 2 sea_short_poster.jpg </dev/null 2>>/tmp/ff_short_build.log

# Publish as primary short + cache-busted name
cp -f sea_short.mp4 "$OUTDIR/sea_in_th_my_reel_15s.mp4"
cp -f sea_short.mp4 "$OUTDIR/sea_in_th_my_reel_short.mp4"
cp -f sea_short.mp4 "$OUTDIR/sea_in_th_my_reel_v2_short.mp4"
cp -f sea_short_poster.jpg "$OUTDIR/sea_in_th_my_reel_poster.jpg"
chmod 644 "$OUTDIR"/sea_in_th_my_reel*

DUR=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTDIR/sea_in_th_my_reel_short.mp4")
echo "=== DONE duration=${DUR}s ==="
ls -lah "$OUTDIR"/sea_in_th_my_reel_short.mp4 "$OUTDIR"/sea_in_th_my_reel_15s.mp4
echo "URL: https://mathrelaxing.store/static/ads/sea_in_th_my_reel_short.mp4"
echo "URL: https://mathrelaxing.store/static/ads/sea_in_th_my_reel_15s.mp4"
echo "POSTER: https://mathrelaxing.store/static/ads/sea_in_th_my_reel_poster.jpg"
