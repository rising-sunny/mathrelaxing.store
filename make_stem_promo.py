"""
make_stem_promo.py — Video promo STEM Notebook (1080x1080, 30fps).
iPad landscape: se "toca" una pestaña y salta a ese grid (tap-to-jump).
"""
import sys, os, math, tempfile, shutil
sys.path.insert(0,"/var/www/mathrelaxing.store")
from mathrelaxing_kit import fnt, ctext, NAVY, GOLD, WHITE, TEAL, CINZEL, RALEWAY, RALEWAY_IT, LOGO, encode_video, FPS, dot_bg
import fitz
from PIL import Image, ImageDraw

PDF="/var/www/mathrelaxing.store/static/downloads/digital/stem_notebook/STEM_Notebook.pdf"
OUT="/var/www/mathrelaxing.store/static/downloads/digital/stem_notebook/STEM_Notebook_promo.mp4"
AUDIO="/var/www/mathrelaxing.store/static/downloads/fractal-flora-coloring-book/promo.mp4"

V=1080
# layout notebook (para mapear pestañas)
PW_,PH_=1280,960; TOP_,BOT_=76,44; X1_=1148; W_=1280
# iPad landscape en el lienzo
IPW,IPH=904,678; IPX=(V-IPW)//2; IPY=212; BZ=16
SX,SY=IPX+BZ,IPY+BZ; SW,SH=IPW-2*BZ,IPH-2*BZ
PSCALE=min(SW/PW_,SH/PH_); POX=SX+(SW-PW_*PSCALE)/2; POY=SY+(SH-PH_*PSCALE)/2

def tab_center(i):
    """centro de la pestaña i en coords del lienzo."""
    av=PH_-TOP_-BOT_; th=av/8
    px=(X1_+22 + W_-8)/2; py=TOP_+i*th+th/2
    return (POX+px*PSCALE, POY+py*PSCALE)

def render(idx, zoom=1.7):
    d=fitz.open(PDF); pix=d[idx].get_pixmap(matrix=fitz.Matrix(zoom,zoom))
    im=Image.frombytes("RGB",[pix.width,pix.height],pix.samples); d.close()
    return im.resize((int(PW_*PSCALE),int(PH_*PSCALE)),Image.LANCZOS)

def base_canvas():
    cv=Image.new("RGB",(V,V),NAVY); d=ImageDraw.Draw(cv); dot_bg(d,V)
    ctext(d,V/2,42,"STEM Digital Notebook",fnt(CINZEL,50),WHITE)
    ctext(d,V/2,108,"tap a tab \xb7 jump anywhere",fnt(RALEWAY_IT,26),GOLD)
    d.rounded_rectangle([IPX,IPY,IPX+IPW,IPY+IPH],radius=40,fill=(25,27,34))
    d.ellipse([IPX+8,V*0.5-5,IPX+18,V*0.5+5],fill=(52,55,63))   # cámara lateral
    d.rectangle([SX,SY,SX+SW,SY+SH],fill=(255,255,255))
    ctext(d,V/2,IPY+IPH+22,"GoodNotes  \xb7  Notability  \xb7  142 pages",fnt(RALEWAY,24),TEAL)
    lg=Image.open(LOGO).convert("RGBA"); lw=120; lh=int(lg.height*lw/lg.width)
    lg=lg.resize((lw,lh),Image.LANCZOS); cv=cv.convert("RGBA"); cv.alpha_composite(lg,((V-lw)//2,V-lh-20))
    return cv.convert("RGB")

def frame(base, screen, tap=None):
    cv=base.copy(); cv.paste(screen,(int(POX),int(POY)))
    if tap:
        (tx,ty),prog=tap   # prog 0..1
        ov=Image.new("RGBA",(V,V),(0,0,0,0)); od=ImageDraw.Draw(ov)
        R=int(14+prog*34); a=int(180*(1-prog))
        od.ellipse([tx-R,ty-R,tx+R,ty+R],outline=(*GOLD,a),width=5)
        od.ellipse([tx-9,ty-9,tx+9,ty+9],fill=(*GOLD,int(150*(1-prog*0.5))))
        cv=Image.alpha_composite(cv.convert("RGBA"),ov).convert("RGB")
    return cv

def main():
    seq=[(0,1),(1,2),(2,22),(3,42),(4,62),(5,82),(6,102),(7,122)]  # (tab, page)
    pages={pg:render(pg) for _,pg in seq}
    base=base_canvas()
    tmp=tempfile.mkdtemp(prefix="stem_"); fi=[0]
    def save(im): im.save(os.path.join(tmp,f"f_{fi[0]:05d}.png")); fi[0]+=1
    HOLD=int(0.95*FPS); HOLD0=int(1.2*FPS); TAP=int(0.5*FPS); CROSS=int(0.28*FPS); FADE=int(0.7*FPS)
    for k,(tab,pg) in enumerate(seq):
        scr=pages[pg]
        if k==0:
            f0=frame(base,scr)
            for _ in range(HOLD0): save(f0)
        else:
            prev=pages[seq[k-1][1]]; tc=tab_center(tab)
            for f in range(TAP):    # pulso de toque sobre la pestaña destino
                save(frame(base,prev,tap=(tc,f/TAP)))
            fa=frame(base,prev); fb=frame(base,scr)
            for f in range(CROSS): save(Image.blend(fa,fb,(f+1)/CROSS))
            done=frame(base,scr)
            for _ in range(HOLD): save(done)
    last=frame(base,pages[seq[-1][1]]); navy=Image.new("RGB",(V,V),NAVY)
    for f in range(FADE): save(Image.blend(last,navy,((f+1)/FADE)*0.6))
    dur=fi[0]/FPS; print(f"  {fi[0]} frames ({dur:.1f}s)")
    encode_video(tmp,OUT,AUDIO,dur); shutil.rmtree(tmp,ignore_errors=True)

if __name__=="__main__":
    print("Video promo STEM..."); main(); print("Done ->",OUT)
