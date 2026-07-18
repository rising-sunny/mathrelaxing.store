#!/usr/bin/env bash
# SEA Meta ad reel v2 — motion loops + recently published products.
set -euo pipefail

ROOT=/var/www/mathrelaxing.store
WORKDIR=/tmp/sea_reel_v2
OUTDIR=$ROOT/static/ads
mkdir -p "$WORKDIR" "$OUTDIR"
rm -rf "$WORKDIR"/*
cd "$WORKDIR"

FONT=$ROOT/static/fonts/Cinzel.ttf
FONT2=$ROOT/static/fonts/Raleway.ttf
LOGO=$ROOT/static/img/logo.png
SIZE=1080
FPS=30
SEG_LOOP=3
SEG_PRODUCT=3
STILL_FRAMES=90   # 3s * 30fps

: >/tmp/ff_still.log
: >/tmp/ff_vid.log
: >/tmp/ff_end.log
: >/tmp/ff_concat.log

still_to_clip() {
  local img="$1" out="$2" label="$3"
  [[ -f "$img" ]] || { echo "missing img $img" >>/tmp/ff_still.log; return 1; }
  # Reliable still→video: cover-crop square + label bar (no zoompan float math)
  ffmpeg -y -loop 1 -i "$img" -t "$SEG_PRODUCT" \
    -vf "scale=${SIZE}:${SIZE}:force_original_aspect_ratio=increase,crop=${SIZE}:${SIZE},fps=${FPS},\
drawbox=x=0:y=ih-110:w=iw:h=110:color=0x0B1220@0.72:t=fill,\
drawtext=fontfile=${FONT2}:text='${label}':fontcolor=0xE8E4DC:fontsize=32:\
x=(w-text_w)/2:y=h-70,format=yuv420p" \
    -an -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
    "$out" </dev/null 2>>/tmp/ff_still.log
}

video_to_clip() {
  local in="$1" out="$2" start="${3:-0}" dur="${4:-$SEG_LOOP}" label="${5:-}"
  [[ -f "$in" ]] || return 1
  local vf="scale=${SIZE}:${SIZE}:force_original_aspect_ratio=increase,crop=${SIZE}:${SIZE},fps=${FPS},format=yuv420p"
  if [[ -n "$label" ]]; then
    vf="${vf},drawbox=x=0:y=ih-110:w=iw:h=110:color=0x0B1220@0.72:t=fill,drawtext=fontfile=${FONT2}:text='${label}':fontcolor=0xE8E4DC:fontsize=32:x=(w-text_w)/2:y=h-70"
  fi
  ffmpeg -y -ss "$start" -t "$dur" -i "$in" \
    -vf "$vf" -an -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
    "$out" </dev/null 2>>/tmp/ff_vid.log
}

pick_hero() {
  local slug="$1"
  local g="$ROOT/static/digital/${slug}/01_hero.jpg"
  local c="$ROOT/static/img/${slug}_cover.jpg"
  local p="$ROOT/static/previews/${slug}.jpg"
  if [[ -f "$g" ]]; then echo "$g"
  elif [[ -f "$c" ]]; then echo "$c"
  elif [[ -f "$p" ]]; then echo "$p"
  else echo ""
  fi
}

n=0
: > list.txt
push() {
  local f
  n=$((n + 1))
  f=$(printf "%02d.mp4" "$n")
  if "$@"; then
    # last arg of still_to_clip/video_to_clip is not the outfile in our calls —
    # we pass outfile as $2 always. Rename if needed.
    true
  fi
}

# Helper: try make clip into numbered file and append concat list
make_video() {
  n=$((n + 1))
  local f out_args
  f=$(printf "%02d.mp4" "$n")
  if video_to_clip "$1" "$f" "${2:-0}" "${3:-$SEG_LOOP}" "${4:-}"; then
    echo "file '$f'" >> list.txt
    echo "OK video $f — $4"
  else
    n=$((n - 1))
    echo "FAIL video $1"
  fi
}

make_still() {
  local slug="$1" label="$2"
  local img
  img=$(pick_hero "$slug")
  n=$((n + 1))
  local f
  f=$(printf "%02d.mp4" "$n")
  if [[ -n "$img" ]] && still_to_clip "$img" "$f" "$label"; then
    echo "file '$f'" >> list.txt
    echo "OK still $f — $label ($img)"
  else
    n=$((n - 1))
    echo "FAIL still $slug"
  fi
}

make_promo_or_still() {
  local slug="$1" label="$2"
  local promo="$ROOT/static/digital/${slug}/00_preview.mp4"
  if [[ -f "$promo" ]]; then
    make_video "$promo" 0 "$SEG_PRODUCT" "$label"
  else
    make_still "$slug" "$label"
  fi
}

echo "=== Building reel segments ==="

# Hook: hypnotic math motion
make_video "$ROOT/static/video/thomas_attractor_loop.mp4" 0 "$SEG_LOOP" "Thomas Attractor"
make_video "$ROOT/static/digital/julia-set-loop/00_preview.mp4" 0 "$SEG_LOOP" "Julia Set Loop"
make_video "$ROOT/static/digital/voronoi-cell-garden-loop/00_preview.mp4" 0 "$SEG_LOOP" "Voronoi Garden"

# Recently published — Batch 1
make_still "happy-chemicals-print-set" "Happy Chemicals Prints"
make_still "computer-science-poster-set" "CS Poster Set"
make_still "unit-circle-poster" "Unit Circle Poster"
make_still "schrodinger-equation-print" "Schrodinger Equation"
make_still "stem-lab-notebook" "STEM Lab Notebook"
make_still "stem-digital-notebook" "STEM Digital Notebook"

# Recently published — Batch 2 (visual templates)
make_promo_or_still "editorial-resume-kit" "Editorial Resume Kit"
make_still "atelier-resume-kit" "Atelier Resume Kit"
make_still "letter-of-recommendation-pack" "Letter of Recommendation"
make_still "family-emergency-binder" "Family Emergency Binder"

# Recently published — Batch 3
make_promo_or_still "bauhaus-print-set" "Bauhaus Print Set"
make_still "mathematical-constants-bundle" "Math Constants Bundle"
make_still "beautiful-equations-print-set" "Beautiful Equations"
make_still "golden-ratio-poster" "Golden Ratio Poster"
make_still "lorenz-attractor-print-set" "Lorenz Print Set"
make_still "clifford-attractor-print-set" "Clifford Print Set"
make_still "newton-fractal-print-set" "Newton Fractal Set"

# Close with motion + de jong
make_video "$ROOT/static/dejong_loop_1080.mp4" 0 "$SEG_LOOP" "De Jong Loop"
make_video "$ROOT/static/examples/lorenz_flow_1080p30.mp4" 0 2.2 "Chaos · Order · Beauty"

echo "=== End card ==="
n=$((n + 1))
f=$(printf "%02d.mp4" "$n")
ffmpeg -y -f lavfi -i "color=c=0x0B1220:s=${SIZE}x${SIZE}:d=3.5:r=${FPS}" \
  -i "$LOGO" \
  -filter_complex "\
    [1:v]scale=200:-1,format=rgba[logo]; \
    [0:v][logo]overlay=(W-w)/2:130[v1]; \
    [v1]drawtext=fontfile=${FONT}:text='MathRelaxing':fontcolor=0xC8A96E:fontsize=60:x=(w-text_w)/2:y=370,\
drawtext=fontfile=${FONT2}:text='New digital math art · Instant download':fontcolor=0xE8E4DC:fontsize=30:x=(w-text_w)/2:y=460,\
drawtext=fontfile=${FONT2}:text='Prints · Notebooks · Loops · Kits':fontcolor=0xA8A29A:fontsize=26:x=(w-text_w)/2:y=520,\
drawtext=fontfile=${FONT2}:text='SHOP NOW':fontcolor=0x0B1220:fontsize=40:box=1:boxcolor=0xC8A96E@1:boxborderw=18:x=(w-text_w)/2:y=650,\
drawtext=fontfile=${FONT2}:text='mathrelaxing.store':fontcolor=0xC8A96E:fontsize=26:x=(w-text_w)/2:y=770,\
drawtext=fontfile=${FONT2}:text='India  ·  Thailand  ·  Malaysia':fontcolor=0x6B6560:fontsize=22:x=(w-text_w)/2:y=870\
  " \
  -t 3.5 -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -an \
  "$f" </dev/null 2>>/tmp/ff_end.log
echo "file '$f'" >> list.txt
echo "OK endcard $f"

echo "=== Concat list ($n segments) ==="
cat list.txt

ffmpeg -y -f concat -safe 0 -i list.txt -c:v libx264 -preset slow -crf 19 \
  -pix_fmt yuv420p -movflags +faststart -an \
  sea_in_th_my_reel.mp4 </dev/null 2>>/tmp/ff_concat.log

# Short: first 3 hooks + 5 recent products + last 2 motion + end
# Use lines 1-3, 4-8, and last line
{
  head -n 3 list.txt
  sed -n '4,10p' list.txt
  tail -n 1 list.txt
} > list_short.txt
ffmpeg -y -f concat -safe 0 -i list_short.txt -c:v libx264 -preset slow -crf 19 \
  -pix_fmt yuv420p -movflags +faststart -an \
  sea_in_th_my_reel_15s.mp4 </dev/null 2>>/tmp/ff_concat.log

ffmpeg -y -ss 3 -i sea_in_th_my_reel.mp4 -frames:v 1 -q:v 2 sea_in_th_my_reel_poster.jpg </dev/null 2>>/tmp/ff_concat.log

cp -f sea_in_th_my_reel.mp4 sea_in_th_my_reel_15s.mp4 sea_in_th_my_reel_poster.jpg "$OUTDIR/"
cp -f sea_in_th_my_reel.mp4 "$OUTDIR/sea_in_th_my_reel_v2.mp4"
cp -f sea_in_th_my_reel_15s.mp4 "$OUTDIR/sea_in_th_my_reel_v2_short.mp4"
chmod 644 "$OUTDIR"/sea_in_th_my_reel*

echo "=== DONE ==="
ls -lah "$OUTDIR"/sea_in_th_my_reel*
ffprobe -v error -show_entries format=duration -show_entries stream=width,height \
  -of default=noprint_wrappers=1 "$OUTDIR/sea_in_th_my_reel.mp4"
echo "FULL:  https://mathrelaxing.store/static/ads/sea_in_th_my_reel.mp4"
echo "V2:    https://mathrelaxing.store/static/ads/sea_in_th_my_reel_v2.mp4"
echo "SHORT: https://mathrelaxing.store/static/ads/sea_in_th_my_reel_15s.mp4"
echo "POSTER:https://mathrelaxing.store/static/ads/sea_in_th_my_reel_poster.jpg"
