"""
Etsy listing previews for Sacred Geometry — iPad Edition (2000x2000).
1) iPad mockup hero with a colored design on screen
2) "What's included"
3) "Two ways to color" (GoodNotes vs Procreate)
"""
import fitz, os, math, random
import numpy as np
from scipy.ndimage import label, binary_dilation
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SRC      = "/var/www/mathrelaxing.store/static/downloads/sacred-math-coloring-book/interior.pdf"
OUT      = "/var/www/mathrelaxing.store/static/downloads/digital/ipad_sg/previews"
FONT_DIR = "/var/www/mathrelaxing.store/static/fonts"
CINZEL   = FONT_DIR + "/Cinzel.ttf"
RALEWAY  = FONT_DIR + "/Raleway.ttf"
RALEWAY_IT = FONT_DIR + "/Raleway-Italic.ttf"
LOGO     = "/var/www/mathrelaxing.store/static/img/logo.png"
os.makedirs(OUT, exist_ok=True)
random.seed(5); np.random.seed(5)

S = 2000
NAVY=(18,23,46); GOLD=(217,173,82); WHITE=(244,247,245); DIM=(150,162,185); TEAL=(125,207,179)
PALS = [
    [(255,226,150),(255,168,88),(230,96,68),(150,48,82),(70,28,66)],     # sunset
    [(216,234,247),(150,196,224),(74,123,168),(26,61,107),(13,35,71)],   # ocean
    [(232,216,246),(190,158,226),(138,98,190),(88,52,138),(48,28,84)],   # amethyst
]

def font(p,s): return ImageFont.truetype(p,s)
def ctext(d,cx,y,t,f,fill):
    b=d.textbbox((0,0),t,font=f); d.text((cx-(b[2]-b[0])/2,y),t,font=f,fill=fill)

# ── color a design via flood-filled facets (3D-shaded) ───────────────────────
def render_rgb(idx, tw=1100):
    p=fitz.open(SRC)[idx]
    pix=p.get_pixmap(matrix=fitz.Matrix(tw/p.rect.width, tw/p.rect.width), colorspace=fitz.csRGB, alpha=False)
    return np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3).copy()

def design_crop(arr):
    g=arr.mean(2); h,w=g.shape
    reg=g[:int(h*0.83),:]; ys,xs=np.where(reg<120)
    if len(xs)==0: return arr
    pad=int(0.04*max(w,h))
    return arr[max(0,ys.min()-pad):min(int(h*0.83),ys.max()+pad), max(0,xs.min()-pad):min(w,xs.max()+pad)]

def color_design(idx, pal):
    arr=design_crop(render_rgb(idx)).astype(np.float32)
    g=arr.mean(2); lines=binary_dilation(g<120,iterations=1)
    lbl,n=label(~lines); h,w=g.shape
    border=set(lbl[0,:])|set(lbl[-1,:])|set(lbl[:,0])|set(lbl[:,-1])
    cur=arr.copy()
    cents=[]
    for i in range(1,n+1):
        if i in border: continue
        m=lbl==i
        if m.sum()<40: continue
        ys,xs=np.where(m); cents.append((i,m,xs.mean()+ys.mean()))
    if cents:
        dv=np.array([c[2] for c in cents]); lo,span=dv.min(),(np.ptp(dv) or 1)
        for (i,m,d) in cents:
            t=min(max((d-lo)/span+random.uniform(-0.08,0.08),0),1)
            pos=t*(len(pal)-1); k=int(pos); fr=pos-k
            a=pal[k]; b=pal[min(k+1,len(pal)-1)]
            col=[a[j]*(1-fr)+b[j]*fr for j in range(3)]
            for j in range(3): cur[:,:,j][m]=col[j]
    return Image.fromarray(np.clip(cur,0,255).astype(np.uint8),"RGB")

def line_design(idx):
    return Image.fromarray(design_crop(render_rgb(idx)).astype(np.uint8),"RGB")

