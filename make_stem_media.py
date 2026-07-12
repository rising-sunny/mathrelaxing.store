"""
make_stem_media.py — Previews Etsy para el STEM Notebook (2000x2000).
1 hero (iPad landscape) · 2 grids incluidos · 3 pestañas explicadas · 4 incluido
"""
import sys, os, math
sys.path.insert(0,"/var/www/mathrelaxing.store")
from mathrelaxing_kit import fnt, ctext, paste_logo, drawcheck, dot_bg, NAVY, GOLD, WHITE, TEAL, DIM, CINZEL, RALEWAY, RALEWAY_IT, LOGO
import fitz
from PIL import Image, ImageDraw

PDF="/var/www/mathrelaxing.store/static/downloads/digital/stem_notebook/STEM_Notebook.pdf"
OUT="/var/www/mathrelaxing.store/static/downloads/digital/stem_notebook/previews"
os.makedirs(OUT,exist_ok=True)
S=2000

# geometría de contenido (de make_stem_notebook): área del grid
PW_,PH_=1280,960; X0,Y0,X1,Y1=54,76,1148,916
SECTIONS=[("Dot",2),("Graph",22),("Hexagonal",42),("Isometric",62),("Cornell",82),("Polar",102),("Lined",122)]

def render(idx, zoom=2.0, crop=None):
    d=fitz.open(PDF); p=d[idx]
    pix=p.get_pixmap(matrix=fitz.Matrix(zoom,zoom))
    im=Image.frombytes("RGB",[pix.width,pix.height],pix.samples)
    d.close()
    if crop:
        im=im.crop([int(c*zoom) for c in crop])
    return im

