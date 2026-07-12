"""
Seamless loop video renderer for mathematical attractors.

Each attractor type uses a different technique to achieve a perfect loop:
- Lorenz / Aizawa: Camera rotates 360° around Z axis
- Clifford: Parameter oscillates through a full sinusoidal period
- Attractor Morph: Interpolates between two attractor shapes and back
- Lorenz Drift: Parameters trace a closed loop in parameter space

Output: MP4 (H.264) with configurable fps (30/60) and resolution (1080p/4K).
"""
import os, io, math, tempfile, subprocess
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image


# ── Simulation helpers ─────────────────────────────────────────────────────

def _simulate_lorenz(sigma=10.0, rho=28.0, beta=2.667, dt=0.003, n_steps=15000, seed=42):
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


def _simulate_clifford(a, b, c, d, n_steps=30000, dt=0.005, seed=42):
    np.random.seed(seed)
    x, y = 0.1, 0.1
    traj = []
    for _ in range(n_steps):
        xn = np.sin(a * y) + c * np.cos(a * x)
        yn = np.sin(b * x) + d * np.cos(b * y)
        x, y = xn, yn
        traj.append((x, y))
    return np.array(traj)


def _simulate_aizawa(a=0.95, b=0.7, c=0.6, d=3.5, e=0.25, f=0.1,
                     dt=0.005, n_steps=15000, seed=42):
    np.random.seed(seed)
    x, y, z = 0.1, 0.1, 0.1
    traj = []
    for _ in range(n_steps):
        dx = ((z - b) * x - d * y) * dt
        dy = (d * x + (z - b) * y) * dt
        dz = (c + a * z - (z**3)/3 - (x**2 + y**2) * (1 + e * z) + f * z * x**3) * dt
        x += dx; y += dy; z += dz
        traj.append((x, y, z))
    return np.array(traj)


# ── Frame renderers ─────────────────────────────────────────────────────────

def _render_3d_frame(trajectory, angle_deg, width_px, height_px, dpi,
                     color_start, color_end, bg, trail_length=5000):
    """Render a 3D attractor (Lorenz/Aizawa) from a rotating camera angle."""
    angle = math.radians(angle_deg)
    fw, fh = width_px / dpi, height_px / dpi

    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)

    x, y, z = trajectory[:, 0], trajectory[:, 1], trajectory[:, 2]
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    x_rot = x * cos_a - y * sin_a
    y_rot = x * sin_a + y * cos_a

    n = len(trajectory)
    start = max(0, n - trail_length)
    x_r, y_r, z_r = x_rot[start:], y_rot[start:], z[start:]

    points = np.array([x_r, z_r]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)

    z_norm = (z_r - z_r.min()) / (z_r.max() - z_r.min() + 1e-10)
    cmap = LinearSegmentedColormap.from_list("mr_loop", [color_start, color_end])

    n_pts = len(x_r)
    alphas = np.linspace(0.05, 0.9, n_pts - 1) ** 0.5
    colors = cmap(z_norm[:-1])
    colors[:, 3] = alphas

    y_norm = (y_r[:-1] - y_r[:-1].min()) / (y_r[:-1].max() - y_r[:-1].min() + 1e-10)
    lw = 0.3 + y_norm * 1.2

    lc = LineCollection(segments, colors=colors, linewidths=lw)
    ax.add_collection(lc)

    pad = 2
    ax.set_xlim(x_r.min() - pad, x_r.max() + pad)
    ax.set_ylim(z.min() - pad, z.max() + pad)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=bg)
    plt.close(fig)
    buf.seek(0)

    from PIL import Image
    return Image.open(buf).convert("RGB")


def _render_2d_frame(trajectory, angle_frac, width_px, height_px, dpi,
                     color_start, color_end, bg, trail_length=25000):
    """Render a 2D attractor (Clifford) using histogram accumulation.
    Each pixel counts visits, then tone-mapped for fine delicate curves.
    """
    x, y = trajectory[:, 0], trajectory[:, 1]
    start = max(0, len(trajectory) - trail_length)
    x_r, y_r = x[start:], y[start:]

    margin = 0.08
    x_min, x_max = x_r.min(), x_r.max()
    y_min, y_max = y_r.min(), y_r.max()
    x_range = x_max - x_min or 1
    y_range = y_max - y_min or 1

    px = ((x_r - x_min) / x_range * width_px * (1 - 2*margin) + width_px * margin).astype(int)
    py = ((y_r - y_min) / y_range * height_px * (1 - 2*margin) + height_px * margin).astype(int)

    # Accumulate visits per pixel + color channels
    hist = np.zeros((height_px, width_px), dtype=np.float64)
    r_acc = np.zeros((height_px, width_px), dtype=np.float64)
    g_acc = np.zeros((height_px, width_px), dtype=np.float64)
    b_acc = np.zeros((height_px, width_px), dtype=np.float64)

    cs_r = int(color_start[1:3], 16)
    cs_g = int(color_start[3:5], 16)
    cs_b = int(color_start[5:7], 16)
    ce_r = int(color_end[1:3], 16)
    ce_g = int(color_end[3:5], 16)
    ce_b = int(color_end[5:7], 16)

    n_pts = len(x_r)
    for i in range(n_pts):
        xi, yi = px[i], py[i]
        if 0 <= xi < width_px and 0 <= yi < height_px:
            t = i / n_pts
            hist[yi, xi] += 1
            r_acc[yi, xi] += cs_r * (1-t) + ce_r * t
            g_acc[yi, xi] += cs_g * (1-t) + ce_g * t
            b_acc[yi, xi] += cs_b * (1-t) + ce_b * t

    # Tone map: sqrt of log scale for better visibility while keeping fine lines
    mask = hist > 0
    intensity = np.zeros_like(hist)
    intensity[mask] = np.sqrt(np.log1p(hist[mask]) / np.log1p(hist.max()))

    # Average color per pixel
    r_avg = np.zeros_like(hist)
    g_avg = np.zeros_like(hist)
    b_avg = np.zeros_like(hist)
    r_avg[mask] = r_acc[mask] / hist[mask]
    g_avg[mask] = g_acc[mask] / hist[mask]
    b_avg[mask] = b_acc[mask] / hist[mask]

    # Parse bg
    bg_r = int(bg[1:3], 16)
    bg_g = int(bg[3:5], 16)
    bg_b = int(bg[5:7], 16)

    # Compose: intensity controls blend between bg and attractor color
    # Add subtle glow by boosting intensity slightly
    glow = np.clip(intensity * 1.3, 0, 1)
    pixels = np.zeros((height_px, width_px, 3), dtype=np.uint8)
    pixels[:,:,0] = np.clip(bg_r * (1 - glow) + r_avg * glow, 0, 255).astype(np.uint8)
    pixels[:,:,1] = np.clip(bg_g * (1 - glow) + g_avg * glow, 0, 255).astype(np.uint8)
    pixels[:,:,2] = np.clip(bg_b * (1 - glow) + b_avg * glow, 0, 255).astype(np.uint8)

    from PIL import Image
    return Image.fromarray(pixels)


# ── Video generation functions ──────────────────────────────────────────────

def generate_lorenz_loop(output_path, fps=30, duration_secs=30,
                         width=1920, height=1080,
                         sigma=10.0, rho=28.0, beta=2.667,
                         color_start="#c8a96e", color_end="#7ecfb3",
                         bg="#080808", trail_length=5000):
    """Lorenz seamless loop: camera rotates 360° around Z axis."""
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="lorenz_vid_")
    dpi = max(100, width // 12)

    print(f"  Simulating Lorenz (σ={sigma}, ρ={rho}, β={beta})...")
    traj = _simulate_lorenz(sigma, rho, beta, n_steps=15000)

    print(f"  Rendering {n_frames} frames ({duration_secs}s @ {fps}fps, {width}x{height})...")
    for i in range(n_frames):
        angle = (i / n_frames) * 360.0
        img = _render_3d_frame(traj, angle, width, height, dpi,
                              color_start, color_end, bg, trail_length)
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps * 5) == 0:
            print(f"    Frame {i}/{n_frames} ({angle:.0f}°)")

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_clifford_loop(output_path, fps=30, duration_secs=20,
                           width=1920, height=1080,
                           a=-1.4, b=1.6, c=1.0, d=0.7,
                           color_start="#c8a96e", color_end="#7ecfb3",
                           bg="#080808"):
    """Clifford seamless loop: parameter 'a' oscillates sin(2π*t) → returns to start."""
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="clifford_vid_")
    dpi = max(100, width // 12)

    # Base parameter + oscillation amplitude
    a_base = a
    a_amp = abs(a) * 0.3  # oscillate ±30% of a

    print(f"  Rendering {n_frames} Clifford frames...")
    for i in range(n_frames):
        frac = i / n_frames
        a_current = a_base + a_amp * math.sin(2 * math.pi * frac)
        traj = _simulate_clifford(a_current, b, c, d, n_steps=30000)
        img = _render_2d_frame(traj, frac, width, height, dpi,
                               color_start, color_end, bg)
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps * 5) == 0:
            print(f"    Frame {i}/{n_frames} (a={a_current:.3f})")

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_clifford_nebula(output_path, fps=30, duration_secs=20,
                             width=1920, height=1080,
                             a=-1.7, b=1.8, c=-0.9, d=0.4,
                             color_start="#e85d75", color_end="#6ec8cf",
                             bg="#0a0a14"):
    """Clifford Nebula: soft cloud-like structure, parameters oscillate for seamless loop."""
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="cliff_neb_")

    a_amp = abs(a) * 0.15
    b_amp = abs(b) * 0.15

    print(f"  Rendering {n_frames} Clifford Nebula frames...")
    for i in range(n_frames):
        frac = i / n_frames
        a_cur = a + a_amp * math.sin(2 * math.pi * frac)
        b_cur = b + b_amp * math.cos(2 * math.pi * frac)
        traj = _simulate_clifford(a_cur, b_cur, c, d, n_steps=40000)
        img = _render_2d_frame(traj, frac, width, height, 160,
                               color_start, color_end, bg, trail_length=35000)
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps * 5) == 0:
            print(f"    Frame {i}/{n_frames} (a={a_cur:.3f}, b={b_cur:.3f})")

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_clifford_spiral(output_path, fps=30, duration_secs=20,
                             width=1920, height=1080,
                             a=1.5, b=-1.4, c=1.0, d=0.5,
                             color_start="#f59e0b", color_end="#8b5cf6",
                             bg="#0c0a1a"):
    """Clifford Spiral: tight spiral arms, parameters oscillate for seamless loop."""
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="cliff_spir_")

    c_amp = abs(c) * 0.2

    print(f"  Rendering {n_frames} Clifford Spiral frames...")
    for i in range(n_frames):
        frac = i / n_frames
        c_cur = c + c_amp * math.sin(2 * math.pi * frac)
        traj = _simulate_clifford(a, b, c_cur, d, n_steps=40000)
        img = _render_2d_frame(traj, frac, width, height, 160,
                               color_start, color_end, bg, trail_length=35000)
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps * 5) == 0:
            print(f"    Frame {i}/{n_frames} (c={c_cur:.3f})")

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_clifford_bloom(output_path, fps=30, duration_secs=20,
                           width=1920, height=1080,
                           a=-1.2, b=-1.1, c=1.0, d=1.1,
                           color_start="#ec4899", color_end="#06b6d4",
                           bg="#0a0a0a"):
    """Clifford Bloom: flower-like pattern, parameters oscillate for seamless loop."""
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="cliff_bloom_")

    d_amp = abs(d) * 0.2

    print(f"  Rendering {n_frames} Clifford Bloom frames...")
    for i in range(n_frames):
        frac = i / n_frames
        d_cur = d + d_amp * math.sin(2 * math.pi * frac)
        traj = _simulate_clifford(a, b, c, d_cur, n_steps=40000)
        img = _render_2d_frame(traj, frac, width, height, 160,
                               color_start, color_end, bg, trail_length=35000)
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps * 5) == 0:
            print(f"    Frame {i}/{n_frames} (d={d_cur:.3f})")

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_aizawa_loop(output_path, fps=30, duration_secs=25,
                         width=1920, height=1080,
                         a=0.95, b=0.7, c=0.6, d=3.5, e=0.25, f=0.1,
                         color_start="#c8a96e", color_end="#7ecfb3",
                         bg="#080808", trail_length=5000):
    """Aizawa seamless loop: camera rotates 360° around Z axis."""
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="aizawa_vid_")
    dpi = max(100, width // 12)

    print(f"  Simulating Aizawa (a={a}, b={b}, c={c})...")
    traj = _simulate_aizawa(a, b, c, d, e, f, n_steps=15000)

    print(f"  Rendering {n_frames} frames...")
    for i in range(n_frames):
        angle = (i / n_frames) * 360.0
        img = _render_3d_frame(traj, angle, width, height, dpi,
                              color_start, color_end, bg, trail_length)
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps * 5) == 0:
            print(f"    Frame {i}/{n_frames} ({angle:.0f}°)")

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_morph_loop(output_path, fps=30, duration_secs=30,
                        width=1920, height=1080,
                        color_start="#c8a96e", color_end="#7ecfb3",
                        bg="#080808", trail_length=5000):
    """Attractor Morph: smoothly morph between Lorenz and Aizawa shapes.
    Uses sinusoidal blend: 0→1→0 over the loop period = seamless.
    """
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="morph_vid_")
    dpi = max(100, width // 12)

    print(f"  Simulating base attractors for morph...")
    traj_lorenz = _simulate_lorenz(n_steps=15000)
    traj_aizawa = _simulate_aizawa(n_steps=15000)

    # Normalize both trajectories to same coordinate space
    def _normalize(traj):
        mn, mx = traj.min(axis=0), traj.max(axis=0)
        return (traj - mn) / (mx - mn + 1e-10)

    norm_l = _normalize(traj_lorenz)
    norm_a = _normalize(traj_aizawa)

    print(f"  Rendering {n_frames} morph frames...")
    for i in range(n_frames):
        frac = i / n_frames
        # Smooth blend: 0→1→0 using cosine interpolation
        blend = 0.5 * (1 - math.cos(2 * math.pi * frac))
        # At frac=0 and frac=1, blend=0 (pure Lorenz)
        # At frac=0.5, blend=1 (pure Aizawa)

        # Interpolate trajectories
        n_pts = min(len(norm_l), len(norm_a))
        blended = norm_l[:n_pts] * (1 - blend) + norm_a[:n_pts] * blend

        angle = frac * 360.0
        img = _render_3d_frame(blended, angle, width, height, dpi,
                              color_start, color_end, bg, trail_length=min(trail_length, n_pts))
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps * 5) == 0:
            print(f"    Frame {i}/{n_frames} (blend={blend:.2f})")

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_drift_loop(output_path, fps=30, duration_secs=60,
                        width=1920, height=1080,
                        sigma=10.0, rho=28.0, beta=2.667,
                        color_start="#c8a96e", color_end="#7ecfb3",
                        bg="#080808", trail_length=5000):
    """Lorenz Drift: parameters trace a closed loop in (rho, beta) space.
    rho and beta oscillate with sin/cos → returns to start = seamless.
    """
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="drift_vid_")
    dpi = max(100, width // 12)

    # Drift amplitudes
    rho_amp = rho * 0.15   # ±15% variation
    beta_amp = beta * 0.2  # ±20% variation

    print(f"  Rendering {n_frames} drift frames (σ={sigma}, ρ={rho}±{rho_amp:.1f}, β={beta}±{beta_amp:.2f})...")
    for i in range(n_frames):
        frac = i / n_frames
        rho_cur = rho + rho_amp * math.sin(2 * math.pi * frac)
        beta_cur = beta + beta_amp * math.cos(2 * math.pi * frac)

        traj = _simulate_lorenz(sigma, rho_cur, beta_cur, n_steps=12000)

        # Slow camera rotation too (1 full turn)
        angle = frac * 360.0
        img = _render_3d_frame(traj, angle, width, height, dpi,
                              color_start, color_end, bg, trail_length=4000)
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps * 10) == 0:
            print(f"    Frame {i}/{n_frames} (ρ={rho_cur:.1f}, β={beta_cur:.2f})")

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


