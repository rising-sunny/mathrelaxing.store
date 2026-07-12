import sys, math, os
sys.path.insert(0, "/var/www/mathrelaxing.store")
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import matplotlib.path as mpath
from matplotlib.backends.backend_pdf import PdfPages
from scripts.math_meshes import get_mesh

import matplotlib.colors as mcolors

def generate_palette(colors):
    cmap = mcolors.LinearSegmentedColormap.from_list("custom", colors, N=8)
    return {i+1: mcolors.to_hex(cmap(i/7.0)) for i in range(8)}

PALETTES = [
    generate_palette(['#FFFA70', '#E55807', '#5C0029']), # Sunset (Yellow -> Orange -> Deep Red/Purple)
    generate_palette(['#E0FBFC', '#3D5A80', '#0B132B']), # Ocean (Light cyan -> Blue -> Navy)
    generate_palette(['#D8F3DC', '#2D6A4F', '#081C15']), # Emerald (Mint -> Green -> Very dark green)
    generate_palette(['#FDE2E4', '#C9184A', '#38040E']), # Ruby (Light pink -> Red -> Very dark red)
    generate_palette(['#E0AAFF', '#7B2CBF', '#10002B']), # Amethyst (Light purple -> Violet -> Very dark purple)
    generate_palette(['#FFFFFF', '#808080', '#000000']), # Monochrome (White -> Gray -> Black)
]

def get_palette(idx):
    return PALETTES[idx % len(PALETTES)]

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

def get_incenter(pts):
    A, B, C = pts[0], pts[1], pts[2]
    a = np.linalg.norm(B - C)
    b = np.linalg.norm(A - C)
    c = np.linalg.norm(A - B)
    P = a + b + c
    if P == 0: return A, 0
    Ix = (a*A[0] + b*B[0] + c*C[0]) / P
    Iy = (a*A[1] + b*B[1] + c*C[1]) / P
    area = 0.5 * abs((B[0]-A[0])*(C[1]-A[1]) - (C[0]-A[0])*(B[1]-A[1]))
    s = P / 2
    r = area / s if s > 0 else 0
    return np.array([Ix, Iy]), r

def render_mesh(idx, aspect=8.5/11.0):
    verts, faces, title = get_mesh(idx)
    # Center and normalize
    verts = verts - np.mean(verts, axis=0)
    max_rad = np.max(np.linalg.norm(verts, axis=1))
    verts = verts / (max_rad + 0.001)

    # Make the camera circle around slightly to give different angles for different models
    angle = idx * 0.5
    cam_dist = 2.8
    eye = np.array([math.cos(angle)*cam_dist, 1.2, math.sin(angle)*cam_dist])
    target = np.array([0, 0, 0])
    up = np.array([0, 1, 0])
    
    view = lookat(eye, target, up)
    proj = perspective(35, aspect, 0.1, 100.0)
    
    verts_hom = np.hstack((verts, np.ones((len(verts), 1))))
    verts_view = (view @ verts_hom.T).T
    verts_proj = (proj @ verts_view.T).T
    
    w = verts_proj[:, 3].reshape(-1, 1)
    # Avoid division by zero
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
        
        # Disable backface culling so open surfaces like Mobius strips render both sides
        # Use absolute value of dot product to light both sides
        intensity = max(0.1, abs(np.dot(normal, light_dir)))
        z_depth = (verts_view[f[0], 2] + verts_view[f[1], 2] + verts_view[f[2], 2]) / 3
        
        pts_2d = verts_2d[f]
        incenter, incircle_r = get_incenter(pts_2d)
        
        face_data.append({
            'pts_2d': pts_2d,
            'intensity': intensity,
            'z': z_depth,
            'incenter': incenter,
            'r': incircle_r
        })
        
    face_data.sort(key=lambda x: x['z'])
    
    if len(face_data) > 0:
        intensities = np.array([fd['intensity'] for fd in face_data])
        min_i, max_i = intensities.min(), intensities.max()
        for fd in face_data:
            normalized_i = (fd['intensity'] - min_i) / (max_i - min_i + 0.001)
            # Add a bit of non-linear gamma so we get more midtones
            normalized_i = math.pow(normalized_i, 0.7)
            color_idx = int(normalized_i * 8)
            fd['color_idx'] = min(7, color_idx) + 1
            
    return face_data, title

