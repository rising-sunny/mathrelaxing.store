"""
iPad Edition bundle for Fractal Flora (free-color line art, not color-by-number).
PDF (hyperlinked index) + 50 transparent PNGs + Procreate .swatches + guide + zips.
"""
import fitz, os, json, zipfile, math, colorsys, glob
import numpy as np
from PIL import Image

SRC      = "/var/www/mathrelaxing.store/static/downloads/fractal-flora-coloring-book/interior.pdf"
OUT      = "/var/www/mathrelaxing.store/static/downloads/digital/ipad_ff"
PNG_DIR  = OUT + "/Procreate_PNG"
FONT_DIR = "/var/www/mathrelaxing.store/static/fonts"
CINZEL   = FONT_DIR + "/Cinzel.ttf"; RALEWAY = FONT_DIR + "/Raleway.ttf"; RALEWAY_IT = FONT_DIR + "/Raleway-Italic.ttf"
LOGO     = "/var/www/mathrelaxing.store/static/img/logo.png"
NAME     = "FractalFlora"
DESIGN_FROM, DESIGN_TO = 3, 52
os.makedirs(OUT, exist_ok=True); os.makedirs(PNG_DIR, exist_ok=True)
GOLD=(0.85,0.68,0.32); WHITE=(1,1,1); DIM=(0.5,0.57,0.7); BG=(0.07,0.09,0.18); TEAL=(0.49,0.81,0.7)

def build_pdf():
    src=fitz.open(SRC); nd=DESIGN_TO-DESIGN_FROM+1
    pw,ph=src[DESIGN_FROM].rect.width, src[DESIGN_FROM].rect.height
    COLS,ROWS=4,5; per=COLS*ROWS; nidx=math.ceil(nd/per)
    final=fitz.open()
    for _ in range(nidx):
        pg=final.new_page(width=pw,height=ph); pg.draw_rect(pg.rect,color=None,fill=BG)
    final.insert_pdf(src,from_page=DESIGN_FROM,to_page=DESIGN_TO)
    mx,mtop,gap=40,90,14
    cw=(pw-2*mx-(COLS-1)*gap)/COLS; ch=(ph-mtop-40-(ROWS-1)*gap)/ROWS
    import tempfile; td=tempfile.mkdtemp()
    for i in range(nd):
        idxp=i//per; slot=i%per; r,c=slot//COLS,slot%COLS; pg=final[idxp]
        if slot==0:
            pg.insert_textbox(fitz.Rect(40,36,pw-40,70),"Tap a design to jump to it",fontfile=CINZEL,fontsize=17,color=WHITE,align=1)
        x0=mx+c*(cw+gap); y0=mtop+r*(ch+gap); rect=fitz.Rect(x0,y0,x0+cw,y0+ch-14)
        pix=src[DESIGN_FROM+i].get_pixmap(matrix=fitz.Matrix(0.5,0.5),colorspace=fitz.csRGB); tp=os.path.join(td,f"t{i}.png"); pix.save(tp)
        pg.draw_rect(rect,color=(0.2,0.26,0.42),fill=(1,1,1),width=0.5)
        pg.insert_image(rect,filename=tp,keep_proportion=True)
        pg.insert_textbox(fitz.Rect(x0,y0+ch-15,x0+cw,y0+ch+1),str(i+1),fontfile=RALEWAY,fontsize=8,color=GOLD,align=1)
        pg.insert_link({"kind":fitz.LINK_GOTO,"from":rect,"page":nidx+i,"to":fitz.Point(0,0)})
    out=OUT+f"/{NAME}_iPad_GoodNotes.pdf"; final.save(out,deflate=True,garbage=4); src.close(); final.close()
    print(f"  PDF: {os.path.basename(out)} ({os.path.getsize(out)/1024/1024:.1f} MB, {nidx} index + {nd} designs)")

def build_pngs(dpi=300):
    src=fitz.open(SRC); n=0
    for idx in range(DESIGN_FROM,DESIGN_TO+1):
        n+=1
        pix=src[idx].get_pixmap(matrix=fitz.Matrix(dpi/72,dpi/72),colorspace=fitz.csRGB,alpha=False)
        arr=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3).astype(np.uint8)
        gray=arr.mean(2); alpha=(np.clip((210-gray)/90.0,0,1)*255).astype(np.uint8)
        Image.fromarray(np.dstack([arr,alpha]),"RGBA").save(f"{PNG_DIR}/{NAME}_{n:02d}.png",optimize=True)
    src.close(); print(f"  PNGs: {n} transparent designs @ {dpi}dpi")

