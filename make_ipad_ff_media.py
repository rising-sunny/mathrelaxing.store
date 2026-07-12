"""
Fractal Flora iPad Edition media — CELL-BY-CELL coloring (center outward).
Uses square-cell fractal designs (Dragon Curve etc.); each little cell fills
in one by one. Previews (2000) + promo video (1080).
"""
import fitz, os, math, subprocess, shutil, tempfile
import numpy as np
from scipy.ndimage import label, binary_dilation
from PIL import Image, ImageDraw, ImageFont

SRC="/var/www/mathrelaxing.store/static/downloads/fractal-flora-coloring-book/interior.pdf"
DST="/var/www/mathrelaxing.store/static/downloads/digital/ipad_ff"
PREV=DST+"/previews"; os.makedirs(PREV,exist_ok=True)
FONT="/var/www/mathrelaxing.store/static/fonts"
CINZEL=FONT+"/Cinzel.ttf"; RALEWAY=FONT+"/Raleway.ttf"; RALEWAY_IT=FONT+"/Raleway-Italic.ttf"
LOGO="/var/www/mathrelaxing.store/static/img/logo.png"
AUDIO="/var/www/mathrelaxing.store/static/downloads/fractal-flora-coloring-book/promo.mp4"

NAVY=(18,23,46); GOLD=(217,173,82); WHITE=(244,247,245); TEAL=(125,207,179); DIM=(150,162,185)
WARM=[(255,226,150),(255,168,88),(230,96,68),(150,48,82),(70,28,66)]      # sunset
COOL=[(214,242,247),(140,200,224),(74,140,196),(40,86,150),(26,44,96)]     # ocean
AMTH=[(232,216,246),(190,158,226),(138,98,190),(88,52,138),(48,28,84)]     # amethyst

DESIGN_HERO=17; DESIGN_TWO=18; VID1=17; VID2=18   # dragon curve / twin dragon

def fnt(p,s): return ImageFont.truetype(p,s)
def ctext(d,cx,y,t,f,fill):
    b=d.textbbox((0,0),t,font=f); d.text((cx-(b[2]-b[0])/2,y),t,font=f,fill=fill)

def render_rgb(idx,tw=1000):
    p=fitz.open(SRC)[idx]
    pix=p.get_pixmap(matrix=fitz.Matrix(tw/p.rect.width,tw/p.rect.width),colorspace=fitz.csRGB,alpha=False)
    return np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3).copy()

def design_crop(arr):
    g=arr.mean(2); h,w=g.shape; reg=g[:int(h*0.86),:]; ys,xs=np.where(reg<140)
    if len(xs)==0: return arr
    pad=int(0.04*max(w,h))
    return arr[max(0,ys.min()-pad):min(int(h*0.86),ys.max()+pad), max(0,xs.min()-pad):min(w,xs.max()+pad)]

def prep_cells(idx, pal, tw=1000):
    arr=design_crop(render_rgb(idx,tw)).astype(np.float32); g=arr.mean(2); h,w=g.shape
    best=None
    for dil in (2,3):
        lines=binary_dilation(g<150,iterations=dil); lbl,n=label(~lines)
        border=set(lbl[0,:])|set(lbl[-1,:])|set(lbl[:,0])|set(lbl[:,-1])
        cs=[]
        for i in range(1,n+1):
            if i in border: continue
            s=(lbl==i).sum()
            if 18<s<g.size*0.04: cs.append(lbl==i)
        if best is None or len(cs)>len(best): best=cs
    cells=best or []
    cxc,cyc=w/2,h/2; info=[]
    for m in cells:
        ys,xs=np.where(m); info.append((m, math.hypot(xs.mean()-cxc, ys.mean()-cyc)))
    info.sort(key=lambda t:t[1])
    if info:
        dd=np.array([d for _,d in info]); dmin,dspan=dd.min(),(np.ptp(dd) or 1)
    out=[]
    for (m,d) in info:
        t=(d-dmin)/dspan; pos=t*(len(pal)-1); k=int(pos); fr=pos-k
        a=pal[k]; b=pal[min(k+1,len(pal)-1)]; col=[a[j]*(1-fr)+b[j]*fr for j in range(3)]
        out.append((m,col))
    print(f"    design {idx}: {len(out)} cells")
    return arr, out

def colored_full(idx,pal):
    arr,cells=prep_cells(idx,pal); cur=arr.copy()
    for (m,col) in cells:
        for j in range(3): cur[:,:,j][m]=col[j]
    return Image.fromarray(np.clip(cur,0,255).astype(np.uint8),"RGB")
def line_img(idx):
    return Image.fromarray(design_crop(render_rgb(idx)).astype(np.uint8),"RGB")