# ── Flow Field loop generators ─────────────────────────────────────────────

def _ff_noise_uv(rng, frequency=1.2, octaves=3, RES=300):
    gx = np.linspace(0, 1, RES)
    gy = np.linspace(0, 1, RES)
    GX, GY = np.meshgrid(gx, gy)
    pts = np.column_stack([GX.ravel(), GY.ravel()])
    angle = np.zeros(RES * RES)
    amp, freq = 1.0, frequency
    for _ in range(octaves):
        n_feat = 12
        freqs  = rng.standard_normal((n_feat, 2)) * freq * 2 * math.pi
        phases = rng.uniform(0, 2 * math.pi, n_feat)
        angle += amp * np.sin(pts @ freqs.T + phases).sum(axis=1)
        amp *= 0.5; freq *= 2.0
    U = np.cos(angle).reshape(RES, RES)
    V = np.sin(angle).reshape(RES, RES)
    return U, V


def _ff_vortex_uv(vx, vy, Gm, RES=300):
    gx = np.linspace(0, 1, RES)
    gy = np.linspace(0, 1, RES)
    GX, GY = np.meshgrid(gx, gy)
    px, py = GX.ravel(), GY.ravel()
    U, V = np.zeros_like(px), np.zeros_like(py)
    for i in range(len(vx)):
        dx, dy = px - vx[i], py - vy[i]
        r2 = dx*dx + dy*dy + 1e-4
        U += -Gm[i] * dy / r2
        V +=  Gm[i] * dx / r2
    mag = np.sqrt(U*U + V*V) + 1e-9
    return (U/mag).reshape(RES, RES), (V/mag).reshape(RES, RES)


def _ff_sources_uv(sx, sy, Sm, RES=300):
    gx = np.linspace(0, 1, RES)
    gy = np.linspace(0, 1, RES)
    GX, GY = np.meshgrid(gx, gy)
    px, py = GX.ravel(), GY.ravel()
    U, V = np.zeros_like(px), np.zeros_like(py)
    for i in range(len(sx)):
        dx, dy = px - sx[i], py - sy[i]
        r2 = dx*dx + dy*dy + 1e-4
        U += Sm[i] * dx / r2
        V += Sm[i] * dy / r2
    mag = np.sqrt(U*U + V*V) + 1e-9
    return (U/mag).reshape(RES, RES), (V/mag).reshape(RES, RES)


def _ff_cellular_uv(frequency=2.0, RES=300):
    gx = np.linspace(0, 1, RES)
    gy = np.linspace(0, 1, RES)
    GX, GY = np.meshgrid(gx, gy)
    fx, fy = frequency, frequency
    U = -np.sin(fy * math.pi * 2 * GY) * np.cos(fx * math.pi * 2 * GX)
    V =  np.sin(fx * math.pi * 2 * GX) * np.cos(fy * math.pi * 2 * GY)
    mag = np.sqrt(U*U + V*V) + 1e-9
    return (U/mag), (V/mag)


def _ff_build_interps(U, V, RES=300):
    from scipy.interpolate import RegularGridInterpolator
    g = np.linspace(0, 1, RES)
    iu = RegularGridInterpolator((g, g), U, method='linear',
                                  bounds_error=False, fill_value=0.0)
    iv = RegularGridInterpolator((g, g), V, method='linear',
                                  bounds_error=False, fill_value=0.0)
    return iu, iv


def _ff_step(px, py, iu, iv, step, rng, recycle_prob=0.003):
    pts = np.column_stack([py, px])
    u, v = iu(pts), iv(pts)
    px = (px + u * step) % 1.0
    py = (py + v * step) % 1.0
    mask = rng.random(len(px)) < recycle_prob
    if mask.any():
        px[mask] = rng.random(mask.sum())
        py[mask] = rng.random(mask.sum())
    return px, py


def _ff_render_lines(width, height, trail_x, trail_y,
                     cs_rgb, ce_rgb, bg_rgb, lw=1):
    from PIL import Image, ImageDraw
    img  = Image.new('RGB', (width, height), bg_rgb)
    draw = ImageDraw.Draw(img, 'RGBA')
    trail, n_p = trail_x.shape
    for p in range(n_p):
        t = p / n_p
        c = tuple(int(cs_rgb[k]*(1-t) + ce_rgb[k]*t) for k in range(3))
        for j in range(trail - 1):
            x1, y1 = trail_x[j, p] * width,     (1-trail_y[j, p]) * height
            x2, y2 = trail_x[j+1, p] * width,   (1-trail_y[j+1, p]) * height
            if abs(x1-x2) > width*0.1 or abs(y1-y2) > height*0.1:
                continue
            alpha = int((1 - j/trail) * 190)
            draw.line([(x1, y1), (x2, y2)], fill=(*c, alpha), width=lw)
    return img


def _ff_render_density(width, height, all_px, all_py, cs_rgb, ce_rgb, bg_rgb):
    from PIL import Image as PILImage
    H, xedges, yedges = np.histogram2d(
        all_px, 1-all_py, bins=[width//4, height//4], range=[[0,1],[0,1]])
    H = np.log1p(H)
    mx = H.max()
    if mx > 0:
        H /= mx
    H = H.T
    small = PILImage.fromarray((H * 255).astype(np.uint8), mode='L')
    mask  = np.array(small.resize((width, height), PILImage.BILINEAR)) / 255.0
    pixels = np.zeros((height, width, 3), dtype=np.uint8)
    for k in range(3):
        pixels[:, :, k] = np.clip(
            bg_rgb[k]*(1-mask) + ce_rgb[k]*mask, 0, 255).astype(np.uint8)
    return PILImage.fromarray(pixels)


def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _ff_warmup(px, py, iu, iv, step, rng, steps):
    for _ in range(steps):
        px, py = _ff_step(px, py, iu, iv, step, rng, recycle_prob=0.0)
    return px, py


def generate_ff_origin_loop(output_path, fps=30, duration_secs=30,
                             width=1080, height=1350,
                             color_start="#C8A96E", color_end="#4EC9B0",
                             bg="#080808"):
    """Flow field — balanced three-octave noise, line style. Amber → teal."""
    rng = np.random.default_rng(42)
    U, V = _ff_noise_uv(rng, frequency=1.5, octaves=3)
    iu, iv = _ff_build_interps(U, V)

    n_p, trail, step = 700, 50, 0.003
    px = rng.random(n_p); py = rng.random(n_p)
    px, py = _ff_warmup(px, py, iu, iv, step, rng, trail)

    hist_x = np.tile(px, (trail+1, 1))
    hist_y = np.tile(py, (trail+1, 1))
    for _ in range(trail):
        px, py = _ff_step(px, py, iu, iv, step, rng)
        hist_x = np.roll(hist_x, 1, axis=0); hist_x[0] = px
        hist_y = np.roll(hist_y, 1, axis=0); hist_y[0] = py

    cs, ce, bg_c = _hex_to_rgb(color_start), _hex_to_rgb(color_end), _hex_to_rgb(bg)
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="ff_origin_")
    print(f"  FF Origin: {n_frames} frames…")
    for i in range(n_frames):
        px, py = _ff_step(px, py, iu, iv, step, rng)
        hist_x = np.roll(hist_x, 1, axis=0); hist_x[0] = px
        hist_y = np.roll(hist_y, 1, axis=0); hist_y[0] = py
        img = _ff_render_lines(width, height, hist_x, hist_y, cs, ce, bg_c, lw=1)
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps*10) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_ff_vortex_loop(output_path, fps=30, duration_secs=25,
                             width=1080, height=1350,
                             color_start="#F472B6", color_end="#22D3EE",
                             bg="#080808"):
    """Flow field — 3 point vortices, spiraling line style. Rose → cyan."""
    rng = np.random.default_rng(22)
    vx = np.array([0.28, 0.72, 0.50])
    vy = np.array([0.32, 0.60, 0.78])
    Gm = np.array([1.5, -1.1, 0.9])
    U, V = _ff_vortex_uv(vx, vy, Gm)
    iu, iv = _ff_build_interps(U, V)

    n_p, trail, step = 800, 55, 0.0025
    px = rng.random(n_p); py = rng.random(n_p)
    px, py = _ff_warmup(px, py, iu, iv, step, rng, trail)

    hist_x = np.tile(px, (trail+1, 1))
    hist_y = np.tile(py, (trail+1, 1))
    for _ in range(trail):
        px, py = _ff_step(px, py, iu, iv, step, rng)
        hist_x = np.roll(hist_x, 1, axis=0); hist_x[0] = px
        hist_y = np.roll(hist_y, 1, axis=0); hist_y[0] = py

    cs, ce, bg_c = _hex_to_rgb(color_start), _hex_to_rgb(color_end), _hex_to_rgb(bg)
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="ff_vortex_")
    print(f"  FF Vortex: {n_frames} frames…")
    for i in range(n_frames):
        px, py = _ff_step(px, py, iu, iv, step, rng)
        hist_x = np.roll(hist_x, 1, axis=0); hist_x[0] = px
        hist_y = np.roll(hist_y, 1, axis=0); hist_y[0] = py
        img = _ff_render_lines(width, height, hist_x, hist_y, cs, ce, bg_c, lw=1)
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps*10) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_ff_aurora_loop(output_path, fps=30, duration_secs=40,
                             width=1080, height=1350,
                             color_start="#10B981", color_end="#E879F9",
                             bg="#060610"):
    """Flow field — low-freq noise, thick brush strokes. Emerald → fuchsia."""
    rng = np.random.default_rng(137)
    U, V = _ff_noise_uv(rng, frequency=0.55, octaves=2)
    # Horizontal bias for curtain-like bands
    U = U * 0.3
    mag = np.sqrt(U*U + V*V) + 1e-9
    U, V = U/mag, V/mag
    iu, iv = _ff_build_interps(U, V)

    n_p, trail, step = 500, 45, 0.004
    px = rng.random(n_p); py = rng.random(n_p)
    px, py = _ff_warmup(px, py, iu, iv, step, rng, trail)

    hist_x = np.tile(px, (trail+1, 1))
    hist_y = np.tile(py, (trail+1, 1))
    for _ in range(trail):
        px, py = _ff_step(px, py, iu, iv, step, rng)
        hist_x = np.roll(hist_x, 1, axis=0); hist_x[0] = px
        hist_y = np.roll(hist_y, 1, axis=0); hist_y[0] = py

    cs, ce, bg_c = _hex_to_rgb(color_start), _hex_to_rgb(color_end), _hex_to_rgb(bg)
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="ff_aurora_")
    print(f"  FF Aurora: {n_frames} frames…")
    for i in range(n_frames):
        px, py = _ff_step(px, py, iu, iv, step, rng)
        hist_x = np.roll(hist_x, 1, axis=0); hist_x[0] = px
        hist_y = np.roll(hist_y, 1, axis=0); hist_y[0] = py
        img = _ff_render_lines(width, height, hist_x, hist_y, cs, ce, bg_c, lw=3)
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps*10) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_ff_turbulence_loop(output_path, fps=30, duration_secs=20,
                                 width=1080, height=1350,
                                 color_start="#7C3AED", color_end="#F59E0B",
                                 bg="#080808"):
    """Flow field — cellular stream function, density render. Violet → amber."""
    U, V = _ff_cellular_uv(frequency=2.2)
    iu, iv = _ff_build_interps(U, V)

    rng  = np.random.default_rng(13)
    n_p, step = 4000, 0.003
    px = rng.random(n_p); py = rng.random(n_p)
    px, py = _ff_warmup(px, py, iu, iv, step, rng, 60)

    # Rolling density buffer (last K steps)
    K = 30
    buf_x = np.tile(px, (K, 1))
    buf_y = np.tile(py, (K, 1))

    cs, ce, bg_c = _hex_to_rgb(color_start), _hex_to_rgb(color_end), _hex_to_rgb(bg)
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="ff_turb_")
    print(f"  FF Turbulence: {n_frames} frames…")
    for i in range(n_frames):
        for _ in range(2):  # 2 micro-steps per frame for denser trails
            px, py = _ff_step(px, py, iu, iv, step, rng)
        buf_x = np.roll(buf_x, 1, axis=0); buf_x[0] = px
        buf_y = np.roll(buf_y, 1, axis=0); buf_y[0] = py
        all_px = buf_x.ravel()
        all_py = buf_y.ravel()
        img = _ff_render_density(width, height, all_px, all_py, cs, ce, bg_c)
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps*5) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_ff_tide_loop(output_path, fps=30, duration_secs=45,
                           width=1080, height=1350,
                           color_start="#14B8A6", color_end="#6366F1",
                           bg="#080808"):
    """Flow field — alternating source/sink dipoles, long arcs. Teal → indigo."""
    rng = np.random.default_rng(333)
    sx = np.array([0.2, 0.5, 0.8, 0.35, 0.65, 0.15, 0.85])
    sy = np.array([0.2, 0.5, 0.8, 0.75, 0.25, 0.55, 0.45])
    Sm = np.array([1.0, -1.0, 1.0, -1.0, 1.0, -0.8, 0.8])
    U, V = _ff_sources_uv(sx, sy, Sm)
    iu, iv = _ff_build_interps(U, V)

    n_p, trail, step = 750, 60, 0.003
    px = rng.random(n_p); py = rng.random(n_p)
    px, py = _ff_warmup(px, py, iu, iv, step, rng, trail)

    hist_x = np.tile(px, (trail+1, 1))
    hist_y = np.tile(py, (trail+1, 1))
    for _ in range(trail):
        px, py = _ff_step(px, py, iu, iv, step, rng)
        hist_x = np.roll(hist_x, 1, axis=0); hist_x[0] = px
        hist_y = np.roll(hist_y, 1, axis=0); hist_y[0] = py

    cs, ce, bg_c = _hex_to_rgb(color_start), _hex_to_rgb(color_end), _hex_to_rgb(bg)
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="ff_tide_")
    print(f"  FF Tide: {n_frames} frames…")
    for i in range(n_frames):
        px, py = _ff_step(px, py, iu, iv, step, rng)
        hist_x = np.roll(hist_x, 1, axis=0); hist_x[0] = px
        hist_y = np.roll(hist_y, 1, axis=0); hist_y[0] = py
        img = _ff_render_lines(width, height, hist_x, hist_y, cs, ce, bg_c, lw=1)
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps*10) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


