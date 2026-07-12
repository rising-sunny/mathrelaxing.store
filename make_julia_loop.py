"""
make_julia_loop.py — Julia set seamless morph loop (MathRelaxing).
c recorre el círculo c = R·e^(iθ), θ:0→2π  → el fractal muta y vuelve EXACTO
al inicio (loop perfecto). Paleta navy→teal→gold→cream cíclica (marca).

  python3 make_julia_loop.py sample   # 820², 150 frames, rápido -> /tmp/julia_sample
  python3 make_julia_loop.py full      # 1080², 60fps, 16s
"""
import sys, os, math, tempfile, shutil, subprocess
sys.path.insert(0,"/var/www/mathrelaxing.store")
import numpy as np
from PIL import Image

OUT="/var/www/mathrelaxing.store/static/downloads/digital/julia"
os.makedirs(OUT,exist_ok=True)

SPAN   = 2.6             # ventana del plano (zoom suave para llenar mejor el cuadro)
BAIL   = 200.0
NB     = 5.0             # nº de bandas de color (glow fractal)
K_IN   = 0.985           # factor "justo por dentro" del cardioide (Julias conectados todo el loop)

NAVY=(16,20,42); INT=(26,33,62); TEAL=(70,212,200); GOLD=(240,196,100); CREAM=(248,244,230)

def c_of(theta):
    """c sobre el borde del cardioide principal (×K_IN, justo por dentro).
    c(θ)=e^{iθ}/2 - e^{2iθ}/4. Loop cerrado θ:0→2π → seamless, y Julias
    intrincados y CONECTADOS en todo el recorrido (sin fase 'polvo')."""
    e =complex(math.cos(theta),   math.sin(theta))
    e2=complex(math.cos(2*theta), math.sin(2*theta))
    return K_IN*(0.5*e - 0.25*e2)

def build_lut(n=512):
    stops=[NAVY,TEAL,GOLD,CREAM,NAVY]   # cíclico (vuelve a navy)
    seg=np.linspace(0,len(stops)-1,n)
    lut=np.zeros((n,3))
    for i,s in enumerate(seg):
        k=int(s); f=s-k; a=stops[k]; b=stops[min(k+1,len(stops)-1)]
        lut[i]=[a[j]+(b[j]-a[j])*f for j in range(3)]
    return lut.astype(np.uint8)
LUT=build_lut(512)

def render_julia(c, W, H, maxiter):
    x=np.linspace(-SPAN/2, SPAN/2, W)
    y=np.linspace(-SPAN/2, SPAN/2, H)
    Z=(x[None,:]+1j*y[:,None]).astype(np.complex128)
    div=np.zeros((H,W),np.float64)
    alive=np.ones((H,W),bool)
    for i in range(maxiter):
        Z[alive]=Z[alive]*Z[alive]+c
        mag=np.abs(Z)
        esc=alive & (mag>BAIL)
        # coloreado suave (continuous escape)
        div[esc]= i + 1 - np.log(np.log(mag[esc]))/math.log(2)
        alive[esc]=False
    # mapear a color
    t=(div*NB/maxiter) % 1.0
    idx=(t*(len(LUT)-1)).astype(np.int32)
    img=LUT[idx]
    img[alive]=INT                       # cuerpo del conjunto (navy ligeramente más claro)
    return Image.fromarray(img,"RGB")

def encode(tmp, out, fps):
    cmd=(f'ffmpeg -y -framerate {fps} -i "{tmp}/f_%05d.png" '
         f'-c:v libx264 -pix_fmt yuv420p -crf 18 -preset slow -movflags +faststart "{out}"')
    subprocess.run(cmd,shell=True,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print(f"  {os.path.basename(out)} ({os.path.getsize(out)/1024/1024:.1f} MB)")

def build(W,H,N,maxiter,fps,out_name,stills=None,prev_dir="/tmp/julia_sample"):
    tmp=tempfile.mkdtemp(prefix="julia_")
    os.makedirs(prev_dir,exist_ok=True)
    stills=set(stills or [])
    for f in range(N):
        im=render_julia(c_of(2*math.pi*f/N),W,H,maxiter)
        im.save(os.path.join(tmp,f"f_{f:05d}.png"))
        if f in stills: im.save(f"{prev_dir}/julia_{f:05d}.png")
        if f%60==0: print(f"  frame {f}/{N}", flush=True)
    out=f"{OUT}/{out_name}.mp4"
    encode(tmp,out,fps); shutil.rmtree(tmp,ignore_errors=True)
    return out

if __name__=="__main__":
    cmd=sys.argv[1] if len(sys.argv)>1 else "sample"
    if cmd=="sample":
        N=150; print("Julia sample..."); build(820,820,N,120,30,"Julia_sample",stills=[0,N//4,N//2,3*N//4])
    elif cmd=="full":
        N=720; print("Julia full (1080, 60fps, 12s)...")
        build(1080,1080,N,200,60,"JuliaMorph_01",
              stills=[N//8,N//4,3*N//8,N//2,5*N//8,3*N//4], prev_dir="/tmp/julia_full")
    print("Done.")
