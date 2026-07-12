"""
iPad promo video for Sacred Geometry — iPad Edition (1080x1080, 30fps).
An iPad mockup where a real low-poly design colors itself facet by facet
(3D-shaded), with MathRelaxing branding. For Etsy listing video.
"""
import fitz, os, math, random, subprocess, shutil, tempfile
import numpy as np
from scipy.ndimage import label, binary_dilation
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SRC      = "/var/www/mathrelaxing.store/static/downloads/sacred-math-coloring-book/interior.pdf"
OUT      = "/var/www/mathrelaxing.store/static/downloads/digital/ipad_sg/SacredGeometry_iPad_promo.mp4"
FONT_DIR = "/var/www/mathrelaxing.store/static/fonts"
CINZEL   = FONT_DIR + "/Cinzel.ttf"
RALEWAY  = FONT_DIR + "/Raleway.ttf"
RALEWAY_IT = FONT_DIR + "/Raleway-Italic.ttf"
LOGO     = "/var/www/mathrelaxing.store/static/img/logo.png"
random.seed(9); np.random.seed(9)

S=1080; FPS=30
NAVY=(18,23,46); GOLD=(217,173,82); WHITE=(244,247,245); TEAL=(125,207,179); DIM=(150,162,185)
DESIGN1=20; PAL1=[(255,226,150),(255,168,88),(230,96,68),(150,48,82),(70,28,66)]      # sunset (torus)
DESIGN2=48; PAL2=[(232,216,246),(190,158,226),(138,98,190),(88,52,138),(48,28,84)]    # amethyst (sphere)
AUDIO_SRC="/var/www/mathrelaxing.store/static/downloads/fractal-flora-coloring-book/promo.mp4"

def font(p,s): return ImageFont.truetype(p,s)
def ctext(d,cx,y,t,f,fill):
    b=d.textbbox((0,0),t,font=f); d.text((cx-(b[2]-b[0])/2,y),t,font=f,fill=fill)

def render_rgb(idx, tw=900):
    p=fitz.open(SRC)[idx]
    pix=p.get_pixmap(matrix=fitz.Matrix(tw/p.rect.width, tw/p.rect.width), colorspace=fitz.csRGB, alpha=False)
    return np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3).copy()

def design_crop(arr):
    g=arr.mean(2); h,w=g.shape; reg=g[:int(h*0.83),:]; ys,xs=np.where(reg<120)
    if len(xs)==0: return arr
    pad=int(0.04*max(w,h))
    return arr[max(0,ys.min()-pad):min(int(h*0.83),ys.max()+pad), max(0,xs.min()-pad):min(w,xs.max()+pad)]

def prep(idx, pal):
    arr=design_crop(render_rgb(idx)).astype(np.float32)
    g=arr.mean(2); lines=binary_dilation(g<120,iterations=1)
    lbl,n=label(~lines); h,w=g.shape
    border=set(lbl[0,:])|set(lbl[-1,:])|set(lbl[:,0])|set(lbl[:,-1])
    cents=[]
    for i in range(1,n+1):
        if i in border: continue
        m=lbl==i
        if m.sum()<40: continue
        ys,xs=np.where(m); cents.append((m, xs.mean(), ys.mean(), math.hypot(xs.mean()-w/2, ys.mean()-h/2)))
    dv=np.array([c[1]+c[2] for c in cents]); lo,span=dv.min(),(np.ptp(dv) or 1)
    facets=[]
    for (m,mx,my,dist) in cents:
        t=min(max((mx+my-lo)/span+random.uniform(-0.07,0.07),0),1)
        pos=t*(len(pal)-1); k=int(pos); fr=pos-k
        a=pal[k]; b=pal[min(k+1,len(pal)-1)]
        col=[a[j]*(1-fr)+b[j]*fr for j in range(3)]
        facets.append((m,col,dist))
    facets.sort(key=lambda f:f[2])   # bloom from center outward
    return arr, facets

# ── iPad geometry on the 1080 canvas ─────────────────────────────────────────
IPW,IPH=560,748
IPX=(S-IPW)//2; IPY=150
BEZEL=16
SX,SY=IPX+BEZEL, IPY+BEZEL
SW,SH=IPW-2*BEZEL, IPH-2*BEZEL

