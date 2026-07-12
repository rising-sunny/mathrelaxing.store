import io
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap


import threading
_render_state = threading.local()

class TransparentRender:
    def __enter__(self):
        _render_state.transparent = True
    def __exit__(self, *args):
        _render_state.transparent = False

def _make_cmap(color_start: str, color_end: str) -> LinearSegmentedColormap:
    if getattr(_render_state, "transparent", False):
        return LinearSegmentedColormap.from_list("mr", [(0,0,0,0), color_end])
    return LinearSegmentedColormap.from_list("mr", [color_start, color_end])


def _bad_color(bg):
    """Colour for masked (zero-density) cells. In transparent (apparel) mode the
    empty plate must be fully transparent — otherwise the attractor's bounding
    box prints as an opaque black rectangle on the garment."""
    return (0, 0, 0, 0) if getattr(_render_state, "transparent", False) else bg


# ── Apparel-exclusive designs ───────────────────────────────────────────────
# Bold, high-contrast mathematical motifs composed specifically for garments
# (thick neon stroke + glow + white core so they read on black fabric), with the
# defining equation set elegantly beneath. Rendered straight to a transparent
# PNG — never the thin poster attractors reused on cloth.

_DEJAVU = "/usr/share/fonts/truetype/dejavu"


def _apparel_curve(design, params):
    """Return (x, y) arrays for an apparel motif, in arbitrary data units."""
    g = lambda k, d: float(params.get(k, d))
    if design == "rose":
        k = g("k", 4.0)
        t = np.linspace(0, 2 * np.pi, 4000)
        r = np.cos(k * t)
        return r * np.cos(t), r * np.sin(t)
    if design == "maurer":
        n = g("n", 6.0)
        walk = g("walk", 71.0)
        k = np.arange(0, 361)
        th = np.radians(k * walk)
        r = np.sin(n * th)
        return r * np.cos(th), r * np.sin(th)
    if design == "lissajous":
        a, b = g("a", 5.0), g("b", 4.0)
        delta = g("delta", np.pi / 2)
        t = np.linspace(0, 2 * np.pi, 4000)
        return np.sin(a * t + delta), np.sin(b * t)
    if design == "spirograph":
        R, r, d = g("R", 5.0), g("r", 3.0), g("d", 5.0)
        from math import gcd
        period = int(r) // gcd(int(R), int(r)) if int(r) else 1
        t = np.linspace(0, 2 * np.pi * max(period, 1), 6000)
        x = (R - r) * np.cos(t) + d * np.cos((R - r) / r * t)
        y = (R - r) * np.sin(t) - d * np.sin((R - r) / r * t)
        return x, y
    raise ValueError(f"unknown apparel design: {design}")


