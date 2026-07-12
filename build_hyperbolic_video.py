import math
import os
import shutil
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_MP4 = "/var/www/mathrelaxing.store/static/videos/tiktok_hyperbolic_v1.mp4"
FRAMES = Path("/tmp/hyperbolic_frames")
FPS = 24
W, H = 1080, 1920

CARD_MX = 60
CARD_W = W - 2 * CARD_MX
CARD_H = round(CARD_W * 9 / 7)
CARD_X = CARD_MX
CARD_Y = 460
CARD_RAD = 34

BG_TOP = (31, 24, 52)
BG_BOT = (58, 34, 74)
GOLD = (240, 197, 116)
WHITE = (255, 255, 255)

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)

def make_background():
    top = np.array(BG_TOP, float); bot = np.array(BG_BOT, float)
    col = (top[None, :] + (bot - top)[None, :] * (np.arange(H)[:, None] / (H - 1)))
    return Image.fromarray(np.repeat(col[:, None, :], W, axis=1).astype(np.uint8), "RGB")

def card_mask():
    m = Image.new("L", (CARD_W, CARD_H), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, CARD_W - 1, CARD_H - 1], radius=CARD_RAD, fill=255)
    return m

def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)

def draw_text_centered(canvas, y, text, f, color, alpha=1.0):
    d = ImageDraw.Draw(canvas, "RGBA")
    c = (*color, int(255 * alpha))
    d.text((W / 2, y), text, font=f, fill=c, anchor="mm")

def make_music(duration_s, path):
    import wave
    sr = 44100
    n = int(duration_s * sr) + sr
    out = np.zeros(n, dtype=np.float64)

    def add_pad(freqs, start, dur, amp):
        i0 = int(start * sr); i1 = min(n, int((start + dur) * sr))
        if i1 <= i0: return
        L = i1 - i0
        win = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(L) / max(1, L - 1))
        lt = np.arange(L) / sr
        sig = np.zeros(L)
        for f in freqs:
            a = amp * (0.55 if f < 150 else 1.0)
            sig += a * (np.sin(2 * np.pi * f * lt) + 0.25 * np.sin(2 * np.pi * 2 * f * lt))
        out[i0:i1] += sig * win

    chords = [[110.00, 261.63, 329.63, 392.00, 493.88], [87.31, 261.63, 329.63, 440.00], [130.81, 329.63, 392.00, 493.88], [98.00, 246.94, 293.66, 392.00]]
    seg = duration_s / 8
    for k in range(8):
        ch = chords[k % len(chords)]
        add_pad(ch, max(0.0, k * seg - 0.3), seg + 0.8, amp=0.10)

    def add_bell(freq, start, amp, dur=1.6):
        i0 = int(start * sr); i1 = min(n, int((start + dur) * sr))
        if i1 <= i0: return
        L = i1 - i0; lt = np.arange(L) / sr
        env = np.exp(-lt * 3.0)
        out[i0:i1] += amp * env * (np.sin(2 * np.pi * freq * lt) + 0.4 * np.sin(2 * np.pi * 2 * freq * lt) + 0.15 * np.sin(2 * np.pi * 3 * freq * lt))

    penta = [440.00, 523.25, 587.33, 659.25, 783.99, 880.00]
    bt, idx = 1.0, 0
    while bt < duration_s - 0.3:
        amp = min(0.16, 0.05 + 0.11 * max(0.0, (bt - 6.0) / 6.0))
        add_bell(penta[idx % len(penta)], bt, amp=amp)
        idx += 1; bt += 0.9 if bt < 6.0 else 0.45

    d = int(0.18 * sr); rev = np.zeros(n); rev[d:] = out[:-d] * 0.35
    out += rev
    fi, fo = int(1.0 * sr), int(1.6 * sr)
    out[:fi] *= np.linspace(0, 1, fi); out[-fo:] *= np.linspace(1, 0, fo)
    out /= (np.max(np.abs(out)) + 1e-9); out *= 0.7

    pcm = (out * 32767).astype(np.int16)
    stereo = np.column_stack([pcm, pcm])
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(stereo.tobytes())

