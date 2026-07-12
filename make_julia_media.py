"""
make_julia_media.py — Previews Etsy para Julia morph loop (2000x2000).
Uso: python3 make_julia_media.py <ruta_still.png>
  1 hero · 2 specs · 3 seamless-loop badge
"""
import sys, os, math
sys.path.insert(0,"/var/www/mathrelaxing.store")
from mathrelaxing_kit import fnt, ctext, paste_logo, drawcheck, dot_bg, NAVY, GOLD, WHITE, TEAL, DIM, CINZEL, RALEWAY, RALEWAY_IT, LOGO
from PIL import Image, ImageDraw, ImageFilter

OUT="/var/www/mathrelaxing.store/static/downloads/digital/julia/previews"
os.makedirs(OUT,exist_ok=True)
S=2000
TITLE="Julia Set Animation"
SUB="Seamless Fractal Loop"

def load(still, box):
    im=Image.open(still).convert("RGB")
    r=box/max(im.width,im.height); return im.resize((int(im.width*r),int(im.height*r)),Image.LANCZOS)

def framed(im, pad=0, border=GOLD, bw=4, radius=28):
    """tarjeta con borde dorado y sombra suave."""
    w,h=im.width,im.height
    card=Image.new("RGB",(w,h),(0,0,0)); card.paste(im,(0,0))
    return card

def shadow_paste(cv, card, x, y, rad=30):
    sh=Image.new("RGBA",cv.size,(0,0,0,0)); ds=ImageDraw.Draw(sh)
    ds.rounded_rectangle([x+12,y+18,x+card.width+12,y+card.height+18],radius=24,fill=(0,0,0,130))
    sh=sh.filter(ImageFilter.GaussianBlur(26))
    base=Image.alpha_composite(cv.convert("RGBA"),sh).convert("RGB"); base.paste(card,(x,y))
    return base

def p1(still):
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv); dot_bg(d,S)
    ctext(d,S/2,96,TITLE,fnt(CINZEL,90),WHITE)
    ctext(d,S/2,214,SUB+"  \xb7  Mathematical Wallpaper",fnt(RALEWAY_IT,40),GOLD)
    im=load(still,1440); x=(S-im.width)//2; y=350
    cv=shadow_paste(cv,im,x,y); d=ImageDraw.Draw(cv)
    d.rectangle([x-2,y-2,x+im.width+2,y+im.height+2],outline=GOLD,width=4)
    ctext(d,S/2,y+im.height+44,"Art born from equations",fnt(RALEWAY_IT,36),TEAL)
    paste_logo(cv,S-150); cv.save(f"{OUT}/julia_preview_1_hero.jpg","JPEG",quality=92); print("  p1")

def p2(still):
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv); d.rectangle([0,0,S,8],fill=GOLD)
    ctext(d,S/2,100,"What You Get",fnt(CINZEL,80),WHITE)
    ctext(d,S/2,212,TITLE,fnt(RALEWAY_IT,38),GOLD)
    im=load(still,820); x=140; y=440
    cv=shadow_paste(cv,im,x,y); d=ImageDraw.Draw(cv)
    d.rectangle([x-2,y-2,x+im.width+2,y+im.height+2],outline=GOLD,width=3)
    items=["1080 x 1080 px  \xb7  square","60 fps  \xb7  ultra-smooth","~12 second seamless loop",
           "MP4 (H.264)  \xb7  silent","Wallpaper \xb7 screensaver \xb7 frame","Instant download \xb7 personal use"]
    ix=x+im.width+80; iy=470
    for t in items:
        d.rounded_rectangle([ix,iy,ix+70,iy+70],radius=16,fill=(30,38,64)); drawcheck(d,ix+35,iy+35,32,GOLD)
        d.text((ix+98,iy+16),t,font=fnt(RALEWAY,34),fill=WHITE); iy+=120
    paste_logo(cv,S-150); cv.save(f"{OUT}/julia_preview_2_specs.jpg","JPEG",quality=92); print("  p2")

def p3(still):
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv); dot_bg(d,S)
    im=load(still,1500); x=(S-im.width)//2; y=300
    cv=shadow_paste(cv,im,x,y); d=ImageDraw.Draw(cv)
    d.rectangle([x-2,y-2,x+im.width+2,y+im.height+2],outline=GOLD,width=4)
    # badge ∞ loop
    by=y+im.height-150; bx=S/2
    d.ellipse([bx-150,by-60,bx+150,by+90],fill=(16,20,42))
    ctext(d,bx,by-66,"∞",fnt(CINZEL,120),GOLD)
    ctext(d,S/2,y+im.height+40,"Seamless Loop \xb7 plays forever, no visible cut",fnt(RALEWAY,36),TEAL)
    ctext(d,S/2,150,"Loops Forever",fnt(CINZEL,76),WHITE)
    paste_logo(cv,S-150); cv.save(f"{OUT}/julia_preview_3_loop.jpg","JPEG",quality=92); print("  p3")

if __name__=="__main__":
    still=sys.argv[1] if len(sys.argv)>1 else "/tmp/julia_full/julia_00270.png"
    print("Previews Julia desde",still); p1(still); p2(still); p3(still); print("Done ->",OUT)