def ipad(screen_img, fw=1080, fh=1440):
    body=Image.new("RGBA",(fw,fh),(0,0,0,0)); d=ImageDraw.Draw(body)
    d.rounded_rectangle([0,0,fw,fh],radius=70,fill=(28,30,38,255)); bz=34
    sx,sy=bz,bz+10; sw,sh=fw-2*bz,fh-2*bz-20
    scr=Image.new("RGB",(sw,sh),(255,255,255))
    im=screen_img.copy(); r=min(sw/im.width,sh/im.height)*0.94; im=im.resize((int(im.width*r),int(im.height*r)),Image.LANCZOS)
    scr.paste(im,((sw-im.width)//2,(sh-im.height)//2)); body.paste(scr,(sx,sy))
    d.ellipse([fw/2-5,15,fw/2+5,25],fill=(80,84,96,255)); return body
def paste_logo(img,y,scale=0.13,alpha=0.9):
    lg=Image.open(LOGO).convert("RGBA"); lw=int(img.width*scale); lh=int(lg.height*lw/lg.width); lg=lg.resize((lw,lh),Image.LANCZOS)
    if alpha<1:
        r,g,b,a=lg.split(); a=a.point(lambda p:int(p*alpha)); lg=Image.merge("RGBA",(r,g,b,a))
    img.paste(lg,((img.width-lw)//2,y),lg)
def drawcheck(d,cx,cy,s,col): d.line([(cx-s*0.34,cy+s*0.02),(cx-s*0.06,cy+s*0.28),(cx+s*0.36,cy-s*0.32)],fill=col,width=8,joint="curve")

S=2000
def p1():
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv)
    for x in range(0,S,46):
        for y in range(0,S,46): d.ellipse([x-1,y-1,x+1,y+1],fill=(26,32,58))
    ctext(d,S/2,90,"Coloring Book for iPad",fnt(CINZEL,76),WHITE)
    ctext(d,S/2,196,"Fractal Flora  ·  50 Line-Art Designs",fnt(RALEWAY_IT,40),GOLD)
    pad=ipad(colored_full(DESIGN_HERO,WARM)); r=900/pad.width; pad=pad.resize((int(pad.width*r),int(pad.height*r)),Image.LANCZOS)
    cv.paste(pad,((S-pad.width)//2,300),pad)
    d=ImageDraw.Draw(cv); ctext(d,S/2,300+pad.height+34,"GoodNotes  ·  Notability  ·  Procreate",fnt(RALEWAY,34),TEAL)
    paste_logo(cv,S-150); cv.save(PREV+"/ipad_preview_1_hero.jpg","JPEG",quality=92)
def p2():
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv); d.rectangle([0,0,S,8],fill=GOLD)
    ctext(d,S/2,110,"Everything Included",fnt(CINZEL,80),WHITE)
    ctext(d,S/2,220,"Fractal Flora  ·  iPad Edition",fnt(RALEWAY_IT,38),GOLD)
    items=["50 unique fractal & botanical line-art designs","Hyperlinked PDF index for GoodNotes & Notability",
           "50 transparent PNGs (300 dpi) for Procreate","Procreate color palette  ·  30 garden swatches",
           "'How to use on iPad' quick guide","Instant download  ·  personal use"]
    y=400
    for desc in items:
        d.rounded_rectangle([160,y,250,y+84],radius=18,fill=(30,38,64)); drawcheck(d,205,y+42,40,GOLD)
        d.text((300,y+20),desc,font=fnt(RALEWAY,38),fill=WHITE); y+=135
    paste_logo(cv,S-150); cv.save(PREV+"/ipad_preview_2_included.jpg","JPEG",quality=92)
def p3():
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv)
    ctext(d,S/2,90,"Two Ways to Color",fnt(CINZEL,78),WHITE)
    ctext(d,S/2,196,"however you love to work on your iPad",fnt(RALEWAY_IT,38),GOLD)
    def panel(cx,img,label,sub):
        r=min(620/img.width,820/img.height); im=img.resize((int(img.width*r),int(img.height*r)),Image.LANCZOS)
        card=Image.new("RGB",(im.width+60,im.height+60),(250,250,248)); card.paste(im,(30,30))
        cv.paste(card,(cx-card.width//2,330)); dd=ImageDraw.Draw(cv)
        ctext(dd,cx,330+card.height+30,label,fnt(CINZEL,42),TEAL); ctext(dd,cx,330+card.height+88,sub,fnt(RALEWAY,30),DIM)
    panel(S//4+40,line_img(DESIGN_TWO),"GoodNotes","color on top with Apple Pencil")
    panel(S//2+S//4-40,colored_full(DESIGN_TWO,COOL),"Procreate","color beneath the line art")
    paste_logo(cv,S-150); cv.save(PREV+"/ipad_preview_3_twoways.jpg","JPEG",quality=92)

V=1080; FPS=30
IPW,IPH=560,748; IPX=(V-IPW)//2; IPY=150; BZ=16; SX,SY=IPX+BZ,IPY+BZ; SW,SH=IPW-2*BZ,IPH-2*BZ
def vbase():
    cv=Image.new("RGB",(V,V),NAVY); d=ImageDraw.Draw(cv)
    for x in range(0,V,46):
        for y in range(0,V,46): d.ellipse([x-1,y-1,x+1,y+1],fill=(26,32,58))
    ctext(d,V/2,46,"Coloring Book for iPad",fnt(CINZEL,52),WHITE)
    ctext(d,V/2,118,"Fractal Flora  ·  GoodNotes & Procreate",fnt(RALEWAY_IT,27),GOLD)
    d.rounded_rectangle([IPX,IPY,IPX+IPW,IPY+IPH],radius=44,fill=(25,27,34))
    d.ellipse([V/2-5,IPY+7,V/2+5,IPY+17],fill=(52,55,63)); d.rectangle([SX,SY,SX+SW,SY+SH],fill=(255,255,255))
    ctext(d,V/2,IPY+IPH+34,"GoodNotes  ·  Notability  ·  Procreate",fnt(RALEWAY,26),TEAL)
    lg=Image.open(LOGO).convert("RGBA"); lw=120; lh=int(lg.height*lw/lg.width); lg=lg.resize((lw,lh),Image.LANCZOS)
    cv=cv.convert("RGBA"); cv.alpha_composite(lg,((V-lw)//2,V-lh-26)); return cv.convert("RGB")
def screen_from(arr):
    im=Image.fromarray(np.clip(arr,0,255).astype(np.uint8),"RGB")
    r=min(SW/im.width,SH/im.height)*0.95; im=im.resize((int(im.width*r),int(im.height*r)),Image.LANCZOS)
    sc=Image.new("RGB",(SW,SH),(255,255,255)); sc.paste(im,((SW-im.width)//2,(SH-im.height)//2)); return sc

def video():
    base=vbase(); tmp=tempfile.mkdtemp(prefix="ffcell_"); fi=[0]
    def save(cv): cv.save(os.path.join(tmp,f"f_{fi[0]:05d}.png")); fi[0]+=1
    def fw(arr): cv=base.copy(); cv.paste(screen_from(arr),(SX,SY)); return cv
    HOLD=int(0.6*FPS); FILL=int(4.6*FPS); HOLD2=int(1.3*FPS); CROSS=int(0.5*FPS); FADE=int(0.7*FPS)
    designs=[(VID1,WARM),(VID2,COOL)]; last=None
    for di,(idx,pal) in enumerate(designs):
        arr,cells=prep_cells(idx,pal); cur=arr.copy(); n=len(cells)
        if di==0:
            for _ in range(HOLD): save(fw(cur))
        per=max(1, math.ceil(n/FILL)); i=0
        while i<n:
            for (m,col) in cells[i:i+per]:
                for j in range(3): cur[:,:,j][m]=col[j]
            save(fw(cur)); i+=per
        done=fw(cur)
        for _ in range(HOLD2): save(done)
        if di==0:
            nxt=design_crop(render_rgb(designs[1][0])).astype(np.float32); nb=fw(nxt)
            for f in range(CROSS): save(Image.blend(done,nb,(f+1)/CROSS))
        last=done
    navy=Image.new("RGB",(V,V),NAVY)
    for f in range(FADE): save(Image.blend(last,navy,((f+1)/FADE)*0.6))
    dur=fi[0]/FPS; print(f"  video {fi[0]} frames ({dur:.1f}s)")
    aud="/tmp/ffc_aud.aac"; fo=max(0.5,dur-1.3)
    subprocess.run(f'ffmpeg -y -i {AUDIO} -map 0:a:0 -t {dur:.2f} -af "afade=t=in:st=0:d=0.8,afade=t=out:st={fo:.2f}:d=1.3" -ac 2 -c:a aac -b:a 160k {aud}',shell=True,capture_output=True)
    ha=os.path.exists(aud) and os.path.getsize(aud)>1000
    out=DST+"/FractalFlora_iPad_promo.mp4"
    cmd=f'ffmpeg -y -framerate {FPS} -i {tmp}/f_%05d.png'+(f' -i {aud}' if ha else '')+' -c:v libx264 -pix_fmt yuv420p -crf 18 -preset slow -movflags +faststart'+(' -c:a aac -shortest' if ha else '')+f' {out}'
    subprocess.run(cmd,shell=True,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    shutil.rmtree(tmp,ignore_errors=True); print(f"  video done ({os.path.getsize(out)/1024/1024:.1f} MB, audio={ha})")

print("Previews..."); p1(); p2(); p3()
print("Video..."); video()
print("Done.")
