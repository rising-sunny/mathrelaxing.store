import io
import math
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


BASE = Path("/var/www/mathrelaxing.store")
PREVIEW_DIR = BASE / "static" / "previews"
COVER_DIR = BASE / "static" / "covers"
VIDEO_DIR = BASE / "static" / "videos"
DOWNLOAD_DIR = BASE / "static" / "downloads"
PINTEREST_DIR = BASE / "static" / "pinterest" / "kleinian-gardens"


@dataclass(frozen=True)
class Preset:
    title: str
    slug: str
    n: int
    ring: float
    radius: float
    depth: int
    twist: float
    phase: float
    view: float
    palette: tuple[str, ...]
    bg: tuple[str, str]
    min_radius: float = 0.0024
    max_radius: float = 8.0


@dataclass(frozen=True)
class Circle:
    z: complex
    r: float
    depth: int


PALETTES = {
    "aurora": ("#44f1ff", "#fff7cf", "#ff5e8a", "#ffd15a", "#8bf7c7"),
    "cathedral": ("#f9c56b", "#fff4d5", "#48d6ff", "#c084fc", "#ff6b6b"),
    "orchid": ("#f0abfc", "#67e8f9", "#fef3c7", "#fb7185", "#a7f3d0"),
    "ember": ("#f97316", "#facc15", "#f8fafc", "#fb7185", "#38bdf8"),
    "glacier": ("#a5f3fc", "#f8fafc", "#60a5fa", "#f0abfc", "#fcd34d"),
}


PRESETS = [
    Preset("Inversion Cathedral", "cathedral", 5, 1.07, 0.76, 7, 0.10, 0.03, 2.95, PALETTES["cathedral"], ("#05050a", "#101018")),
    Preset("Mobius Bloom", "bloom", 6, 1.00, 0.71, 7, 0.18, 0.23, 2.90, PALETTES["aurora"], ("#03070b", "#10151c")),
    Preset("Hyperbolic Orchid", "orchid", 5, 0.92, 0.82, 7, -0.14, 0.48, 2.75, PALETTES["orchid"], ("#06040b", "#140b16")),
    Preset("Inversion Relic", "relic", 4, 1.03, 0.86, 8, 0.07, 0.15, 2.85, PALETTES["ember"], ("#070604", "#160d06")),
    Preset("Limit Set Aurora", "aurora", 7, 1.08, 0.62, 7, 0.22, 0.38, 3.05, PALETTES["aurora"], ("#02070c", "#07151a")),
    Preset("Circle Lattice", "lattice", 6, 1.13, 0.67, 7, -0.09, 0.66, 3.05, PALETTES["glacier"], ("#03060b", "#0d1220")),
    Preset("Golden Inversive Gate", "gate", 5, 1.18, 0.70, 7, 0.16, 0.80, 3.10, PALETTES["cathedral"], ("#060504", "#15100a")),
    Preset("Kleinian Garden", "garden", 6, 0.96, 0.75, 7, -0.19, 0.12, 2.82, PALETTES["orchid"], ("#05050a", "#111018")),
    Preset("Loxodromic Pearl", "pearl", 7, 0.98, 0.66, 7, 0.13, 0.58, 2.88, PALETTES["glacier"], ("#03050a", "#0f1720")),
    Preset("Fractal Reliquary", "reliquary", 4, 0.90, 0.92, 8, -0.06, 0.36, 2.68, PALETTES["ember"], ("#080604", "#160a05")),
    Preset("Mobius Lantern", "lantern", 5, 0.99, 0.80, 7, 0.24, 0.72, 2.85, PALETTES["aurora"], ("#020609", "#0e1217")),
    Preset("Hyperbolic Window", "window", 6, 1.20, 0.64, 7, -0.15, 0.92, 3.12, PALETTES["cathedral"], ("#040508", "#11111a")),
]


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] * (1.0 - t) + b[i] * t) for i in range(3))


def palette_color(palette: tuple[str, ...], t: float, alpha: int) -> tuple[int, int, int, int]:
    t = t % 1.0
    colors = [hex_rgb(c) for c in palette]
    pos = t * len(colors)
    i = int(pos) % len(colors)
    j = (i + 1) % len(colors)
    frac = pos - int(pos)
    rgb = lerp(colors[i], colors[j], frac)
    return (*rgb, alpha)


