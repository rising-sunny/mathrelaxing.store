"""
watermark_preview.py — genera un PREVIEW degradado + marca de agua para
productos cuyo entregable ES el video (loops). El archivo de descarga sigue
siendo el MP4 limpio 1080p; esto es solo para el video del listing.

  python3 watermark_preview.py <input.mp4> <output.mp4> [size=540]

Marca: "mathrelaxing.store" repetido en diagonal, blanco ~18% alpha (inservible
para robar, pero deja ver el movimiento).
"""
import sys, os, subprocess
from PIL import Image, ImageDraw, ImageFont

FONT = "/var/www/mathrelaxing.store/static/fonts/Raleway.ttf"

def make_watermark(size, text="mathrelaxing.store", alpha=110):
    # tiling por CIZALLA (shear): cobertura total garantizada, diagonal sin huecos.
    # Cada texto lleva sombra oscura -> legible sobre zonas claras Y oscuras.
    wm = Image.new("RGBA", (size, size), (0,0,0,0))
    d = ImageDraw.Draw(wm)
    f = ImageFont.truetype(FONT, int(size*0.042))
    tw = d.textbbox((0,0), text, font=f)[2]
    stepx = int(tw + size*0.06)
    stepy = int(size*0.12)
    slope = 0.36
    for y in range(-stepy, size+stepy, stepy):
        base = (int(-y*slope) % stepx) - stepx
        x = base
        while x < size + tw:
            d.text((x+1, y+1), text, font=f, fill=(0,0,0,int(alpha*0.6)))   # sombra
            d.text((x,   y),   text, font=f, fill=(255,255,255,alpha))      # texto
            x += stepx
    return wm

def main():
    inp, out = sys.argv[1], sys.argv[2]
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 540
    wm = make_watermark(size); wmp = "/tmp/_wm.png"; wm.save(wmp)
    cmd = (f'ffmpeg -y -i "{inp}" -i {wmp} '
           f'-filter_complex "[0:v]scale={size}:{size}[v];[v][1:v]overlay=0:0" '
           f'-c:v libx264 -pix_fmt yuv420p -crf 25 -preset slow -movflags +faststart -an "{out}"')
    subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"OK -> {out} ({os.path.getsize(out)/1024/1024:.1f} MB, {size}px, watermarked)")

if __name__ == "__main__":
    main()