def main():
    out_dir = "/var/www/mathrelaxing.store/static/downloads/sacred-math-coloring-book"
    os.makedirs(out_dir, exist_ok=True)
        
    pdf_path = os.path.join(out_dir, "interior.pdf")
    
    with PdfPages(pdf_path) as pdf:
        # 1. Title Page
        fig = plt.figure(figsize=(8.5, 11))
        fig.text(0.5, 0.62, "SACRED GEOMETRY", ha='center', va='center', fontsize=46, family='serif', weight='light')
        fig.text(0.5, 0.55, "& TOPOLOGY", ha='center', va='center', fontsize=46, family='serif', weight='light')
        fig.text(0.5, 0.45, "A 3D Color-by-Numbers Journey", ha='center', va='center', fontsize=18, family='serif', style='italic', color='#444')
        fig.text(0.5, 0.40, "50 Geometric 3D Models · MathRelaxing", ha='center', va='center', fontsize=11, family='serif', color='#777')
        pdf.savefig(fig)
        plt.close(fig)
        
        # 2. Palette & Instructions Page
        fig = plt.figure(figsize=(8.5, 11))
        ax = fig.add_axes([0.12, 0.1, 0.76, 0.82])
        ax.axis('off')
        ax.text(0.0, 0.97, "How to colour", ha='left', va='top', fontsize=22, family='serif', color='#222')
        intro = ("1. Match the numbers in the polygons to the colour legend at the bottom\n"
                 "   of the page.\n"
                 "2. Relax and enjoy the illusion of 3D volume emerge from flat shapes!\n"
                 "3. Small accent polygons have been pre-coloured for your convenience.\n\n"
                 "Use any pens, pencils, or markers. Slip a spare sheet behind the page\n"
                 "if using wet markers.")
        ax.text(0.0, 0.88, intro, ha='left', va='top', fontsize=12.5, family='serif', color='#333', linespacing=1.5)
        pdf.savefig(fig)
        plt.close(fig)
        
        # 3. Coloring Pages
        all_data = []
        idx = 0
        while len(all_data) < 50:
            face_data, title = render_mesh(idx, aspect=8.5/11.0)
            idx += 1
            if len(face_data) == 0:
                continue
            
            fig = plt.figure(figsize=(8.5, 11))
            ax = fig.add_axes([0.05, 0.15, 0.9, 0.8])
            ax_legend = fig.add_axes([0.1, 0.05, 0.8, 0.05])
            ax.set_aspect('equal')
            ax.axis('off')
            ax_legend.axis('off')
            
            # Auto-fit bounds
            all_pts = np.vstack([fd['pts_2d'] for fd in face_data])
            min_x, max_x = all_pts[:,0].min(), all_pts[:,0].max()
            min_y, max_y = all_pts[:,1].min(), all_pts[:,1].max()
            w, h = max_x - min_x, max_y - min_y
            margin = max(w, h) * 0.05
            data_w = (max_x + margin) - (min_x - margin)
            data_h = (max_y + margin) - (min_y - margin)
            
            axes_w = 0.9 * 8.5
            axes_h = 0.8 * 11.0
            
            if data_h / data_w > axes_h / axes_w:
                scale_pts = (axes_h / data_h) * 72.0
            else:
                scale_pts = (axes_w / data_w) * 72.0
                
            ax.set_xlim(min_x - margin, max_x + margin)
            ax.set_ylim(min_y - margin, max_y + margin)
            
            # Pass 1: Pre-compute paths and determine number placement
            for fd in face_data:
                fd['path'] = mpath.Path(fd['pts_2d'])
                fd['has_number'] = False
            
            numbered_count = 0
            for idx_z, fd in enumerate(face_data):
                ic_x, ic_y = fd['incenter']
                r = fd['r']
                font_size = 2 * r * scale_pts * 0.35 
                font_size = min(9, font_size)
                fd['font_size'] = font_size
                if font_size >= 4.5:
                    occluded = False
                    for fd_front in face_data[idx_z+1:]:
                        if fd_front['path'].contains_point((ic_x, ic_y)):
                            occluded = True
                            break
                    if not occluded:
                        fd['has_number'] = True
                        numbered_count += 1
                        
            if numbered_count < 20:
                plt.close(fig)
                print(f"Discarding model '{title}' (only {numbered_count} numbers).")
                continue
                
            print(f"Generating page {len(all_data)+1}/50: {title} ({numbered_count} numbers)")
            all_data.append((face_data, title))
            
            # Pass 2: Draw polygons and text
            palette = get_palette(idx)
            for idx_z, fd in enumerate(face_data):
                z = idx_z + 1
                if fd['has_number']:
                    facecolor = 'white'
                else:
                    facecolor = palette[fd['color_idx']]
                    
                poly = Polygon(fd['pts_2d'], closed=True, facecolor=facecolor, edgecolor='black', linewidth=0.5, zorder=z)
                ax.add_patch(poly)
                
                if fd['has_number']:
                    ic_x, ic_y = fd['incenter']
                    ax.text(ic_x, ic_y, str(fd['color_idx']), ha='center', va='center', 
                            fontsize=fd['font_size'], color='#999999', zorder=z)
                                
            # Draw legend
            palette = get_palette(idx)
            box_w = 1.0 / 8.0
            for i in range(1, 9):
                x = (i-1) * box_w
                rect = Polygon([[x, 0], [x+box_w, 0], [x+box_w, 1], [x, 1]], 
                               facecolor=palette[i], edgecolor='black', linewidth=0.5)
                ax_legend.add_patch(rect)
                text_color = 'white' if i <= 4 else 'black'
                if np.mean(mcolors.to_rgb(palette[i])) < 0.5:
                    text_color = 'white'
                else:
                    text_color = 'black'
                ax_legend.text(x + box_w/2, 0.5, str(i), ha='center', va='center', color=text_color, fontsize=10, family='serif')
            ax_legend.set_xlim(0, 1)
            ax_legend.set_ylim(0, 1)
                    
            fig.text(0.5, 0.12, f"{idx+1}. {title}", ha='center', fontsize=12)
            pdf.savefig(fig)
            plt.close(fig)
            
        # 4. Solutions (Thumbnails)
        print("Generating Solution Keys...")
        thumbs_per_page = 9
        for page_idx in range(math.ceil(50 / thumbs_per_page)):
            fig, axs = plt.subplots(3, 3, figsize=(8.5, 11))
            fig.subplots_adjust(hspace=0.4, wspace=0.3)
            fig.text(0.5, 0.95, "Solution Key", ha='center', va='center', fontsize=20, weight='bold')
            
            for i in range(9):
                ax = axs[i//3, i%3]
                ax.axis('off')
                data_idx = page_idx * 9 + i
                if data_idx < 50:
                    face_data, title = all_data[data_idx]
                    all_pts = np.vstack([fd['pts_2d'] for fd in face_data])
                    min_x, max_x = all_pts[:,0].min(), all_pts[:,0].max()
                    min_y, max_y = all_pts[:,1].min(), all_pts[:,1].max()
                    margin = max(max_x - min_x, max_y - min_y) * 0.05
                    ax.set_xlim(min_x - margin, max_x + margin)
                    ax.set_ylim(min_y - margin, max_y + margin)
                    ax.set_aspect('equal')
                    for fd in face_data:
                        palette = get_palette(data_idx)
                        poly = Polygon(fd['pts_2d'], closed=True, facecolor=palette[fd['color_idx']], edgecolor='none')
                        ax.add_patch(poly)
                    ax.set_title(str(data_idx+1), fontsize=10, family='serif', color='#555')
            pdf.savefig(fig)
            plt.close(fig)
            
    print(f"DONE: {pdf_path}")

if __name__ == "__main__":
    main()
