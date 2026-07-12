"""
Thomas attractor — seamless 60fps loop for Etsy (1080x1080).
Cyclically-symmetric attractor: dx=sin(y)-b*x, dy=sin(z)-b*y, dz=sin(x)-b*z.

Rendered as a glowing DENSITY cloud (numpy rasterization) so the dense,
symmetric structure reads well. Loop is seamless via 360 deg rotation about
the vertical axis -> identical first/last frame.
"""
import os, math, tempfile, subprocess, shutil
import numpy as np
from scipy.ndimage import gaussian_filter
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image

OUT = "/var/www/mathrelaxing.store/static/downloads/digital/thomas_attractor_loop.mp4"

W = H = 1080
FPS = 60
DURATION = 12
N_FRAMES = FPS * DURATION

BG = (0.027, 0.027, 0.031)
# gold -> aqua glow (brand), brightening to near-white at peaks
CMAP = LinearSegmentedColormap.from_list(
    "thomas", [BG, (0.40, 0.33, 0.18), (0.78, 0.66, 0.43),
               (0.49, 0.81, 0.70), (0.86, 0.97, 0.93)])
LUT = (CMAP(np.linspace(0, 1, 256))[:, :3] * 255).astype(np.float32)


def simulate_thomas(b=0.19, dt=0.03, n_steps=500000, warmup=2000):
    x, y, z = 0.1, 0.2, 0.3
    for _ in range(warmup):                      # discard transient
        x, y, z = (x + (math.sin(y) - b*x)*dt,
                   y + (math.sin(z) - b*y)*dt,
                   z + (math.sin(x) - b*z)*dt)
    xs = np.empty(n_steps); ys = np.empty(n_steps); zs = np.empty(n_steps)
    for i in range(n_steps):
        x, y, z = (x + (math.sin(y) - b*x)*dt,
                   y + (math.sin(z) - b*y)*dt,
                   z + (math.sin(x) - b*z)*dt)
        xs[i] = x; ys[i] = y; zs[i] = z
    return xs, ys, zs


def render_frame(xs, ys, zs, angle_deg, R, zlo, zhi):
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    xr = xs * ca - ys * sa          # horizontal (rotating)
    # vertical = zs (rotation axis), depth = xs*sa + ys*ca (toward camera)
    depth = xs * sa + ys * ca

    rng = [[zlo, zhi], [-R, R]]
    # density + depth-weighted density (for subtle 3D shading)
    dens, _, _ = np.histogram2d(zs, xr, bins=(H, W), range=rng)
    dnorm = (depth - depth.min()) / (np.ptp(depth) + 1e-9)
    depthw, _, _ = np.histogram2d(zs, xr, bins=(H, W), range=rng, weights=dnorm)

    dens = gaussian_filter(dens, 0.9)
    depthw = gaussian_filter(depthw, 0.9)

    inten = np.log1p(dens)
    inten /= (inten.max() + 1e-9)
    # nearer regions a touch brighter
    avg_depth = np.divide(depthw, dens, out=np.zeros_like(dens), where=dens > 0)
    inten = np.clip(inten * (0.78 + 0.30 * avg_depth), 0, 1)

    idx = (inten * 255).astype(np.int32)
    rgb = LUT[idx]                                # HxWx3
    rgb = np.flipud(rgb)                          # z up
    return Image.fromarray(rgb.astype(np.uint8), "RGB")


def main():
    print("Simulating Thomas attractor (b=0.208186, 500k pts)...")
    xs, ys, zs = simulate_thomas()
    R = float(np.sqrt(xs**2 + ys**2).max()) * 1.05
    zlo, zhi = float(zs.min()) - 0.3, float(zs.max()) + 0.3
    print(f"  R={R:.2f}  z=[{zlo:.2f},{zhi:.2f}]")

    tmp = tempfile.mkdtemp(prefix="thomas_")
    print(f"Rendering {N_FRAMES} frames ({DURATION}s @ {FPS}fps, {W}x{H})...")
    for i in range(N_FRAMES):
        ang = (i / N_FRAMES) * 360.0
        render_frame(xs, ys, zs, ang, R, zlo, zhi).save(
            os.path.join(tmp, f"f_{i:05d}.png"))
        if i % FPS == 0:
            print(f"    frame {i}/{N_FRAMES} ({ang:.0f} deg)")

    print("Encoding...")
    subprocess.run(
        f'ffmpeg -y -framerate {FPS} -i {tmp}/f_%05d.png '
        f'-c:v libx264 -pix_fmt yuv420p -crf 18 -preset slow '
        f'-movflags +faststart {OUT}',
        shell=True, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Done! {OUT}  ({os.path.getsize(OUT)/1024/1024:.1f} MB)")


if __name__ == "__main__":
    main()
