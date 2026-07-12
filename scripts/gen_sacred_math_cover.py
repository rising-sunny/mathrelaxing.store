import sys
import os
import math
sys.path.insert(0, "/var/www/mathrelaxing.store")
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import matplotlib.image as mpimg
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.colors as mcolors
from scripts.math_meshes import get_mesh

# Aesthetic matching the collection
BG="#1A1638"; GOLD="#C8A96E"; CREAM="#EDE6D6"; FAINT="#191536"; BAND="#000000"
LOGO_PATH="/var/www/mathrelaxing.store/static/img/logo.png"
_LOGO=mpimg.imread(LOGO_PATH)

def generate_palette(colors):
    cmap = mcolors.LinearSegmentedColormap.from_list("custom", colors, N=8)
    return {i+1: mcolors.to_hex(cmap(i/7.0)) for i in range(8)}

PALETTE = generate_palette(['#FFFA70', '#E55807', '#5C0029'])

def place_logo(fig, rect):
    ax=fig.add_axes(rect); ax.axis("off"); ax.imshow(_LOGO, aspect="equal")

def draw_entramado(bg_ax, width, height):
    spacing = 0.4
    
    # Draw a network of triangles to form a beautiful sacred geometry grid
    for i in range(-20, int(width * 3) + 20):
        x = i * spacing
        bg_ax.plot([x/width, (x + height)/width], [0, math.sqrt(3)], color=GOLD, alpha=0.08, lw=1.0)
        bg_ax.plot([x/width, (x - height)/width], [0, math.sqrt(3)], color=GOLD, alpha=0.08, lw=1.0)
        
    for j in range(-20, int(height * 3) + 20):
        y = j * spacing * math.sqrt(3) / 2
        bg_ax.plot([0, 1], [y/height, y/height], color=GOLD, alpha=0.08, lw=1.0)
        
    bg_ax.set_xlim(0, 1)
    bg_ax.set_ylim(0, 1)

def lookat(eye, target, up):
    zaxis = target - eye
    n = np.linalg.norm(zaxis)
    if n == 0: zaxis = np.array([0,0,1])
    else: zaxis = zaxis / n
    xaxis = np.cross(up, zaxis)
    n = np.linalg.norm(xaxis)
    if n == 0: xaxis = np.array([1,0,0])
    else: xaxis = xaxis / n
    yaxis = np.cross(zaxis, xaxis)
    view = np.eye(4)
    view[0, 0:3] = xaxis
    view[1, 0:3] = yaxis
    view[2, 0:3] = zaxis
    view[0:3, 3] = -np.array([np.dot(xaxis, eye), np.dot(yaxis, eye), np.dot(zaxis, eye)])
    return view

def perspective(fov, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fov) / 2)
    proj = np.zeros((4, 4))
    proj[0, 0] = f / aspect
    proj[1, 1] = f
    proj[2, 2] = (far + near) / (near - far)
    proj[2, 3] = (2 * far * near) / (near - far)
    proj[3, 2] = -1.0
    return proj

def draw_spec_mesh(ax, idx, is_back=False):
    verts, faces, title = get_mesh(idx)
    verts = verts - np.mean(verts, axis=0)
    verts = verts / (np.max(np.linalg.norm(verts, axis=1)) + 0.001)

    eye = np.array([1.8, 1.2, 2.5]) if not is_back else np.array([1.0, 1.5, 3.0])
    target = np.array([0, 0, 0])
    up = np.array([0, 1, 0])
    
    view = lookat(eye, target, up)
    proj = perspective(35, 1.0, 0.1, 100.0)
    
    verts_hom = np.hstack((verts, np.ones((len(verts), 1))))
    verts_view = (view @ verts_hom.T).T
    verts_proj = (proj @ verts_view.T).T
    w = verts_proj[:, 3].reshape(-1, 1)
    w[w == 0] = 0.0001
    verts_2d = verts_proj[:, 0:2] / w
    
    light_dir = np.array([1, 2, 1])
    light_dir = light_dir / np.linalg.norm(light_dir)
    
    face_data = []
    for i, f in enumerate(faces):
        v0, v1, v2 = verts[f[0]], verts[f[1]], verts[f[2]]
        normal = np.cross(v1 - v0, v2 - v0)
        n_len = np.linalg.norm(normal)
        if n_len == 0: continue
        normal = normal / n_len
        view_dir = ((v0 + v1 + v2) / 3) - eye
        if np.dot(normal, view_dir) > 0: continue
            
        intensity = max(0.0, np.dot(normal, light_dir))
        z_depth = (verts_view[f[0], 2] + verts_view[f[1], 2] + verts_view[f[2], 2]) / 3
        face_data.append({'pts_2d': verts_2d[f], 'intensity': intensity, 'z': z_depth})
        
    face_data.sort(key=lambda x: x['z'])
    if len(face_data) > 0:
        intensities = np.array([fd['intensity'] for fd in face_data])
        min_i, max_i = intensities.min(), intensities.max()
        for fd in face_data:
            normalized_i = (fd['intensity'] - min_i) / (max_i - min_i + 0.001)
            normalized_i = math.pow(normalized_i, 0.7)
            color_idx = min(7, int(normalized_i * 8)) + 1
            fd['color_idx'] = color_idx
            
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_xlim(-0.85, 0.85)
    ax.set_ylim(-0.85, 0.85)
    
    for fd in face_data:
        color = PALETTE[fd['color_idx']]
        if is_back:
            # Monochrome for back cover
            c_val = sum(mcolors.to_rgb(color)) / 3
            color = mcolors.to_hex((c_val * 0.3, c_val * 0.2, c_val * 0.4))
            
        poly = Polygon(fd['pts_2d'], closed=True, facecolor=color, edgecolor='white', linewidth=1.5 if not is_back else 0.5)
        ax.add_patch(poly)

