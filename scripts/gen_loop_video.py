#!/usr/bin/env python3
"""Generate a seamless loop video of a Lorenz attractor.

Uses matplotlib for high-quality rendering (same as the main renderer).
Camera rotates 360° over N frames -> last frame = first frame = seamless loop.
"""
import sys, os, io, math, tempfile
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection


def simulate_lorenz(sigma=10.0, rho=28.0, beta=2.667, dt=0.003, n_steps=15000, seed=42):
    np.random.seed(seed)
    x, y, z = 1.0, 1.0, 1.0
    traj = []
    for _ in range(n_steps):
        dx = sigma * (y - x) * dt
        dy = (x * (rho - z) - y) * dt
        dz = (x * y - beta * z) * dt
        x += dx; y += dy; z += dz
        traj.append((x, y, z))
    return np.array(traj)


def render_frame(trajectory, angle_deg, width_px=640, height_px=640,
                 color_start="#c8a96e", color_end="#7ecfb3", bg="#080808",
                 trail_length=5000, dpi=100):
    """Render one frame using matplotlib for high quality."""
    angle = math.radians(angle_deg)

    fw = width_px / dpi
    fh = height_px / dpi

    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)

    # Project with rotation
    x, y, z = trajectory[:, 0], trajectory[:, 1], trajectory[:, 2]
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    x_rot = x * cos_a - y * sin_a
    y_rot = x * sin_a + y * cos_a

    # Use last trail_length points
    n = len(trajectory)
    start = max(0, n - trail_length)
    x_r = x_rot[start:]
    y_r = y_rot[start:]
    z_r = z[start:]

    # Create colored line segments
    points = np.array([x_r, z_r]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)

    # Normalize Z for color mapping
    z_norm = (z_r - z_r.min()) / (z_r.max() - z_r.min() + 1e-10)

    # Create colormap
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("lorenz_loop", [color_start, color_end])

    # Fade alpha: older = more transparent
    n_pts = len(x_r)
    alphas = np.linspace(0.05, 0.9, n_pts - 1)
    alphas = alphas ** 0.5  # non-linear for smoother fade

    colors = cmap(z_norm[:-1])
    colors[:, 3] = alphas

    # Line width varies with depth (y_rot) for 3D feel
    y_depth = y_r[:-1]
    y_norm = (y_depth - y_depth.min()) / (y_depth.max() - y_depth.min() + 1e-10)
    lw = 0.3 + y_norm * 1.2

    lc = LineCollection(segments, colors=colors, linewidths=lw)
    ax.add_collection(lc)

    # Set axis limits with padding
    pad = 2
    ax.set_xlim(x_r.min() - pad, x_r.max() + pad)
    ax.set_ylim(z.min() - pad, z.max() + pad)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)

    # Render to bytes
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=bg)
    plt.close(fig)
    buf.seek(0)

    from PIL import Image
    img = Image.open(buf).convert("RGB")
    return img


def main():
    fps = 30
    duration_secs = 6
    n_frames = fps * duration_secs  # 180 frames
    width, height = 640, 640

    output_dir = tempfile.mkdtemp(prefix="lorenz_loop_")
    print(f"Simulating Lorenz attractor...")
    trajectory = simulate_lorenz(n_steps=15000)

    print(f"Rendering {n_frames} frames ({duration_secs}s at {fps}fps)...")
    for i in range(n_frames):
        angle = (i / n_frames) * 360.0
        img = render_frame(trajectory, angle, width, height)
        img.save(os.path.join(output_dir, f"frame_{i:04d}.png"), "PNG")
        if i % 30 == 0:
            print(f"  Frame {i}/{n_frames} (angle={angle:.0f}°)")

    output_mp4 = "/tmp/lorenz_loop_seamless.mp4"
    print(f"Encoding MP4...")
    os.system(
        f'ffmpeg -y -framerate {fps} -i {output_dir}/frame_%04d.png '
        f'-c:v libx264 -pix_fmt yuv420p -crf 18 -preset slow '
        f'-movflags +faststart {output_mp4}'
    )

    size_mb = os.path.getsize(output_mp4) / 1024 / 1024
    print(f"\nDone! {output_mp4} ({size_mb:.1f} MB)")
    print(f"Duration: {duration_secs}s, {width}x{height}, {fps}fps, seamless loop")


if __name__ == "__main__":
    main()