def build_swatches():
    colors=[  # garden / floral palette
        (244,180,196),(233,118,150),(198,62,108),(255,206,158),(245,150,92),
        (214,86,60),(255,236,168),(240,210,110),(196,224,140),(140,200,120),
        (74,160,96),(36,110,84),(168,224,212),(96,190,196),(120,150,220),
        (170,150,228),(120,92,180),(232,200,238),(210,150,210),(150,80,150),
        (250,240,225),(208,196,176),(120,104,92),(60,72,90),(255,170,120),
        (190,228,170),(96,170,150),(228,120,160),(176,140,200),(86,120,70),
    ]
    sw=[]
    for (r,g,b) in colors:
        h,s,v=colorsys.rgb_to_hsv(r/255,g/255,b/255)
        sw.append({"hue":round(h,4),"saturation":round(s,4),"brightness":round(v,4),"alpha":1,"colorSpace":0})
    data=[{"name":"MathRelaxing — Fractal Flora","swatches":sw}]
    out=OUT+f"/{NAME}.swatches"
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z: z.writestr("Swatches.json",json.dumps(data))
    print(f"  Swatches: {len(colors)} colors")

def build_guide():
    from PIL import ImageDraw, ImageFont
    doc=fitz.open(); pw,ph=612,792; pg=doc.new_page(width=pw,height=ph); pg.draw_rect(pg.rect,color=None,fill=BG)
    lw=120; lh=int(120*575/800); pg.insert_image(fitz.Rect(pw/2-lw/2,56,pw/2+lw/2,56+lh),filename=LOGO,keep_proportion=True)
    def line(y,t,f,s,col,pad=55): pg.insert_textbox(fitz.Rect(pad,y,pw-pad,y+s*2.0),t,fontfile=f,fontsize=s,color=col,align=1,lineheight=1.0)
    def para(y,t,s=10.5,col=(0.8,0.85,0.93),pad=70): pg.insert_textbox(fitz.Rect(pad,y,pw-pad,y+200),t,fontfile=RALEWAY,fontsize=s,color=col,align=0,lineheight=1.35)
    def head(y,t): pg.insert_textbox(fitz.Rect(72,y,pw-72,y+22),t,fontfile=CINZEL,fontsize=12.5,color=TEAL)
    line(148,"Coloring on Your iPad",CINZEL,21,WHITE)
    line(181,"Fractal Flora  \xb7  iPad Edition",RALEWAY_IT,11,GOLD)
    line(204,"No printer, no mess \xb7 just you, your Apple Pencil, and fifty fractal gardens.",RALEWAY_IT,9.5,(0.62,0.68,0.8))
    sh=pg.new_shape(); sh.draw_line((72,234),(pw-72,234)); sh.finish(color=GOLD,width=0.8); sh.commit()
    head(258,"In GoodNotes or Notability")
    para(284,"Open the PDF and begin on the index page. Tap any design to glide straight to it, then color right on the artwork with whichever brush you love. Layer washes, blends and gradients freely.")
    head(372,"In Procreate")
    para(398,"Drop a transparent PNG onto a fresh canvas. The linework rests on its own layer, so paint on a layer beneath it and every stroke stays effortlessly within the lines. Import the included palette for a ready-made garden of colors.")
    head(486,"A gentle note")
    para(512,"These are open, free-form designs \xb7 no numbers, no rules. Follow the palette or invent your own. Zoom in for the finest curves, and let each fractal bloom however you feel. There is no rush here \xb7 unwinding is the whole point.")
    line(712,"mathrelaxing.store",CINZEL,12,GOLD)
    line(737,"\xa9 MathRelaxing \xb7 For personal use only",RALEWAY,7.5,DIM)
    out=OUT+"/How_to_use_on_iPad.pdf"; doc.save(out); doc.close(); print(f"  Guide saved")

def build_packages():
    pngs=sorted(glob.glob(PNG_DIR+"/*.png")); LIMIT=19*1024*1024
    groups=[[]]; sizes=[0]
    for p in pngs:
        sz=os.path.getsize(p)
        if sizes[-1]+sz>LIMIT and groups[-1]: groups.append([]); sizes.append(0)
        groups[-1].append(p); sizes[-1]+=sz
    for i,g in enumerate(groups,1):
        suf="" if len(groups)==1 else f"_part{i}"
        zp=f"{OUT}/{NAME}_Procreate_PNG{suf}.zip"
        with zipfile.ZipFile(zp,"w",zipfile.ZIP_DEFLATED) as z:
            for p in g: z.write(p,"Procreate_PNG/"+os.path.basename(p))
        print(f"  ZIP: {os.path.basename(zp)} ({len(g)} PNGs, {os.path.getsize(zp)/1024/1024:.1f} MB)")

print("Building Fractal Flora iPad bundle...")
build_pdf(); build_pngs(); build_swatches(); build_guide()
print("Packaging..."); build_packages(); print("Done.")