def _hex_rgba(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def render_apparel_design(params, width, height):
    """Bold transparent PNG for a garment: glowing math motif + elegant equation."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    design = params.get("apparel_design")
    main = _hex_rgba(params.get("color", "#5EEAD4"))
    glow = _hex_rgba(params.get("glow", params.get("color", "#22D3EE")))
    eq = params.get("equation_text", "")

    W, H = int(width), int(height)
    x, y = _apparel_curve(design, params)

    # Fit the motif into a centred box, leaving the lower band for the equation.
    bx0, by0, bx1, by1 = int(W * 0.12), int(H * 0.06), int(W * 0.88), int(H * 0.70)
    xmin, xmax, ymin, ymax = x.min(), x.max(), y.min(), y.max()
    s = min((bx1 - bx0) / (xmax - xmin + 1e-9), (by1 - by0) / (ymax - ymin + 1e-9))
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    px = cx + (x - (xmin + xmax) / 2) * s
    py = cy - (y - (ymin + ymax) / 2) * s
    pts = list(zip(px.tolist(), py.tolist()))

    lw = max(3, int(W * 0.0065))
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # 1) Soft outer glow.
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(gl).line(pts, fill=glow[:3] + (180,), width=lw * 5, joint="curve")
    img = Image.alpha_composite(img, gl.filter(ImageFilter.GaussianBlur(W * 0.014)))
    # 2) Tighter colour halo.
    gl2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(gl2).line(pts, fill=glow[:3] + (220,), width=lw * 2, joint="curve")
    img = Image.alpha_composite(img, gl2.filter(ImageFilter.GaussianBlur(W * 0.004)))
    # 3) Crisp bright stroke.
    cr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(cr).line(pts, fill=main, width=lw, joint="curve")
    img = Image.alpha_composite(img, cr)
    # 4) White neon core.
    co = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(co).line(pts, fill=(255, 255, 255, 235), width=max(1, lw // 3), joint="curve")
    img = Image.alpha_composite(img, co)

    # Equation, elegant italic serif, auto-fit to width, centred under the motif.
    draw = ImageDraw.Draw(img)
    if eq:
        size = int(W * 0.052)
        font_path = f"{_DEJAVU}/DejaVuSerif-Italic.ttf"
        font = ImageFont.truetype(font_path, size)
        max_w = W * 0.78
        while draw.textlength(eq, font=font) > max_w and size > 18:
            size -= 4
            font = ImageFont.truetype(font_path, size)
        tw = draw.textlength(eq, font=font)
        ty = int(H * 0.80)
        # Thin hairline divider above the equation.
        dl = int(W * 0.16)
        draw.line([(W / 2 - dl, ty - int(H * 0.035)), (W / 2 + dl, ty - int(H * 0.035))],
                  fill=(255, 255, 255, 70), width=2)
        draw.text((W / 2 - tw / 2, ty), eq, font=font, fill=(248, 248, 248, 238))

    import io as _io
    buf = _io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def render_equation(equation_type: str, params: dict, width: int = 1200, height: int = 1200, hq: bool = False) -> bytes:
    dpi = 100
    fig_w = width / dpi
    fig_h = height / dpi

    def p(key, default=None):
        v = params.get(key)
        if isinstance(v, dict):
            return v.get("value", default)
        return v if v is not None else default

    color_start = p("color_start", "#c8a96e")
    color_end = p("color_end", "#7ecfb3")
    background_color = p("background_color", "#080808")

    if equation_type == "apparel":
        # Garment-exclusive bold motif + elegant equation (always transparent).
        return render_apparel_design(params, width, height)
    if equation_type == "lorenz":
        return _render_lorenz_hq(params, fig_w, fig_h, dpi, color_start, color_end, background_color) if hq else _render_lorenz(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "clifford":
        return _render_clifford(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "aizawa":
        return _render_aizawa_hq(params, fig_w, fig_h, dpi, color_start, color_end, background_color) if hq else _render_aizawa(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "de_jong":
        return _render_de_jong(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "gray-scott":
        return _render_gray_scott(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type in ("harmonograph",):
        return _render_harmonograph(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "lissajous":
        return _render_lissajous(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "rose":
        return _render_rose(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "superformula":
        return _render_superformula(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type in ("julia", "mandelbrot"):
        return _render_fractal(equation_type, params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "mobius-grid":
        return _render_mobius_grid(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "kleinian-inversion":
        return _render_mobius_grid(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "joukowski":
        return _render_joukowski(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "turing":
        return _render_turing(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "voronoi":
        return _render_voronoi(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "chladni":
        return _render_chladni(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "flow-field":
        return _render_flow_field(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    elif equation_type == "fractal-flame":
        return _render_fractal_flame(params, fig_w, fig_h, dpi, color_start, color_end, background_color)
    else:
        raise ValueError(f"Unknown equation_type: {equation_type}")




def _fig_to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    transparent = getattr(_render_state, "transparent", False)
    fig.savefig(buf, format="png", dpi=fig.dpi, pad_inches=0, transparent=transparent)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _p(params, key, default=None):
    v = params.get(key)
    if isinstance(v, dict):
        return v.get("value", default)
    return v if v is not None else default


def _add_gradient_path(ax, x, y, cmap, linewidth, alpha):
    points = np.column_stack([x, y]).reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    collection = LineCollection(segments, cmap=cmap, linewidths=linewidth, alpha=alpha)
    collection.set_array(np.linspace(0, 1, len(x) - 1))
    try:
        collection.set_capstyle("round")
    except Exception:
        pass
    ax.add_collection(collection)


def _normalize_layers(layers, margin=1.06):
    max_extent = 1.0
    for x, y in layers:
        max_extent = max(
            max_extent,
            float(np.max(np.abs(x))),
            float(np.max(np.abs(y))),
        )
    scale = 1.0 / (max_extent * margin)
    return [(x * scale, y * scale) for x, y in layers]


def _render_lorenz(params, fw, fh, dpi, cs, ce, bg):
    sigma = float(_p(params, "sigma", 10))
    rho   = float(_p(params, "rho",   28))
    beta  = float(_p(params, "beta",  2.667))

    dt, n = 0.005, 80000
    x, y, z = 0.1, 0.0, 0.0
    xs, ys, zs = np.empty(n), np.empty(n), np.empty(n)
    for i in range(n):
        dx = sigma * (y - x)
        dy = x * (rho - z) - y
        dz = x * y - beta * z
        x += dx * dt; y += dy * dt; z += dz * dt
        xs[i], ys[i], zs[i] = x, y, z

    cmap = _make_cmap(cs, ce)
    fig = plt.figure(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax = fig.add_subplot(111, projection="3d", facecolor=bg)
    t = np.linspace(0, 1, n)
    ax.scatter(xs, ys, zs, c=t, cmap=cmap, s=0.3, alpha=0.85, linewidths=0)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _isotropic_window(xe, ye, fw, fh, margin=0.04):
    """View window that preserves the data's true proportions on a fw×fh canvas.

    Returns (x0, x1, y0, y1): the data bbox plus a small margin, expanded along
    one axis (background padding) until its ratio matches the canvas, so the
    figure renders with equal x/y scale — never stretched, never cropped.
    """
    x0, x1 = float(xe[0]), float(xe[-1])
    y0, y1 = float(ye[0]), float(ye[-1])
    mx, my = (x1 - x0) * margin, (y1 - y0) * margin
    x0, x1, y0, y1 = x0 - mx, x1 + mx, y0 - my, y1 + my
    canvas_ratio = fh / fw
    win_w, win_h = x1 - x0, y1 - y0
    if win_h / win_w < canvas_ratio:
        pad = (win_w * canvas_ratio - win_h) / 2
        y0, y1 = y0 - pad, y1 + pad
    else:
        pad = (win_h / canvas_ratio - win_w) / 2
        x0, x1 = x0 - pad, x1 + pad
    return x0, x1, y0, y1


def _render_lorenz_hq(params, fw, fh, dpi, cs, ce, bg):
    """Density-based 2D projection — rich, gallery-quality render."""
    sigma = float(_p(params, "sigma", 10))
    rho   = float(_p(params, "rho",   28))
    beta  = float(_p(params, "beta",  2.667))

    px_short = int(min(fw, fh) * dpi)
    n    = max(500_000, int(px_short * 250))
    bins = max(1200, int(px_short * 0.65))

    dt = 0.003
    x, y, z = 0.1, 0.0, 0.0
    xs, zs = np.empty(n), np.empty(n)
    for i in range(n):
        dx = sigma * (y - x)
        dy = x * (rho - z) - y
        dz = x * y - beta * z
        x += dx * dt; y += dy * dt; z += dz * dt
        xs[i], zs[i] = x, z

    hist, xe, ze = np.histogram2d(xs, zs, bins=bins)
    img = np.log1p(hist.T)
    img_masked = np.ma.masked_where(img == 0, img)

    cmap = _make_cmap(cs, ce)
    cmap.set_bad(color=_bad_color(bg))

    # True-proportion framing: real data extent, isotropic scale, bg padding
    x0, x1, z0, z1 = _isotropic_window(xe, ze, fw, fh)

    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    ax.imshow(img_masked, cmap=cmap, origin="lower", interpolation="lanczos",
              extent=[xe[0], xe[-1], ze[0], ze[-1]], aspect="auto")
    ax.set_xlim(x0, x1)
    ax.set_ylim(z0, z1)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_clifford(params, fw, fh, dpi, cs, ce, bg):
    a = float(_p(params, "a", -1.4))
    b = float(_p(params, "b",  1.6))
    c = float(_p(params, "c",  1.0))
    d = float(_p(params, "d",  0.7))

    px_short = int(min(fw, fh) * dpi)
    n    = max(5_000_000, int(px_short * 1200))
    bins = max(1200, int(px_short * 0.7))

    x, y = 0.0, 0.0
    xs, ys = np.empty(n), np.empty(n)
    for i in range(n):
        xn = np.sin(a * y) + c * np.cos(a * x)
        yn = np.sin(b * x) + d * np.cos(b * y)
        x, y = xn, yn
        xs[i], ys[i] = x, y

    cmap = _make_cmap(cs, ce)
    hist, xe, ye = np.histogram2d(xs, ys, bins=bins)
    img = np.log1p(hist.T)
    # Boost contrast: power-law stretch for more visible fine detail
    img = img / (img.max() + 1e-10)
    img = img ** 0.6  # gamma < 1 brightens faint areas
    img_masked = np.ma.masked_where(img == 0, img)
    cmap.set_bad(color=_bad_color(bg))

    # True-proportion framing: real data extent, isotropic scale, bg padding
    x0, x1, y0, y1 = _isotropic_window(xe, ye, fw, fh)

    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    ax.imshow(img_masked, cmap=cmap, origin="lower", interpolation="lanczos",
              extent=[xe[0], xe[-1], ye[0], ye[-1]], aspect="auto")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_de_jong(params, fw, fh, dpi, cs, ce, bg):
    """Density-based De Jong attractor: x'=sin(a*y)-cos(b*x), y'=sin(c*x)-cos(d*y)."""
    a = float(_p(params, "a", -2.0))
    b = float(_p(params, "b", -2.0))
    c = float(_p(params, "c", 2.0))
    d = float(_p(params, "d", -2.0))

    px_short = int(min(fw, fh) * dpi)
    n    = max(5_000_000, int(px_short * 1200))
    bins = max(1200, int(px_short * 0.7))

    x, y = 0.1, 0.1
    xs, ys = np.empty(n), np.empty(n)
    for i in range(n):
        xn = np.sin(a * y) - np.cos(b * x)
        yn = np.sin(c * x) - np.cos(d * y)
        x, y = xn, yn
        xs[i], ys[i] = x, y

    cmap = _make_cmap(cs, ce)
    hist, xe, ye = np.histogram2d(xs, ys, bins=bins)
    img = np.log1p(hist.T)
    img = img / (img.max() + 1e-10)
    img = img ** 0.6
    img_masked = np.ma.masked_where(img == 0, img)
    cmap.set_bad(color=_bad_color(bg))

    # Preserve the attractor's true (roughly circular) proportions: draw the
    # histogram at its real data extent with isotropic scaling, then expand the
    # view window with background padding until it matches the canvas ratio.
    # The previous approach stretched the data to fill the 4:5 canvas, which
    # visibly deformed the figure on portrait previews/prints.
    x0, x1 = float(xe[0]), float(xe[-1])
    y0, y1 = float(ye[0]), float(ye[-1])
    mx, my = (x1 - x0) * 0.04, (y1 - y0) * 0.04
    x0, x1, y0, y1 = x0 - mx, x1 + mx, y0 - my, y1 + my

    canvas_ratio = fh / fw
    win_w, win_h = x1 - x0, y1 - y0
    if win_h / win_w < canvas_ratio:
        pad = (win_w * canvas_ratio - win_h) / 2
        y0, y1 = y0 - pad, y1 + pad
    else:
        pad = (win_h / canvas_ratio - win_w) / 2
        x0, x1 = x0 - pad, x1 + pad

    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    ax.imshow(img_masked, cmap=cmap, origin="lower", interpolation="lanczos",
              extent=[xe[0], xe[-1], ye[0], ye[-1]], aspect="auto")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_aizawa(params, fw, fh, dpi, cs, ce, bg):
    """Density-based 2D projection of Aizawa attractor using x,z plane."""
    return _render_aizawa_hq(params, fw, fh, dpi, cs, ce, bg)


def _render_aizawa_hq(params, fw, fh, dpi, cs, ce, bg):
    """Density-based 2D projection of Aizawa attractor using x,z plane (much denser)."""
    a = float(_p(params, "a", 0.95))
    b = float(_p(params, "b", 0.7))
    c = float(_p(params, "c", 0.6))
    d = float(_p(params, "d", 3.5))
    e = float(_p(params, "e", 0.25))
    f = float(_p(params, "f", 0.1))

    px_short = int(min(fw, fh) * dpi)
    n    = max(2_000_000, int(px_short * 800))
    bins = max(1200, int(px_short * 0.7))

    dt = 0.005
    # Use multiple initial conditions to fill the attractor
    ics = [(0.1, 0.0, 0.0), (-0.1, 0.5, 0.2), (0.3, -0.2, 0.5), (-0.5, 0.3, -0.2)]
    all_xs, all_zs = [], []
    per_ic = n // len(ics)
    for x0, y0, z0 in ics:
        x, y, z = x0, y0, z0
        xs, zs = np.empty(per_ic), np.empty(per_ic)
        for i in range(per_ic):
            dx = (z - b) * x - d * y
            dy = d * x + (z - b) * y
            dz = c + a * z - (z ** 3) / 3 - (x ** 2 + y ** 2) * (1 + e * z) + f * z * (x ** 3)
            x += dx * dt; y += dy * dt; z += dz * dt
            # Skip divergent trajectories
            if abs(x) > 50 or abs(z) > 50:
                x, y, z = x0, y0, z0
            xs[i], zs[i] = x, z
        all_xs.append(xs)
        all_zs.append(zs)

    xs = np.concatenate(all_xs)
    zs = np.concatenate(all_zs)

    hist, xe, ye = np.histogram2d(xs, zs, bins=bins)
    img = np.log1p(hist.T)
    # Boost contrast: power-law stretch for more visible fine detail
    img = img / (img.max() + 1e-10)
    img = img ** 0.45  # aggressive gamma to brighten faint curves
    img_masked = np.ma.masked_where(img == 0, img)

    cmap = _make_cmap(cs, ce)
    cmap.set_bad(color=_bad_color(bg))

    # True-proportion framing: real data extent, isotropic scale, bg padding
    x0, x1, y0, y1 = _isotropic_window(xe, ye, fw, fh)

    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    ax.imshow(img_masked, cmap=cmap, origin="lower", interpolation="lanczos",
              extent=[xe[0], xe[-1], ye[0], ye[-1]], aspect="auto")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_gray_scott(params, fw, fh, dpi, cs, ce, bg):
    """
    Gray-Scott reaction-diffusion with high detail and complexity.
    Creates intricate organic patterns resembling coral, spots, or mazes.
    """
    from PIL import Image, ImageFilter
    
    f  = float(_p(params, "f",  0.055))
    k  = float(_p(params, "k",  0.062))
    Du = float(_p(params, "Du", 0.16))
    Dv = float(_p(params, "Dv", 0.08))
    pattern_type = _p(params, "pattern_type", "coral")
    # Spatial variation for organic complexity
    f_var = float(_p(params, "f_var", 0.0))    # amplitude of spatial f variation
    k_var = float(_p(params, "k_var", 0.0))    # amplitude of spatial k variation
    var_freq = float(_p(params, "var_freq", 4.0))  # frequency of spatial variation
    
    # Scale simulation to output resolution
    px_short = int(min(fw, fh) * dpi)
    size = min(512, max(200, px_short // 2))
    steps = 4000 if pattern_type == "coral" else 3000
    # Reduce steps for preview-sized outputs
    if px_short < 800:
        steps = steps // 3
        size = max(150, size // 2)
    
    np.random.seed(42)
    u = np.ones((size, size))
    v = np.zeros((size, size))
    
    # Build spatial f/k maps for organic variation
    yy, xx = np.mgrid[0:size, 0:size] / size
    f_map = f + f_var * np.sin(var_freq * 2 * np.pi * xx) * np.cos(var_freq * 2 * np.pi * yy)
    k_map = k + k_var * np.cos(var_freq * 1.5 * np.pi * xx + 0.5) * np.sin(var_freq * 1.5 * np.pi * yy + 0.3)
    
    # Complex initialization for more interesting patterns
    mid = size // 2
    if pattern_type == "coral":
        # Multiple seed points for coral-like growth
        n_seeds = 8
        for _ in range(n_seeds):
            sx = np.random.randint(20, size-20)
            sy = np.random.randint(20, size-20)
            r = np.random.randint(5, 15)
            u[sx-r:sx+r, sy-r:sy+r] = 0.5
            v[sx-r:sx+r, sy-r:sy+r] = 0.25
    elif pattern_type == "spots":
        # Random spots
        n_spots = 15
        for _ in range(n_spots):
            sx = np.random.randint(0, size)
            sy = np.random.randint(0, size)
            r = np.random.randint(3, 8)
            u[max(0,sx-r):min(size,sx+r), max(0,sy-r):min(size,sy+r)] = 0.5
            v[max(0,sx-r):min(size,sx+r), max(0,sy-r):min(size,sy+r)] = 0.25
    elif pattern_type == "mitosis":
        # Center seed for splitting spots
        u[mid-8:mid+8, mid-8:mid+8] = 0.5
        v[mid-8:mid+8, mid-8:mid+8] = 0.25
    elif pattern_type == "worms":
        # Horizontal line seeds
        for offset in [-30, -10, 10, 30]:
            y0 = mid + offset
            u[y0-2:y0+2, 20:size-20] = 0.5
            v[y0-2:y0+2, 20:size-20] = 0.25
    elif pattern_type == "stripes":
        # Vertical stripe seeds
        for offset in [-40, -20, 0, 20, 40]:
            x0 = mid + offset
            u[20:size-20, max(0,x0-2):min(size,x0+2)] = 0.5
            v[20:size-20, max(0,x0-2):min(size,x0+2)] = 0.25
    elif pattern_type == "waves":
        # Ring seed
        yy_i, xx_i = np.ogrid[0:size, 0:size]
        dist = np.sqrt((yy_i - mid)**2 + (xx_i - mid)**2)
        ring = (dist > 15) & (dist < 25)
        u[ring] = 0.5
        v[ring] = 0.25
    elif pattern_type == "fingerprint":
        # Multiple parallel line seeds
        for offset in range(-60, 61, 12):
            y0 = mid + offset
            if 0 <= y0-1 < y0+1 < size:
                u[y0-1:y0+1, 10:size-10] = 0.5
                v[y0-1:y0+1, 10:size-10] = 0.25
    else:  # labyrinth
        # Grid of small perturbations
        grid_n = 6
        for i in range(grid_n):
            for j in range(grid_n):
                sx = int(size * (i + 0.5) / grid_n)
                sy = int(size * (j + 0.5) / grid_n)
                u[sx-3:sx+3, sy-3:sy+3] = 0.5
                v[sx-3:sx+3, sy-3:sy+3] = 0.25
    
    # Add noise for texture
    u += 0.02 * np.random.random((size, size))
    v += 0.02 * np.random.random((size, size))

    def laplacian(arr):
        return (
            np.roll(arr, 1, 0) + np.roll(arr, -1, 0) +
            np.roll(arr, 1, 1) + np.roll(arr, -1, 1) - 4 * arr
        )

    # Simulate with periodic boundary for seamless patterns
    has_spatial_var = f_var > 0 or k_var > 0
    for _ in range(steps):
        uvv = u * v * v
        f_local = f_map if has_spatial_var else f
        k_local = k_map if has_spatial_var else k
        u += Du * laplacian(u) - uvv + f_local * (1 - u)
        v += Dv * laplacian(v) + uvv - (f_local + k_local) * v
        # Clip to keep stable
        u = np.clip(u, 0, 1)
        v = np.clip(v, 0, 1)

    # Create visualization with enhanced depth and texture
    cmap = _make_cmap(cs, ce)
    
    # Normalize v component for display
    display_v = (v - v.min()) / (v.max() - v.min() + 1e-10)
    
    # Compute gradient magnitude for edge/texture shading
    gy, gx = np.gradient(v)
    grad_mag = np.sqrt(gx**2 + gy**2)
    grad_mag = grad_mag / (grad_mag.max() + 1e-10)
    # Subtle edge highlighting
    edge_light = 1.0 + 0.35 * grad_mag
    
    # Compute local variance for texture richness
    from scipy.ndimage import uniform_filter
    local_mean = uniform_filter(v, size=5)
    local_var = uniform_filter((v - local_mean)**2, size=5)
    texture = np.sqrt(np.clip(local_var / (local_var.max() + 1e-10), 0, None))
    # Subtle texture modulation
    texture_mod = 1.0 + 0.2 * texture
    
    # Combine: base color from v, modulated by edges and texture
    combined = np.clip(display_v * edge_light * texture_mod, 0, 1)
    
    # Create RGBA image
    rgba_img = cmap(combined)
    rgba_img = (rgba_img * 255).astype(np.uint8)
    
    # Convert to PIL and resize with high quality
    target_w, target_h = int(fw * dpi), int(fh * dpi)
    pil_img = Image.fromarray(rgba_img, mode='RGBA')
    pil_img = pil_img.resize((target_w, target_h), Image.LANCZOS)
    
    # Create figure with proper aspect ratio
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    ax.imshow(pil_img, aspect="auto")
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_harmonograph(params, fw, fh, dpi, cs, ce, bg):
    f1 = float(_p(params, "f1", 2.0))
    f2 = float(_p(params, "f2", 3.0))
    ph = float(_p(params, "p",  0.5))
    d  = float(_p(params, "d",  0.002))

    px_short = int(min(fw, fh) * dpi)
    n_pts  = max(200_000, int(px_short * 60))
    lw     = max(0.2, 0.3 * (px_short / 1200))

    t = np.linspace(0, 60 * np.pi, n_pts)
    x = np.sin(f1 * t + ph) * np.exp(-d * t)
    y = np.sin(f2 * t) * np.exp(-d * t)

    # Stretch Y by ratio to fill portrait frame
    ratio = fh / fw
    y = y * ratio

    cmap = _make_cmap(cs, ce)
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    from matplotlib.collections import LineCollection
    n = len(t)
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    lc = LineCollection(segments, cmap=cmap, alpha=0.8, linewidth=lw, capstyle='round')
    lc.set_array(np.linspace(0, 1, n))
    ax.add_collection(lc)
    # Dynamic limits to fill frame
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(y.min() * 1.05, y.max() * 1.05)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_lissajous(params, fw, fh, dpi, cs, ce, bg):
    fx    = float(_p(params, "fx",    3.0))
    fy    = float(_p(params, "fy",    4.0))
    delta = float(_p(params, "delta", 1.5708))
    # Harmonic overtones for complexity
    harm_x = float(_p(params, "harm_x", 0.0))   # amplitude of 2nd harmonic on x
    harm_y = float(_p(params, "harm_y", 0.0))   # amplitude of 2nd harmonic on y
    harm_fx = float(_p(params, "harm_fx", 2.0))  # frequency multiplier for x harmonic
    harm_fy = float(_p(params, "harm_fy", 2.0))  # frequency multiplier for y harmonic
    # Amplitude modulation for breathing/organic feel
    mod_depth = float(_p(params, "mod_depth", 0.0))
    mod_freq  = float(_p(params, "mod_freq", 1.0))

    px_short = int(min(fw, fh) * dpi)
    n_pts = max(10_000, int(px_short * 8))
    lw    = max(0.8, 1.2 * (px_short / 1200))

    t = np.linspace(0, 2 * np.pi, n_pts)
    # Base Lissajous
    x = np.sin(fx * t + delta)
    y = np.sin(fy * t)
    # Add harmonic overtones
    if harm_x > 0:
        x = x + harm_x * np.sin(harm_fx * fx * t + delta * 0.7)
    if harm_y > 0:
        y = y + harm_y * np.sin(harm_fy * fy * t - delta * 0.3)
    # Amplitude modulation
    if mod_depth > 0:
        envelope = 1.0 + mod_depth * np.sin(mod_freq * t)
        x = x * envelope
        y = y * envelope

    # Stretch Y by ratio to fill portrait frame
    ratio = fh / fw
    y = y * ratio

    cmap = _make_cmap(cs, ce)
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    from matplotlib.collections import LineCollection
    n = len(t)
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    lc = LineCollection(segments, cmap=cmap, alpha=0.9, linewidth=lw, capstyle='round')
    lc.set_array(np.linspace(0, 1, n))
    ax.add_collection(lc)
    # Dynamic limits to fill frame
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(y.min() * 1.05, y.max() * 1.05)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_rose(params, fw, fh, dpi, cs, ce, bg):
    petals = float(_p(params, "petals", 7.0))
    phase = float(_p(params, "phase", 0.0))
    power = float(_p(params, "power", 1.0))
    turns = float(_p(params, "turns", 24.0))
    petal_mix = float(_p(params, "petal_mix", 0.16))
    radial_mix = float(_p(params, "radial_mix", 0.18))
    radial_freq = float(_p(params, "radial_freq", max(3.0, petals * 0.55)))
    phase_drift = float(_p(params, "phase_drift", 0.42))
    twist = float(_p(params, "twist", max(2.0, petals / 2.0)))
    echo_layers = int(round(float(_p(params, "echo_layers", 3))))
    echo_layers = max(2, min(6, echo_layers))

    px_short = int(min(fw, fh) * dpi)
    n_pts = max(22000, int(px_short * 18))
    lw = max(0.45, 0.92 * (px_short / 1200))
    theta = np.linspace(0, turns * np.pi, n_pts)

    layers = []
    for idx in range(echo_layers):
        layer_theta = theta + idx * 0.028 * np.pi
        layer_phase = phase + idx * 0.34
        layer_scale = 1.0 - idx * 0.08

        base = np.cos(
            (petals + 0.18 * idx) * layer_theta
            + layer_phase
            + phase_drift * np.sin(layer_theta * (twist + idx * 0.15))
        )
        signed = np.sign(base) * np.power(np.clip(np.abs(base), 1e-6, None), power + idx * 0.03)
        harmonic = petal_mix * np.sin((petals * (1.45 + 0.04 * idx) + 1.0) * layer_theta - layer_phase * 0.6)
        envelope = 1.0 + radial_mix * np.cos((radial_freq + idx * 0.85) * layer_theta + layer_phase * 0.45)
        drift = 0.08 * petal_mix * np.cos(layer_theta * (0.5 + 0.04 * idx) + idx * 0.7)
        radius = ((0.86 * signed) + harmonic + drift) * envelope * layer_scale

        x = radius * np.cos(layer_theta)
        y = radius * np.sin(layer_theta)
        layers.append((x, y))

    layers = _normalize_layers(layers, margin=1.06)

    # Stretch Y by ratio to fill portrait frame
    ratio = fh / fw
    layers = [(x, y * ratio) for x, y in layers]

    cmap = _make_cmap(cs, ce)
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    for idx, (x, y) in enumerate(reversed(layers)):
        layer_alpha = min(0.88, 0.24 + idx * 0.16)
        layer_lw = lw * (1.36 - idx * 0.08)
        _add_gradient_path(ax, x, y, cmap, layer_lw, layer_alpha)
    # Fixed proportional limits to fill portrait frame completely
    ax.set_xlim(-1.06, 1.06)
    ax.set_ylim(-1.06 * ratio, 1.06 * ratio)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_superformula(params, fw, fh, dpi, cs, ce, bg):
    m = float(_p(params, "m", 7.0))
    n1 = float(_p(params, "n1", 0.3))
    n2 = float(_p(params, "n2", 1.7))
    n3 = float(_p(params, "n3", 1.7))
    turns = float(_p(params, "turns", 12.0))
    scale_bias = float(_p(params, "scale_bias", 1.0))
    wave_depth = float(_p(params, "wave_depth", 0.32))
    wave_freq = float(_p(params, "wave_freq", max(4.0, m * 0.75)))
    phase_drift = float(_p(params, "phase_drift", 0.38))
    orbit_mix = float(_p(params, "orbit_mix", 0.12))
    echo_layers = int(round(float(_p(params, "echo_layers", 4))))
    echo_layers = max(2, min(6, echo_layers))

    px_short = int(min(fw, fh) * dpi)
    n_pts = max(24000, int(px_short * 20))
    lw = max(0.45, 0.98 * (px_short / 1200))
    theta = np.linspace(0, turns * np.pi, n_pts)

    def profile(layer_theta, layer_phase, layer_idx):
        local_m = m + 0.25 * layer_idx
        drift = phase_drift * np.sin(layer_theta * (0.35 + 0.03 * layer_idx))
        cos_term = np.abs(np.cos(local_m * layer_theta / 4.0 + layer_phase + drift))
        sin_term = np.abs(np.sin(local_m * layer_theta / 4.0 - layer_phase))
        n2_eff = np.clip(
            n2 * (1.0 + 0.28 * wave_depth * np.cos(layer_theta * (wave_freq + layer_idx * 0.65) + layer_phase)),
            0.12,
            None,
        )
        n3_eff = np.clip(
            n3 * (1.0 + 0.28 * wave_depth * np.sin(layer_theta * (wave_freq * 0.82 + layer_idx * 0.45) - layer_phase * 0.5)),
            0.12,
            None,
        )
        base = np.power(cos_term, n2_eff) + np.power(sin_term, n3_eff)
        radius = np.power(np.clip(base, 1e-6, None), -1.0 / max(n1 * (1.0 + 0.05 * layer_idx), 1e-3))
        radius /= np.max(radius)
        breathing = 1.0 + 0.18 * wave_depth * np.cos(
            layer_theta * (wave_freq * 0.55 + 1.0 + layer_idx * 0.2) + layer_phase
        )
        orbit = orbit_mix * 0.22 * np.sin((m * 0.5 + 2.0 + layer_idx * 0.25) * layer_theta + layer_phase * 0.7)
        resonance = 0.14 * wave_depth * np.sin(
            (local_m * 1.35 + wave_freq + layer_idx * 0.35) * layer_theta - layer_phase * 0.6
        )
        fold = orbit_mix * 0.08 * np.cos((wave_freq * 0.5 + 1.5) * layer_theta + layer_phase)
        return np.power(radius, 0.92) * breathing * scale_bias + orbit + resonance + fold

    layers = []
    for idx in range(echo_layers):
        layer_theta = theta + idx * 0.02 * np.pi
        layer_phase = idx * 0.28 * np.pi
        layer_scale = 1.0 - idx * 0.07
        radius = profile(layer_theta, layer_phase, idx) * layer_scale
        x = radius * np.cos(layer_theta)
        y = radius * np.sin(layer_theta)
        layers.append((x, y))

    layers = _normalize_layers(layers, margin=1.08)

    # Stretch Y by ratio to fill portrait frame
    ratio = fh / fw
    layers = [(x, y * ratio) for x, y in layers]

    cmap = _make_cmap(cs, ce)
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    for idx, (x, y) in enumerate(reversed(layers)):
        layer_alpha = min(0.9, 0.22 + idx * 0.15)
        layer_lw = lw * (1.42 - idx * 0.09)
        _add_gradient_path(ax, x, y, cmap, layer_lw, layer_alpha)
    ax.set_xlim(-1.16, 1.16)
    ax.set_ylim(-1.16 * ratio, 1.16 * ratio)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_fractal(eq_type, params, fw, fh, dpi, cs, ce, bg):
    max_iter = int(_p(params, "max_iter", 256))
    zoom     = float(_p(params, "zoom", 1.0))
    cx       = float(_p(params, "cx", -0.5 if eq_type == "mandelbrot" else 0.0))
    cy       = float(_p(params, "cy", 0.0))

    w_size = int(fw * dpi)
    h_size = int(fh * dpi)
    ratio = fh / fw
    xmin, xmax = cx - 2.0 / zoom, cx + 2.0 / zoom
    ymin, ymax = cy - (ratio * 2.0) / zoom, cy + (ratio * 2.0) / zoom
    x = np.linspace(xmin, xmax, w_size)
    y = np.linspace(ymin, ymax, h_size)
    C = x[np.newaxis, :] + 1j * y[:, np.newaxis]

    if eq_type == "mandelbrot":
        Z = np.zeros_like(C)
        c_const = C
    else:
        c_re = float(_p(params, "c_re", -0.7))
        c_im = float(_p(params, "c_im", 0.27))
        Z = C.copy()
        c_const = c_re + 1j * c_im

    M = np.zeros(C.shape, dtype=float)
    for i in range(max_iter):
        mask = np.abs(Z) <= 2
        Z[mask] = Z[mask] ** 2 + (c_const[mask] if eq_type == "mandelbrot" else c_const)
        M[mask] += 1

    interior = M == max_iter
    exterior = ~interior

    ext_vals = M[exterior]
    if ext_vals.size > 0:
        counts, bin_edges = np.histogram(ext_vals, bins=1024)
        cdf = np.cumsum(counts).astype(float)
        cdf /= cdf[-1]
        display = np.empty(M.shape, dtype=float)
        display[exterior] = np.interp(ext_vals, bin_edges[:-1], cdf)
    else:
        display = M / max_iter

    display[interior] = np.nan

    cmap = LinearSegmentedColormap.from_list("mr-fractal", [bg, cs, ce])
    cmap.set_bad(color=_bad_color(bg))
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    ax.imshow(display, cmap=cmap, origin="lower", interpolation="bilinear",
              vmin=0, vmax=1, aspect="auto")
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_mobius_grid(params, fw, fh, dpi, cs, ce, bg):
    """
    Stunning Möbius transformation grid visualization.
    Creates elegant circular arcs through complex plane transformations.
    """
    grid_density = int(_p(params, "grid_density", 12))
    warp_factor = float(_p(params, "warp_factor", 0.6))
    curl_intensity = float(_p(params, "curl_intensity", 1.4))
    n_points = int(_p(params, "n_points", 800))
    echo_layers = int(_p(params, "echo_layers", 3))

    px_short = int(min(fw, fh) * dpi)
    # Scale linewidth with resolution but cap for previews to avoid thick lines
    # Preview (1280px): lw~0.5, Print (3200px): lw~1.7
    if px_short <= 200000:  # preview
        lw = max(0.35, 0.5)
    else:  # print
        lw = max(0.35, 0.65 * (px_short / 1200))

    def hex_to_rgb01(h):
        return np.array([int(h[i:i+2], 16) / 255.0 for i in (1, 3, 5)])

    c0 = hex_to_rgb01(cs)
    c1 = hex_to_rgb01(ce)

    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)

    # Portrait aspect ratio fill
    ratio = fh / fw
    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-1.15 * ratio, 1.15 * ratio)

    layers = []
    for layer_idx in range(echo_layers):
        layer_scale = 1.0 - layer_idx * 0.12
        layer_warp = warp_factor * (1.0 + layer_idx * 0.15)

        all_x, all_y = [], []
        t = np.linspace(0, 2 * np.pi, n_points)

        for i in range(grid_density):
            offset = (i / grid_density - 0.5) * 2.5 * layer_scale

            for j in range(grid_density // 2 + 1):
                angle_offset = (j / (grid_density / 2)) * np.pi

                x_base = np.cos(t + angle_offset) * (0.15 + abs(offset) * 0.35)
                y_base = np.sin(t + angle_offset) * (0.15 + abs(offset) * 0.35)

                r_sq = x_base**2 + y_base**2
                denom = 1 + layer_warp * r_sq
                x_mobius = x_base / denom + offset * 0.3 * np.cos(angle_offset)
                y_mobius = y_base / denom + offset * 0.3 * np.sin(angle_offset)

                curl = curl_intensity * (1 + layer_idx * 0.3)
                x_final = x_mobius * np.cos(curl * r_sq) - y_mobius * np.sin(curl * r_sq)
                y_final = x_mobius * np.sin(curl * r_sq) + y_mobius * np.cos(curl * r_sq)

                all_x.extend(x_final * layer_scale)
                all_y.extend(y_final * layer_scale)

                x_line = np.cos(t) * offset * 0.8
                y_line = np.sin(t) * offset * 0.8
                r_sq_line = x_line**2 + y_line**2
                denom_line = 1 + layer_warp * r_sq_line * 0.5
                x_line_mob = x_line / denom_line
                y_line_mob = y_line / denom_line

                all_x.extend(x_line_mob * layer_scale)
                all_y.extend(y_line_mob * layer_scale)

        layers.append((np.array(all_x), np.array(all_y)))

    for layer_idx, (x_coords, y_coords) in enumerate(reversed(layers)):
        t_val = layer_idx / max(len(layers) - 1, 1)
        color = tuple((1.0 - t_val) * c0 + t_val * c1)
        alpha = 0.55 + layer_idx * 0.15

        # For previews, use smaller points and lower alpha to avoid thick/glowing lines
        if px_short <= 200000:
            ax.scatter(x_coords, y_coords, c=[color], s=lw*6, alpha=min(alpha, 0.65), edgecolors='none')
        else:
            ax.scatter(x_coords, y_coords, c=[color], s=lw*14, alpha=min(alpha, 0.92), edgecolors='none')

    # Fill full portrait canvas — no aspect lock
    ratio = fh / fw
    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-1.15 * ratio, 1.15 * ratio)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_joukowski(params, fw, fh, dpi, cs, ce, bg):
    """
    Elegant Joukowski airfoil transformation visualization.
    Creates stunning wing-like curves from circle transformations.
    """
    n_circles = int(_p(params, "n_circles", 8))
    n_points = int(_p(params, "n_points", 600))
    center_offset = float(_p(params, "center_offset", 0.15))
    scale_factor = float(_p(params, "scale_factor", 1.1))
    twist = float(_p(params, "twist", 0.35))
    echo_layers = int(_p(params, "echo_layers", 4))

    px_short = int(min(fw, fh) * dpi)
    lw = max(0.4, 0.85 * (px_short / 1200))

    def hex_to_rgb01(h):
        return np.array([int(h[i:i+2], 16) / 255.0 for i in (1, 3, 5)])

    c0 = hex_to_rgb01(cs)
    c1 = hex_to_rgb01(ce)

    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-1.1, 1.1)

    layers = []
    for layer_idx in range(echo_layers):
        layer_center_off = center_offset * (1.0 + layer_idx * 0.08)
        layer_scale = scale_factor * (1.0 - layer_idx * 0.06)
        layer_twist = twist * (1.0 + layer_idx * 0.15)

        all_segments = []
        t = np.linspace(0, 2 * np.pi, n_points)

        for i in range(n_circles):
            radius = 0.12 + (i / n_circles) * 0.55

            for j in range(3):
                angle_shift = j * 2.094 + layer_twist * radius
                center_x = layer_center_off * np.cos(angle_shift)
                center_y = layer_center_off * np.sin(angle_shift) * 0.4

                x_circle = center_x + radius * np.cos(t)
                y_circle = center_y + radius * np.sin(t)

                z = x_circle + 1j * y_circle
                joukowski_z = z + 1/z

                x_j = np.real(joukowski_z) * layer_scale
                y_j = np.imag(joukowski_z) * layer_scale

                points = np.column_stack([x_j, y_j]).reshape(-1, 1, 2)
                segments = np.concatenate([points[:-1], points[1:]], axis=1)
                all_segments.extend(segments)

        layers.append(all_segments)

    for layer_idx, segments in enumerate(reversed(layers)):
        t_val = layer_idx / max(len(layers) - 1, 1)
        color = tuple((1.0 - t_val) * c0 + t_val * c1)
        alpha = 0.55 + layer_idx * 0.15

        if len(segments) > 0:
            segs_array = np.array(segments)
            lc = LineCollection(segs_array, colors=[color], alpha=min(alpha, 0.95), linewidths=lw * 1.6)
            ax.add_collection(lc)

    # Fill full portrait canvas — no aspect lock
    ratio = fh / fw
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-1.1 * ratio, 1.1 * ratio)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_turing(params, fw, fh, dpi, cs, ce, bg):
    """
    Turing Patterns — reaction-diffusion spot and stripe formations.
    Mimics natural patterns like zebra stripes, leopard spots, fish scales.
    Uses Fitzhugh-Nagumo type reaction-diffusion for distinct patterns.
    """
    # Parameters for pattern type
    pattern_type = _p(params, "pattern_type", "spots")  # spots, stripes, labyrinth
    scale = float(_p(params, "scale", 1.0))
    
    # Use higher DPI for Turing to get sharp detail
    dpi = max(dpi, 150)
    px_short = int(min(fw, fh) * dpi)
    
    # Larger simulation grid for more detail and closer patterns
    # scale 1.0 = full grid, scale 3.0 = grid/3 (larger features). Cap is high so
    # large prints (apparel AOP) get a crisp grid instead of a tiny upscaled one.
    base_size = min(1400, max(400, int(px_short * 0.45)))
    min_size = 80 if pattern_type in ("labyrinth", "stripes") else 64
    size = max(min_size, int(base_size / max(scale, 1.0)))
    
    # Time steps for pattern development — reduce for small scale (larger grid)
    if scale <= 1.5:
        steps = 5000 if pattern_type == "spots" else 6000
    elif pattern_type == "labyrinth":
        steps = 8000
    elif pattern_type == "stripes":
        steps = 9000
    else:
        steps = 6000
    
    # Fitzhugh-Nagumo parameters for different patterns
    if pattern_type == "spots":
        a, b = 0.08, 0.06
        tau = 2.5
        Du, Dv = 0.5, 0.125
    elif pattern_type == "stripes":
        a, b = 0.02, 0.08
        tau = 2.0
        Du, Dv = 0.5, 0.15
    else:  # labyrinth
        a, b = 0.04, 0.08
        tau = 1.0
        Du, Dv = 0.3, 0.15
    
    # Initialize with noise
    np.random.seed(42)
    u = np.random.random((size, size)) * 0.2 + 0.5
    v = np.random.random((size, size)) * 0.1 + 0.25
    
    # Add initial perturbations at multiple scales
    num_seeds = 3 if pattern_type == "spots" else 6
    base_radius = int(15 * (scale / 2))
    for _ in range(num_seeds):
        x, y = np.random.randint(0, size, 2)
        r = max(2, np.random.randint(base_radius, base_radius + 10))
        if pattern_type == "labyrinth":
            u[max(0,x-r):min(size,x+r), max(0,y-r):min(size,y+r)] += 0.5
        else:
            u[max(0,x-r):min(size,x+r), max(0,y-r):min(size,y+r)] += 0.3
    
    def laplacian(arr):
        return (
            np.roll(arr, 1, 0) + np.roll(arr, -1, 0) +
            np.roll(arr, 1, 1) + np.roll(arr, -1, 1) - 4 * arr
        )
    
    # Simulate
    for _ in range(steps):
        lap_u = laplacian(u)
        lap_v = laplacian(v)
        
        # Fitzhugh-Nagumo reaction terms
        uvv = u * v * v
        u += Du * lap_u * scale + u - u**3 - v + a
        v += (Dv * lap_v * scale + u - v) / tau + b
        
        # Clip to keep stable
        np.clip(u, -1, 1, out=u)
        np.clip(v, -1, 1, out=v)
    
    # Enhanced visualization with edge shading and texture
    from PIL import Image, ImageFilter
    
    # Normalize to 0-1
    display_u = (u - u.min()) / (u.max() - u.min() + 1e-10)
    
    # Gradient-based edge shading for depth
    gy, gx = np.gradient(u)
    grad_mag = np.sqrt(gx**2 + gy**2)
    grad_mag = grad_mag / (grad_mag.max() + 1e-10)
    edge_light = 1.0 + 0.3 * grad_mag
    
    # Local variance for texture richness
    from scipy.ndimage import uniform_filter
    local_mean = uniform_filter(u, size=3)
    local_var = uniform_filter((u - local_mean)**2, size=3)
    texture = np.sqrt(np.clip(local_var / (local_var.max() + 1e-10), 0, None))
    texture_mod = 1.0 + 0.15 * texture
    
    combined = np.clip(display_u * edge_light * texture_mod, 0, 1)
    
    # Create colormap: dark bg -> start color -> end color
    bg_rgb = tuple(int(bg.lstrip('#')[i:i+2], 16)/255 for i in (0,2,4))
    cmap_3stop = LinearSegmentedColormap.from_list("mr_turing", [bg_rgb, cs, ce])
    rgba_img = cmap_3stop(combined)
    rgba_img = (rgba_img * 255).astype(np.uint8)
    
    # Convert to PIL and resize with high-quality upscaling
    target_w, target_h = int(fw * dpi), int(fh * dpi)
    pil_img = Image.fromarray(rgba_img, mode='RGBA')
    
    # For preview-sized outputs, crop a center portion and zoom in
    # so patterns are large and clearly visible from afar
    if px_short <= 192000:  # preview resolution
        crop_fraction = 0.5  # show 50% of the full simulation (2x zoom)
        cw = int(pil_img.width * crop_fraction)
        ch = int(pil_img.height * crop_fraction)
        cx = (pil_img.width - cw) // 2
        cy = (pil_img.height - ch) // 2
        pil_img = pil_img.crop((cx, cy, cx + cw, cy + ch))
    
    # Resize to target — always LANCZOS for smooth detail
    pil_img = pil_img.resize((target_w, target_h), Image.LANCZOS)
    
    # Create figure and display
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    ax.imshow(pil_img, aspect="auto")
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_voronoi(params, fw, fh, dpi, cs, ce, bg):
    """
    Voronoi Organics — stunning cellular patterns with 3D relief, glowing borders,
    multi-color cells, and specular highlights for maximum visual impact.
    """
    from scipy.spatial import Voronoi, KDTree
    from scipy.ndimage import gaussian_filter, sobel
    from PIL import Image
    
    n_cells = int(_p(params, "n_cells", 60))
    organic = float(_p(params, "organic", 0.5))
    irregularity = float(_p(params, "irregularity", 0.3))
    glow_strength = float(_p(params, "glow_strength", 0.5))
    cell_color_var = float(_p(params, "cell_color_var", 0.3))
    
    # Higher DPI for sharp detail
    dpi = max(dpi, 150)
    px_short = int(min(fw, fh) * dpi)
    size = min(800, max(500, int(px_short * 0.5)))
    if px_short < 800:
        size = max(300, size // 2)
    
    np.random.seed(42)
    
    # Generate seed points with grid + random perturbation
    grid_n = int(np.sqrt(n_cells * 1.2))
    points = []
    for i in range(grid_n):
        for j in range(grid_n):
            base_x = (i + 0.5) / grid_n
            base_y = (j + 0.5) / grid_n
            x = base_x + np.random.normal(0, irregularity / grid_n)
            y = base_y + np.random.normal(0, irregularity / grid_n)
            points.append([x, y])
    
    points = np.array(points)
    points_scaled = points * [size, size]
    
    if len(points) > n_cells:
        idx = np.random.choice(len(points), n_cells, replace=False)
        points = points[idx]
        points_scaled = points_scaled[idx]

    # Optional seed drift: each seed orbits its home position. Driving `drift_phase`
    # from 0 to 2*pi traces a full circle and returns exactly to the start, so an
    # animation that advances drift_phase over its length loops seamlessly. The
    # cells slide, swell and shrink — the living motion of a Voronoi field.
    drift = float(_p(params, "drift", 0.0))
    drift_phase = float(_p(params, "drift_phase", 0.0))
    if drift > 0:
        n_pts = len(points_scaled)
        offs = np.linspace(0.0, 2 * np.pi, n_pts, endpoint=False)
        amp = drift * size
        points_scaled = points_scaled + np.stack([
            amp * np.sin(drift_phase + offs),
            amp * np.cos(drift_phase + offs * 1.7),
        ], axis=1)

    tree = KDTree(points_scaled)
    y_coords, x_coords = np.mgrid[0:size, 0:size]
    coords = np.stack([x_coords.ravel(), y_coords.ravel()], axis=1)
    
    dist, idx = tree.query(coords)
    dist_img = dist.reshape(size, size)
    idx_img = idx.reshape(size, size)
    
    seed_x = points_scaled[idx_img, 0]
    seed_y = points_scaled[idx_img, 1]
    dx = x_coords - seed_x
    dy = y_coords - seed_y
    
    # Organic boundary warping with multi-scale noise
    if organic > 0:
        noise1 = np.sin(x_coords * 0.05) * np.cos(y_coords * 0.07) * organic * 12
        noise2 = np.sin(x_coords * 0.12 + 1.0) * np.cos(y_coords * 0.09 + 0.5) * organic * 6
        noise3 = np.cos(x_coords * 0.2 + 2.0) * np.sin(y_coords * 0.18 + 1.5) * organic * 3
        dist_img += (noise1 + noise2 + noise3) * 0.5
    
    cell_radius = size / np.sqrt(n_cells) * 0.8
    dist_normalized = np.clip(dist_img / cell_radius, 0, 1)
    
    # ---- MULTI-COLOR CELLS ----
    # Assign each cell a unique hue from a rich palette
    n_actual = idx_img.max() + 1
    cell_hues = np.random.random(n_actual)
    cell_sat = 0.5 + np.random.random(n_actual) * 0.4  # 0.5-0.9
    cell_val = 0.6 + np.random.random(n_actual) * 0.35  # 0.6-0.95
    
    # Blend cell color with the main colormap based on distance from center
    cell_h = cell_hues[idx_img]
    cell_s = cell_sat[idx_img]
    cell_v = cell_val[idx_img]
    
    # Map cell base to 0-1 for colormap blending
    cell_base = cell_h * 0.5 + dist_normalized * 0.5
    
    # ---- 3D RELIEF WITH SPECULAR ----
    # Smooth the distance field for nice surface normals
    smooth_dist = gaussian_filter(dist_normalized, sigma=1.5)
    grad_y, grad_x = np.gradient(smooth_dist)
    
    # Surface normal → lighting
    light_x, light_y = 0.4, 0.3
    diffuse = 1.0 - (grad_x * light_x + grad_y * light_y) * 2.5
    diffuse = np.clip(diffuse, 0.2, 1.3)
    
    # Specular highlight (Phong-like)
    spec_angle = grad_x * light_x + grad_y * light_y
    specular = np.clip(spec_angle, 0, None) ** 8 * 0.6
    
    # Depth: darker at edges, lighter at center
    depth = 1.0 - dist_normalized * 0.35
    
    # Interior texture — subtle noise pattern per cell
    interior_noise = np.sin(x_coords * 0.3 + cell_h * 20) * np.cos(y_coords * 0.25 + cell_h * 15)
    interior_texture = 1.0 + interior_noise * 0.08 * cell_color_var
    
    # Combine all lighting
    lighting = diffuse * depth * interior_texture + specular
    
    # ---- GLOWING BORDERS ----
    edge_x = sobel(idx_img.astype(float), axis=1)
    edge_y = sobel(idx_img.astype(float), axis=0)
    edges = np.sqrt(edge_x**2 + edge_y**2)
    edge_mask = edges > 1.0
    
    # Create soft glow around borders
    edge_glow = gaussian_filter(edges, sigma=2.0)
    edge_glow = edge_glow / (edge_glow.max() + 1e-10)
    glow = edge_glow * glow_strength
    
    # ---- COMPOSE FINAL IMAGE ----
    # Base: cell color modulated by lighting
    img = cell_base * lighting
    
    # Add glow on borders (bright highlights)
    img += glow * 0.5
    
    # Darken the border lines themselves for definition
    img[edge_mask] *= 0.7
    
    # Normalize
    img = (img - img.min()) / (img.max() - img.min() + 1e-10)
    
    # ---- RICH COLORMAP ----
    # Build a multi-stop colormap for more color variety
    bg_rgb = tuple(int(bg.lstrip('#')[i:i+2], 16)/255 for i in (0,2,4))
    cs_rgb = tuple(int(cs.lstrip('#')[i:i+2], 16)/255 for i in (0,2,4)) if isinstance(cs, str) else cs
    ce_rgb = tuple(int(ce.lstrip('#')[i:i+2], 16)/255 for i in (0,2,4)) if isinstance(ce, str) else ce
    # Mid-point color (blend of start and end with hue shift)
    mid_rgb = tuple(min(1.0, (a + b) / 2 + 0.15) for a, b in zip(cs_rgb, ce_rgb))
    cmap_rich = LinearSegmentedColormap.from_list("mr_voronoi", [bg_rgb, cs_rgb, mid_rgb, ce_rgb])
    
    rgba = cmap_rich(img)
    rgba = (rgba * 255).astype(np.uint8)
    
    # Add glow as bright overlay on the RGBA image
    glow_rgb = np.stack([glow * 200, glow * 180, glow * 255], axis=-1)
    glow_rgb = np.clip(glow_rgb, 0, 255).astype(np.uint8)
    rgba[:,:,:3] = np.clip(rgba[:,:,:3].astype(np.int16) + glow_rgb.astype(np.int16), 0, 255).astype(np.uint8)
    
    pil_img = Image.fromarray(rgba, mode='RGBA')
    
    target_w, target_h = int(fw * dpi), int(fh * dpi)
    pil_img = pil_img.resize((target_w, target_h), Image.LANCZOS)
    
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    ax.imshow(pil_img, aspect="auto")
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _render_chladni(params, fw, fh, dpi, cs, ce, bg):
    """
    Chladni Figures — realistic sand-on-plate vibration patterns.
    Simulates sand accumulating along nodal lines of standing waves.
    Multiple pattern types for visual diversity.
    """
    from PIL import Image, ImageFilter, ImageEnhance
    from scipy.ndimage import gaussian_filter
    
    # Mode parameters determine the pattern
    mode_m = int(_p(params, "mode_m", 5))
    mode_n = int(_p(params, "mode_n", 3))
    
    # Grid size
    px_short = int(min(fw, fh) * dpi)
    size = min(1200, max(800, px_short))
    if px_short < 800:
        size = max(400, size // 2)
    
    # Create grid with fine resolution
    x = np.linspace(0, np.pi, size)
    y = np.linspace(0, np.pi, size)
    X, Y = np.meshgrid(x, y)
    
    m, n = mode_m, mode_n
    
    # --- Distinct Chladni formulas per (m,n) pair ---
    # Use m % 5 to select from 5 fundamentally different plate geometries
    # Each produces a unique visual family regardless of mode values
    plate_type = m % 5
    
    # Center coordinates for circular/elliptical plates
    cx, cy = np.pi/2, np.pi/2
    R = np.sqrt((X - cx)**2 + (Y - cy)**2) / (np.pi/2)
    Theta = np.arctan2(Y - cy, X - cx)
    
    if plate_type == 0:
        # Square plate: classic two-mode superposition (symmetric cross patterns)
        Z = np.sin(m * X) * np.sin(n * Y) + np.sin(n * X) * np.sin(m * Y)
    elif plate_type == 1:
        # Circular plate: radial Bessel-like + angular modes (mandala/radial)
        Z = np.cos(m * R * np.pi) * np.cos(n * Theta) + np.cos(n * R * np.pi) * np.cos(m * Theta)
    elif plate_type == 2:
        # Elliptical plate: stretched circular modes (elongated patterns)
        stretch = 1.3
        R_ell = np.sqrt(((X - cx)*stretch)**2 + (Y - cy)**2) / (np.pi/2)
        Z = (np.cos(m * R_ell * np.pi) * np.cos(n * Theta) 
             + 0.6 * np.sin(m * X) * np.cos(n * Y))
    elif plate_type == 3:
        # Diagonal plate: rotated 45° modes (diamond/X patterns)
        U = (X + Y) / np.sqrt(2)
        V = (X - Y) / np.sqrt(2)
        Z = (np.sin(m * U) * np.sin(n * V) 
             + np.sin(n * U) * np.sin(m * V)
             + 0.3 * np.cos((m+n) * X) * np.cos((m-n) * Y))
    else:
        # Free plate: triple-mode interference (complex organic shapes)
        Z = (np.sin(m * X) * np.cos(n * Y) 
             + np.cos(m * R * np.pi / 2) * np.sin(n * Theta + m * R)
             + 0.5 * np.sin((m+n) * X * Y / (np.pi)))
    
    # Normalize to -1 to 1
    Z = Z / (np.abs(Z).max() + 1e-10)
    
    # --- Realistic sand accumulation ---
    # Sand collects where amplitude is near zero (nodal lines)
    # Use a sharper falloff for thinner, more defined nodal lines
    sand_density = np.exp(-(Z**2) * 120)  # Sharper peak at Z=0
    
    # Add secondary sand ridges near nodes for realism
    sand_density += 0.15 * np.exp(-(Z**2) * 8)  # Wider, fainter halo
    
    # --- Granular sand texture ---
    np.random.seed(42 + mode_m * 13 + mode_n * 7)
    
    # Fine grain noise (individual sand particles)
    grain_fine = np.random.random((size, size))
    
    # Medium grain noise (sand clumps)
    grain_medium = gaussian_filter(np.random.random((size, size)), sigma=1.5)
    
    # Combine grains: sand particles cluster along nodal lines
    # High sand density = more visible grains; low density = dark plate
    grain_texture = 0.4 * grain_fine + 0.6 * grain_medium
    
    # Sand only appears where density is significant
    sand_mask = (sand_density > 0.1).astype(float)
    sand_pattern = sand_density * (0.5 + 0.5 * grain_texture) * sand_mask
    
    # Add scattered sand grains away from nodal lines (realistic debris)
    debris = np.random.random((size, size))
    debris_mask = ((debris > 0.997) & (sand_density < 0.1)).astype(float) * 0.15
    sand_pattern = np.clip(sand_pattern + debris_mask, 0, 1)
    
    # --- Colormap: dark plate → sand color ---
    # Use 3-stop colormap: bg (plate) → cs (sand base) → ce (sand highlight)
    bg_rgb = tuple(int(bg.lstrip('#')[i:i+2], 16)/255 for i in (0,2,4))
    cmap = LinearSegmentedColormap.from_list("mr_chladni", [bg_rgb, cs, ce])
    
    rgba = cmap(sand_pattern)
    rgba = (rgba * 255).astype(np.uint8)
    
    pil_img = Image.fromarray(rgba, mode='RGBA')
    
    # Subtle sharpening to make sand grains pop
    pil_img = pil_img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
    
    # Resize to target dimensions
    target_w, target_h = int(fw * dpi), int(fh * dpi)
    pil_img = pil_img.resize((target_w, target_h), Image.LANCZOS)
    
    # Create final figure
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    ax.imshow(pil_img, aspect="auto")
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    
    return _fig_to_bytes(fig)



def _render_flow_field(params, fw, fh, dpi, cs, ce, bg):
    """
    Flow Field — supports multiple field physics and render styles.
    field_type: "noise" | "cellular" | "vortex" | "sources"
    style:      "lines" | "density" | "brush"
    """
    from scipy.interpolate import RegularGridInterpolator

    field_type = str(_p(params, "field_type", "noise"))
    style      = str(_p(params, "style",      "lines"))
    freq       = float(_p(params, "frequency",     1.5))
    octaves    = int(  _p(params, "octaves",        3))
    n_part     = int(  _p(params, "num_particles", 1200))
    steps      = int(  _p(params, "steps",          600))
    step_size  = float(_p(params, "step_size",    0.004))
    seed_val   = int(  _p(params, "seed",            42))
    lw         = float(_p(params, "line_width",     0.5))
    alpha_val  = float(_p(params, "alpha",         0.55))
    curl       = float(_p(params, "curl",           0.0))
    n_poles    = int(  _p(params, "n_poles",          4))

    rng = np.random.RandomState(seed_val)
    ratio = fh / fw
    x0, x1 = -1.0, 1.0
    y0, y1 = -ratio, ratio

    GRID = 400
    gx = np.linspace(x0, x1, GRID)
    gy = np.linspace(y0, y1, int(GRID * ratio))
    GX, GY = np.meshgrid(gx, gy)

    # ── Build vector field ──────────────────────────────────────────────────

    if field_type == "cellular":
        # Cat's-eye vortex cells: alternating circulation from sin stream function
        # u = -∂ψ/∂y, v = ∂ψ/∂x  where ψ = -cos(fx*x)*cos(fy*y)
        fx_v = freq * np.pi * (1.0 + rng.uniform(-0.12, 0.12))
        fy_v = freq * np.pi * (1.0 + rng.uniform(-0.12, 0.12))
        U_f = -np.sin(fy_v * GY) * np.cos(fx_v * GX)
        V_f =  np.sin(fx_v * GX) * np.cos(fy_v * GY)
        mag = np.sqrt(U_f**2 + V_f**2) + 1e-9
        angle_field = np.arctan2(V_f / mag, U_f / mag)

    elif field_type == "vortex":
        # N point vortices — particles orbit each center
        vx_p = rng.uniform(-0.55, 0.55, n_poles)
        vy_p = rng.uniform(-ratio * 0.55, ratio * 0.55, n_poles)
        sgn  = rng.choice([-1, 1], n_poles).astype(float)
        str_ = sgn * rng.uniform(0.8, 1.8, n_poles)
        U_f  = np.zeros_like(GX)
        V_f  = np.zeros_like(GX)
        for i in range(n_poles):
            dx = GX - vx_p[i]; dy = GY - vy_p[i]
            r2 = dx**2 + dy**2 + 0.012**2
            U_f += -str_[i] * dy / r2
            V_f += +str_[i] * dx / r2
        mag = np.sqrt(U_f**2 + V_f**2) + 1e-9
        angle_field = np.arctan2(V_f / mag, U_f / mag)

    elif field_type == "sources":
        # Alternating sources/sinks — field lines like magnetic dipoles
        sx_p = rng.uniform(-0.62, 0.62, n_poles)
        sy_p = rng.uniform(-ratio * 0.62, ratio * 0.62, n_poles)
        str_ = np.array([1.0 if i % 2 == 0 else -1.0 for i in range(n_poles)])
        str_ *= rng.uniform(0.8, 1.2, n_poles)
        U_f  = np.zeros_like(GX)
        V_f  = np.zeros_like(GX)
        for i in range(n_poles):
            dx = GX - sx_p[i]; dy = GY - sy_p[i]
            r2 = dx**2 + dy**2 + 0.04**2
            U_f += str_[i] * dx / r2
            V_f += str_[i] * dy / r2
        mag = np.sqrt(U_f**2 + V_f**2) + 1e-9
        angle_field = np.arctan2(V_f / mag, U_f / mag)

    else:  # "noise"
        flat = np.column_stack([GX.ravel(), GY.ravel()])
        angle_raw = np.zeros(len(flat))
        amp_k, fk = 1.0, freq
        for k in range(octaves):
            F = rng.randn(8, 2) * fk * 2 * np.pi
            P = rng.uniform(0, 2 * np.pi, 8)
            for j in range(8):
                angle_raw += amp_k * np.sin(flat @ F[j] + P[j])
            amp_k *= 0.5; fk *= 2.0
        ny_g = len(gy)
        angle_raw = angle_raw.reshape(ny_g, GRID)
        angle_field = angle_raw / (np.abs(angle_raw).max() + 1e-9) * np.pi
        if curl != 0.0:
            angle_field = angle_field + curl * np.arctan2(GY, GX) * 0.4

    interp = RegularGridInterpolator(
        (gy, gx), angle_field, method="linear", bounds_error=False, fill_value=0.0
    )

    # ── Trace particles ─────────────────────────────────────────────────────

    if style == "density":
        # Accumulate particle positions — renders like Clifford/De Jong
        px = rng.uniform(x0, x1, n_part)
        py = rng.uniform(y0, y1, n_part)
        active = np.ones(n_part, dtype=bool)
        prev_x, prev_y = px.copy(), py.copy()
        acc_xs, acc_ys = [], []

        for step in range(steps):
            if not active.any():
                break
            q = np.column_stack([prev_y[active], prev_x[active]])
            ang = interp(q)
            new_x, new_y = prev_x.copy(), prev_y.copy()
            new_x[active] = prev_x[active] + np.cos(ang) * step_size
            new_y[active] = prev_y[active] + np.sin(ang) * step_size
            out = (new_x < x0) | (new_x > x1) | (new_y < y0) | (new_y > y1)
            acc = active & ~out
            if acc.any():
                acc_xs.append(new_x[acc])
                acc_ys.append(new_y[acc])
            active[out] = False
            # For cellular/vortex fields, restart exiting particles from random positions
            if field_type in ("cellular", "vortex"):
                new_x[out] = rng.uniform(x0, x1, out.sum())
                new_y[out] = rng.uniform(y0, y1, out.sum())
                active[out] = True
            prev_x, prev_y = new_x, new_y

        all_xs = np.concatenate(acc_xs) if acc_xs else np.array([])
        all_ys = np.concatenate(acc_ys) if acc_ys else np.array([])
        bins_w = max(600, int(fw * dpi * 0.5))
        bins_h = max(600, int(fh * dpi * 0.5))
        if len(all_xs) > 0:
            hist, _, _ = np.histogram2d(
                all_xs, all_ys, bins=[bins_w, bins_h],
                range=[[x0, x1], [y0, y1]]
            )
        else:
            hist = np.zeros((bins_w, bins_h))
        img = np.log1p(hist.T)
        img = img / (img.max() + 1e-10)
        img_masked = np.ma.masked_where(img == 0, img)
        cmap = _make_cmap(cs, ce)
        cmap.set_bad(color=_bad_color(bg))
        fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
        ax.set_facecolor(bg)
        ax.imshow(img_masked, cmap=cmap, origin="lower", interpolation="lanczos",
                  aspect="auto", extent=[x0, x1, y0, y1])
        ax.set_axis_off()
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        return _fig_to_bytes(fig)

    # ── Line-based: "lines" or "brush" ──────────────────────────────────────
    if style == "brush":
        actual_lw    = lw * 7.0
        actual_alpha = alpha_val * 0.3
        actual_n     = max(150, n_part // 7)
    else:
        actual_lw    = lw
        actual_alpha = alpha_val
        actual_n     = n_part

    px = rng.uniform(x0, x1, actual_n)
    py = rng.uniform(y0, y1, actual_n)
    active = np.ones(actual_n, dtype=bool)
    seg_list, color_list = [], []
    prev_x, prev_y = px.copy(), py.copy()

    for step in range(steps):
        if not active.any():
            break
        q = np.column_stack([prev_y[active], prev_x[active]])
        ang = interp(q)
        new_x, new_y = prev_x.copy(), prev_y.copy()
        new_x[active] = prev_x[active] + np.cos(ang) * step_size
        new_y[active] = prev_y[active] + np.sin(ang) * step_size
        out = (new_x < x0) | (new_x > x1) | (new_y < y0) | (new_y > y1)
        seg = active & ~out
        if seg.any():
            p0 = np.column_stack([prev_x[seg], prev_y[seg]])
            p1 = np.column_stack([new_x[seg],  new_y[seg]])
            seg_list.append(np.stack([p0, p1], axis=1))
            color_list.append(np.full(seg.sum(), step / steps))
        active[out] = False
        prev_x, prev_y = new_x, new_y

    cmap = _make_cmap(cs, ce)
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi, facecolor=bg)
    ax.set_facecolor(bg)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    if seg_list:
        all_segs   = np.concatenate(seg_list,  axis=0)
        all_colors = np.concatenate(color_list, axis=0)
        lc = LineCollection(all_segs, cmap=cmap, linewidths=actual_lw, alpha=actual_alpha)
        lc.set_array(all_colors)
        try:
            lc.set_capstyle("round")
        except Exception:
            pass
        ax.add_collection(lc)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return _fig_to_bytes(fig)


def _apply_ff_variation(vtype, px, py):
    r2 = px*px + py*py + 1e-8
    r  = np.sqrt(r2)
    theta = np.arctan2(py, px)
    if vtype == "sinusoidal":
        return np.sin(px), np.sin(py)
    elif vtype == "spherical":
        return px/r2, py/r2
    elif vtype == "swirl":
        s, c = np.sin(r2), np.cos(r2)
        return px*s - py*c, px*c + py*s
    elif vtype == "horseshoe":
        return (px-py)*(px+py)/r, 2*px*py/r
    elif vtype == "polar":
        return theta/np.pi, r - 1
    elif vtype == "heart":
        return r*np.sin(r*theta), -r*np.cos(r*theta)
    elif vtype == "julia":
        sq = np.sqrt(r)
        return sq*np.cos(theta/2), sq*np.sin(theta/2)
    elif vtype == "eyefish":
        return 2*px/(r+1), 2*py/(r+1)
    elif vtype == "bubble":
        return 4*px/(r2+4), 4*py/(r2+4)
    elif vtype == "disk":
        t = theta/np.pi
        return t*np.sin(np.pi*r), t*np.cos(np.pi*r)
    else:  # linear
        return px.copy(), py.copy()


def _render_fractal_flame(params, fw, fh, dpi, cs, ce, bg):
    from PIL import Image as PILImage

    seed       = int(_p(params, "seed",       42))
    n_funcs    = int(_p(params, "n_funcs",    4))
    n_iters    = int(_p(params, "n_iters",    8_000_000))
    gamma      = float(_p(params, "gamma",    2.2))
    sym        = int(_p(params, "symmetry",   1))
    variation  = str(_p(params, "variation",  "sinusoidal"))
    var2       = str(_p(params, "var2",       "linear"))
    v_mix      = float(_p(params, "v_mix",    0.0))
    brightness = float(_p(params, "brightness", 1.0))
    phase      = float(_p(params, "phase",    0.0))

    W = int(round(fw * dpi))
    H = int(round(fh * dpi))

    rng = np.random.default_rng(seed)

    # Build affine transforms
    T_aff, T_col, T_w = [], [], []
    for i in range(n_funcs):
        angle = rng.uniform(0, 2*np.pi) + phase
        scale = rng.uniform(0.3, 0.85)
        shear = rng.uniform(-0.25, 0.25)
        tx    = rng.uniform(-1.2, 1.2)
        ty    = rng.uniform(-1.2, 1.2)
        co, si = np.cos(angle)*scale, np.sin(angle)*scale
        T_aff.append((co, -si+shear, tx, si, co+shear, ty))
        T_col.append(i / max(n_funcs - 1, 1))
        T_w.append(rng.uniform(0.5, 1.5))

    # N-fold symmetry rotations
    if sym > 1:
        for k in range(sym):
            ang = 2*np.pi*k/sym
            co, si = np.cos(ang), np.sin(ang)
            T_aff.append((co, -si, 0.0, si, co, 0.0))
            T_col.append(k / sym)
            T_w.append(1.0)

    n_T = len(T_aff)
    weights = np.array(T_w, dtype=np.float64)
    weights /= weights.sum()
    cum_w = np.cumsum(weights)

    N_W  = 2000
    SKIP = 30

    wx = rng.uniform(-1.0, 1.0, N_W)
    wy = rng.uniform(-1.0, 1.0, N_W)
    wc = rng.random(N_W)

    def _step(wx, wy, wc):
        r_vals = rng.random(N_W)
        fidx = np.searchsorted(cum_w, r_vals).clip(0, n_T-1)
        new_x = np.empty(N_W); new_y = np.empty(N_W); new_c = np.empty(N_W)
        for fi in range(n_T):
            m = fidx == fi
            if not m.any(): continue
            a,b,c,d,e,f = T_aff[fi]
            px = a*wx[m] + b*wy[m] + c
            py = d*wx[m] + e*wy[m] + f
            vx1, vy1 = _apply_ff_variation(variation, px, py)
            vx2, vy2 = _apply_ff_variation(var2, px, py)
            px = (1-v_mix)*vx1 + v_mix*vx2
            py = (1-v_mix)*vy1 + v_mix*vy2
            new_x[m] = px; new_y[m] = py
            new_c[m] = (wc[m] + T_col[fi]) * 0.5
        return new_x, new_y, new_c

    # Pre-scan for auto view bounds
    scan_wx, scan_wy, scan_wc = wx.copy(), wy.copy(), wc.copy()
    all_sx, all_sy = [], []
    for _ in range(60):
        scan_wx, scan_wy, scan_wc = _step(scan_wx, scan_wy, scan_wc)
        all_sx.extend(scan_wx.tolist())
        all_sy.extend(scan_wy.tolist())

    asx = np.array(all_sx); asy = np.array(all_sy)
    valid = np.isfinite(asx) & np.isfinite(asy)
    if valid.sum() > 200:
        xs, ys = asx[valid], asy[valid]
        x2, x98 = np.percentile(xs, 2), np.percentile(xs, 98)
        y2, y98 = np.percentile(ys, 2), np.percentile(ys, 98)
        px_ = (x98-x2)*0.15; py_ = (y98-y2)*0.15
        xmin, xmax = x2-px_, x98+px_
        ymin, ymax = y2-py_, y98+py_
    else:
        xmin, xmax, ymin, ymax = -2.5, 2.5, -2.5, 2.5

    hist_n   = np.zeros((H, W), dtype=np.float64)
    hist_col = np.zeros((H, W), dtype=np.float64)
    x_sc = W / (xmax - xmin)
    y_sc = H / (ymax - ymin)

    n_steps = n_iters // N_W + SKIP
    for step in range(n_steps):
        wx, wy, wc = _step(wx, wy, wc)
        if step < SKIP:
            continue
        xi = ((wx - xmin) * x_sc).astype(int)
        yi = ((wy - ymin) * y_sc).astype(int)
        ok = np.isfinite(wx) & np.isfinite(wy) & (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
        if ok.any():
            np.add.at(hist_n,   (yi[ok], xi[ok]), 1)
            np.add.at(hist_col, (yi[ok], xi[ok]), wc[ok])

    mx = hist_n.max() or 1
    log_a = np.log1p(hist_n * brightness) / np.log1p(mx * brightness)
    alpha = np.power(log_a, 1.0 / gamma)

    with np.errstate(invalid='ignore'):
        color_t = np.where(hist_n > 0, hist_col / hist_n, 0.5)

    def hex2rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    bg_rgb = hex2rgb(bg); cs_rgb = hex2rgb(cs); ce_rgb = hex2rgb(ce)

    pixels = np.zeros((H, W, 3), dtype=np.uint8)
    for k in range(3):
        fg  = cs_rgb[k]*(1-color_t) + ce_rgb[k]*color_t
        val = bg_rgb[k]*(1-alpha) + fg*alpha
        pixels[:, :, k] = np.clip(val, 0, 255).astype(np.uint8)

    img = PILImage.fromarray(pixels, mode='RGB')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.read()