def make_background(width: int, height: int, bg: tuple[str, str], seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    c0 = np.array(hex_rgb(bg[0]), dtype=np.float32)
    c1 = np.array(hex_rgb(bg[1]), dtype=np.float32)
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, width, dtype=np.float32)[None, :]
    radial = np.sqrt((x - 0.52) ** 2 + ((y - 0.45) * 0.85) ** 2)
    radial = np.clip(1.0 - radial * 1.9, 0, 1)
    vertical = np.clip(y * 0.95, 0, 1)
    mix = np.clip(0.18 + radial * 0.62 + vertical * 0.18, 0, 1)
    arr = c0[None, None, :] * (1 - mix[:, :, None]) + c1[None, None, :] * mix[:, :, None]
    noise = rng.normal(0, 1.4, size=(height, width, 1))
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def apollonian_circles(p: Preset, max_circles: int = 28_000) -> list[Circle]:
    """Generate a clean Apollonian circle packing, then draw it through a Mobius lens."""
    # Three equal inner circles tangent to a unit outer circle.
    r = math.sqrt(3) / (2 + math.sqrt(3))
    d = 1.0 - r
    offset = p.phase * 2 * math.pi
    inner = []
    for k in range(3):
        a = offset + math.pi / 2 + 2 * math.pi * k / 3
        z = d * complex(math.cos(a), math.sin(a))
        inner.append((1.0 / r, z))
    circles = [(-1.0, 0j), *inner]

    def other_solution(state, i):
        bs = [x[0] for x in state]
        zs = [x[1] for x in state]
        others = [j for j in range(4) if j != i]
        b_new = 2 * sum(bs[j] for j in others) - bs[i]
        z_new = (2 * sum(bs[j] * zs[j] for j in others) - bs[i] * zs[i]) / b_new
        return b_new, z_new

    result: list[Circle] = [Circle(z, abs(1 / b), 0) for b, z in circles if b > 0]
    stack = [(tuple(circles), 0)]
    seen = set()

    while stack and len(result) < max_circles:
        state, depth = stack.pop()
        if depth >= p.depth + 2:
            continue
        for i in range(4):
            b_new, z_new = other_solution(state, i)
            if b_new <= 0:
                continue
            r_new = abs(1.0 / b_new)
            if r_new < p.min_radius or r_new > 1.2:
                continue
            if abs(z_new) + r_new > 1.015:
                continue
            key = (round(z_new.real, 6), round(z_new.imag, 6), round(r_new, 6))
            if key in seen:
                continue
            seen.add(key)
            result.append(Circle(z_new, r_new, depth + 1))
            new_state = list(state)
            new_state[i] = (b_new, z_new)
            stack.append((tuple(new_state), depth + 1))

    return result


def mobius_points(z: complex, r: float, p: Preset, phase: float, samples: int, bloom: float = 0.0):
    theta = np.linspace(0, 2 * np.pi, samples, endpoint=True)
    pts = z + r * np.exp(1j * theta)
    rot = np.exp(1j * 2 * np.pi * (phase + p.phase))
    pts *= rot
    # `bloom` pulses the inversion strength so the whole packing surges outward
    # and contracts (a breathing bloom) instead of barely wobbling. Clamped below
    # 1 to keep the Möbius map well-behaved.
    a_mag = min(0.58, 0.23 + 0.045 * p.n + abs(p.twist) * 0.42)
    a_mag = min(0.72, a_mag * (1.0 + bloom))
    a_ang = 2 * np.pi * (phase * 0.5 + p.twist + 0.13 * p.n)
    a = a_mag * complex(math.cos(a_ang), math.sin(a_ang))
    pts = (pts + a) / (1 + np.conj(a) * pts + 1e-8)
    if p.twist:
        rr = np.abs(pts)
        pts *= np.exp(1j * p.twist * 1.35 * rr * rr)
    return pts