# ── Encoding & cleanup ─────────────────────────────────────────────────────

def _encode_mp4(frame_dir, output_path, fps, crf=18):
    """Encode PNG frames to MP4 using ffmpeg."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cmd = (
        f'ffmpeg -y -framerate {fps} -i {frame_dir}/f_%05d.png '
        f'-c:v libx264 -pix_fmt yuv420p -crf {crf} -preset slow '
        f'-movflags +faststart {output_path}'
    )
    subprocess.run(cmd, shell=True, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _cleanup(tmpdir):
    """Remove temporary frame directory."""
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── Julia Set loop generators ──────────────────────────────────────────────

def _julia_compute(c_real, c_imag, xmin, xmax, ymin, ymax, W, H, max_iter=120):
    """Vectorized Julia set — returns smooth escape-count array (float32)."""
    x = np.linspace(xmin, xmax, W, dtype=np.float64)
    y = np.linspace(ymin, ymax, H, dtype=np.float64)
    Zr = np.broadcast_to(x,            (H, W)).copy()
    Zi = np.broadcast_to(y[:, None],   (H, W)).copy()

    esc_iter = np.zeros((H, W), dtype=np.float32)
    esc_abs  = np.zeros((H, W), dtype=np.float32)
    escaped  = np.zeros((H, W), dtype=bool)

    for i in range(max_iter):
        new_zr = Zr*Zr - Zi*Zi + c_real
        Zi     = 2.0*Zr*Zi + c_imag
        Zr     = new_zr
        abs2   = Zr*Zr + Zi*Zi
        new_esc = ~escaped & (abs2 > 4.0)
        if new_esc.any():
            esc_iter[new_esc] = i + 1
            esc_abs[new_esc]  = np.sqrt(abs2[new_esc])
            escaped |= new_esc
        # Zero out escaped points to prevent overflow on subsequent iterations
        Zr[escaped] = 0.0
        Zi[escaped] = 0.0

    smooth = np.where(
        escaped,
        esc_iter - np.log2(np.log2(np.maximum(esc_abs, 1.001))),
        0.0,
    ).astype(np.float32)
    return smooth


def _julia_colorize(M, cs_rgb, ce_rgb, bg_rgb, period=32.0):
    """Map smooth iteration count → RGB PIL image."""
    from PIL import Image as PILImage
    H, W = M.shape
    t = (M % period) / period          # cycling color within exterior
    mask = (M > 0).astype(np.float32)  # 1=exterior, 0=interior

    pixels = np.zeros((H, W, 3), dtype=np.uint8)
    for k in range(3):
        exterior = cs_rgb[k]*(1-t) + ce_rgb[k]*t
        interior = bg_rgb[k]
        pixels[:, :, k] = np.clip(
            interior*(1-mask) + exterior*mask, 0, 255).astype(np.uint8)
    return PILImage.fromarray(pixels)


def _julia_zoom_image(c_r, c_i, cx, cy, half_width, width, height,
                      cs, ce, bg, period):
    asp = height / width
    M = _julia_compute(
        c_r, c_i,
        cx-half_width, cx+half_width,
        cy-half_width*asp, cy+half_width*asp,
        width, height,
    )
    return _julia_colorize(M, cs, ce, bg, period=period)


def _smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _generate_julia_inward_zoom_loop(output_path, *, fps, duration_secs, width, height,
                                     c_r, c_i, cx, cy, z_wide, z_deep,
                                     cs, ce, bg, period, name):
    """Render a one-direction Julia zoom with a short dissolve reset.

    A finite MP4 cannot be a literal endless mathematical zoom unless the
    start/end views are exactly self-similar. This keeps motion moving inward
    for the whole clip and hides the loop boundary with a brief fractal dissolve
    instead of reversing the camera.
    """
    n_frames = fps * duration_secs
    blend_frames = max(fps * 3, n_frames // 8)
    main_frames = n_frames - blend_frames
    tmpdir = tempfile.mkdtemp(prefix="julia_inward_")
    print(f"  {name}: {n_frames} frames, inward zoom with {blend_frames}f reset dissolve...")

    start_img = _julia_zoom_image(c_r, c_i, cx, cy, z_wide, width, height, cs, ce, bg, period)

    for i in range(n_frames):
        if i < main_frames:
            t = i / max(1, main_frames)
            s = z_wide * ((z_deep / z_wide) ** t)
            img = _julia_zoom_image(c_r, c_i, cx, cy, s, width, height, cs, ce, bg, period)
        else:
            # Continue inward while dissolving back to the first frame. This
            # avoids the visible "zoom-out" motion in the previous version.
            t = i / max(1, n_frames)
            s = z_wide * ((z_deep / z_wide) ** t)
            deep_img = _julia_zoom_image(c_r, c_i, cx, cy, s, width, height, cs, ce, bg, period)
            alpha = _smoothstep((i - main_frames) / max(1, blend_frames - 1))
            img = Image.blend(deep_img.convert("RGB"), start_img.convert("RGB"), alpha)

        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps*10) == 0:
            print(f"    {i}/{n_frames}")

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def _mandelbrot_compute(cx, cy, half_width, W, H, max_iter=360):
    asp = H / W
    x = np.linspace(cx-half_width, cx+half_width, W, dtype=np.float64)
    y = np.linspace(cy-half_width*asp, cy+half_width*asp, H, dtype=np.float64)
    Cr = np.broadcast_to(x, (H, W)).copy()
    Ci = np.broadcast_to(y[:, None], (H, W)).copy()
    Zr = np.zeros((H, W), dtype=np.float64)
    Zi = np.zeros((H, W), dtype=np.float64)
    esc_iter = np.zeros((H, W), dtype=np.float32)
    esc_abs = np.ones((H, W), dtype=np.float64)
    active = np.ones((H, W), dtype=bool)

    for i in range(max_iter):
        zr = Zr[active]
        zi = Zi[active]
        Zr[active] = zr*zr - zi*zi + Cr[active]
        Zi[active] = 2*zr*zi + Ci[active]
        abs2 = Zr*Zr + Zi*Zi
        escaped = active & (abs2 > 4.0)
        esc_iter[escaped] = i + 1
        esc_abs[escaped] = np.sqrt(abs2[escaped])
        active[escaped] = False
        if not active.any():
            break

    return np.where(
        esc_iter > 0,
        esc_iter - np.log2(np.log2(np.maximum(esc_abs, 1.001))),
        0.0,
    ).astype(np.float32)


def _mandelbrot_colorize(M, cs_rgb, ce_rgb, bg_rgb, period=36.0):
    H, W = M.shape
    t = (M % period) / period
    mask = (M > 0).astype(np.float32)
    pixels = np.zeros((H, W, 3), dtype=np.uint8)
    for k in range(3):
        exterior = cs_rgb[k]*(1-t) + ce_rgb[k]*t
        interior = bg_rgb[k]
        pixels[:, :, k] = np.clip(
            interior*(1-mask) + exterior*mask, 0, 255
        ).astype(np.uint8)
    return Image.fromarray(pixels)


def _mandelbrot_zoom_image(cx, cy, half_width, render_w, render_h, out_w, out_h,
                           cs, ce, bg, period):
    zoom_ratio = max(1.0, 1.55 / max(half_width, 1e-12))
    max_iter = min(720, int(170 + 56 * math.log2(zoom_ratio + 1.0)))
    M = _mandelbrot_compute(cx, cy, half_width, render_w, render_h, max_iter=max_iter)
    img = _mandelbrot_colorize(M, cs, ce, bg, period=period)
    if render_w != out_w or render_h != out_h:
        img = img.resize((out_w, out_h), Image.Resampling.LANCZOS)
    return img


def _generate_mandelbrot_minibrot_zoom_loop(output_path, *, fps, duration_secs,
                                            width, height, cx, cy,
                                            z_wide, z_deep, cs, ce, bg,
                                            period, name):
    """Render a forward-only zoom into a self-similar minibrot region.

    This is closer to the expected "infinite zoom" feel than a Julia pulse:
    the camera keeps moving inward and lands on recognizable Mandelbrot-family
    forms, then the loop resets with a short dissolve.
    """
    n_frames = fps * duration_secs
    blend_frames = max(fps * 3, n_frames // 9)
    main_frames = n_frames - blend_frames
    render_w = min(width, 720)
    render_h = round(render_w * height / width)
    tmpdir = tempfile.mkdtemp(prefix="minibrot_zoom_")
    print(f"  {name}: {n_frames} frames, minibrot zoom {render_w}x{render_h}->{width}x{height}...")

    start_img = _mandelbrot_zoom_image(
        cx, cy, z_wide, render_w, render_h, width, height, cs, ce, bg, period
    )

    for i in range(n_frames):
        if i < main_frames:
            t = i / max(1, main_frames)
            s = z_wide * ((z_deep / z_wide) ** t)
            img = _mandelbrot_zoom_image(
                cx, cy, s, render_w, render_h, width, height, cs, ce, bg, period
            )
        else:
            t = i / max(1, n_frames)
            s = z_wide * ((z_deep / z_wide) ** t)
            deep_img = _mandelbrot_zoom_image(
                cx, cy, s, render_w, render_h, width, height, cs, ce, bg, period
            )
            alpha = _smoothstep((i - main_frames) / max(1, blend_frames - 1))
            img = Image.blend(deep_img.convert("RGB"), start_img.convert("RGB"), alpha)

        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps*10) == 0:
            print(f"    {i}/{n_frames}")

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_julia_zoom1_loop(output_path, fps=30, duration_secs=30,
                               width=1080, height=1350):
    """Mandelbrot seahorse-valley minibrot zoom."""
    return _generate_mandelbrot_minibrot_zoom_loop(
        output_path,
        fps=fps, duration_secs=duration_secs, width=width, height=height,
        cx=-0.743643887037151, cy=0.13182590420533,
        z_wide=1.55, z_deep=0.0025,
        cs=(35, 220, 220), ce=(245, 170, 60), bg=(4, 4, 12),
        period=36.0, name="Fractal Zoom I",
    )


def generate_julia_zoom2_loop(output_path, fps=30, duration_secs=45,
                               width=1080, height=1350):
    """Mandelbrot antenna-valley minibrot zoom."""
    return _generate_mandelbrot_minibrot_zoom_loop(
        output_path,
        fps=fps, duration_secs=duration_secs, width=width, height=height,
        cx=-1.768778833, cy=0.001738996,
        z_wide=1.45, z_deep=0.004,
        cs=(160, 80, 255), ce=(20, 220, 220), bg=(4, 4, 12),
        period=32.0, name="Fractal Zoom II",
    )


def generate_julia_morph_loop(output_path, fps=30, duration_secs=30,
                               width=1080, height=1350):
    """Julia c = 0.7885·e^(2πit) — perfectly seamless parameter morph."""
    R = 0.7885
    cs = (255, 100,  60)
    ce = ( 60, 100, 255)
    bg = (  8,   8,   8)
    xmin, xmax = -1.5, 1.5
    asp = height / width

    n_frames = fps * duration_secs
    tmpdir   = tempfile.mkdtemp(prefix="julia_morph_")
    print(f"  Julia Morph: {n_frames} frames…")

    for i in range(n_frames):
        t   = i / n_frames
        c_r = R * math.cos(2*math.pi*t)
        c_i = R * math.sin(2*math.pi*t)
        s   = (xmax - xmin) / 2
        M   = _julia_compute(c_r, c_i,
                              xmin, xmax, -s*asp, s*asp,
                              width, height)
        # Hue also shifts with t for extra visual richness
        t_col = (t * 0.5) % 1.0
        curr_cs = tuple(int(cs[k]*(1-t_col) + ce[k]*t_col) for k in range(3))
        curr_ce = tuple(int(ce[k]*(1-t_col) + cs[k]*t_col) for k in range(3))
        img = _julia_colorize(M, curr_cs, curr_ce, bg, period=30.0)
        img.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps*10) == 0: print(f"    {i}/{n_frames}")

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def _hue_shift_array(rgb_arr, shift):
    """Shift hue of an RGB numpy array. shift ∈ [0,1]."""
    import matplotlib.colors as mcolors
    hsv = mcolors.rgb_to_hsv(rgb_arr.astype(np.float32) / 255.0)
    hsv[:, :, 0] = (hsv[:, :, 0] + shift) % 1.0
    return (mcolors.hsv_to_rgb(hsv) * 255).astype(np.uint8)


def _render_flame_base(params_dict, width, height):
    """Render a static fractal flame and return PIL Image."""
    import sys, io
    sys.path.insert(0, '/var/www/mathrelaxing.store')
    from services.renderer import render_equation
    from PIL import Image as PILImage
    data = render_equation('fractal-flame', params_dict, width=width, height=height)
    return PILImage.open(io.BytesIO(data)).convert('RGB')


def generate_ff_flame_aurora_loop(output_path, fps=30, duration_secs=30,
                                   width=1080, height=1350):
    """Fractal flame — sinusoidal, smooth hue-shift color cycle. Amber/teal."""
    from PIL import Image as PILImage
    params = {
        'variation': {'value': 'sinusoidal'}, 'var2': {'value': 'linear'},
        'v_mix': {'value': 0.0}, 'seed': {'value': 42}, 'n_funcs': {'value': 4},
        'symmetry': {'value': 1}, 'n_iters': {'value': 12_000_000},
        'gamma': {'value': 2.2}, 'brightness': {'value': 1.2},
        'color_start': {'value': '#C8A96E'}, 'color_end': {'value': '#4EC9B0'},
        'background_color': {'value': '#080808'},
    }
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix='ffa_aurora_')
    print(f"  FF Flame Aurora: {n_frames} frames…")
    for i in range(n_frames):
        phase = 2 * math.pi * i / n_frames
        params['phase'] = {'value': phase}
        frame_base = _render_flame_base(params, width, height)
        
        # Full 0.35 hue swing — amber → teal → violet → back, clearly visible
        shift = 0.35 * math.sin(phase)
        arr = _hue_shift_array(np.array(frame_base), shift)
        PILImage.fromarray(arr).save(os.path.join(tmpdir, f'f_{i:05d}.png'))
        if i % (fps * 10) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_ff_flame_phoenix_loop(output_path, fps=30, duration_secs=25,
                                    width=1080, height=1350):
    """Fractal flame — swirl 3-fold, 120° rotational loop. Rose/gold."""
    from PIL import Image as PILImage
    params = {
        'variation': {'value': 'swirl'}, 'var2': {'value': 'linear'},
        'v_mix': {'value': 0.0}, 'seed': {'value': 137}, 'n_funcs': {'value': 3},
        'symmetry': {'value': 3}, 'n_iters': {'value': 12_000_000},
        'gamma': {'value': 2.2}, 'brightness': {'value': 1.0},
        'color_start': {'value': '#F472B6'}, 'color_end': {'value': '#FBBF24'},
        'background_color': {'value': '#080808'},
    }
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix='ffa_phoenix_')
    print(f"  FF Flame Phoenix: {n_frames} frames…")
    for i in range(n_frames):
        phase = 2 * math.pi * i / n_frames
        params['phase'] = {'value': phase}
        frame = _render_flame_base(params, width, height)
        frame.save(os.path.join(tmpdir, f'f_{i:05d}.png'))
        if i % (fps * 10) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_ff_flame_crystal_loop(output_path, fps=30, duration_secs=20,
                                    width=1080, height=1350):
    """Fractal flame — julia 6-fold, 60° rotational loop. Ice/pink."""
    from PIL import Image as PILImage
    params = {
        'variation': {'value': 'julia'}, 'var2': {'value': 'linear'},
        'v_mix': {'value': 0.0}, 'seed': {'value': 333}, 'n_funcs': {'value': 3},
        'symmetry': {'value': 6}, 'n_iters': {'value': 12_000_000},
        'gamma': {'value': 2.2}, 'brightness': {'value': 1.1},
        'color_start': {'value': '#A5F3FC'}, 'color_end': {'value': '#F0ABFC'},
        'background_color': {'value': '#080808'},
    }
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix='ffa_crystal_')
    print(f"  FF Flame Crystal: {n_frames} frames…")
    for i in range(n_frames):
        phase = 2 * math.pi * i / n_frames
        params['phase'] = {'value': phase}
        frame = _render_flame_base(params, width, height)
        frame.save(os.path.join(tmpdir, f'f_{i:05d}.png'))
        if i % (fps * 5) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_ff_flame_vortex_loop(output_path, fps=30, duration_secs=35,
                                   width=1080, height=1350):
    """Fractal flame — swirl+sinusoidal sym=1, hue-shift loop. Teal/indigo."""
    from PIL import Image as PILImage
    params = {
        'variation': {'value': 'swirl'}, 'var2': {'value': 'sinusoidal'},
        'v_mix': {'value': 0.4}, 'seed': {'value': 88}, 'n_funcs': {'value': 5},
        'symmetry': {'value': 1}, 'n_iters': {'value': 12_000_000},
        'gamma': {'value': 2.2}, 'brightness': {'value': 1.0},
        'color_start': {'value': '#14B8A6'}, 'color_end': {'value': '#6366F1'},
        'background_color': {'value': '#080808'},
    }
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix='ffa_vortex_')
    print(f"  FF Flame Vortex: {n_frames} frames…")
    for i in range(n_frames):
        phase = 2 * math.pi * i / n_frames
        params['phase'] = {'value': phase}
        frame_base = _render_flame_base(params, width, height)
        
        # 0.30 hue swing — teal → indigo → magenta → back, clearly visible
        shift = 0.30 * math.sin(phase)
        arr = _hue_shift_array(np.array(frame_base), shift)
        PILImage.fromarray(arr).save(os.path.join(tmpdir, f'f_{i:05d}.png'))
        if i % (fps * 10) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_ff_flame_galaxy_loop(output_path, fps=30, duration_secs=40,
                                   width=1080, height=1350):
    """Fractal flame — julia+swirl sym=2, 180° rotational loop. Gold/midnight."""
    from PIL import Image as PILImage
    params = {
        'variation': {'value': 'julia'}, 'var2': {'value': 'swirl'},
        'v_mix': {'value': 0.3}, 'seed': {'value': 1618}, 'n_funcs': {'value': 5},
        'symmetry': {'value': 2}, 'n_iters': {'value': 12_000_000},
        'gamma': {'value': 2.2}, 'brightness': {'value': 1.0},
        'color_start': {'value': '#C8A96E'}, 'color_end': {'value': '#1E3A5F'},
        'background_color': {'value': '#080808'},
    }
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix='ffa_galaxy_')
    print(f"  FF Flame Galaxy: {n_frames} frames…")
    for i in range(n_frames):
        phase = 2 * math.pi * i / n_frames
        params['phase'] = {'value': phase}
        frame = _render_flame_base(params, width, height)
        frame.save(os.path.join(tmpdir, f'f_{i:05d}.png'))
        if i % (fps * 10) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


# ── Generic equation-based loop helpers ───────────────────────────────────

def _render_eq_pil(eq_type, params, width, height):
    """Render any equation type via renderer.py → PIL Image RGB at exact (width, height)."""
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from services.renderer import render_equation
    from PIL import Image as _PILImg
    # Ensure even dimensions (h264 requirement)
    w = width  + (width  % 2)
    h = height + (height % 2)
    png = render_equation(eq_type, params, width=width, height=height)
    img = _PILImg.open(io.BytesIO(png)).convert('RGB')
    if img.size != (w, h):
        img = img.resize((w, h), _PILImg.LANCZOS)
    return img


def _make_hue_loop(eq_type, params, output_path, fps, duration_secs, width, height, swing=0.30, label=''):
    from PIL import Image as PILImage
    print(f"  {label}: rendering base…")
    base_arr = np.array(_render_eq_pil(eq_type, params, width, height))
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix=f'hue_{label[:8].replace(" ","_")}_')
    print(f"  {label}: {n_frames} frames…")
    for i in range(n_frames):
        shift = swing * math.sin(2 * math.pi * i / n_frames)
        arr = _hue_shift_array(base_arr, shift)
        PILImage.fromarray(arr).save(os.path.join(tmpdir, f'f_{i:05d}.png'))
        if i % (fps * 10) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def _make_rotation_loop(eq_type, params, output_path, fps, duration_secs, width, height, period_deg=360, label=''):
    from PIL import Image as PILImage
    print(f"  {label}: rendering base…")
    base = _render_eq_pil(eq_type, params, width, height)
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix=f'rot_{label[:8].replace(" ","_")}_')
    print(f"  {label}: {n_frames} frames…")
    for i in range(n_frames):
        angle = (i / n_frames) * period_deg
        frame = base.rotate(angle, resample=PILImage.BICUBIC, expand=False)
        frame.save(os.path.join(tmpdir, f'f_{i:05d}.png'))
        if i % (fps * 10) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def _make_morph_loop(eq_type, param_list, output_path, fps, duration_secs, width, height, label=''):
    from PIL import Image as PILImage
    bases = []
    for i, params in enumerate(param_list):
        print(f"  {label}: keyframe {i+1}/{len(param_list)}…")
        bases.append(np.array(_render_eq_pil(eq_type, params, width, height)).astype(float))
    n_frames = fps * duration_secs
    n_keys = len(bases)
    tmpdir = tempfile.mkdtemp(prefix=f'morph_{label[:8].replace(" ","_")}_')
    print(f"  {label}: {n_frames} frames…")
    for i in range(n_frames):
        t = (i / n_frames) * n_keys
        k = int(t) % n_keys
        k2 = (k + 1) % n_keys
        alpha = t - int(t)
        arr = ((1 - alpha) * bases[k] + alpha * bases[k2]).astype(np.uint8)
        PILImage.fromarray(arr).save(os.path.join(tmpdir, f'f_{i:05d}.png'))
        if i % (fps * 10) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def _make_chladni_morph_loop(mode_a, mode_b, cs, ce, bg, output_path, fps,
                             duration_secs, width, height,
                             drive_k=280.0, breathe=0.07, hue_swing=0.0, label=''):
    """Dynamic Chladni plate: the nodal lines continuously reorganize as the
    drive frequency sweeps between two vibration modes.

    Physically this is a standing wave whose shape is a time-varying
    superposition of two plate eigenmodes A and B:

        Z(t) = cos(theta)*F_A + sin(theta)*F_B,   theta = 2*pi * frame/total

    The sand collects where Z ~ 0, so as theta advances the nodal set migrates
    A -> B -> A -> B and the figure visibly redraws itself — far livelier than
    rigidly rotating a single fixed pattern. theta spanning a full 2*pi makes
    the loop seamless.
    """
    from PIL import Image as PILImage, ImageFilter
    from scipy.ndimage import gaussian_filter
    from matplotlib.colors import LinearSegmentedColormap

    # Rectangular grid matching the output aspect (no vertical stretch). The
    # domain is inset by `pad` so we never sample exactly on the plate edges
    # (sin(m*0)=0 makes the whole perimeter a nodal line, which otherwise pools
    # sand into an ugly frame around the figure).
    pad = 0.32
    gh = 900
    gw = max(2, int(gh * width / height))
    y_max = np.pi * height / width
    x = np.linspace(pad, np.pi - pad, gw)
    y = np.linspace(pad, y_max - pad, gh)
    X, Y = np.meshgrid(x, y)

    def _field(mn):
        m, n = mn
        f = np.sin(m * X) * np.sin(n * Y) + np.sin(n * X) * np.sin(m * Y)
        return f / (np.abs(f).max() + 1e-10)

    field_a = _field(mode_a)
    field_b = _field(mode_b)

    # Granular sand texture computed ONCE so individual grains stay put frame to
    # frame (recomputing per frame would make the whole plate shimmer with noise).
    rng = np.random.default_rng(42 + mode_a[0] * 13 + mode_b[1] * 7)
    grain = 0.4 * rng.random((gh, gw)) + 0.6 * gaussian_filter(rng.random((gh, gw)), sigma=1.5)

    bg_rgb = tuple(int(bg.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4))
    cmap = LinearSegmentedColormap.from_list("mr_chladni", [bg_rgb, cs, ce])

    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix=f'chladni_{label[:8].replace(" ", "_")}_')
    ow, oh = width + (width % 2), height + (height % 2)
    print(f"  {label}: {n_frames} frames…")
    for i in range(n_frames):
        theta = 2 * math.pi * (i / n_frames)
        Z = math.cos(theta) * field_a + math.sin(theta) * field_b
        Z = Z / (np.abs(Z).max() + 1e-10)

        # Breathing line-width makes the sand visibly settle and scatter as the
        # plate is driven harder / softer through the sweep.
        k = drive_k * (1.0 + breathe * math.sin(2 * theta))
        sand = np.exp(-(Z ** 2) * k) + 0.12 * np.exp(-(Z ** 2) * 22)
        mask = (sand > 0.1).astype(float)
        sand_pattern = np.clip(sand * (0.5 + 0.5 * grain) * mask, 0, 1)

        rgba = (cmap(sand_pattern) * 255).astype(np.uint8)
        img = PILImage.fromarray(rgba, mode='RGBA').convert('RGB')
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
        if hue_swing:
            img = PILImage.fromarray(_hue_shift_array(np.array(img), hue_swing * math.sin(theta)))
        img = img.resize((ow, oh), PILImage.LANCZOS)
        img.save(os.path.join(tmpdir, f'f_{i:05d}.png'))
        if i % (fps * 5) == 0:
            print(f"    {i}/{n_frames}")

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def _chladni_morph_gen(mode_a, mode_b, cs, ce, bg, dur=20, hue_swing=0.0, label=''):
    def _g(output_path, fps=30, duration_secs=None, width=1080, height=1350):
        return _make_chladni_morph_loop(mode_a, mode_b, cs, ce, bg, output_path, fps,
                                        duration_secs or dur, width, height,
                                        hue_swing=hue_swing, label=label)
    return _g


def _hue_gen(eq_type, params, dur=20, swing=0.30, label=''):
    def _g(output_path, fps=30, duration_secs=None, width=1080, height=1350):
        return _make_hue_loop(eq_type, params, output_path, fps,
                              duration_secs or dur, width, height, swing=swing, label=label)
    return _g


def _rot_gen(eq_type, params, dur=20, period_deg=360, label=''):
    def _g(output_path, fps=30, duration_secs=None, width=1080, height=1350):
        return _make_rotation_loop(eq_type, params, output_path, fps,
                                   duration_secs or dur, width, height, period_deg=period_deg, label=label)
    return _g


def _morph_gen(eq_type, param_list, dur=25, label=''):
    def _g(output_path, fps=30, duration_secs=None, width=1080, height=1350):
        return _make_morph_loop(eq_type, param_list, output_path, fps,
                                duration_secs or dur, width, height, label=label)
    return _g


def _phase_gen(eq_type, params, phase_key, dur=20, label=''):
    def _g(output_path, fps=30, duration_secs=None, width=1080, height=1350):
        from PIL import Image as PILImage
        n_frames = fps * (duration_secs or dur)
        tmpdir = tempfile.mkdtemp(prefix=f'phase_{label[:8].replace(" ","_")}_')
        print(f"  {label}: {n_frames} frames…")
        
        base_phase = params.get(phase_key, {}).get('value', 0.0)
        
        for i in range(n_frames):
            t = i / n_frames
            # Linearly interpolate phase from base_phase to base_phase + 2*pi for a seamless mathematical loop
            current_phase = base_phase + (2.0 * np.pi * t)
            
            frame_params = {k: {"value": v["value"]} for k, v in params.items()}
            frame_params[phase_key]["value"] = current_phase
            
            frame_img = _render_eq_pil(eq_type, frame_params, width, height)
            frame_img.save(os.path.join(tmpdir, f'f_{i:05d}.png'))
            if i % (fps * 5) == 0: print(f"    {i}/{n_frames}")
            
        _encode_mp4(tmpdir, output_path, fps)
        _cleanup(tmpdir)
        return output_path
    return _g

# ── Harmonic Geometry loops ────────────────────────────────────────────────
_HG_CS, _HG_CE, _HG_BG = '#4338CA', '#F43F5E', '#080808'

generate_harmonic_hue1 = _phase_gen('lissajous',
    {'a': {'value': 3}, 'b': {'value': 2}, 'delta': {'value': 0.0},
     'color_start': {'value': _HG_CS}, 'color_end': {'value': _HG_CE}, 'background_color': {'value': _HG_BG}},
    phase_key='delta', dur=25, label='Harmonic Lissajous I')

generate_harmonic_hue2 = _phase_gen('lissajous',
    {'a': {'value': 5}, 'b': {'value': 4}, 'delta': {'value': 0.0},
     'color_start': {'value': '#10B981'}, 'color_end': {'value': '#3B82F6'}, 'background_color': {'value': _HG_BG}},
    phase_key='delta', dur=20, label='Harmonic Lissajous II')

generate_harmonic_hue3 = _phase_gen('harmonograph',
    {'f1': {'value': 2.01}, 'f2': {'value': 3.0}, 'f3': {'value': 3.0}, 'f4': {'value': 2.0},
     'd1': {'value': 0.004}, 'd2': {'value': 0.0065}, 'd3': {'value': 0.008}, 'd4': {'value': 0.019},
     'p1': {'value': 0.0}, 'p2': {'value': 0.0}, 'p3': {'value': 0.0}, 'p4': {'value': 0.0},
     'color_start': {'value': '#8B5CF6'}, 'color_end': {'value': '#EC4899'}, 'background_color': {'value': _HG_BG}},
    phase_key='p1', dur=30, label='Harmonograph III')

# ── Radial Symmetry loops ──────────────────────────────────────────────────
_RS_BG = '#080808'

generate_rose_spin = _phase_gen('rose',
    {'petals': {'value': 5}, 'phase': {'value': 0.0},
     'color_start': {'value': '#F472B6'}, 'color_end': {'value': '#FBBF24'}, 'background_color': {'value': _RS_BG}},
    phase_key='phase', dur=20, label='Rose Phase')

generate_superformula_spin = _phase_gen('superformula',
    {'m': {'value': 6}, 'phase': {'value': 0.0}, 'n1': {'value': 1.0}, 'n2': {'value': 1.0}, 'n3': {'value': 1.0},
     'color_start': {'value': '#A5F3FC'}, 'color_end': {'value': '#F0ABFC'}, 'background_color': {'value': _RS_BG}},
    phase_key='phase', dur=15, label='Superformula Phase I')

generate_superformula_hue = _phase_gen('superformula',
    {'m': {'value': 8}, 'phase': {'value': 0.0}, 'n1': {'value': 0.5}, 'n2': {'value': 1.7}, 'n3': {'value': 1.7},
     'color_start': {'value': '#C8A96E'}, 'color_end': {'value': '#6366F1'}, 'background_color': {'value': _RS_BG}},
    phase_key='phase', dur=25, label='Superformula Phase II')

# ── Reaction Diffusion loops ───────────────────────────────────────────────
_RD_BG = '#080808'


def _gs_seed(size, pattern_type, rng):
    """Initial U/V fields for the Gray-Scott simulation (mirrors renderer.py)."""
    u = np.ones((size, size)); v = np.zeros((size, size))
    mid = size // 2
    if pattern_type == 'coral':
        for _ in range(10):
            sx, sy = rng.integers(20, size - 20), rng.integers(20, size - 20)
            r = rng.integers(5, 15)
            u[sx-r:sx+r, sy-r:sy+r] = 0.5; v[sx-r:sx+r, sy-r:sy+r] = 0.25
    elif pattern_type == 'spots':
        for _ in range(18):
            sx, sy = rng.integers(0, size), rng.integers(0, size)
            r = rng.integers(3, 8)
            u[max(0,sx-r):min(size,sx+r), max(0,sy-r):min(size,sy+r)] = 0.5
            v[max(0,sx-r):min(size,sx+r), max(0,sy-r):min(size,sy+r)] = 0.25
    else:  # stripes
        for off in range(-60, 61, 14):
            x0 = mid + off
            u[20:size-20, max(0,x0-2):min(size,x0+2)] = 0.5
            v[20:size-20, max(0,x0-2):min(size,x0+2)] = 0.25
    u += 0.02 * rng.random((size, size)); v += 0.02 * rng.random((size, size))
    return u, v


def _make_gs_dynamic_loop(pattern_type, cs, ce, output_path, fps, duration_secs, width, height,
                          f=0.055, k=0.062, Du=0.16, Dv=0.08,
                          warmup=1500, steps_per_frame=13, label=''):
    """Run the Gray-Scott reaction-diffusion simulation and capture it AS IT
    EVOLVES — the pattern grows, divides and spreads. Frames are played forward
    then reversed (ping-pong), so the loop is seamless and reads as an organic
    pulse: the structure blooms and recedes instead of a frozen image recoloring.
    """
    from PIL import Image as PILImage
    from services.renderer import _make_cmap
    import io as _io

    cmap = _make_cmap(cs, ce)
    size = 256
    rng = np.random.default_rng(42)
    u, v = _gs_seed(size, pattern_type, rng)

    def laplacian(a):
        return (np.roll(a,1,0)+np.roll(a,-1,0)+np.roll(a,1,1)+np.roll(a,-1,1)-4*a)

    def step(u, v):
        uvv = u*v*v
        u = np.clip(u + Du*laplacian(u) - uvv + f*(1-u), 0, 1)
        v = np.clip(v + Dv*laplacian(v) + uvv - (f+k)*v, 0, 1)
        return u, v

    # Warm up so capture begins on real structure, not a blank field.
    for _ in range(warmup):
        u, v = step(u, v)

    total_frames = int(fps * duration_secs)
    n_unique = total_frames // 2 + 1   # ping-pong → ~half are unique renders
    tmpdir = tempfile.mkdtemp(prefix=f'gs_{label[:8].replace(" ","_")}_')
    print(f"  {label}: simulating {n_unique} keyframes…", flush=True)

    def render_frame(v):
        disp = (v - v.min()) / (v.max() - v.min() + 1e-10)
        gy, gx = np.gradient(v)
        edge = 1.0 + 0.35 * (np.sqrt(gx*gx+gy*gy) / (np.sqrt(gx*gx+gy*gy).max()+1e-10))
        shaded = np.clip(disp * edge, 0, 1)
        rgb = (cmap(shaded)[:, :, :3] * 255).astype(np.uint8)
        img = PILImage.fromarray(rgb).resize((width, height), PILImage.LANCZOS)
        return img

    # Render the unique evolving keyframes as u_*.png (not picked up by the
    # encoder, which reads f_*.png).
    for i in range(n_unique):
        render_frame(v).save(os.path.join(tmpdir, f'u_{i:05d}.png'))
        for _ in range(steps_per_frame):
            u, v = step(u, v)
        if i % (fps * 5) == 0:
            print(f"    {i}/{n_unique}", flush=True)

    # Ping-pong order (forward then back, skipping the two turning frames so
    # neither endpoint freezes), materialized as the contiguous f_*.png the
    # encoder expects.
    order = list(range(n_unique)) + list(range(n_unique - 2, 0, -1))
    order = order[:total_frames]
    for j, src_i in enumerate(order):
        os.symlink(os.path.join(tmpdir, f'u_{src_i:05d}.png'),
                   os.path.join(tmpdir, f'f_{j:05d}.png'))
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def _gs_dynamic_gen(pattern_type, cs, ce, dur=20, f=0.055, k=0.062, label=''):
    def _g(output_path, fps=30, duration_secs=None, width=1080, height=1350):
        return _make_gs_dynamic_loop(pattern_type, cs, ce, output_path, fps,
                                     duration_secs or dur, width, height,
                                     f=f, k=k, label=label)
    return _g


# Coral Pulse — coral fronds bloom outward and draw back, a living tide.
generate_gs_pulse1 = _gs_dynamic_gen('coral', '#14B8A6', '#F472B6',
                                     dur=20, f=0.055, k=0.062, label='GS Coral Pulse')
# Spot Pulse — spots emerge, divide (mitosis) and re-merge.
generate_gs_pulse2 = _gs_dynamic_gen('spots', '#FBBF24', '#6366F1',
                                     dur=25, f=0.035, k=0.065, label='GS Spots Pulse')
# Stripe Wave — stripes ripple and reorganize across the field.
generate_gs_wave   = _gs_dynamic_gen('stripes', '#C8A96E', '#4EC9B0',
                                     dur=30, f=0.025, k=0.055, label='GS Wave')

# ── Complex Plane loops ────────────────────────────────────────────────────
_CP_BG = '#080808'


def _make_cp_dynamic_loop(eq_type, base_params, anim, output_path, fps, duration_secs,
                          width, height, spin_deg=0.0, hue_swing=0.0, label=''):
    """Re-render the equation every frame with its shape parameters oscillating,
    so the mathematical STRUCTURE itself warps/breathes/swirls over a seamless
    loop — not just a static image being rotated or hue-shifted.

    anim: list of (param_name, amplitude, cycles, phase_offset). Each frame the
          param = base + amplitude*sin(2π*cycles*t + phase_offset). `cycles` must
          be an integer so the value returns to its start → seamless loop.
    spin_deg: optional whole-frame rotation across the loop (use a multiple of
              360 to stay seamless). hue_swing: optional ± hue oscillation.
    """
    from PIL import Image as PILImage
    n_frames = int(fps * duration_secs)
    tmpdir = tempfile.mkdtemp(prefix=f'cpdyn_{label[:8].replace(" ","_")}_')
    base_vals = {k: v['value'] for k, v in base_params.items()}
    bg_fill = _hex_rgb(base_params.get('background_color', {}).get('value', '#080808'))
    print(f"  {label}: {n_frames} dynamic frames…", flush=True)
    for i in range(n_frames):
        t = i / n_frames
        fp = {k: {'value': v} for k, v in base_vals.items()}
        for (name, amp, cycles, off) in anim:
            fp[name] = {'value': base_vals.get(name, 0.0) + amp * math.sin(2 * math.pi * cycles * t + off)}
        img = _render_eq_pil(eq_type, fp, width, height)
        if spin_deg:
            img = img.rotate(spin_deg * t, resample=PILImage.BICUBIC, expand=False, fillcolor=bg_fill)
        if hue_swing:
            img = PILImage.fromarray(_hue_shift_array(np.array(img), hue_swing * math.sin(2 * math.pi * t)))
        img.save(os.path.join(tmpdir, f'f_{i:05d}.png'))
        if i % (fps * 5) == 0:
            print(f"    {i}/{n_frames}", flush=True)
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def _cp_dynamic_gen(eq_type, base_params, anim, dur=25, spin_deg=0.0, hue_swing=0.0, label=''):
    def _g(output_path, fps=30, duration_secs=None, width=1080, height=1350):
        return _make_cp_dynamic_loop(eq_type, base_params, anim, output_path, fps,
                                     duration_secs or dur, width, height,
                                     spin_deg=spin_deg, hue_swing=hue_swing, label=label)
    return _g


def _make_mobius_flow_loop(p, q, cs, ce, bg, output_path, fps, duration_secs, width, height,
                           turns=1, n_bands=3, n_rings=22, hue_swing=0.0, breathe=0.42, label=''):
    """True Möbius FLOW — the whole grid of curves MOVES: every frame the entire
    Steiner-circle web is pushed through a time-varying Möbius transformation, so
    the lines themselves rotate around the two foci and breathe in and out (not
    just light travelling along static curves).

    In the cross-ratio coordinate w = (z-p)/(z-q) the transformation is a single
    complex multiply, m(t) = exp(breathe·sin 2πt) · exp(i·2π·turns·t): the angular
    part rotates the family of arcs through both foci, the radial breathing part
    expands/contracts the orbit circles. Both return to start at t=1 → seamless.
    """
    from PIL import Image as PILImage

    ow, oh = width + (width % 2), height + (height % 2)
    xspan = 1.7
    yspan = xspan * oh / ow
    c0 = np.array(_hex_rgb(cs), float) / 255.0
    c1 = np.array(_hex_rgb(ce), float) / 255.0

    # Static grid in w-space (transformed live each frame):
    #  · orbit circles |w| = r_k  (breathing makes these expand/contract)
    #  · arcs through both foci, arg(w) = θ_j  (rotation makes these sweep round)
    curves = []  # (w_points, tone)
    radii = np.concatenate([np.geomspace(0.14, 0.85, n_rings // 2),
                            np.geomspace(1.0 / 0.85, 1.0 / 0.14, n_rings // 2)])
    ang = np.linspace(0, 2 * np.pi, 600, endpoint=False)
    for k, r in enumerate(radii):
        curves.append((r * np.exp(1j * ang), k / max(len(radii) - 1, 1)))
    rho = np.geomspace(0.05, 20.0, 500)
    for j in range(18):
        th = 2 * math.pi * j / 18
        curves.append((rho * np.exp(1j * th), (j % 6) / 5.0))

    n_frames = int(fps * duration_secs)
    tmpdir = tempfile.mkdtemp(prefix=f'mflow_{label[:8].replace(" ", "_")}_')
    print(f"  {label}: {n_frames} flow frames…", flush=True)
    for i in range(n_frames):
        t = i / n_frames
        mult = math.exp(breathe * math.sin(2 * math.pi * t)) * np.exp(1j * 2 * math.pi * turns * t)
        fig, ax = plt.subplots(figsize=(ow / 100, oh / 100), dpi=100, facecolor=bg)
        ax.set_facecolor(bg)
        ax.set_xlim(-xspan, xspan); ax.set_ylim(-yspan, yspan)
        ax.set_axis_off()
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        for w0, tone in curves:
            w = mult * w0
            z = (q * w - p) / (w - 1.0)
            xr, yr = z.real, z.imag
            col = c0 * (1 - tone) + c1 * tone
            inview = np.isfinite(xr) & np.isfinite(yr) & (np.abs(xr) < xspan * 1.05) & (np.abs(yr) < yspan * 1.05)
            if not inview.any():
                continue
            rgba_g = np.zeros((len(xr), 4)); rgba_g[:, 0], rgba_g[:, 1], rgba_g[:, 2] = col; rgba_g[:, 3] = 0.28
            ax.scatter(xr[inview], yr[inview], c=rgba_g[inview], s=10.0, edgecolors='none')
            rgba = np.zeros((len(xr), 4)); rgba[:, 0], rgba[:, 1], rgba[:, 2] = col; rgba[:, 3] = 0.85
            ax.scatter(xr[inview], yr[inview], c=rgba[inview], s=3.2, edgecolors='none')
        fig.canvas.draw()
        buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
        buf = buf.reshape(fig.canvas.get_width_height()[::-1] + (4,))[:, :, :3]
        plt.close(fig)
        img = PILImage.fromarray(buf, 'RGB')
        if img.size != (ow, oh):
            img = img.resize((ow, oh), PILImage.LANCZOS)
        if hue_swing:
            img = PILImage.fromarray(_hue_shift_array(np.array(img), hue_swing * math.sin(2 * math.pi * t)))
        img.save(os.path.join(tmpdir, f'f_{i:05d}.png'))
        if i % (fps * 5) == 0:
            print(f"    {i}/{n_frames}", flush=True)

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def _mobius_flow_gen(p, q, cs, ce, bg, dur=25, turns=1, n_bands=3, hue_swing=0.0, breathe=0.42, label=''):
    def _g(output_path, fps=30, duration_secs=None, width=1080, height=1350):
        return _make_mobius_flow_loop(p, q, cs, ce, bg, output_path, fps,
                                      duration_secs or dur, width, height,
                                      turns=turns, n_bands=n_bands, hue_swing=hue_swing,
                                      breathe=breathe, label=label)
    return _g


def _make_joukowski_flow_loop(cs, ce, bg, output_path, fps, duration_secs, width, height,
                              mu=-0.10 + 0.10j, alpha_deg=14.0, n_stream=48, n_waves=7,
                              turns=1, hue_swing=0.0, label=''):
    """True Joukowski FLOW: potential-flow streamlines around the airfoil, with
    light coursing downstream along them — the aerodynamics the airfoil is famous
    for, instead of the foil shape merely hue-shifting.

    Flow is solved exactly around the generating cylinder |zeta-mu| = R (Kutta
    circulation set so the rear stagnation sits at the trailing edge), then mapped
    through the Joukowski transform z = zeta + 1/zeta. Streamlines are integrated
    once; each frame sweeps bright bands along their arc length, advancing a whole
    wavelength over the loop so it is seamless.
    """
    from PIL import Image as PILImage

    ow, oh = width + (width % 2), height + (height % 2)
    U = 1.0
    mu = complex(mu)
    R = abs(1 - mu)
    alpha = math.radians(alpha_deg)
    gamma_k = math.asin(max(-1.0, min(1.0, mu.imag / R)))
    Gamma = 4 * math.pi * U * R * math.sin(alpha + gamma_k)

    def f_prime(eta):
        return U * (np.exp(-1j * alpha) - R ** 2 * np.exp(1j * alpha) / eta ** 2) + Gamma / (2j * np.pi * eta)

    # Integrate streamlines from an upstream rake; flow wraps the cylinder.
    x0, ds, maxsteps = -3.4, 0.02, 1100
    streamlines = []
    for y0 in np.linspace(-2.8, 2.8, n_stream):
        eta = complex(x0, y0)
        pts = [eta]
        for _ in range(maxsteps):
            v = np.conj(f_prime(eta))
            sp = abs(v)
            if sp < 1e-9:
                break
            eta = eta + ds * v / sp
            if abs(eta - (- mu)) < R * 1.004 and abs(eta) < R * 1.004:
                break
            pts.append(eta)
            if eta.real > 3.4 or abs(eta.imag) > 3.2:
                break
        if len(pts) < 6:
            continue
        zeta = np.array(pts) + mu
        z = zeta + 1.0 / zeta
        d = np.abs(np.diff(z))
        s = np.concatenate([[0.0], np.cumsum(d)])
        s_norm = s / s[-1] if s[-1] > 0 else s
        tone = (y0 + 2.8) / 5.6
        streamlines.append((z.real, z.imag, s_norm, tone))

    # Airfoil outline (image of the cylinder) for a solid bright body.
    th = np.linspace(0, 2 * np.pi, 500)
    zeta_c = R * np.exp(1j * th) + mu
    z_c = zeta_c + 1.0 / zeta_c
    foil_x, foil_y = z_c.real, z_c.imag

    c0 = np.array(_hex_rgb(cs), float) / 255.0
    c1 = np.array(_hex_rgb(ce), float) / 255.0
    foil_rgb = tuple(0.5 * (c0 + c1))

    xspan = 2.9
    yspan = xspan * oh / ow

    n_frames = int(fps * duration_secs)
    tmpdir = tempfile.mkdtemp(prefix=f'jflow_{label[:8].replace(" ", "_")}_')
    print(f"  {label}: {n_frames} flow frames ({len(streamlines)} streamlines)…", flush=True)
    for i in range(n_frames):
        t = i / n_frames
        fig, ax = plt.subplots(figsize=(ow / 100, oh / 100), dpi=100, facecolor=bg)
        ax.set_facecolor(bg)
        ax.set_xlim(-xspan, xspan)
        ax.set_ylim(-yspan, yspan)
        ax.set_axis_off()
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        for xr, yr, sn, tone in streamlines:
            # The streamlines themselves undulate: a transverse ripple travels
            # downstream along each line (amplitude grows downstream), so the lines
            # visibly flow — not just light moving along static curves.
            disp = 0.07 * (0.25 + sn) * np.sin(2 * np.pi * (2.0 * sn - t))
            yr_t = yr + disp
            bright = 0.42 + 0.58 * (0.5 + 0.5 * np.cos(2 * np.pi * (n_waves * sn - turns * t))) ** 1.5
            col = c0 * (1 - tone) + c1 * tone
            rgba_g = np.zeros((len(sn), 4)); rgba_g[:, 0], rgba_g[:, 1], rgba_g[:, 2] = col
            rgba_g[:, 3] = bright * 0.5
            ax.scatter(xr, yr_t, c=rgba_g, s=10.0, edgecolors='none')
            rgba = np.zeros((len(sn), 4)); rgba[:, 0], rgba[:, 1], rgba[:, 2] = col
            rgba[:, 3] = bright
            ax.scatter(xr, yr_t, c=rgba, s=3.5, edgecolors='none')
        ax.fill(foil_x, foil_y, color=foil_rgb, zorder=5)
        ax.plot(foil_x, foil_y, color='white', lw=0.6, alpha=0.5, zorder=6)
        fig.canvas.draw()
        buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
        buf = buf.reshape(fig.canvas.get_width_height()[::-1] + (4,))[:, :, :3]
        plt.close(fig)
        img = PILImage.fromarray(buf, 'RGB')
        if img.size != (ow, oh):
            img = img.resize((ow, oh), PILImage.LANCZOS)
        if hue_swing:
            img = PILImage.fromarray(_hue_shift_array(np.array(img), hue_swing * math.sin(2 * math.pi * t)))
        img.save(os.path.join(tmpdir, f'f_{i:05d}.png'))
        if i % (fps * 5) == 0:
            print(f"    {i}/{n_frames}", flush=True)

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def _joukowski_flow_gen(cs, ce, bg, dur=20, alpha_deg=14.0, n_waves=7, turns=1, hue_swing=0.0, label=''):
    def _g(output_path, fps=30, duration_secs=None, width=1080, height=1350):
        return _make_joukowski_flow_loop(cs, ce, bg, output_path, fps,
                                         duration_secs or dur, width, height,
                                         alpha_deg=alpha_deg, n_waves=n_waves, turns=turns,
                                         hue_swing=hue_swing, label=label)
    return _g


# Möbius Flow — the whole Steiner-circle web rotates and breathes around two
# fixed points (a living double vortex). Motion is the star; hue barely shifts.
generate_mobius_spin = _mobius_flow_gen(
    -0.5 + 0j, 0.5 + 0j, '#C8A96E', '#4EC9B0', _CP_BG,
    dur=30, turns=1, n_bands=3, hue_swing=0.04, breathe=0.45, label='Mobius Flow')

# Joukowski Flow — potential-flow streamlines undulate and stream downstream
# around the airfoil: the aerodynamics the map is famous for.
generate_joukowski_hue = _joukowski_flow_gen(
    '#F472B6', '#FBBF24', _CP_BG,
    dur=20, alpha_deg=14.0, n_waves=7, turns=1, hue_swing=0.05, label='Joukowski Flow')

# Möbius Drift — vertically-stacked foci, web rotating the other way and
# breathing; reads distinctly from the horizontal Flow above.
generate_mobius_hue = _mobius_flow_gen(
    0 - 0.5j, 0 + 0.5j, '#A5F3FC', '#F0ABFC', _CP_BG,
    dur=25, turns=-1, n_bands=2, hue_swing=0.06, breathe=0.50, label='Mobius Drift')

# ── Turing Patterns loops ──────────────────────────────────────────────────
_TP_BG = '#080808'

generate_turing_shift1 = _hue_gen('turing',
    {'pattern_type': {'value': 'spots'},
     'color_start': {'value': '#FBBF24'}, 'color_end': {'value': '#6366F1'}, 'background_color': {'value': _TP_BG}},
    dur=20, swing=0.30, label='Turing Spots')


def generate_turing_spots_drift_loop(output_path, fps=30, duration_secs=20,
                                      width=1080, height=1350):
    """Turing spots with geometric drift, wave displacement, and hue cycling."""
    from PIL import Image as PILImage
    from scipy.ndimage import map_coordinates

    render_w = min(width, 720)
    render_h = round(render_w * height / width)
    params = {
        'pattern_type': {'value': 'spots'},
        'color_start': {'value': '#FBBF24'},
        'color_end': {'value': '#6366F1'},
        'background_color': {'value': _TP_BG},
    }
    print(f"  Turing Spots Drift: rendering base {render_w}x{render_h}...")
    base = np.array(_render_eq_pil('turing', params, render_w, render_h))
    h, w = base.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    amp = max(10.0, min(w, h) * 0.045)
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix='turing_drift_')
    print(f"  Turing Spots Drift: {n_frames} frames...")

    for i in range(n_frames):
        phase = 2 * math.pi * i / n_frames
        dx = amp * (
            np.sin((yy / h) * 2.0 * math.pi * 2.0 + phase) +
            0.45 * np.sin(((xx + yy) / (w + h)) * 2.0 * math.pi * 3.0 - phase)
        )
        dy = amp * (
            np.cos((xx / w) * 2.0 * math.pi * 2.0 - phase) +
            0.45 * np.cos(((xx - yy) / (w + h)) * 2.0 * math.pi * 3.0 + phase)
        )
        drift_x = (w * 0.045) * math.sin(phase)
        drift_y = (h * 0.035) * math.cos(phase)
        coords = np.array([
            (yy + dy + drift_y) % h,
            (xx + dx + drift_x) % w,
        ])
        warped = np.empty_like(base)
        for channel in range(3):
            warped[:, :, channel] = map_coordinates(
                base[:, :, channel], coords, order=1, mode='wrap'
            )

        # Breathing zoom keeps the geometry alive without breaking the loop.
        img = PILImage.fromarray(warped)
        zoom = 1.0 + 0.035 * (0.5 - 0.5 * math.cos(phase))
        if zoom > 1.001:
            zw, zh = int(w / zoom), int(h / zoom)
            left = (w - zw) // 2
            top = (h - zh) // 2
            img = img.crop((left, top, left + zw, top + zh)).resize((w, h), PILImage.Resampling.LANCZOS)

        arr = _hue_shift_array(np.array(img), 0.18 * math.sin(phase + math.pi / 5))
        frame = PILImage.fromarray(arr).resize((width, height), PILImage.Resampling.LANCZOS)
        frame.save(os.path.join(tmpdir, f'f_{i:05d}.png'), 'PNG')
        if i % (fps * 5) == 0:
            print(f"    {i}/{n_frames}")

    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


generate_turing_shift1 = generate_turing_spots_drift_loop

generate_turing_shift2 = _hue_gen('turing',
    {'pattern_type': {'value': 'stripes'},
     'color_start': {'value': '#F472B6'}, 'color_end': {'value': '#4EC9B0'}, 'background_color': {'value': _TP_BG}},
    dur=25, swing=0.35, label='Turing Stripes')

generate_turing_shift3 = _hue_gen('turing',
    {'pattern_type': {'value': 'labyrinth'},
     'color_start': {'value': '#C8A96E'}, 'color_end': {'value': '#A5F3FC'}, 'background_color': {'value': _TP_BG}},
    dur=30, swing=0.25, label='Turing Labyrinth')

# ── Voronoi Organics loops ─────────────────────────────────────────────────
_VO_BG = '#080808'

# Drifting seeds: each cell orbits its home position, so the whole mosaic
# slides, swells and shrinks — cells under a microscope. drift_phase 0→2π
# completes every orbit, so the loop is seamless.
generate_voronoi_hue1 = _phase_gen('voronoi',
    {'n_cells': {'value': 60}, 'organic': {'value': 0.5},
     'drift': {'value': 0.022}, 'drift_phase': {'value': 0.0},
     'color_start': {'value': '#14B8A6'}, 'color_end': {'value': '#F472B6'}, 'background_color': {'value': _VO_BG}},
    phase_key='drift_phase', dur=20, label='Voronoi Drift I')

generate_voronoi_hue2 = _phase_gen('voronoi',
    {'n_cells': {'value': 80}, 'organic': {'value': 0.7},
     'drift': {'value': 0.018}, 'drift_phase': {'value': 0.0},
     'color_start': {'value': '#C8A96E'}, 'color_end': {'value': '#6366F1'}, 'background_color': {'value': _VO_BG}},
    phase_key='drift_phase', dur=25, label='Voronoi Drift II')

generate_voronoi_hue3 = _phase_gen('voronoi',
    {'n_cells': {'value': 40}, 'organic': {'value': 0.3},
     'drift': {'value': 0.028}, 'drift_phase': {'value': 0.0},
     'color_start': {'value': '#A5F3FC'}, 'color_end': {'value': '#F0ABFC'}, 'background_color': {'value': _VO_BG}},
    phase_key='drift_phase', dur=15, label='Voronoi Drift III')

# ── Chladni Figures loops ──────────────────────────────────────────────────
_CF_BG = '#080808'

# Dynamic plates: the nodal lines morph between two vibration modes (the plate
# driven through a frequency sweep), so the sand visibly redraws itself instead
# of a single fixed figure merely spinning.
generate_chladni_spin1 = _chladni_morph_gen(
    (5, 4), (8, 7), '#C8A96E', '#4EC9B0', _CF_BG,
    dur=20, label='Chladni Morph I')        # (5,4) ↔ (8,7)

generate_chladni_spin2 = _chladni_morph_gen(
    (4, 7), (9, 5), '#F472B6', '#FBBF24', _CF_BG,
    dur=15, label='Chladni Morph II')       # (4,7) ↔ (9,5)

generate_chladni_hue = _chladni_morph_gen(
    (6, 5), (7, 8), '#A5F3FC', '#F0ABFC', _CF_BG,
    dur=25, hue_swing=0.18, label='Chladni Morph III')  # (6,5) ↔ (7,8) + glow

# ── De Jong Attractor loops ────────────────────────────────────────────────
_DJ_BG = '#080808'
_DEJONG_PRESETS = [
    {'a': {'value': -2.0}, 'b': {'value': -2.0}, 'c': {'value': -1.2}, 'd': {'value':  2.0},
     'color_start': {'value': '#14B8A6'}, 'color_end': {'value': '#F472B6'}, 'background_color': {'value': _DJ_BG}},
    {'a': {'value':  1.4}, 'b': {'value': -2.3}, 'c': {'value':  2.4}, 'd': {'value': -2.1},
     'color_start': {'value': '#FBBF24'}, 'color_end': {'value': '#6366F1'}, 'background_color': {'value': _DJ_BG}},
    {'a': {'value': -1.5}, 'b': {'value': -2.3}, 'c': {'value':  1.6}, 'd': {'value': -1.9},
     'color_start': {'value': '#A5F3FC'}, 'color_end': {'value': '#F0ABFC'}, 'background_color': {'value': _DJ_BG}},
    {'a': {'value':  1.7}, 'b': {'value': -1.9}, 'c': {'value': -2.0}, 'd': {'value': -1.3},
     'color_start': {'value': '#C8A96E'}, 'color_end': {'value': '#4EC9B0'}, 'background_color': {'value': _DJ_BG}},
    {'a': {'value':  2.0}, 'b': {'value': -1.5}, 'c': {'value':  1.5}, 'd': {'value': -2.0},
     'color_start': {'value': '#F472B6'}, 'color_end': {'value': '#FBBF24'}, 'background_color': {'value': _DJ_BG}},
]

def _dejong_frame(a, b, c, d, width, height, cs_rgb, ce_rgb, bg_rgb,
                  n_points=450_000, bins=760):
    from scipy.ndimage import gaussian_filter

    x, y = 0.1, 0.1
    xs = np.empty(n_points, dtype=np.float32)
    ys = np.empty(n_points, dtype=np.float32)
    for i in range(n_points):
        xn = math.sin(a * y) - math.cos(b * x)
        yn = math.sin(c * x) - math.cos(d * y)
        x, y = xn, yn
        xs[i], ys[i] = x, y

    hist, xe, ye = np.histogram2d(xs, ys, bins=bins)
    img = np.log1p(hist.T)
    img = gaussian_filter(img, sigma=0.55)
    img = img / (img.max() + 1e-10)
    img = img ** 0.55

    rgb = np.zeros((bins, bins, 3), dtype=np.uint8)
    mask = img > 0.004
    for k in range(3):
        grad = cs_rgb[k] * (1 - img) + ce_rgb[k] * img
        rgb[:, :, k] = np.where(mask, grad, bg_rgb[k]).astype(np.uint8)

    pil = Image.fromarray(rgb)
    ratio = height / width
    target_h = min(bins, int(bins * ratio))
    if target_h < bins:
        top = (bins - target_h) // 2
        pil = pil.crop((0, top, bins, top + target_h))
    return pil.resize((width, height), Image.Resampling.LANCZOS)


def _hex_rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def generate_dejong_morph(output_path, fps=30, duration_secs=30,
                          width=1080, height=1350):
    """Dynamic De Jong particle swarm with parameter morph, orbit, and zoom."""
    from scipy.ndimage import gaussian_filter

    render_w = min(width, 720)
    render_h = round(render_w * height / width)
    motion_presets = _DEJONG_PRESETS[1:]
    presets = [
        (
            p['a']['value'], p['b']['value'], p['c']['value'], p['d']['value'],
            _hex_rgb(p['color_start']['value']),
            _hex_rgb(p['color_end']['value']),
        )
        for p in motion_presets
    ]
    bg = np.array(_hex_rgb(_DJ_BG), dtype=np.float32)
    rng = np.random.default_rng(314159)
    n_particles = 240_000
    x = rng.uniform(-2.0, 2.0, n_particles).astype(np.float32)
    y = rng.uniform(-2.0, 2.0, n_particles).astype(np.float32)
    n_frames = fps * duration_secs
    n_keys = len(presets)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "17",
        "-preset", "medium",
        "-movflags", "+faststart",
        output_path,
    ]

    def state_at(frame_index):
        u = (frame_index / n_frames) * n_keys
        k = int(u) % n_keys
        k2 = (k + 1) % n_keys
        alpha = _smoothstep(u - int(u))
        p0, p1 = presets[k], presets[k2]
        vals = [(1 - alpha) * p0[j] + alpha * p1[j] for j in range(4)]
        phase = 2 * math.pi * frame_index / n_frames
        vals[0] += 0.12 * math.sin(phase * 2.0)
        vals[1] += 0.10 * math.cos(phase * 2.7)
        vals[2] += 0.10 * math.sin(phase * 3.3 + 0.6)
        vals[3] += 0.12 * math.cos(phase * 2.2 + 0.4)
        cs = np.array([(1 - alpha) * p0[4][j] + alpha * p1[4][j] for j in range(3)], dtype=np.float32)
        ce = np.array([(1 - alpha) * p0[5][j] + alpha * p1[5][j] for j in range(3)], dtype=np.float32)
        return vals, cs, ce, phase

    def step_particles(a, b, c, d):
        nonlocal x, y
        xn = np.sin(a * y) - np.cos(b * x)
        yn = np.sin(c * x) - np.cos(d * y)
        x, y = xn.astype(np.float32), yn.astype(np.float32)

    first_vals, _, _, _ = state_at(0)
    print("  De Jong Morph Dynamic: warming particle field...", flush=True)
    for _ in range(80):
        step_particles(*first_vals)

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    trail = None
    try:
        print(f"  De Jong Morph Dynamic: streaming {n_frames} frames to ffmpeg...", flush=True)
        for i in range(n_frames):
            (a, b, c, d), cs, ce, phase = state_at(i)
            for _ in range(3):
                step_particles(a, b, c, d)
            if i % 3 == 0:
                n_reset = n_particles // 120
                reset_idx = rng.integers(0, n_particles, n_reset)
                x[reset_idx] = rng.uniform(-2.0, 2.0, n_reset)
                y[reset_idx] = rng.uniform(-2.0, 2.0, n_reset)

            angle = 0.22 * math.sin(phase * 1.15) + 0.12 * math.sin(phase * 2.0 + 0.4)
            ca, sa = math.cos(angle), math.sin(angle)
            zoom = 1.05 + 0.12 * math.sin(phase * 1.7 + 0.5)
            pan_x = 0.13 * math.sin(phase * 1.3)
            pan_y = 0.11 * math.cos(phase * 1.1 + 0.7)
            xr = (x * ca - y * sa) / zoom + pan_x
            yr = (x * sa + y * ca) / zoom + pan_y

            px = ((xr + 2.35) / 4.70 * render_w).astype(np.int32)
            py = ((2.35 - yr) / 4.70 * render_h).astype(np.int32)
            valid = (px >= 0) & (px < render_w) & (py >= 0) & (py < render_h)
            hist = np.zeros((render_h, render_w), dtype=np.float32)
            np.add.at(hist, (py[valid], px[valid]), 1.0)

            density = np.log1p(hist)
            density = gaussian_filter(density, sigma=0.65)
            vmax = np.percentile(density[density > 0], 99.2) if np.any(density > 0) else 1.0
            density = np.clip(density / (vmax + 1e-6), 0, 1) ** 0.38
            glow = gaussian_filter(density, sigma=2.0)
            intensity = np.clip(density * 1.35 + glow * 0.55, 0, 1)
            grad = cs * (1 - density[..., None]) + ce * density[..., None]
            frame = bg * (1 - intensity[..., None]) + grad * intensity[..., None]
            if trail is not None:
                frame = frame * 0.76 + trail * 0.24
            trail = frame
            arr = Image.fromarray(frame.clip(0, 255).astype(np.uint8), "RGB")
            arr = arr.resize((width, height), Image.Resampling.LANCZOS)
            proc.stdin.write(np.ascontiguousarray(np.array(arr)).tobytes())
            if i % (fps * 5) == 0:
                print(f"    {i}/{n_frames}", flush=True)
    finally:
        if proc.stdin:
            proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed while encoding De Jong Morph")
    return output_path

generate_dejong_hue1 = _hue_gen('de_jong',
    {'a': {'value': 1.7}, 'b': {'value': -1.9}, 'c': {'value': -2.0}, 'd': {'value': -1.3},
     'color_start': {'value': '#14B8A6'}, 'color_end': {'value': '#F472B6'}, 'background_color': {'value': _DJ_BG}},
    dur=25, swing=0.30, label='De Jong Hue I')

generate_dejong_hue2 = _hue_gen('de_jong',
    {'a': {'value': 2.01}, 'b': {'value': -2.53}, 'c': {'value': 1.61}, 'd': {'value': -0.33},
     'color_start': {'value': '#C8A96E'}, 'color_end': {'value': '#6366F1'}, 'background_color': {'value': _DJ_BG}},
    dur=20, swing=0.35, label='De Jong Hue II')

# ── Particle Systems ──────────────────────────────────────────────────────────

def _particles_to_image(width, height, px, py, weights, blur_r, color_dim, color_bright, bg_rgb):
    """Render N particles into a PIL image via 2D histogram + glow."""
    from PIL import Image as PILImg, ImageFilter
    x_bins = np.linspace(0, 1, width + 1)
    y_bins = np.linspace(0, 1, height + 1)
    density, _, _ = np.histogram2d(px, py, bins=[x_bins, y_bins], weights=weights)
    density = density.T  # (H, W)
    vmax = np.percentile(density, 99.5) if density.max() > 0 else 1.0
    density = np.clip(density / (vmax + 1e-8), 0, 1)
    d3 = density[:, :, np.newaxis]
    ca = np.array(color_dim,    dtype=np.float32)
    cb = np.array(color_bright, dtype=np.float32)
    bg = np.array(bg_rgb,       dtype=np.float32)
    arr = bg * (1 - d3) + (ca + (cb - ca) * d3) * d3 * 3
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = PILImg.fromarray(arr, 'RGB')
    glow = img.filter(ImageFilter.GaussianBlur(radius=blur_r))
    return PILImg.blend(img, glow, 0.55)


def _particles_accumulate(width, height, all_px, all_py, all_w,
                           blur_r, color_dim, color_bright, bg_rgb, gamma=0.45):
    """Accumulate many frames of particle positions into one dense static image.
    Uses log-density mapping so dim particles remain visible."""
    from PIL import Image as PILImg, ImageFilter
    x_bins = np.linspace(0, 1, width + 1)
    y_bins = np.linspace(0, 1, height + 1)
    density, _, _ = np.histogram2d(all_px, all_py, bins=[x_bins, y_bins], weights=all_w)
    density = density.T
    # Log-density: lifts dim regions so every particle is visible
    density = np.log1p(density)
    vmax = density.max() if density.max() > 0 else 1.0
    density = density / vmax
    # Gamma correction: pull mid-tones up
    density = density ** gamma
    d3 = density[:, :, np.newaxis]
    ca = np.array(color_dim,    dtype=np.float32)
    cb = np.array(color_bright, dtype=np.float32)
    bg = np.array(bg_rgb,       dtype=np.float32)
    arr = bg * (1 - d3) + (ca + (cb - ca) * d3) * d3 * 2.5
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = PILImg.fromarray(arr, 'RGB')
    glow = img.filter(ImageFilter.GaussianBlur(radius=blur_r))
    return PILImg.blend(img, glow, 0.6)


def generate_particle_vortex(output_path, fps=30, duration_secs=20,
                              width=1080, height=1350):
    """Particle tunnel vortex — spiraling stream from far to near."""
    width, height = width + width % 2, height + height % 2
    rng = np.random.default_rng(7)
    N = 70000
    z0     = rng.random(N)
    theta0 = rng.uniform(0, 2 * np.pi, N)
    r_seed = rng.exponential(0.35, N).clip(0.02, 1.0)
    swirl_ph = rng.uniform(0, 2 * np.pi, N)
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="pvortex_")
    print(f"  Particle Vortex: {n_frames} frames…")
    for i in range(n_frames):
        t = i / n_frames
        z = (z0 + t) % 1.0
        # 4 turns + a per-particle turbulent swirl that tightens near the throat
        # (both seamless over the loop) → a churning vortex, not a steady spin.
        theta = (theta0 + 2 * np.pi * 4 * t
                 + 0.45 * (1.2 - z) * np.sin(2 * np.pi * t + swirl_ph))
        r = r_seed * (1.0 - z ** 1.4) * 0.46
        x2d = 0.5 + r * np.cos(theta)
        y2d = 0.52 + r * np.sin(theta) * (width / height)
        frame = _particles_to_image(width, height, x2d, y2d, z ** 0.6,
                                    3, (25, 15, 90), (180, 230, 255), (2, 2, 8))
        frame.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps * 5) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_particle_nebula(output_path, fps=30, duration_secs=25,
                              width=1080, height=1350):
    """Roiling 3D nebula — the cloud tumbles on two axes while every particle
    swirls on its own little orbit and the whole cloud breathes, so it churns
    like gas rather than rigidly spinning."""
    width, height = width + width % 2, height + height % 2
    rng = np.random.default_rng(13)
    N = 60000
    # 3D Gaussian cloud
    x3 = rng.normal(0, 0.22, N)
    y3 = rng.normal(0, 0.22, N)
    z3 = rng.normal(0, 0.10, N)
    r3 = np.sqrt(x3**2 + y3**2 + z3**2)
    swirl = 0.085
    ph1 = rng.uniform(0, 2 * np.pi, N)
    ph2 = rng.uniform(0, 2 * np.pi, N)
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="pnebula_")
    print(f"  Particle Nebula: {n_frames} frames…")
    for i in range(n_frames):
        t = i / n_frames
        tau = 2 * np.pi * t
        # Per-particle turbulent swirl (seamless: period 1) — gas churning.
        xs = x3 + swirl * np.sin(tau + ph1)
        ys = y3 + swirl * np.cos(tau + ph2)
        zs = z3 + swirl * 0.6 * np.sin(tau + ph1 + ph2)
        # Tumble on Y, gentle wobble on X.
        ca, sa = np.cos(tau), np.sin(tau)
        xr = xs * ca - zs * sa
        zr = xs * sa + zs * ca
        wob = 0.20 * np.sin(tau)
        cw, sw = np.cos(wob), np.sin(wob)
        yr = ys * cw - zr * sw
        x2d = 0.5 + xr
        y2d = 0.5 + yr * (height / width)
        brightness = np.exp(-r3 * 2.5) * (0.7 + 0.3 * np.sin(tau + ph1))
        frame = _particles_to_image(width, height, x2d, y2d, brightness,
                                    4, (100, 20, 60), (255, 160, 80), (4, 2, 8))
        frame.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps * 5) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_particle_storm(output_path, fps=30, duration_secs=20,
                             width=1080, height=1350):
    """Electric storm — high-density particles on a chaotic field."""
    width, height = width + width % 2, height + height % 2
    rng = np.random.default_rng(99)
    N = 90000
    px0 = rng.random(N)
    py0 = rng.random(N)
    # Two frequency components for rich turbulence
    freq1, freq2 = 3.2, 7.1
    phase = rng.uniform(0, 2 * np.pi, N)
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="pstorm_")
    print(f"  Particle Storm: {n_frames} frames…")
    for i in range(n_frames):
        t = i / n_frames
        tau = 2 * np.pi * t
        # Wider Lissajous swirl as a periodic DISPLACEMENT of the fixed base
        # positions (cleanly seamless, unlike a cumulative random walk).
        px = (px0 + 0.05 * np.sin(freq1 * 2 * np.pi * py0 + phase + tau)) % 1.0
        py = (py0 + 0.05 * np.cos(freq2 * 2 * np.pi * px0 + phase + tau)) % 1.0
        # Electric crackle: sharp brightness bursts a few times per loop.
        crackle = (0.5 + 0.5 * np.sin(3 * tau + phase)) ** 6
        brightness = (0.45 + 0.35 * np.sin(phase + tau) + 0.5 * crackle).clip(0.1, 1.3)
        frame = _particles_to_image(width, height, px, py, brightness,
                                    2, (10, 30, 120), (200, 240, 255), (2, 3, 10))
        frame.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps * 5) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_particle_galaxy(output_path, fps=30, duration_secs=30,
                              width=1080, height=1350):
    """Spiral galaxy with DIFFERENTIAL rotation — the core whirls faster than the
    rim so the arms wind up and shear, plus per-star twinkle. Rigid spinning is
    replaced by real galactic dynamics."""
    width, height = width + width % 2, height + height % 2
    rng = np.random.default_rng(21)
    N = 80000
    # Logarithmic spiral arms (2 arms, offset by π)
    arm_idx = rng.integers(0, 2, N)
    t_param = rng.exponential(0.4, N).clip(0.01, 2.5)
    theta0 = t_param * 2.8 + arm_idx * np.pi + rng.normal(0, 0.25, N)
    r_arm = 0.085 * np.exp(0.35 * t_param)        # larger so it fills the frame
    brightness0 = np.exp(-t_param * 0.9)
    # Differential rotation: inner stars complete more whole turns over the loop
    # than outer ones (flat-ish rotation curve). Keeping the per-star turn count
    # an INTEGER guarantees every star returns to its start → seamless loop.
    turns = np.maximum(1, np.round(1 + 3.0 / (1 + r_arm / 0.085))).astype(np.float64)
    twinkle_ph = rng.uniform(0, 2 * np.pi, N)
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="pgalaxy_")
    print(f"  Particle Galaxy: {n_frames} frames…")
    for i in range(n_frames):
        t = i / n_frames
        theta = theta0 + 2 * np.pi * turns * t        # differential, seamless per star
        xr = r_arm * np.cos(theta)
        yr = r_arm * np.sin(theta)
        x2d = 0.5 + xr
        y2d = 0.5 + yr * (width / height)
        weight = brightness0 * (0.62 + 0.38 * np.sin(twinkle_ph + 2 * np.pi * 2 * t))
        frame = _particles_to_image(width, height, x2d, y2d, weight,
                                    4, (80, 60, 20), (255, 240, 180), (3, 3, 5))
        frame.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps * 5) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


def generate_particle_wave(output_path, fps=30, duration_secs=15,
                            width=1080, height=1350):
    """Standing wave pattern of particles — interference fringes."""
    width, height = width + width % 2, height + height % 2
    rng = np.random.default_rng(55)
    N = 60000
    px0 = rng.random(N)
    py0 = rng.random(N)
    n_frames = fps * duration_secs
    tmpdir = tempfile.mkdtemp(prefix="pwave_")
    print(f"  Particle Wave: {n_frames} frames…")
    for i in range(n_frames):
        t = i / n_frames
        # Three interfering travelling waves (two axial + one diagonal) make the
        # fringes shift and beat instead of sitting still.
        w1 = np.sin(2 * np.pi * (6 * px0 - t * 2))
        w2 = np.sin(2 * np.pi * (6 * py0 - t * 3))
        w3 = np.sin(2 * np.pi * (5 * (px0 + py0) * 0.707 - t * 1))
        interference = ((w1 * w2) + w3 + 2) / 4.0          # ~0..1
        brightness = np.clip(interference, 0, 1) ** 1.4
        # Larger wave-driven displacement so the particle sheet visibly ripples.
        px = (px0 + 0.030 * np.sin(2 * np.pi * (4 * py0 + t))) % 1.0
        py = (py0 + 0.030 * np.cos(2 * np.pi * (4 * px0 - t))) % 1.0
        frame = _particles_to_image(width, height, px, py, brightness,
                                    3, (10, 60, 80), (80, 240, 220), (2, 5, 8))
        frame.save(os.path.join(tmpdir, f"f_{i:05d}.png"), "PNG")
        if i % (fps * 5) == 0: print(f"    {i}/{n_frames}")
    _encode_mp4(tmpdir, output_path, fps)
    _cleanup(tmpdir)
    return output_path


# ── Particle static image generators (accumulate full loop → max density) ────

def render_particle_vortex_static(output_path, width=2160, height=2700):
    """Vortex tunnel — perspective cone of spiraling particles filling the canvas."""
    width, height = width + width % 2, height + height % 2
    rng = np.random.default_rng(7)
    N = 1_000_000
    # Cylindrical coords: z=depth(0=bottom/near, 1=top/far), theta=angle, r=ring radius
    z      = rng.random(N)
    theta  = rng.uniform(0, 2 * np.pi, N)
    r_spread = rng.normal(0, 0.04, N)          # thin ring with slight blur
    # Tunnel cone: outer radius grows with z (far=wide, near=narrow)
    r_cone = 0.45 * z + 0.02 + np.abs(r_spread)
    # Perspective foreshortening: far particles compressed toward center
    fov = 1.8
    scale = fov / (fov + (1 - z) * 1.5)
    x2d = 0.5 + r_cone * np.cos(theta) * scale
    y2d = 0.35 + (0.55 * z + r_cone * np.sin(theta) * 0.35) * scale
    brightness = 0.3 + 0.7 * z                 # far particles brighter (lit from top)
    img = _particles_accumulate(width, height, x2d, y2d, brightness,
                                blur_r=5, color_dim=(20, 10, 80),
                                color_bright=(160, 210, 255), bg_rgb=(2, 2, 8), gamma=0.5)
    img.save(output_path, "JPEG", quality=95)
    return output_path


def render_particle_nebula_static(output_path, width=2160, height=2700):
    """3D nebula cloud at 30° tilt — reveals depth and fills full canvas."""
    width, height = width + width % 2, height + height % 2
    rng = np.random.default_rng(13)
    N = 1_000_000
    # Multiple Gaussian shells for layered nebula look
    x3 = np.concatenate([rng.normal(0, s, N // 3) for s in (0.30, 0.18, 0.08)])
    y3 = np.concatenate([rng.normal(0, s, N // 3) for s in (0.30, 0.18, 0.08)])
    z3 = np.concatenate([rng.normal(0, s, N // 3) for s in (0.12, 0.07, 0.04)])
    r3 = np.sqrt(x3**2 + y3**2 + z3**2)
    # Rotate 30° on Y axis for visible 3D structure
    angle = np.radians(30)
    xr = x3 * np.cos(angle) - z3 * np.sin(angle)
    brightness = np.exp(-r3 * 1.8)
    x2d = 0.5 + xr
    y2d = 0.5 + y3 * (height / width)
    img = _particles_accumulate(width, height, x2d, y2d, brightness,
                                blur_r=7, color_dim=(90, 15, 50),
                                color_bright=(255, 150, 70), bg_rgb=(3, 2, 7), gamma=0.48)
    img.save(output_path, "JPEG", quality=95)
    return output_path


def render_particle_storm_static(output_path, width=2160, height=2700):
    """Electric storm — single frame of 1M particles at peak interference."""
    width, height = width + width % 2, height + height % 2
    rng = np.random.default_rng(99)
    N = 1_000_000
    px0 = rng.random(N)
    py0 = rng.random(N)
    freq1, freq2 = 3.2, 7.1
    phase = rng.uniform(0, 2 * np.pi, N)
    # Use t=0.37 — empirically the frame with highest contrast
    t = 0.37
    dx = 0.018 * np.sin(freq1 * 2 * np.pi * py0 + phase + 2 * np.pi * t)
    dy = 0.018 * np.cos(freq2 * 2 * np.pi * px0 + phase + 2 * np.pi * t)
    px = (px0 + dx * 8) % 1.0       # exaggerate displacement for static
    py = (py0 + dy * 8) % 1.0
    brightness = (0.5 + 0.5 * np.sin(phase + freq1 * px * 6)).clip(0.05, 1.0)
    brightness = brightness ** 1.8   # increase contrast
    img = _particles_accumulate(width, height, px, py, brightness,
                                blur_r=4, color_dim=(8, 25, 110),
                                color_bright=(190, 230, 255), bg_rgb=(2, 3, 10), gamma=0.6)
    img.save(output_path, "JPEG", quality=95)
    return output_path


def render_particle_galaxy_static(output_path, width=2160, height=2700):
    """Spiral galaxy — 2 arms filling the full canvas."""
    width, height = width + width % 2, height + height % 2
    rng = np.random.default_rng(21)
    N = 1_000_000
    arm_idx = rng.integers(0, 2, N)
    # Uniform t so every radius from center to edge is equally sampled
    t_param = rng.uniform(0.01, 3.8, N)
    theta_arm = t_param * 2.5 + arm_idx * np.pi + rng.normal(0, 0.20, N)
    # r scales so r_max(t=3.8) ≈ 0.44 → fills canvas edge-to-edge
    r_arm = 0.148 * np.exp(0.30 * t_param)
    x3 = r_arm * np.cos(theta_arm)
    y3 = r_arm * np.sin(theta_arm) * (width / height)
    brightness = np.exp(-t_param * 0.35)     # bright center, visible outer arms
    x2d = 0.5 + x3
    y2d = 0.5 + y3
    img = _particles_accumulate(width, height, x2d, y2d, brightness,
                                blur_r=6, color_dim=(70, 50, 10),
                                color_bright=(255, 245, 190), bg_rgb=(3, 3, 5), gamma=0.55)
    img.save(output_path, "JPEG", quality=95)
    return output_path


def render_particle_wave_static(output_path, width=2160, height=2700):
    """Wave interference — 1M particles showing full standing wave pattern."""
    width, height = width + width % 2, height + height % 2
    rng = np.random.default_rng(55)
    N = 1_000_000
    px0 = rng.random(N)
    py0 = rng.random(N)
    # Standing wave interference at t=0 (no time evolution needed — pattern is spatial)
    w1 = np.sin(2 * np.pi * 7 * px0)
    w2 = np.sin(2 * np.pi * 7 * py0)
    w3 = np.sin(2 * np.pi * 5 * (px0 + py0))
    interference = ((w1 * w2 + w3 + 2) / 4).clip(0, 1)
    brightness = interference ** 1.4
    img = _particles_accumulate(width, height, px0, py0, brightness,
                                blur_r=5, color_dim=(8, 50, 70),
                                color_bright=(70, 230, 210), bg_rgb=(2, 5, 8), gamma=0.55)
    img.save(output_path, "JPEG", quality=95)
    return output_path


# ── Registry: map animation names to generators ────────────────────────────

ANIMATION_GENERATORS = {
    "lorenz_flow": {
        "fn": generate_lorenz_loop,
        "default_duration": 30,
        "default_params": {"sigma": 10.0, "rho": 28.0, "beta": 2.667},
    },
    "clifford_spin": {
        "fn": generate_clifford_loop,
        "default_duration": 20,
        "default_params": {"a": -1.4, "b": 1.6, "c": 1.0, "d": 0.7},
    },
    "clifford_nebula": {
        "fn": generate_clifford_nebula,
        "default_duration": 20,
        "default_params": {"a": -1.7, "b": 1.8, "c": -0.9, "d": 0.4},
    },
    "clifford_spiral": {
        "fn": generate_clifford_spiral,
        "default_duration": 20,
        "default_params": {"a": 1.5, "b": -1.4, "c": 1.0, "d": 0.5},
    },
    "clifford_bloom": {
        "fn": generate_clifford_bloom,
        "default_duration": 20,
        "default_params": {"a": -1.2, "b": -1.1, "c": 1.0, "d": 1.1},
    },
    "aizawa_dance": {
        "fn": generate_aizawa_loop,
        "default_duration": 25,
        "default_params": {"a": 0.95, "b": 0.7, "c": 0.6, "d": 3.5, "e": 0.25, "f": 0.1},
    },
    "attractor_morph": {
        "fn": generate_morph_loop,
        "default_duration": 30,
        "default_params": {},
    },
    "lorenz_drift": {
        "fn": generate_drift_loop,
        "default_duration": 60,
        "default_params": {"sigma": 10.0, "rho": 28.0, "beta": 2.667},
    },
    "ff_origin": {
        "fn": generate_ff_origin_loop,
        "default_duration": 30,
        "default_params": {},
    },
    "ff_vortex": {
        "fn": generate_ff_vortex_loop,
        "default_duration": 25,
        "default_params": {},
    },
    "ff_aurora": {
        "fn": generate_ff_aurora_loop,
        "default_duration": 40,
        "default_params": {},
    },
    "ff_turbulence": {
        "fn": generate_ff_turbulence_loop,
        "default_duration": 20,
        "default_params": {},
    },
    "ff_tide": {
        "fn": generate_ff_tide_loop,
        "default_duration": 45,
        "default_params": {},
    },
    "julia_zoom1": {
        "fn": generate_julia_zoom1_loop,
        "default_duration": 30,
        "default_params": {},
    },
    "julia_zoom2": {
        "fn": generate_julia_zoom2_loop,
        "default_duration": 45,
        "default_params": {},
    },
    "julia_morph": {
        "fn": generate_julia_morph_loop,
        "default_duration": 30,
        "default_params": {},
    },
    "ff_flame_aurora":  {"fn": generate_ff_flame_aurora_loop,  "default_duration": 30, "default_params": {}},
    "ff_flame_phoenix": {"fn": generate_ff_flame_phoenix_loop, "default_duration": 25, "default_params": {}},
    "ff_flame_crystal": {"fn": generate_ff_flame_crystal_loop, "default_duration": 20, "default_params": {}},
    "ff_flame_vortex":  {"fn": generate_ff_flame_vortex_loop,  "default_duration": 35, "default_params": {}},
    "ff_flame_galaxy":  {"fn": generate_ff_flame_galaxy_loop,  "default_duration": 40, "default_params": {}},
    # Harmonic Geometry
    "harmonic_hue1":   {"fn": generate_harmonic_hue1,   "default_duration": 25, "default_params": {}},
    "harmonic_hue2":   {"fn": generate_harmonic_hue2,   "default_duration": 20, "default_params": {}},
    "harmonic_hue3":   {"fn": generate_harmonic_hue3,   "default_duration": 30, "default_params": {}},
    # Radial Symmetry
    "rose_spin":           {"fn": generate_rose_spin,           "default_duration": 20, "default_params": {}},
    "superformula_spin":   {"fn": generate_superformula_spin,   "default_duration": 15, "default_params": {}},
    "superformula_hue":    {"fn": generate_superformula_hue,    "default_duration": 25, "default_params": {}},
    # Reaction Diffusion
    "gs_pulse1": {"fn": generate_gs_pulse1, "default_duration": 20, "default_params": {}},
    "gs_pulse2": {"fn": generate_gs_pulse2, "default_duration": 25, "default_params": {}},
    "gs_wave":   {"fn": generate_gs_wave,   "default_duration": 30, "default_params": {}},
    # Complex Plane
    "mobius_spin":    {"fn": generate_mobius_spin,    "default_duration": 30, "default_params": {}},
    "joukowski_hue":  {"fn": generate_joukowski_hue,  "default_duration": 20, "default_params": {}},
    "mobius_hue":     {"fn": generate_mobius_hue,     "default_duration": 25, "default_params": {}},
    # Turing Patterns
    "turing_shift1": {"fn": generate_turing_shift1, "default_duration": 20, "default_params": {}},
    "turing_shift2": {"fn": generate_turing_shift2, "default_duration": 25, "default_params": {}},
    "turing_shift3": {"fn": generate_turing_shift3, "default_duration": 30, "default_params": {}},
    # Voronoi Organics
    "voronoi_hue1": {"fn": generate_voronoi_hue1, "default_duration": 20, "default_params": {}},
    "voronoi_hue2": {"fn": generate_voronoi_hue2, "default_duration": 25, "default_params": {}},
    "voronoi_hue3": {"fn": generate_voronoi_hue3, "default_duration": 15, "default_params": {}},
    # Chladni Figures
    "chladni_spin1": {"fn": generate_chladni_spin1, "default_duration": 20, "default_params": {}},
    "chladni_spin2": {"fn": generate_chladni_spin2, "default_duration": 15, "default_params": {}},
    "chladni_hue":   {"fn": generate_chladni_hue,   "default_duration": 25, "default_params": {}},
    # De Jong Attractors
    "dejong_morph": {"fn": generate_dejong_morph, "default_duration": 30, "default_params": {}},
    "dejong_hue1":  {"fn": generate_dejong_hue1,  "default_duration": 25, "default_params": {}},
    "dejong_hue2":  {"fn": generate_dejong_hue2,  "default_duration": 20, "default_params": {}},
    # Particle Systems
    "particle_vortex": {"fn": generate_particle_vortex, "default_duration": 20, "default_params": {}},
    "particle_nebula":  {"fn": generate_particle_nebula,  "default_duration": 25, "default_params": {}},
    "particle_storm":   {"fn": generate_particle_storm,   "default_duration": 20, "default_params": {}},
    "particle_galaxy":  {"fn": generate_particle_galaxy,  "default_duration": 30, "default_params": {}},
    "particle_wave":    {"fn": generate_particle_wave,    "default_duration": 15, "default_params": {}},
}
