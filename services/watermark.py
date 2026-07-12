"""Add a diagonal 'PREVIEW' watermark to images."""
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import math


def enhance_preview(img: Image.Image, contrast: float = 1.15, saturation: float = 1.25) -> Image.Image:
    """Boost contrast and color saturation for vivid preview images."""
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Color(img).enhance(saturation)
    return img


def add_watermark(img: Image.Image, text: str = "PREVIEW", opacity: int = 30) -> Image.Image:
    """Add a repeating diagonal watermark across the image."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Determine font size based on image dimensions
    font_size = max(18, min(img.width, img.height) // 12)

    # Try to use a decent font, fall back to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    # Calculate text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Diagonal angle
    angle = -30
    spacing_x = tw + 300
    spacing_y = th + 200

    # Draw repeating text across a large canvas, then rotate
    canvas_w = int(math.sqrt(img.width ** 2 + img.height ** 2) * 1.5)
    canvas_h = canvas_w
    text_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)

    y = 0
    while y < canvas_h:
        x = 0
        row_offset = (y // spacing_y) % 2 * (spacing_x // 2)
        while x < canvas_w:
            text_draw.text(
                (x + row_offset, y),
                text,
                font=font,
                fill=(255, 255, 255, opacity),
            )
            x += spacing_x
        y += spacing_y

    # Rotate and crop to image size
    rotated = text_layer.rotate(angle, resample=Image.BICUBIC, expand=False)
    # Center crop
    rx = (rotated.width - img.width) // 2
    ry = (rotated.height - img.height) // 2
    rotated = rotated.crop((rx, ry, rx + img.width, ry + img.height))

    result = Image.alpha_composite(img, rotated)
    return result.convert("RGB")

def add_elegant_equation(img: Image.Image, title: str, equation: str) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    font_size_title = max(24, int(img.width * 0.035))
    font_size_eq = max(18, int(img.width * 0.022))
    
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", font_size_title)
        font_eq = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size_eq)
    except:
        font_title = ImageFont.load_default()
        font_eq = ImageFont.load_default()
        
    # Increase bottom margin to clear the bottom bleed area
    margin_bottom = int(img.height * 0.15)
    # Shift center slightly right to account for the spiral binding on the left
    center_x = (img.width // 2) + int(img.width * 0.04)
    
    bbox_title = draw.textbbox((0, 0), title, font=font_title)
    w_title = bbox_title[2] - bbox_title[0]
    
    bbox_eq = draw.textbbox((0, 0), equation, font=font_eq)
    w_eq = bbox_eq[2] - bbox_eq[0]
    
    y_title = img.height - margin_bottom - int(img.height * 0.045)
    y_eq = img.height - margin_bottom
    
    # Add subtle dark gradient at bottom for readability
    gradient_start = img.height - margin_bottom - int(img.height * 0.12)
    for y in range(gradient_start, img.height):
        alpha = int(220 * ((y - gradient_start) / (img.height - gradient_start)))
        draw.line([(0, y), (img.width, y)], fill=(0, 0, 0, alpha))
    
    draw.text((center_x - w_title // 2, y_title), title, font=font_title, fill=(255, 255, 255, 240))
    draw.text((center_x - w_eq // 2, y_eq), equation, font=font_eq, fill=(200, 200, 200, 200))
    
    result = Image.alpha_composite(img, overlay)
    return result.convert("RGB")