def draw_inversion_art(
    p: Preset,
    width: int,
    height: int,
    phase: float = 0.0,
    hue_shift: float = 0.0,
    watermark: bool = False,
    seed_offset: int = 0,
    circles: list[Circle] | None = None,
    bloom: float = 0.0,
) -> Image.Image:
    seed = abs(hash((p.slug, width, height, seed_offset))) % (2**32)
    img = make_background(width, height, p.bg, seed)
    circles = circles if circles is not None else apollonian_circles(p)
    circles.sort(key=lambda item: item.r, reverse=True)

    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fine = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    fd = ImageDraw.Draw(fine)

    aspect = height / width
    x_view = 1.18
    y_view = x_view * aspect
    scale = width / (2 * x_view)

    for circle in circles:
        z, r, depth = circle.z, circle.r, circle.depth
        if r * scale < 0.65:
            continue
        samples = 144 if r > 0.035 else 80
        pts = mobius_points(z, r, p, phase, samples, bloom=bloom)
        xs = width * 0.5 + pts.real * scale
        ys = height * 0.5 - pts.imag * scale
        if xs.max() < -10 or xs.min() > width + 10 or ys.max() < -10 or ys.min() > height + 10:
            continue

        angle_t = (math.atan2(z.imag, z.real) + math.pi) / (2 * math.pi)
        depth_t = depth / max(p.depth, 1)
        t = angle_t * 0.52 + depth_t * 0.42 + hue_shift
        alpha = int(max(36, 205 - depth * 15))
        line = max(1, int(4.8 - depth * 0.36 + min(r * scale, 64) * 0.022))
        glow_line = max(line + 2, int(line * 3.6))
        color = palette_color(p.palette, t, alpha)
        glow_color = palette_color(p.palette, t, max(10, alpha // 3))
        xy = list(zip(xs.tolist(), ys.tolist()))
        if r * scale > 2.0:
            gd.line(xy, fill=glow_color, width=glow_line, joint="curve")
        fd.line(xy, fill=color, width=line, joint="curve")

    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(1.0, width / 640)))
    img = Image.alpha_composite(img.convert("RGBA"), glow)
    img = Image.alpha_composite(img, fine)

    # Small luminous dust from the finest circles.
    dust = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dust)
    for circle in circles[-min(1800, len(circles)):]:
        z, r = circle.z, circle.r
        if r * scale > 1.3:
            continue
        pts = mobius_points(z, 0, p, phase, 1, bloom=bloom)
        cx = width * 0.5 + pts.real[0] * scale
        cy = height * 0.5 - pts.imag[0] * scale
        if 0 <= cx < width and 0 <= cy < height:
            t = ((math.atan2(z.imag, z.real) + math.pi) / (2 * math.pi)) + hue_shift
            col = palette_color(p.palette, t, 95)
            dd.ellipse([cx - 0.65, cy - 0.65, cx + 0.65, cy + 0.65], fill=col)
    dust = dust.filter(ImageFilter.GaussianBlur(radius=0.18))
    img = Image.alpha_composite(img, dust)

    if watermark:
        mark = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        md = ImageDraw.Draw(mark)
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(28, width // 21))
        except Exception:
            font = ImageFont.load_default()
        text = "PREVIEW"
        bbox = md.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        md.text(
            ((width - tw) / 2, (height - th) / 2),
            text,
            fill=(255, 255, 255, 42),
            font=font,
        )
        img = Image.alpha_composite(img, mark)

    return img.convert("RGB")


def save_jpeg(img: Image.Image, path: Path, quality: int = 90):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=quality, optimize=True, progressive=True)


