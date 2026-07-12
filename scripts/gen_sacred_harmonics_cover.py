import sys
import os
import math
sys.path.insert(0, "/var/www/mathrelaxing.store")
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

# Aesthetic matching the collection (Deep blue/purple for harmonics)
BG="#151226"; GOLD="#E2C792"; CREAM="#EDE6D6"; BAND="#000000"
LOGO_PATH="/var/www/mathrelaxing.store/static/img/logo.png"
_LOGO=mpimg.imread(LOGO_PATH)

def place_logo(fig, rect):
    ax=fig.add_axes(rect); ax.axis("off"); ax.imshow(_LOGO, aspect="equal")

def draw_entramado(bg_ax, width, height):
    # Hexagonal / triangular grid
    spacing = 0.4
    for i in range(-20, int(width * 3) + 20):
        x = i * spacing
        bg_ax.plot([x/width, (x + height)/width], [0, math.sqrt(3)], color=GOLD, alpha=0.08, lw=1.0)
        bg_ax.plot([x/width, (x - height)/width], [0, math.sqrt(3)], color=GOLD, alpha=0.08, lw=1.0)
    for j in range(-20, int(height * 3) + 20):
        y = j * spacing * math.sqrt(3) / 2
        bg_ax.plot([0, 1], [y/height, y/height], color=GOLD, alpha=0.08, lw=1.0)
    bg_ax.set_xlim(0, 1)
    bg_ax.set_ylim(0, 1)

def draw_chladni(ax):
    # Generate a beautiful Chladni figure (n=4, m=5 or similar)
    n, m = 5, 2
    L = 1.0
    x = np.linspace(-L, L, 500)
    y = np.linspace(-L, L, 500)
    X, Y = np.meshgrid(x, y)
    
    Z = np.sin(n*np.pi*X/L) * np.sin(m*np.pi*Y/L) - np.sin(m*np.pi*X/L) * np.sin(n*np.pi*Y/L)
    
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_xlim(-L, L)
    ax.set_ylim(-L, L)
    
    # Draw contour lines to look like cymatics/sand patterns
    ax.contour(X, Y, Z, levels=[-0.6, -0.3, 0, 0.3, 0.6], colors=['#FFFA70', '#E55807', '#E2C792', '#E55807', '#FFFA70'], linewidths=[0.8, 1.5, 2.5, 1.5, 0.8], alpha=0.85)

def build_web_cover():
    fig=plt.figure(figsize=(10,12.5))
    bg=fig.add_axes([0,0,1,1]); bg.axis("off"); bg.add_patch(plt.Rectangle((0,0),1,1,color=BG))
    draw_entramado(bg, 10, 12.5)
    
    axm=fig.add_axes([0.15,0.32,0.70,0.50])
    draw_chladni(axm)
    
    fig.text(0.5,0.89,"SACRED HARMONICS",ha="center",fontsize=38,family="serif",color=CREAM,weight="light")
    fig.text(0.5,0.26,"A Coloring Book of Waves",ha="center",fontsize=16,family="serif",style="italic",color=CREAM)
    fig.text(0.5,0.19,"50 Cymatics & Wave Geometry Designs",ha="center",fontsize=11,family="serif",color=GOLD)
    
    band_h=0.135
    bg.add_patch(plt.Rectangle((0,0),1,band_h,color=BAND,zorder=5))
    place_logo(fig,[0.385,0.02,0.23,band_h*0.74])
    
    # Overwrite the bad preview image in the server
    out="/var/www/mathrelaxing.store/static/previews/sacred-harmonics-digital.jpg"
    out_clean="/var/www/mathrelaxing.store/static/previews/sacred-harmonics-digital_clean.jpg"
    fig.savefig(out,facecolor=BG,dpi=100)
    fig.savefig(out_clean,facecolor=BG,dpi=100)
    plt.close(fig)
    print("Cover generated at:", out)

if __name__=="__main__":
    build_web_cover()
