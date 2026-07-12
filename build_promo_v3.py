import os
import io
import math
import subprocess
from PIL import Image, ImageDraw, ImageFont

FPS = 30
W, H = 1080, 1920

STATIC_VIDEOS = "/var/www/mathrelaxing.store/static/videos"

# Font
MONO_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
if not os.path.exists(MONO_PATH):
    MONO_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
mono_large = ImageFont.truetype(MONO_PATH, 50)
mono_small = ImageFont.truetype(MONO_PATH, 35)

def read_video_frames(video_path, start_sec, duration_sec):
    num_frames = int(duration_sec * FPS)
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
    while len(frames) < num_frames and len(frames) > 0:
        frames.append(frames[-1].copy())
    return frames

def fade_text(draw, text, font, pos, opacity, color=(255, 255, 255)):
    mask = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(mask)
    d.text(pos, text, font=font, fill=int(opacity * 255), anchor="mm")
    color_img = Image.new('RGB', (W, H), color)
    return mask, color_img

def build_scene(frames, t_duration, text_main, text_sub=None):
    # Renders a single scene and yields the raw bytes
    for i, frame in enumerate(frames):
        t = i / FPS
        base = frame.copy()
        
        # Darken base
        overlay = Image.new('RGBA', base.size, (0, 0, 0, int(255 * 0.4)))
        base = Image.alpha_composite(base.convert('RGBA'), overlay).convert('RGB')
        
        # Fade logic: fade in (0 to 1s), hold (1 to 3s), fade out (3 to 4s)
        if t < 1.0:
            alpha = t
        elif t > (t_duration - 1.0):
            alpha = max(0.0, t_duration - t)
        else:
            alpha = 1.0
            
        draw = ImageDraw.Draw(base)
        mask, col = fade_text(draw, text_main, mono_large, (W//2, H//2), alpha)
        base.paste(col, mask=mask)
        
        if text_sub:
            mask2, col2 = fade_text(draw, text_sub, mono_small, (W//2, H//2 + 80), alpha, color=(200, 169, 110))
            base.paste(col2, mask=mask2)
            
        yield base.tobytes()

def build_video():
    out_cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo", "-s", f"{W}x{H}",
        "-pix_fmt", "rgb24", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p", "promo_v3_raw.mp4"
    ]
    out_proc = subprocess.Popen(out_cmd, stdin=subprocess.PIPE)

    scenes = [
        ("particle_storm_1080p30.mp4", "4 K   D I G I T A L   A R T", None),
        ("lorenz_drift_1080p30.mp4", "P R E M I U M   A P P A R E L", None),
        ("ff_flame_aurora_1080p30.mp4", "C O L O R I N G   B O O K S", None),
        ("particle_nebula_1080p30.mp4", "D E S K   M A T S", None),
        ("particle_wave_1080p30.mp4", "M A T H E M A T I C A L   A R T", None),
        ("particle_vortex_1080p30.mp4", None, "mathrelaxing.store")
    ]

    logo = Image.open("/var/www/mathrelaxing.store/static/img/logo.png").convert("RGBA")
    # Resize logo
    lw, lh = logo.size
    new_lw = 600
    new_lh = int(lh * (new_lw / lw))
    logo = logo.resize((new_lw, new_lh), Image.LANCZOS)

    for vid_file, t_main, t_sub in scenes:
        frames = read_video_frames(os.path.join(STATIC_VIDEOS, vid_file), 0.0, 4.0)
        
        # Build scene
        for i, frame in enumerate(frames):
            t = i / FPS
            base = frame.copy()
            
            overlay = Image.new('RGBA', base.size, (0, 0, 0, int(255 * 0.4)))
            base = Image.alpha_composite(base.convert('RGBA'), overlay).convert('RGB')
            
            if t < 1.0:
                alpha = t
            elif t > 3.0:
                alpha = max(0.0, 4.0 - t)
            else:
                alpha = 1.0
                
            draw = ImageDraw.Draw(base)
            
            # If last scene, show logo instead of main text
            if t_main is None:
                # Fade in logo
                logo_with_alpha = logo.copy()
                logo_with_alpha.putalpha(logo_with_alpha.getchannel('A').point(lambda p: p * alpha))
                base.paste(logo_with_alpha, (W//2 - new_lw//2, H//2 - new_lh//2 - 50), mask=logo_with_alpha)
            else:
                mask, col = fade_text(draw, t_main, mono_large, (W//2, H//2), alpha)
                base.paste(col, mask=mask)
            
            if t_sub:
                mask2, col2 = fade_text(draw, t_sub, mono_small, (W//2, H//2 + new_lh//2 + 50) if t_main is None else (W//2, H//2 + 80), alpha, color=(200, 169, 110))
                base.paste(col2, mask=mask2)
                
            out_proc.stdin.write(base.tobytes())

    out_proc.stdin.close()
    out_proc.wait()
    print("Done generating promo_v3_raw.mp4")

    print("Merging with audio...")
    audio_cmd = [
        "ffmpeg", "-y", "-i", "promo_v3_raw.mp4", "-i", "audio.mp3",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-af", "afade=t=out:st=22:d=2", "-t", "24",
        "promo_v3_with_audio.mp4"
    ]
    subprocess.run(audio_cmd, check=True)
    print("Done generating promo_v3_with_audio.mp4")

if __name__ == "__main__":
    build_video()
