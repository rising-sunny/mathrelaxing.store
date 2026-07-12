import os
import io
import math
import subprocess
import urllib.request
import urllib.error
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

FPS = 30
W, H = 1080, 1920

# We will run this on the VPS so we can use local paths for videos
STATIC_VIDEOS = "/var/www/mathrelaxing.store/static/videos"
STATIC_IMG = "/var/www/mathrelaxing.store/static/img"

# Fonts
GARAMOND_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
MONO_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
if not os.path.exists(GARAMOND_PATH):
    GARAMOND_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

garamond_large = ImageFont.truetype(GARAMOND_PATH, 90)
garamond_mid = ImageFont.truetype(GARAMOND_PATH, 60)
mono_small = ImageFont.truetype(MONO_PATH, 45)

def fetch_mockup(url, cache_path):
    if not os.path.exists(cache_path):
        print(f"Fetching {url}")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req) as response:
                img_data = response.read()
                with open(cache_path, "wb") as f:
                    f.write(img_data)
        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code}: {e.reason}")
            # Fallback to creating a dummy image
            img = Image.new("RGB", (1000, 1000), (40, 40, 40))
            img.save(cache_path, "JPEG")
    return Image.open(cache_path).convert("RGB")

# Assets
tshirt_mockup = fetch_mockup("https://mathrelaxing.store/api/render/mockup?product=neon-aizawa-apparel&format=unisex_tshirt-1", "tshirt_mockup_tmp.jpg")
book_mockup = Image.open(os.path.join(STATIC_IMG, "hyperbolic_gardens_cover.png")).convert("RGB")

def round_corners(im, rad):
    mask = Image.new('L', im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, im.size[0], im.size[1]), rad, fill=255)
    out = im.copy()
    out.putalpha(mask)
    return out

tshirt_card = round_corners(tshirt_mockup.resize((800, 800)), 40)
book_card = round_corners(book_mockup.resize((700, int(700*1.3))), 40)