def build_cover():
    W,H=1255/72.0, 810/72.0
    fig=plt.figure(figsize=(W,H))
    bg=fig.add_axes([0,0,1,1]); bg.axis("off"); bg.add_patch(plt.Rectangle((0,0),1,1,color=BG))
    draw_entramado(bg, W, H)
    
    # fractions
    fb=9/1255.0; front_l=634/1255.0; front_r=1246/1255.0; spine_l=621/1255.0; spine_r=634/1255.0
    
    # FRONT motif (Mesh 15 - Möbius Band)
    axm=fig.add_axes([front_l+0.055, 0.35, (front_r-front_l)-0.11, 0.45])
    draw_spec_mesh(axm, 15)
    
    fig.text((front_l+front_r)/2, 0.86, "SACRED GEOMETRY", ha="center", va="center", fontsize=34, family="serif", color=CREAM, weight="light")
    fig.text((front_l+front_r)/2, 0.805, "& TOPOLOGY", ha="center", va="center", fontsize=34, family="serif", color=GOLD, weight="light")
    fig.text((front_l+front_r)/2, 0.28, "A 3D Color-by-Numbers Journey", ha="center", fontsize=14, family="serif", style="italic", color=CREAM)
    fig.text((front_l+front_r)/2, 0.225, "50 Geometric 3D Models", ha="center", fontsize=11, family="serif", color=GOLD)
    
    # FRONT — black band + MathRelaxing logo
    band_h=0.155
    bg.add_patch(plt.Rectangle((front_l,0),1-front_l,band_h,color=BAND,zorder=5))
    fc=(front_l+front_r)/2
    place_logo(fig,[fc-0.085,0.018,0.17,band_h*0.74])
    
    # SPINE
    fig.text((spine_l+spine_r)/2, 0.5, "SACRED GEOMETRY & TOPOLOGY   ·   MATHRELAXING", rotation=90, ha="center", va="center", fontsize=8.5, family="serif", color=CREAM)
    
    # BACK (Mesh 5 - Torus)
    back_c=(fb+spine_l)/2
    axb=fig.add_axes([0.06, 0.46, 0.22, 0.30])
    draw_spec_mesh(axb, 5, is_back=True)
    
    blurb=("Immerse yourself in the world of mathematics. Every page in this book\n"
           "was generated using complex formulas and 3D modeling, bringing abstract\n"
           "concepts to life.\n\n"
           "50 unique algorithmic structures, from Möbius Bands to Platonic Solids,\n"
           "rendered in a satisfying low-poly aesthetic. The mathematical engine \n"
           "pre-fills the smallest polygons automatically, ensuring a perfect \n"
           "colouring experience every time.\n\n"
           "Perfect-bound · 8.5 x 11 in · matte cover · printed on demand.")
    fig.text(0.06, 0.40, blurb, ha="left", va="top", fontsize=9.5, family="serif", color=CREAM, linespacing=1.5)
    fig.text(back_c, 0.07, "mathrelaxing.store", ha="center", fontsize=9, family="serif", color=GOLD)
    
    out_dir = "/var/www/mathrelaxing.store/static/downloads/sacred-math-coloring-book"
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "cover.pdf")
    with PdfPages(out) as pdf: pdf.savefig(fig)
    plt.close(fig); print("cover ->", out)

def build_web_cover():
    fig=plt.figure(figsize=(10,12.5))
    bg=fig.add_axes([0,0,1,1]); bg.axis("off"); bg.add_patch(plt.Rectangle((0,0),1,1,color=BG))
    draw_entramado(bg, 10, 12.5)
    
    axm=fig.add_axes([0.13,0.30,0.74,0.50])
    draw_spec_mesh(axm, 15)
    
    fig.text(0.5,0.88,"SACRED GEOMETRY",ha="center",fontsize=40,family="serif",color=CREAM,weight="light")
    fig.text(0.5,0.825,"& TOPOLOGY",ha="center",fontsize=40,family="serif",color=GOLD,weight="light")
    fig.text(0.5,0.25,"A 3D Color-by-Numbers Journey",ha="center",fontsize=15,family="serif",style="italic",color=CREAM)
    fig.text(0.5,0.18,"50 Geometric 3D Models",ha="center",fontsize=11,family="serif",color=GOLD)
    
    band_h=0.135
    bg.add_patch(plt.Rectangle((0,0),1,band_h,color=BAND,zorder=5))
    place_logo(fig,[0.385,0.02,0.23,band_h*0.74])
    
    out="/var/www/mathrelaxing.store/static/img/sacred_math_cover.png"
    fig.savefig(out,facecolor=BG,dpi=100); plt.close(fig); print("web cover ->", out)

if __name__=="__main__":
    build_cover(); build_web_cover()
