"""Compose TikTok 9:16 frames from Happy Chemicals product art."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "frames"
OUT.mkdir(exist_ok=True)
W, H = 1080, 1920


def load(name: str) -> Image.Image:
    return Image.open(ROOT / name).convert("RGB")


def fit_contain(im: Image.Image, tw: int, th: int, bg=(250, 246, 240)) -> Image.Image:
    canvas = Image.new("RGB", (tw, th), bg)
    im = im.copy()
    im.thumbnail((tw - 80, th - 80), Image.Resampling.LANCZOS)
    x = (tw - im.width) // 2
    y = (th - im.height) // 2
    canvas.paste(im, (x, y))
    return canvas


def fit_cover(im: Image.Image, tw: int, th: int) -> Image.Image:
    im = im.copy()
    scale = max(tw / im.width, th / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (nw - tw) // 2
    y = (nh - th) // 2
    return im.crop((x, y, x + tw, y + th))


def soft_bg_from(im: Image.Image) -> Image.Image:
    bg = fit_cover(im, W, H).filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(0.55)
    overlay = Image.new("RGB", (W, H), (250, 246, 240))
    return Image.blend(bg, overlay, 0.35)


def place_card(bg: Image.Image, card: Image.Image, max_w: int, max_h: int, cy: int) -> Image.Image:
    card = card.copy()
    card.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    # soft shadow
    shadow = Image.new("RGBA", (card.width + 40, card.height + 40), (0, 0, 0, 0))
    s = Image.new("RGBA", (card.width, card.height), (0, 0, 0, 60))
    shadow.paste(s, (20, 24))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    out = bg.convert("RGBA")
    x = (W - card.width) // 2
    y = cy - card.height // 2
    out.alpha_composite(shadow, (x - 10, y - 6))
    out.paste(card, (x, y))
    return out.convert("RGB")


def try_font(size: int):
    for name in (
        "C:/Windows/Fonts/georgia.ttf",
        "C:/Windows/Fonts/Georgia.ttf",
        "C:/Windows/Fonts/times.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_text_center(draw, y, text, font, fill=(30, 28, 26)):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, font=font, fill=fill)


def frame_hero():
    hero = load("01_hero.jpg")
    bg = soft_bg_from(hero)
    out = place_card(bg, hero, 920, 1200, H // 2 - 40)
    return out


def frame_set():
    s = load("02_set.jpg")
    bg = soft_bg_from(s)
    out = place_card(bg, s, 980, 1300, H // 2 - 20)
    return out


def frame_molecule(name: str, label: str, accent=(180, 60, 80)):
    mol = load(name)
    bg = soft_bg_from(mol)
    # taller crop of molecule
    out = place_card(bg, mol, 900, 1100, H // 2 - 80)
    d = ImageDraw.Draw(out)
    font = try_font(54)
    small = try_font(32)
    draw_text_center(d, H - 280, label, font, accent)
    draw_text_center(d, H - 210, "molecule print", small, (90, 88, 85))
    return out


def frame_cta():
    cover = load("happy-chemicals-print-set_cover.jpg")
    bg = soft_bg_from(cover)
    out = place_card(bg, cover, 860, 1000, H // 2 - 120)
    d = ImageDraw.Draw(out)
    # bottom CTA bar
    bar = Image.new("RGBA", (W, 420), (250, 246, 240, 230))
    out = out.convert("RGBA")
    out.alpha_composite(bar, (0, H - 420))
    out = out.convert("RGB")
    d = ImageDraw.Draw(out)
    title = try_font(64)
    sub = try_font(36)
    cta = try_font(42)
    tiny = try_font(28)
    draw_text_center(d, H - 360, "Happy Chemicals", title, (25, 23, 22))
    draw_text_center(d, H - 280, "4 molecule art prints · $8.99", sub, (90, 88, 85))
    draw_text_center(d, H - 200, "mathrelaxing.store", cta, (160, 50, 70))
    draw_text_center(d, H - 140, "instant digital delivery", tiny, (120, 118, 115))
    return out


def main():
    frames = {
        "01_hero.jpg": frame_hero(),
        "02_set.jpg": frame_set(),
        "03_serotonin.jpg": frame_molecule("04_serotonin.jpg", "serotonin", (190, 55, 70)),
        "04_dopamine.jpg": frame_molecule("05_dopamine.jpg", "dopamine", (50, 100, 170)),
        "05_cta.jpg": frame_cta(),
    }
    for name, im in frames.items():
        path = OUT / name
        im.save(path, "JPEG", quality=92)
        print("wrote", path, im.size)


if __name__ == "__main__":
    main()