def ipad_land(screen, fw=1480, fh=1110):
    body=Image.new("RGBA",(fw,fh),(0,0,0,0)); d=ImageDraw.Draw(body)
    d.rounded_rectangle([0,0,fw,fh],radius=46,fill=(28,30,38,255))
    bz=26; sx,sy,sw,sh=bz,bz,fw-2*bz,fh-2*bz
    scr=Image.new("RGB",(sw,sh),(255,255,255))
    r=min(sw/screen.width,sh/screen.height); im=screen.resize((int(screen.width*r),int(screen.height*r)),Image.LANCZOS)
    scr.paste(im,((sw-im.width)//2,(sh-im.height)//2)); body.paste(scr,(sx,sy))
    d.ellipse([18,fh/2-5,28,fh/2+5],fill=(80,84,96,255))   # cámara lateral (landscape)
    return body

# ── P1 hero ───────────────────────────────────────────────────────────────────
def p1():
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv); dot_bg(d,S)
    ctext(d,S/2,96,"STEM Digital Notebook",fnt(CINZEL,82),WHITE)
    ctext(d,S/2,210,"Hyperlinked for GoodNotes & Notability",fnt(RALEWAY_IT,40),GOLD)
    pad=ipad_land(render(42, zoom=2.0))   # hex page (distintivo)
    r=1560/pad.width; pad=pad.resize((int(pad.width*r),int(pad.height*r)),Image.LANCZOS)
    cv.paste(pad,((S-pad.width)//2,360),pad)
    d=ImageDraw.Draw(cv)
    ctext(d,S/2,360+pad.height+40,"7 grid types  \xb7  142 pages  \xb7  tap-to-jump tabs",fnt(RALEWAY,38),TEAL)
    paste_logo(cv,S-150); cv.save(f"{OUT}/stem_preview_1_hero.jpg","JPEG",quality=92)
    print("  p1 hero")

# ── P2 grids incluidos ─────────────────────────────────────────────────────────
def p2():
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv); d.rectangle([0,0,S,8],fill=GOLD)
    ctext(d,S/2,90,"7 STEM Grid Types",fnt(CINZEL,80),WHITE)
    ctext(d,S/2,200,"every page you actually need",fnt(RALEWAY_IT,38),GOLD)
    # 4x2 grid de miniaturas (7 + 1 hueco)
    cols,rows=4,2; cw,ch=420,360; gx,gy=40,40
    tot_w=cols*cw+(cols-1)*gx; x0=(S-tot_w)//2; y0=320
    for i,(name,idx) in enumerate(SECTIONS):
        r,c=i//cols,i%cols; x=x0+c*(cw+gx); y=y0+r*(ch+gy+40)
        thumb=render(idx, zoom=1.4, crop=(X0,Y0,X1,Y1))
        rr=min(cw/thumb.width,ch/thumb.height); th=thumb.resize((int(thumb.width*rr),int(thumb.height*rr)),Image.LANCZOS)
        card=Image.new("RGB",(cw,ch),(250,250,248)); card.paste(th,((cw-th.width)//2,(ch-th.height)//2))
        cv.paste(card,(x,y)); dd=ImageDraw.Draw(cv)
        dd.rectangle([x,y,x+cw,y+ch],outline=(60,70,100),width=2)
        ctext(dd,x+cw/2,y+ch+8,name,fnt(RALEWAY,30),WHITE)
    paste_logo(cv,S-140); cv.save(f"{OUT}/stem_preview_2_grids.jpg","JPEG",quality=92)
    print("  p2 grids")

# ── P3 pestañas explicadas ──────────────────────────────────────────────────────
def p3():
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv); dot_bg(d,S)
    ctext(d,S/2,96,"Tap a Tab, Jump Anywhere",fnt(CINZEL,76),WHITE)
    ctext(d,S/2,206,"no scrolling through 142 pages",fnt(RALEWAY_IT,38),GOLD)
    pad=ipad_land(render(42, zoom=2.0)); r=1420/pad.width
    pad=pad.resize((int(pad.width*r),int(pad.height*r)),Image.LANCZOS)
    px,py=(S-pad.width)//2,360; cv.paste(pad,(px,py),pad)
    d=ImageDraw.Draw(cv)
    # callout sobre la franja de pestañas (lado derecho del iPad)
    tabs_x=px+pad.width*0.93
    d.rounded_rectangle([tabs_x-30,py+pad.height*0.10,px+pad.width-18,py+pad.height*0.92],
                        radius=20,outline=GOLD,width=5)
    ctext(d,S/2,py+pad.height+44,"Dot \xb7 Graph \xb7 Hex \xb7 Iso \xb7 Cornell \xb7 Polar \xb7 Lined",fnt(RALEWAY,34),TEAL)
    paste_logo(cv,S-150); cv.save(f"{OUT}/stem_preview_3_tabs.jpg","JPEG",quality=92)
    print("  p3 tabs")

# ── P4 incluido ─────────────────────────────────────────────────────────────────
def p4():
    cv=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(cv); d.rectangle([0,0,S,8],fill=GOLD)
    ctext(d,S/2,110,"Everything Included",fnt(CINZEL,80),WHITE)
    ctext(d,S/2,220,"STEM Digital Notebook",fnt(RALEWAY_IT,38),GOLD)
    items=["142 hyperlinked pages \xb7 tap-to-jump tabs","7 STEM grids: dot, graph, hex, isometric",
           "Cornell notes, polar & ruled pages too","Landscape 4:3 \xb7 made for GoodNotes & Notability",
           "Works in any PDF annotation app","Instant download \xb7 reuse forever"]
    y=420
    for t in items:
        d.rounded_rectangle([170,y,260,y+84],radius=18,fill=(30,38,64)); drawcheck(d,215,y+42,40,GOLD)
        d.text((310,y+20),t,font=fnt(RALEWAY,38),fill=WHITE); y+=135
    paste_logo(cv,S-150); cv.save(f"{OUT}/stem_preview_4_included.jpg","JPEG",quality=92)
    print("  p4 included")

if __name__=="__main__":
    print("Previews STEM..."); p1(); p2(); p3(); p4(); print("Done ->",OUT)