def base_canvas():
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv)
    for x in range(0,S,46):
        for y in range(0,S,46): d.ellipse([x-1,y-1,x+1,y+1],fill=(26,32,58))
    ctext(d,S/2,46,"Color by Number for iPad",font(CINZEL,52),WHITE)
    ctext(d,S/2,118,"Sacred Geometry  ·  GoodNotes & Procreate",font(RALEWAY_IT,27),GOLD)
    # iPad body
    d.rounded_rectangle([IPX,IPY,IPX+IPW,IPY+IPH],radius=44,fill=(25,27,34))
    d.ellipse([S/2-5,IPY+7,S/2+5,IPY+17],fill=(52,55,63))
    # white screen base
    d.rectangle([SX,SY,SX+SW,SY+SH],fill=(255,255,255))
    # footer
    ctext(d,S/2,IPY+IPH+34,"GoodNotes  ·  Notability  ·  Procreate",font(RALEWAY,26),TEAL)
    lg=Image.open(LOGO).convert("RGBA"); lw=120; lh=int(lg.height*lw/lg.width)
    lg=lg.resize((lw,lh),Image.LANCZOS); cv=cv.convert("RGBA"); cv.alpha_composite(lg,((S-lw)//2,S-lh-26))
    return cv.convert("RGB")

def screen_from(arr):
    im=Image.fromarray(np.clip(arr,0,255).astype(np.uint8),"RGB")
    r=min(SW/im.width, SH/im.height)*0.95
    im=im.resize((int(im.width*r),int(im.height*r)),Image.LANCZOS)
    sc=Image.new("RGB",(SW,SH),(255,255,255))
    sc.paste(im,((SW-im.width)//2,(SH-im.height)//2))
    return sc

def main():
    print("Preparing designs...")
    arr1,fac1=prep(DESIGN1,PAL1); arr2,fac2=prep(DESIGN2,PAL2)
    print(f"  design1: {len(fac1)} facets | design2: {len(fac2)} facets")
    base=base_canvas()
    tmp=tempfile.mkdtemp(prefix="ipadpromo_"); fi=[0]
    def save(cv): cv.save(os.path.join(tmp,f"f_{fi[0]:05d}.png")); fi[0]+=1
    def fw(state):
        cv=base.copy(); cv.paste(screen_from(state),(SX,SY)); return cv

    HOLD_BW=int(0.6*FPS); HOLD_DONE=int(1.6*FPS); CROSS=int(0.5*FPS); FADE=int(0.7*FPS)
    FILL_TARGET=115

    def animate(arr, facets, hold_bw):
        cur=arr.copy()
        bw=fw(cur)
        for _ in range(hold_bw): save(bw)
        per=max(1, round(len(facets)/FILL_TARGET))
        i=0
        while i<len(facets):
            for (m,col,_) in facets[i:i+per]:
                for j in range(3): cur[:,:,j][m]=col[j]
            save(fw(cur)); i+=per
        done=fw(cur)
        for _ in range(HOLD_DONE): save(done)
        return done

    print("Rendering frames...")
    done1=animate(arr1,fac1,HOLD_BW)
    bw2=fw(arr2.copy())
    for f in range(CROSS): save(Image.blend(done1,bw2,(f+1)/CROSS))
    done2=animate(arr2,fac2,2)
    navyimg=Image.new("RGB",(S,S),NAVY)
    for f in range(FADE): save(Image.blend(done2,navyimg,((f+1)/FADE)*0.6))
    dur=fi[0]/FPS
    print(f"  {fi[0]} frames ({dur:.1f}s)")

    print("Preparing music...")
    aud="/tmp/ip_audio.aac"
    fo=max(0.5,dur-1.3)
    subprocess.run(f'ffmpeg -y -i {AUDIO_SRC} -map 0:a:0 -t {dur:.2f} -af "afade=t=in:st=0:d=0.8,afade=t=out:st={fo:.2f}:d=1.3" -ac 2 -c:a aac -b:a 160k {aud}',
                   shell=True, capture_output=True)
    has_a=os.path.exists(aud) and os.path.getsize(aud)>1000

    print("Encoding...")
    cmd=f'ffmpeg -y -framerate {FPS} -i {tmp}/f_%05d.png'
    if has_a: cmd+=f' -i {aud}'
    cmd+=' -c:v libx264 -pix_fmt yuv420p -crf 18 -preset slow -movflags +faststart'
    if has_a: cmd+=' -c:a aac -shortest'
    cmd+=f' {OUT}'
    subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(tmp,ignore_errors=True)
    print(f"Done! {OUT} ({os.path.getsize(OUT)/1024/1024:.1f} MB, audio={has_a})")

main()