# ── iPad frame ───────────────────────────────────────────────────────────────
def ipad(screen_img, fw=1080, fh=1440):
    # body
    body=Image.new("RGBA",(fw,fh),(0,0,0,0))
    d=ImageDraw.Draw(body)
    d.rounded_rectangle([0,0,fw,fh],radius=70,fill=(28,30,38,255))
    bz=34
    # screen area
    sx0,sy0,sx1,sy1=bz,bz+10,fw-bz,fh-bz-10
    sw,sh=sx1-sx0,sy1-sy0
    scr=Image.new("RGB",(sw,sh),(255,255,255))
    # fit design centered
    im=screen_img.copy(); r=min(sw/im.width,sh/im.height)*0.92
    im=im.resize((int(im.width*r),int(im.height*r)),Image.LANCZOS)
    scr.paste(im,((sw-im.width)//2,(sh-im.height)//2))
    body.paste(scr,(sx0,sy0))
    # camera dot
    d.ellipse([fw/2-5,15,fw/2+5,25],fill=(80,84,96,255))
    return body

def paste_logo(img, y, scale=0.13, alpha=0.9):
    lg=Image.open(LOGO).convert("RGBA"); lw=int(img.width*scale); lh=int(lg.height*lw/lg.width)
    lg=lg.resize((lw,lh),Image.LANCZOS)
    if alpha<1:
        r,g,b,a=lg.split(); a=a.point(lambda p:int(p*alpha)); lg=Image.merge("RGBA",(r,g,b,a))
    img.paste(lg,((img.width-lw)//2,y),lg)

# ── Preview 1: iPad hero ─────────────────────────────────────────────────────
def p1():
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv)
    # subtle radial-ish background dots
    for x in range(0,S,46):
        for y in range(0,S,46): d.ellipse([x-1,y-1,x+1,y+1],fill=(26,32,58))
    ctext(d,S/2,90,"Color by Number for iPad",font(CINZEL,76),WHITE)
    ctext(d,S/2,196,"Sacred Geometry  ·  50 Low-Poly Designs",font(RALEWAY_IT,40),GOLD)
    pad=ipad(color_design(20,PALS[0]))
    r=900/pad.width; pad=pad.resize((int(pad.width*r),int(pad.height*r)),Image.LANCZOS)
    # soft shadow
    sh=Image.new("RGBA",cv.size,(0,0,0,0)); ds=ImageDraw.Draw(sh)
    px=(S-pad.width)//2; py=300
    ds.rounded_rectangle([px+14,py+22,px+pad.width+14,py+pad.height+22],radius=60,fill=(0,0,0,120))
    sh=sh.filter(ImageFilter.GaussianBlur(26)); cv.paste(Image.alpha_composite(cv.convert("RGBA"),sh).convert("RGB"),(0,0))
    cv.paste(pad,(px,py),pad)
    # badges
    d=ImageDraw.Draw(cv)
    by=py+pad.height+34
    ctext(d,S/2,by,"GoodNotes  ·  Notability  ·  Procreate",font(RALEWAY,34),TEAL)
    paste_logo(cv,S-150)
    cv.save(f"{OUT}/ipad_preview_1_hero.jpg","JPEG",quality=92)

# ── Preview 2: What's included ───────────────────────────────────────────────
def drawcheck(d,cx,cy,s,col):
    d.line([(cx-s*0.34,cy+s*0.02),(cx-s*0.06,cy+s*0.28),(cx+s*0.36,cy-s*0.32)],
           fill=col,width=8,joint="curve")

def p2():
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv)
    d.rectangle([0,0,S,8],fill=GOLD)
    ctext(d,S/2,110,"Everything Included",font(CINZEL,80),WHITE)
    ctext(d,S/2,220,"Sacred Geometry  ·  iPad Edition",font(RALEWAY_IT,38),GOLD)
    items=[
        "50 unique low-poly color-by-number designs",
        "Hyperlinked PDF index for GoodNotes & Notability",
        "50 transparent PNGs (300 dpi) for Procreate",
        "Procreate color palette  ·  30 swatches",
        "'How to use on iPad' quick guide",
        "Instant download  ·  personal use",
    ]
    y=400
    for desc in items:
        d.rounded_rectangle([160,y,250,y+84],radius=18,fill=(30,38,64))
        drawcheck(d,205,y+42,40,GOLD)
        d.text((300,y+20),desc,font=font(RALEWAY,38),fill=WHITE)
        y+=135
    paste_logo(cv,S-150)
    cv.save(f"{OUT}/ipad_preview_2_included.jpg","JPEG",quality=92)

# ── Preview 3: Two ways to color ─────────────────────────────────────────────
def p3():
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv)
    ctext(d,S/2,90,"Two Ways to Color",font(CINZEL,78),WHITE)
    ctext(d,S/2,196,"however you love to work on your iPad",font(RALEWAY_IT,38),GOLD)
    # left: GoodNotes (line art) ; right: Procreate (colored)
    half=S//2
    def panel(cx, img, label, sub):
        r=min(620/img.width, 820/img.height); im=img.resize((int(img.width*r),int(img.height*r)),Image.LANCZOS)
        # white card
        cardw,cardh=im.width+60,im.height+60
        card=Image.new("RGB",(cardw,cardh),(250,250,248))
        card.paste(im,(30,30))
        cv.paste(card,(cx-cardw//2,330))
        dd=ImageDraw.Draw(cv)
        ctext(dd,cx,330+cardh+30,label,font(CINZEL,42),TEAL)
        ctext(dd,cx,330+cardh+88,sub,font(RALEWAY,30),DIM)
    panel(half//2+40, line_design(8), "GoodNotes", "color on top with Apple Pencil")
    panel(half+half//2-40, color_design(8,PALS[2]), "Procreate", "color beneath the line art")
    paste_logo(cv,S-150)
    cv.save(f"{OUT}/ipad_preview_3_twoways.jpg","JPEG",quality=92)

print("Generating iPad previews...")
p1(); print("  1 hero")
p2(); print("  2 included")
p3(); print("  3 two ways")
print("Done ->", OUT)