def image_assets():
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    PINTEREST_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    clean_images = []
    for idx, preset in enumerate(PRESETS):
        circles = apollonian_circles(preset)
        clean = draw_inversion_art(preset, 1280, 1600, seed_offset=idx, circles=circles)
        watermarked = draw_inversion_art(preset, 1280, 1600, watermark=True, seed_offset=idx, circles=circles)
        save_jpeg(clean, PREVIEW_DIR / f"kleinian-gardens-image-pack_{idx}_clean.jpg", 92)
        save_jpeg(watermarked, PREVIEW_DIR / f"kleinian-gardens-image-pack_{idx}.jpg", 88)
        hq = draw_inversion_art(preset, 3200, 4000, seed_offset=idx, circles=circles)
        save_jpeg(hq, DOWNLOAD_DIR / f"kleinian-gardens-image-pack_{idx}_portrait.jpg", 94)
        clean_images.append(clean)

    cover_clean = clean_images[0]
    save_jpeg(cover_clean, PREVIEW_DIR / "kleinian-gardens-image-pack_clean.jpg", 92)
    save_jpeg(draw_inversion_art(PRESETS[0], 1280, 1600, watermark=True), PREVIEW_DIR / "kleinian-gardens-image-pack.jpg", 88)
    save_jpeg(cover_clean.resize((1200, 1500), Image.Resampling.LANCZOS), COVER_DIR / "kleinian-gardens-image-pack.jpg", 90)

    # Vertical social pin/contact asset.
    pin = Image.new("RGB", (1000, 1500), "#06070c")
    art = cover_clean.resize((1000, 1250), Image.Resampling.LANCZOS)
    pin.paste(art, (0, 0))
    overlay = Image.new("RGBA", pin.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([0, 1110, 1000, 1500], fill=(4, 5, 9, 214))
    try:
        title_font = ImageFont.truetype("DejaVuSerif-Bold.ttf", 58)
        body_font = ImageFont.truetype("DejaVuSans.ttf", 25)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    od.text((58, 1160), "Kleinian Gardens", fill=(255, 244, 214, 255), font=title_font)
    od.text((60, 1245), "Hyperbolic inversion art loops\nfrom Mobius transformations", fill=(195, 224, 230, 235), font=body_font, spacing=8)
    od.text((60, 1390), "mathrelaxing.store", fill=(255, 209, 90, 255), font=body_font)
    pin = Image.alpha_composite(pin.convert("RGBA"), overlay).convert("RGB")
    save_jpeg(pin, PINTEREST_DIR / "kleinian-gardens-pinterest.jpg", 90)

    loop_cover = draw_inversion_art(PRESETS[1], 1280, 1600, phase=0.15, hue_shift=0.10)
    save_jpeg(loop_cover, PREVIEW_DIR / "kleinian-gardens-loop-pack_clean.jpg", 92)
    save_jpeg(draw_inversion_art(PRESETS[1], 1280, 1600, phase=0.15, hue_shift=0.10, watermark=True), PREVIEW_DIR / "kleinian-gardens-loop-pack.jpg", 88)
    save_jpeg(loop_cover.resize((1200, 1500), Image.Resampling.LANCZOS), COVER_DIR / "kleinian-gardens-loop-pack.jpg", 90)


def encode_video(key: str, preset: Preset, duration: int, motion: str):
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    width, height, fps = 720, 900, 30
    out_width, out_height = 1080, 1350
    output = VIDEO_DIR / f"{key}_1080p30.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={out_width}:{out_height}:flags=lanczos",
        "-preset", "medium",
        "-crf", "23",
        "-movflags", "+faststart",
        str(output),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n_frames = duration * fps
    circles = apollonian_circles(preset, max_circles=9_000)
    for i in range(n_frames):
        t = i / n_frames
        tau = 2 * math.pi * t
        if motion == "bloom":
            # Real breathing bloom: the packing surges outward and draws back in
            # while swirling, instead of barely wobbling.
            phase = 0.12 * math.sin(tau)
            bloom = 0.42 * math.sin(tau)
            hue = t
        elif motion == "orbit":
            # Full orbital sweep, now with a breath layered on so it pulses as it
            # travels rather than rigidly rotating.
            phase = t
            bloom = 0.22 * math.sin(2 * tau)
            hue = 0.25 * math.sin(tau)
        else:  # cathedral
            # Inversion packing opening and closing with depth.
            phase = 0.14 * math.sin(tau)
            bloom = -0.38 * math.sin(tau)
            hue = 0.5 * t
        frame = draw_inversion_art(preset, width, height, phase=phase, hue_shift=hue,
                                   seed_offset=0, circles=circles, bloom=bloom)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {key}")


def video_assets():
    encode_video("kleinian_bloom", PRESETS[1], 12, "bloom")
    encode_video("kleinian_orbit", PRESETS[4], 12, "orbit")
    encode_video("kleinian_cathedral", PRESETS[0], 12, "cathedral")


def main():
    image_assets()
    video_assets()


if __name__ == "__main__":
    main()