def load_img(path):
    img = Image.open(path).convert("RGB")
    sw, sh = img.size
    ratio = min(CARD_W / sw, CARD_H / sh)
    nw, nh = int(sw * ratio), int(sh * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    res = Image.new("RGB", (CARD_W, CARD_H), (255,255,255))
    res.paste(img, ((CARD_W - nw)//2, (CARD_H - nh)//2))
    return res

def create_flood_fill_coloring(sample_img, seed):
    import numpy as np
    from scipy.ndimage import label
    from PIL import Image, ImageChops

    np.random.seed(seed)
    
    # Convert sample to numpy array (grayscale)
    gray = np.array(sample_img.convert("L"))
    
    # Threshold to find white areas (the shapes to fill)
    # Assume lines are dark, so areas to fill are bright
    mask = gray > 200
    
    # Label connected components
    labeled_array, num_features = label(mask)
    
    # Create random colors for each feature
    # 0 is the background (black lines), keep it black or white
    colors = np.random.randint(50, 255, size=(num_features + 1, 3), dtype=np.uint8)
    colors[0] = [255, 255, 255] # Black lines area should be white before multiplication
    
    # Map labels to colors
    colored_arr = colors[labeled_array]
    
    # Create PIL Image
    colored_img = Image.fromarray(colored_arr, "RGB")
    
    # Multiply with original image to keep the anti-aliased black lines
    final_img = ImageChops.multiply(colored_img, sample_img)
    return final_img

def render_scene(sample_img, title_top, title_bot, fidx, frames_draw, frames_paint, frames_hold):
    cmask = card_mask()
    bg = make_background()
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([CARD_X, CARD_Y + 16, CARD_X + CARD_W, CARD_Y + CARD_H + 28], radius=CARD_RAD, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(26))
    bg_with_shadow = Image.alpha_composite(bg.convert("RGBA"), shadow).convert("RGB")

    f_top = font("DejaVuSans-Bold.ttf", 46)
    f_bot = font("DejaVuSerif-Italic.ttf", 40)
    white_card = Image.new("RGB", (CARD_W, CARD_H), (255, 255, 255))
    
    # Generate the colored version using flood fill!
    color_img = create_flood_fill_coloring(sample_img, fidx)
    line_img = sample_img
    
    def paste_card(card_rgb, text_alpha):
        frame = bg_with_shadow.copy()
        frame.paste(card_rgb, (CARD_X, CARD_Y), cmask)
        draw_text_centered(frame, 220, title_top, f_top, GOLD, text_alpha)
        draw_text_centered(frame, 300, title_bot, f_bot, WHITE, text_alpha)
        return frame

    for f in range(frames_draw):
        prog = smoothstep((f + 1) / frames_draw)
        mask = Image.new("L", (CARD_W, CARD_H), 0)
        mdraw = ImageDraw.Draw(mask)
        max_r = math.hypot(CARD_W/2, CARD_H/2)
        r = prog * max_r
        mdraw.ellipse([CARD_W/2 - r, CARD_H/2 - r, CARD_W/2 + r, CARD_H/2 + r], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(10))
        card = Image.composite(line_img, white_card, mask)
        frame = paste_card(card, text_alpha=prog)
        frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1

    # Paint animation!
    for f in range(frames_paint):
        prog = smoothstep((f + 1) / frames_paint)
        mask = Image.new("L", (CARD_W, CARD_H), 0)
        mdraw = ImageDraw.Draw(mask)
        max_r = math.hypot(CARD_W/2, CARD_H/2)
        r = prog * max_r
        mdraw.ellipse([CARD_W/2 - r, CARD_H/2 - r, CARD_W/2 + r, CARD_H/2 + r], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(15))
        card = Image.composite(color_img, line_img, mask)
        frame = paste_card(card, text_alpha=1.0)
        frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1

    hold_frame = paste_card(color_img, text_alpha=1.0)
    for f in range(frames_hold):
        hold_frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1
        
    for f in range(12):
        prog = smoothstep((f + 1) / 12)
        frame = paste_card(color_img, text_alpha=1.0 - prog)
        frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1

    return fidx

def main():
    if FRAMES.exists(): shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)

    base_dir = "/var/www/mathrelaxing.store/static/img/"
    
    pages = [
        ("hyp_sample_1.png", "Explore non-euclidean geometry.", "The beauty of the Poincaré disk."),
        ("hyp_sample_2.png", "Mind-bending hyperbolic patterns.", "Intricate, organic tessellations."),
        ("hyp_sample_3.png", "A deep, mindful experience.", "50 unique designs to relax and color."),
    ]
    
    fidx = 0
    bg = make_background()
    f_intro1 = font("DejaVuSans-Bold.ttf", 54)
    f_intro2 = font("DejaVuSerif-Italic.ttf", 44)
    
    for f in range(2 * FPS):
        prog = smoothstep(f / (1.0 * FPS)) if f < FPS else 1.0
        frame = bg.copy()
        draw_text_centered(frame, H/2 - 60, "Discover Hyperbolic Gardens", f_intro1, GOLD, prog)
        draw_text_centered(frame, H/2 + 30, "A Mathematical Coloring Book...", f_intro2, WHITE, prog)
        frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1
        
    for f in range(12):
        prog = smoothstep((f+1)/12)
        frame = bg.copy()
        draw_text_centered(frame, H/2 - 60, "Discover Hyperbolic Gardens", f_intro1, GOLD, 1.0 - prog)
        draw_text_centered(frame, H/2 + 30, "A Mathematical Coloring Book...", f_intro2, WHITE, 1.0 - prog)
        frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1

    for (p, t_top, t_bot) in pages:
        p_img = load_img(os.path.join(base_dir, p))
        fidx = render_scene(p_img, t_top, t_bot, fidx, int(2.5 * FPS), int(2.5 * FPS), int(1.5 * FPS))

    cover = load_img("/var/www/mathrelaxing.store/static/img/hyperbolic_gardens_cover.png")
    cmask = card_mask()
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([CARD_X, CARD_Y + 16, CARD_X + CARD_W, CARD_Y + CARD_H + 28], radius=CARD_RAD, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(26))
    bg_with_shadow = Image.alpha_composite(bg.convert("RGBA"), shadow).convert("RGB")
    
    f_out1 = font("DejaVuSans-Bold.ttf", 60)
    f_out2 = font("DejaVuSans-Bold.ttf", 40)
    f_out3 = font("DejaVuSans.ttf", 34)
    
    for f in range(3 * FPS):
        prog = smoothstep(min(1.0, f / (1.5 * FPS)))
        frame = bg_with_shadow.copy()
        
        y_offset = int((1.0 - prog) * 200)
        frame.paste(cover, (CARD_X, CARD_Y + y_offset), cmask)
        
        draw_text_centered(frame, 220, "HYPERBOLIC GARDENS", f_out1, GOLD, prog)
        draw_text_centered(frame, 300, "Coloring Book", f_out2, WHITE, prog)
        
        a = int(255 * prog)
        pill_w, pill_h = 680, 80
        px0 = (W - pill_w) / 2; py0 = 1672
        pd = ImageDraw.Draw(frame, "RGBA")
        pd.rounded_rectangle([px0, py0, px0 + pill_w, py0 + pill_h], radius=pill_h / 2, fill=(255, 255, 255, a))
        pd.text((W / 2, py0 + pill_h / 2), "$14.99  ·  FREE SHIPPING", font=f_out2, fill=(31, 24, 52, a), anchor="mm")
        draw_text_centered(frame, 1788, "mathrelaxing.store/product/hyperbolic-gardens-coloring-book", f_out3, WHITE, prog)
        frame.save(FRAMES / f"f_{fidx:05d}.png"); fidx += 1

    print(f"frames written: {fidx}")
    silent = "/tmp/hyperbolic_silent.mp4"
    music = "/tmp/hyperbolic_music.wav"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(FRAMES / "f_%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-crf", "18", "-movflags", "+faststart", silent], check=True)
    make_music(fidx / FPS, music)
    subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", music, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", OUT_MP4], check=True)
    print(f"DONE -> {OUT_MP4}")

if __name__ == "__main__":
    main()