def read_video_frames(video_path, start_sec, duration_sec):
    # Output frames in RGB
    num_frames = int(duration_sec * FPS)
    cmd = [
        "ffmpeg", "-ss", str(start_sec), "-t", str(duration_sec),
        "-i", video_path,
        "-f", "image2pipe", "-pix_fmt", "rgb24", "-vcodec", "rawvideo", "-"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    
    # We expect 1080x1350 or 1080x1080 depending on the video.
    # We will let ffmpeg do the scaling/cropping to 1080x1920 so we just get raw 1080x1920 frames!
    proc.kill() # cancel this approach
    
    cmd = [
        "ffmpeg", "-ss", str(start_sec), "-t", str(duration_sec),
        "-i", video_path,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-f", "image2pipe", "-pix_fmt", "rgb24", "-vcodec", "rawvideo", "-"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    frames = []
    frame_size = W * H * 3
    for _ in range(num_frames):
        raw = proc.stdout.read(frame_size)
        if len(raw) != frame_size:
            break
        img = Image.frombytes("RGB", (W, H), raw)
        frames.append(img)
    proc.stdout.close()
    proc.wait()
    # Pad if missing
    while len(frames) < num_frames and len(frames) > 0:
        frames.append(frames[-1].copy())
    return frames

def fade_text(draw, text, font, pos, opacity, color=(255, 255, 255)):
    # draw text on a temporary image to handle opacity
    mask = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(mask)
    d.text(pos, text, font=font, fill=int(opacity * 255), anchor="mm")
    
    color_img = Image.new('RGB', (W, H), color)
    return mask, color_img

def build_video():
    out_cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo", "-s", f"{W}x{H}",
        "-pix_fmt", "rgb24", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p", "promo_tiktok.mp4"
    ]
    out_proc = subprocess.Popen(out_cmd, stdin=subprocess.PIPE)

    # 0 - 3s: Hook (Particle Vortex)
    frames_vortex = read_video_frames(os.path.join(STATIC_VIDEOS, "particle_vortex_1080p30.mp4"), 2.0, 3.0)
    for i, frame in enumerate(frames_vortex):
        t = i / FPS
        base = frame.copy()
        draw = ImageDraw.Draw(base)
        # darken base slightly
        overlay = Image.new('RGBA', base.size, (0, 0, 0, int(255 * 0.4)))
        base = Image.alpha_composite(base.convert('RGBA'), overlay).convert('RGB')
        
        # text 1
        if t < 1.5:
            alpha = min(1.0, t / 0.5) if t < 1.0 else max(0.0, 1.0 - (t - 1.0)/0.5)
            mask, col = fade_text(draw, "Mathematics isn't just numbers.", garamond_large, (W//2, H//2), alpha)
            base.paste(col, mask=mask)
        else:
            t2 = t - 1.5
            alpha = min(1.0, t2 / 0.5) if t2 < 1.0 else max(0.0, 1.0 - (t2 - 1.0)/0.5)
            mask, col = fade_text(draw, "It's beautiful.", garamond_large, (W//2, H//2), alpha)
            base.paste(col, mask=mask)
            
        out_proc.stdin.write(base.tobytes())

    # 3 - 7s: Apparel
    frames_kleinian = read_video_frames(os.path.join(STATIC_VIDEOS, "kleinian_cathedral_1080p30.mp4"), 0.0, 4.0)
    for i, frame in enumerate(frames_kleinian):
        t = i / FPS
        base = frame.copy().convert('RGBA')
        # darken
        overlay = Image.new('RGBA', base.size, (0, 0, 0, int(255 * 0.6)))
        base = Image.alpha_composite(base, overlay)
        
        # Slide in mockup from bottom
        y_pos = H + 400
        if t < 0.5:
            y_pos = H + 400 - (H + 400 - (H//2 + 100)) * math.sin((t/0.5) * math.pi/2)
        elif t < 3.5:
            # float gently
            y_pos = (H//2 + 100) + math.sin(t * 2) * 20
        else:
            y_pos = (H//2 + 100) + (H + 400 - (H//2 + 100)) * math.sin(((t-3.5)/0.5) * math.pi/2)
            
        base.paste(tshirt_card, (W//2 - 400, int(y_pos) - 400), tshirt_card)
        
        # Text
        alpha = min(1.0, t / 0.5) if t < 3.5 else max(0.0, 1.0 - (t - 3.5)/0.5)
        mask, col = fade_text(ImageDraw.Draw(base), "Premium POD Apparel", garamond_large, (W//2, 300), alpha)
        base.paste(col, mask=mask)
        
        out_proc.stdin.write(base.convert('RGB').tobytes())

    # 7 - 11s: Books
    frames_joukowski = read_video_frames(os.path.join(STATIC_VIDEOS, "joukowski_hue_1080p30.mp4"), 2.0, 4.0)
    for i, frame in enumerate(frames_joukowski):
        t = i / FPS
        base = frame.copy().convert('RGBA')
        overlay = Image.new('RGBA', base.size, (0, 0, 0, int(255 * 0.6)))
        base = Image.alpha_composite(base, overlay)
        
        bw, bh = book_card.size
        # slide in from left
        x_pos = -bw
        if t < 0.5:
            x_pos = -bw + (W//2 - bw//2 + bw) * math.sin((t/0.5) * math.pi/2)
        elif t < 3.5:
            x_pos = W//2 - bw//2
        else:
            x_pos = W//2 - bw//2 + (W + bw) * math.sin(((t-3.5)/0.5) * math.pi/2)
            
        # Float
        y_pos = H//2 - bh//2 + math.cos(t * 2) * 20
        base.paste(book_card, (int(x_pos), int(y_pos)), book_card)
        
        alpha = min(1.0, t / 0.5) if t < 3.5 else max(0.0, 1.0 - (t - 3.5)/0.5)
        mask, col = fade_text(ImageDraw.Draw(base), "Coloring Books & 4K Art", garamond_large, (W//2, 300), alpha)
        base.paste(col, mask=mask)
        
        out_proc.stdin.write(base.convert('RGB').tobytes())

    # 11 - 15s: Outro
    frames_galaxy = read_video_frames(os.path.join(STATIC_VIDEOS, "particle_galaxy_1080p30.mp4"), 0.0, 4.0)
    for i, frame in enumerate(frames_galaxy):
        t = i / FPS
        base = frame.copy().convert('RGBA')
        overlay = Image.new('RGBA', base.size, (0, 0, 0, int(255 * 0.3)))
        base = Image.alpha_composite(base, overlay)
        
        alpha = min(1.0, t / 0.5) if t < 3.5 else max(0.0, 1.0 - (t - 3.5)/0.5)
        draw = ImageDraw.Draw(base)
        mask1, col1 = fade_text(draw, "MathRelaxing.store", garamond_large, (W//2, H//2 - 50), alpha)
        mask2, col2 = fade_text(draw, "Link in bio", mono_small, (W//2, H//2 + 80), alpha, color=(200, 169, 110))
        
        base.paste(col1, mask=mask1)
        base.paste(col2, mask=mask2)
        
        out_proc.stdin.write(base.convert('RGB').tobytes())

    out_proc.stdin.close()
    out_proc.wait()
    print("Done generating promo_tiktok.mp4")

if __name__ == "__main__":
    build_video()
