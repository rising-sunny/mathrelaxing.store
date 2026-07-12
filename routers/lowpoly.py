"""Low Poly color-by-number generator — GPT-facing endpoints."""

import asyncio
import io
import json
import uuid
from pathlib import Path
from typing import Literal, Optional

import httpx
from PIL import Image, ImageDraw, ImageFont
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from fastapi.responses import HTMLResponse
from database import get_db
from models.product import LowPolyJob
from services import email as email_service
from services import paypal as paypal_service
from services import telegram as telegram_service
from services.low_poly_engine import generate_low_poly

router = APIRouter()

_generation_sem = asyncio.Semaphore(2)

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PREVIEWS_DIR = Path("/var/www/mathrelaxing.store/static/previews/lowpoly")
PURCHASES_DIR = Path("/var/www/mathrelaxing.store/static/purchases/lowpoly")
BASE_URL = "https://mathrelaxing.store"
PRICE_USD = 2.99
PACK_PRICE_USD = 6.99
MAX_IMAGE_BYTES = 20 * 1024 * 1024

# User-friendly density → polygon_size (px)
DENSITY_TO_SIZE = {
    "very_low":   80,  # very few large cells — children / bold designs
    "low":        55,  # few cells — simple
    "medium":     35,  # balanced — default
    "high":       20,  # many cells — detailed
    "very_high":  12,  # maximum detail — complex images, longer processing
    "ultra_high":  8,  # extreme detail — very slow, cells may be too small to color by hand
    "extreme":     5,  # maximum resolution — digital art / posters only, not suitable for hand coloring
}

# User-friendly orientation → page_format for the engine
ORIENTATION_TO_FORMAT = {
    "portrait":     "letter-portrait",   # US Letter 8.5x11 @ 300 DPI
    "landscape":    "letter-landscape",
    "a4-portrait":  "a4-portrait",
    "a4-landscape": "a4-landscape",
    "auto":         "auto",
}

ORIENTATION_TO_RESOLUTION = {
    "portrait":     "2550 × 3300 px at 300 DPI — US Letter (8.5 × 11 in), print-ready",
    "landscape":    "3300 × 2550 px at 300 DPI — US Letter (11 × 8.5 in), print-ready",
    "a4-portrait":  "2480 × 3508 px at 300 DPI — A4 (210 × 297 mm), print-ready",
    "a4-landscape": "3508 × 2480 px at 300 DPI — A4 (297 × 210 mm), print-ready",
    "auto":         "matches your image size at 150 DPI — web quality, not recommended for printing",
}

DENSITY_LABELS = {
    "very_low":   "very low (few large cells, bold — ideal for children or simple images)",
    "low":        "low (large cells, easy to color)",
    "medium":     "medium (balanced — recommended for most images)",
    "high":       "high (small cells, detailed — needs a large image)",
    "very_high":  "very high (maximum detail — only for very large, complex images)",
    "ultra_high": "ultra high (extreme detail — very slow, cells may be too small to color by hand)",
    "extreme":    "extreme (maximum resolution — best for digital art or printed posters, not for hand coloring)",
}


def _difficulty_label(density: str, num_colors: int) -> str:
    cells = {"very_low": 60, "low": 200, "medium": 450, "high": 1000, "very_high": 2200,
             "ultra_high": 6000, "extreme": 15000}
    score = cells.get(density, 450) + max(0, num_colors - 12) * 8
    if score < 150:
        return "Very easy ⭐ — ideal for children"
    if score < 350:
        return "Easy ⭐⭐"
    if score < 700:
        return "Medium 🟡 — good for adults"
    if score < 1200:
        return "Challenging 🔴 — many small cells"
    return "Very challenging 💀 — for experienced colorists"


def _add_watermark(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font_size = max(40, img.width // 9)
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except Exception:
        font = ImageFont.load_default()
    text = "PREVIEW"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    for fx, fy in [
        (img.width // 4 - tw // 2, img.height // 4 - th // 2),
        (img.width // 2 - tw // 2, img.height // 2 - th // 2),
        (3 * img.width // 4 - tw // 2, 3 * img.height // 4 - th // 2),
    ]:
        draw.text((fx, fy), text, fill=(150, 150, 150, 90), font=font)
    merged = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    merged.save(buf, format="PNG")
    return buf.getvalue()


class LowPolyRequest(BaseModel):
    image_url: HttpUrl

    num_colors: int = Field(
        default=12, ge=2, le=32,
        description="Number of colors in the palette (2–32). 8–16 works best for most images.",
    )
    density: Literal["very_low", "low", "medium", "high", "very_high", "ultra_high", "extreme"] = Field(
        default="medium",
        description=(
            "Grid density — controls how many color regions the image is divided into. "
            "very_low=few bold regions, low=simple, medium=balanced (default), "
            "high=detailed, very_high=maximum detail (slow), "
            "ultra_high=extreme detail (very slow), extreme=maximum resolution (digital/poster only)."
        ),
    )
    orientation: Literal["portrait", "landscape", "a4-portrait", "a4-landscape", "auto"] = Field(
        default="auto",
        description=(
            "Page orientation and size. "
            "portrait=US Letter vertical (8.5x11in, 300 DPI, print-ready), "
            "landscape=US Letter horizontal, "
            "a4-portrait=A4 vertical (210x297mm), "
            "a4-landscape=A4 horizontal, "
            "auto=matches image shape (web preview, not print)."
        ),
    )
    polygon_type: Literal["square", "hexagonal"] = Field(
        default="square",
        description="Shape of the grid cells: square or hexagonal.",
    )
    grid_opacity: int = Field(default=200, ge=0, le=255)
    number_opacity: int = Field(default=80, ge=0, le=255)
    legend_font_size: int = Field(default=16, ge=10, le=36)

    def to_engine_params(self) -> dict:
        return {
            "num_colors":      self.num_colors,
            "polygon_type":    self.polygon_type,
            "polygon_size":    DENSITY_TO_SIZE[self.density],
            "grid_opacity":    self.grid_opacity,
            "number_opacity":  self.number_opacity,
            "legend_font_size": self.legend_font_size,
            "page_format":     ORIENTATION_TO_FORMAT[self.orientation],
            "output_width":    None,
            "output_height":   None,
        }


class LowPolyCheckoutRequest(LowPolyRequest):
    customer_email: str = Field(..., description="Customer's email address — the download links will be sent here.")
    customer_name: str = Field(default="", description="Customer name (optional).")


@router.get("/gpt/lowpoly/guide")
def image_guide():
    """
    Returns guidelines on what kind of image works best for the color-by-number generator,
    and explains the available options (density, colors, orientation).
    Call this at the start of the conversation, before the user uploads anything.
    """
    return {
        "title": "Color-by-Number Generator — Image Guide & Options",
        "recommended_image": {
            "resolution": {
                "minimum": "800 x 800 px",
                "ideal":   "1200 x 1200 px or larger",
                "note":    "Larger images allow higher density (more detail). Small images force large, coarse cells.",
            },
            "best_types": [
                "Colorful landscapes: sky, mountains, sea, fields",
                "Animals with distinct color areas: birds, fish, butterflies, tigers",
                "Fruits, flowers, plants — vivid saturated colors",
                "Simple portraits with a contrasting background",
                "Illustrated or cartoon-style images with flat color regions",
            ],
            "what_to_avoid": [
                "Near-monochromatic images (e.g. all-gray foggy scene) — too few distinct colors",
                "Very dark or very low-contrast images — colors won't separate well",
                "Extremely busy textures with no clear regions (e.g. close-up of dense foliage)",
                "Images that are almost entirely white or black",
                "PNG images with transparent backgrounds — use solid-background images",
            ],
            "formats": ["JPEG", "PNG (solid background)"],
            "max_size": "20 MB",
        },
        "options": {
            "num_colors": {
                "description": "Number of colors in the palette.",
                "range": "2 to 32",
                "recommendations": {
                    "6–8":   "Very simple image or children's coloring page",
                    "10–14": "Most photos and illustrations (recommended)",
                    "16–20": "Complex images with many distinct color areas",
                    "24–32": "Maximum color fidelity (advanced, slow)",
                },
                "tip": "Fewer colors = easier to color. More colors = closer to the original image.",
            },
            "density": {
                "description": "Controls how many grid cells divide the image. More cells = more detail but harder to color.",
                "options": DENSITY_LABELS,
                "tip": "For a first try, use 'medium'. Use 'high' or 'very_high' for images at least 1200px wide. Use 'ultra_high' or 'extreme' only for very high-resolution images (2000px+) intended as digital art or posters — cells will be too small to color by hand.",
            },
            "orientation": {
                "description": "Page size and orientation of the output.",
                "options": {
                    "auto":         "Fits the image — web-sized, not print-ready",
                    "portrait":     "US Letter vertical (8.5x11 in) at 300 DPI — print-ready",
                    "landscape":    "US Letter horizontal (11x8.5 in) at 300 DPI — print-ready",
                    "a4-portrait":  "A4 vertical (210x297 mm) at 300 DPI — print-ready",
                    "a4-landscape": "A4 horizontal (297x210 mm) at 300 DPI — print-ready",
                },
                "tip": "Use 'portrait' (carta vertical) for standard home printing. The art will fill the entire page.",
            },
            "polygon_type": {
                "description": "Shape of the grid cells.",
                "options": {
                    "square":  "Square grid — easiest to color, clearest numbers",
                    "hexagonal": "Hexagonal grid — organic feel, like a mosaic",
                },
            },
        },
        "quick_start": (
            "Recommended first try: pick a colorful photo at least 1000px wide, "
            "then use num_colors=12, density='medium', polygon_type='square', orientation='portrait'. "
            "Call /gpt/lowpoly/preview first to see a quick result before generating the full version."
        ),
        "density_list": (
            "**Density** — how many cells divide the image:\n"
            "1. very_low — few large cells, bold (ideal for children or simple images)\n"
            "2. low — large cells, easy to color\n"
            "3. medium — balanced, recommended ✅ (default)\n"
            "4. high — detailed, needs image at least 1200px wide\n"
            "5. very_high — maximum detail, slow\n"
            "6. ultra_high — extreme detail, very slow (cells may be too small to color by hand)\n"
            "7. extreme — maximum resolution, for digital art or posters only"
        ),
        "examples_markdown": (
            "**Number of colors** — tap a link to preview (same photo, different palettes):\n"
            f"- [8 colors — simple, bold, easiest to color]({BASE_URL}/static/examples/8colors_portrait_colored.png)\n"
            f"- [12 colors — balanced, recommended ✅]({BASE_URL}/static/examples/12colors_portrait_colored.png)\n"
            f"- [16 colors — more detail, closer to original]({BASE_URL}/static/examples/16colors_portrait_colored.png)\n\n"
            "**Grid style:**\n"
            f"- [Square grid — clearest numbers, easiest to color ✅]({BASE_URL}/static/examples/12colors_portrait_coloring.png)\n"
            f"- [Hexagonal grid — organic, mosaic feel]({BASE_URL}/static/examples/12colors_hex_coloring_v2.png)"
        ),
    }


async def _fetch_image(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=400, detail=f"Could not fetch image: {e}")
    content_type = resp.headers.get("content-type", "")
    if "image/" not in content_type:
        raise HTTPException(status_code=400, detail=f"URL does not point to an image (got {content_type}).")
    img_bytes = resp.content
    if not img_bytes:
        raise HTTPException(status_code=400, detail="Empty image received.")
    if len(img_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 20 MB limit.")
    return img_bytes


def _run_engine(image_bytes: bytes, params: dict) -> tuple[bytes, bytes]:
    return generate_low_poly(image_bytes=image_bytes, filename="image", font_path=FONT_PATH, **params)


def _save_pngs(coloring_bytes: bytes, colored_bytes: bytes) -> tuple[str, str]:
    job_id = str(uuid.uuid4())[:8]
    PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    (PREVIEWS_DIR / f"{job_id}_coloring.png").write_bytes(coloring_bytes)
    (PREVIEWS_DIR / f"{job_id}_colored.png").write_bytes(colored_bytes)
    return (
        f"{BASE_URL}/static/previews/lowpoly/{job_id}_coloring.png",
        f"{BASE_URL}/static/previews/lowpoly/{job_id}_colored.png",
    )


@router.post("/gpt/lowpoly/preview")
async def preview_lowpoly(req: LowPolyRequest):
    """Quick preview to confirm colors, density, and style before checkout. Returns the numbered coloring page and the colored reference at web size (~700px). Call this before checkout."""
    img_bytes = await _fetch_image(str(req.image_url))

    params = req.to_engine_params()
    # Force small size for fast preview
    params["page_format"] = "auto"
    params["output_width"] = 700
    params["output_height"] = None

    loop = asyncio.get_event_loop()
    async with _generation_sem:
        try:
            coloring_bytes, colored_bytes = await loop.run_in_executor(None, _run_engine, img_bytes, params)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Processing error: {e}")

    coloring_bytes = _add_watermark(coloring_bytes)
    coloring_url, colored_url = _save_pngs(coloring_bytes, colored_bytes)

    density_label = DENSITY_LABELS[req.density]
    difficulty = _difficulty_label(req.density, req.num_colors)
    final_resolution = ORIENTATION_TO_RESOLUTION[req.orientation]
    return {
        "coloring_preview_url": coloring_url,
        "colored_preview_url":  colored_url,
        "difficulty": difficulty,
        "final_resolution": final_resolution,
        "settings": {
            "num_colors":   req.num_colors,
            "density":      req.density,
            "polygon_type": req.polygon_type,
            "orientation":  req.orientation,
        },
        "message": (
            f"Preview ready — {req.num_colors} colors, density '{req.density}' ({density_label}), "
            f"{req.polygon_type} grid. Difficulty: {difficulty}. "
            f"The coloring page has a PREVIEW watermark — it's removed in the final version. "
            f"Does this look good? You can change num_colors, density, polygon_type or orientation, "
            f"then proceed to checkout for the final watermark-free version."
        ),
    }


@router.post("/gpt/lowpoly/preview-upload")
async def preview_lowpoly_upload(
    image: UploadFile = File(..., description="Photo to convert. JPEG or PNG, max 20 MB."),
    num_colors: int = Form(default=12, ge=2, le=32),
    density: str = Form(default="medium"),
    orientation: str = Form(default="portrait"),
    polygon_type: str = Form(default="square"),
):
    """
    Same as /gpt/lowpoly/preview but accepts a file upload instead of a URL.
    Use this when the user uploads their photo directly in the chat.
    """
    if density not in DENSITY_TO_SIZE:
        raise HTTPException(400, f"density must be one of: {list(DENSITY_TO_SIZE)}")
    if orientation not in ORIENTATION_TO_FORMAT:
        raise HTTPException(400, f"orientation must be one of: {list(ORIENTATION_TO_FORMAT)}")
    if polygon_type not in ("square", "hexagonal"):
        raise HTTPException(400, "polygon_type must be 'square' or 'hexagonal'")

    content_type = image.content_type or ""
    if "image/" not in content_type:
        raise HTTPException(400, f"File must be an image (received {content_type}).")
    img_bytes = await image.read()
    if not img_bytes:
        raise HTTPException(400, "Empty file received.")
    if len(img_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image exceeds 20 MB limit.")

    params = {
        "num_colors":      num_colors,
        "polygon_type":    polygon_type,
        "polygon_size":    DENSITY_TO_SIZE[density],
        "grid_opacity":    200,
        "number_opacity":  80,
        "legend_font_size": 16,
        "page_format":     "auto",
        "output_width":    700,
        "output_height":   None,
    }
    loop = asyncio.get_event_loop()
    async with _generation_sem:
        try:
            coloring_bytes, colored_bytes = await loop.run_in_executor(None, _run_engine, img_bytes, params)
        except ValueError as e:
            raise HTTPException(422, str(e))
        except Exception as e:
            raise HTTPException(500, f"Processing error: {e}")

    coloring_bytes = _add_watermark(coloring_bytes)
    coloring_url, colored_url = _save_pngs(coloring_bytes, colored_bytes)
    density_label = DENSITY_LABELS[density]
    difficulty = _difficulty_label(density, num_colors)
    final_resolution = ORIENTATION_TO_RESOLUTION[orientation]
    return {
        "coloring_preview_url": coloring_url,
        "colored_preview_url":  colored_url,
        "difficulty": difficulty,
        "final_resolution": final_resolution,
        "settings": {
            "num_colors":   num_colors,
            "density":      density,
            "polygon_type": polygon_type,
            "orientation":  orientation,
        },
        "message": (
            f"Preview ready — {num_colors} colors, density '{density}' ({density_label}), "
            f"{polygon_type} grid. Difficulty: {difficulty}. "
            f"The coloring page has a PREVIEW watermark — it's removed in the final version. "
            f"Does this look good? You can adjust any option, then proceed to checkout for the final watermark-free version."
        ),
    }


@router.post("/gpt/lowpoly/checkout-upload")
async def checkout_lowpoly_upload(
    image: UploadFile = File(..., description="Photo to convert. JPEG or PNG, max 20 MB."),
    customer_email: str = Form(..., description="Email address where download links will be sent."),
    customer_name: str = Form(default=""),
    num_colors: int = Form(default=12, ge=2, le=32),
    density: str = Form(default="medium"),
    orientation: str = Form(default="portrait"),
    polygon_type: str = Form(default="square"),
    db: Session = Depends(get_db),
):
    """
    Same as /gpt/lowpoly/checkout but accepts a file upload instead of a URL.
    Use this when the user uploaded their photo directly in the chat.
    """
    if density not in DENSITY_TO_SIZE:
        raise HTTPException(400, f"density must be one of: {list(DENSITY_TO_SIZE)}")
    if orientation not in ORIENTATION_TO_FORMAT:
        raise HTTPException(400, f"orientation must be one of: {list(ORIENTATION_TO_FORMAT)}")
    if polygon_type not in ("square", "hexagonal"):
        raise HTTPException(400, "polygon_type must be 'square' or 'hexagonal'")

    content_type = image.content_type or ""
    if "image/" not in content_type:
        raise HTTPException(400, f"File must be an image (received {content_type}).")
    img_bytes = await image.read()
    if not img_bytes:
        raise HTTPException(400, "Empty file received.")
    if len(img_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image exceeds 20 MB limit.")

    params = {
        "num_colors":      num_colors,
        "polygon_type":    polygon_type,
        "polygon_size":    DENSITY_TO_SIZE[density],
        "grid_opacity":    200,
        "number_opacity":  80,
        "legend_font_size": 16,
        "page_format":     ORIENTATION_TO_FORMAT[orientation],
        "output_width":    None,
        "output_height":   None,
    }
    loop = asyncio.get_event_loop()
    async with _generation_sem:
        try:
            coloring_bytes, colored_bytes = await loop.run_in_executor(None, _run_engine, img_bytes, params)
        except ValueError as e:
            raise HTTPException(422, str(e))
        except Exception as e:
            raise HTTPException(500, f"Processing error: {e}")

    token = str(uuid.uuid4())
    PURCHASES_DIR.mkdir(parents=True, exist_ok=True)
    (PURCHASES_DIR / f"{token}_coloring.png").write_bytes(coloring_bytes)
    (PURCHASES_DIR / f"{token}_colored.png").write_bytes(colored_bytes)
    coloring_url = f"{BASE_URL}/static/purchases/lowpoly/{token}_coloring.png"
    colored_url  = f"{BASE_URL}/static/purchases/lowpoly/{token}_colored.png"

    job = LowPolyJob(
        token=token,
        customer_email=customer_email,
        customer_name=customer_name or "",
        params_json=json.dumps(params),
        coloring_url=coloring_url,
        colored_url=colored_url,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        approval_url = await paypal_service.create_lowpoly_order(
            job_id=job.id,
            token=token,
            amount_usd=PRICE_USD,
        )
    except Exception as e:
        raise HTTPException(500, f"Could not create payment: {e}")

    return {
        "checkout_url": approval_url,
        "price": f"${PRICE_USD:.2f}",
        "message": (
            f"Your coloring page is generated and ready! "
            f"Complete the ${PRICE_USD:.2f} payment via PayPal to receive both files "
            f"(coloring page + color reference) by email at {customer_email}."
        ),
    }


@router.post("/gpt/lowpoly/generate")
async def generate_lowpoly(req: LowPolyRequest):
    """
    Generate a full-quality color-by-number coloring page from an image URL.

    Returns two public image URLs:
    - coloring_url: blank numbered coloring page (ready to print and color)
    - colored_url: colored reference showing which color fills each region

    Use orientation='portrait' or 'landscape' for print-ready A4 output at 300 DPI.
    For a quick preview first, call /gpt/lowpoly/preview with the same parameters.
    """
    img_bytes = await _fetch_image(str(req.image_url))

    params = req.to_engine_params()

    loop = asyncio.get_event_loop()
    async with _generation_sem:
        try:
            coloring_bytes, colored_bytes = await loop.run_in_executor(None, _run_engine, img_bytes, params)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Processing error: {e}")

    coloring_url, colored_url = _save_pngs(coloring_bytes, colored_bytes)

    orientation_note = {
        "auto":         "web-sized (matches image shape). Use orientation='portrait' for letter-size print.",
        "portrait":     "US Letter vertical (8.5x11 in), print-ready at 300 DPI — art fills the full page.",
        "landscape":    "US Letter horizontal (11x8.5 in), print-ready at 300 DPI — art fills the full page.",
        "a4-portrait":  "A4 vertical (210x297 mm), print-ready at 300 DPI — art fills the full page.",
        "a4-landscape": "A4 horizontal (297x210 mm), print-ready at 300 DPI — art fills the full page.",
    }[req.orientation]

    density_label = DENSITY_LABELS[req.density]

    return {
        "coloring_url": coloring_url,
        "colored_url":  colored_url,
        "settings": {
            "num_colors":   req.num_colors,
            "density":      req.density,
            "polygon_type": req.polygon_type,
            "orientation":  req.orientation,
        },
        "message": (
            f"Your color-by-number page is ready! "
            f"{req.num_colors} colors, density '{req.density}' ({density_label}), "
            f"{req.polygon_type} grid, {orientation_note} "
            f"Use the colored reference to know which number corresponds to each color."
        ),
    }


@router.post("/gpt/lowpoly/checkout")
async def checkout_lowpoly(req: LowPolyCheckoutRequest, db: Session = Depends(get_db)):
    """
    Generate the full-quality coloring page and create a $2.99 PayPal checkout.
    Returns a payment URL. After payment, the customer receives both files by email.
    Call /gpt/lowpoly/preview first so the user approves the result before paying.
    """
    img_bytes = await _fetch_image(str(req.image_url))
    params = req.to_engine_params()

    loop = asyncio.get_event_loop()
    async with _generation_sem:
        try:
            coloring_bytes, colored_bytes = await loop.run_in_executor(None, _run_engine, img_bytes, params)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Processing error: {e}")

    token = str(uuid.uuid4())
    PURCHASES_DIR.mkdir(parents=True, exist_ok=True)
    (PURCHASES_DIR / f"{token}_coloring.png").write_bytes(coloring_bytes)
    (PURCHASES_DIR / f"{token}_colored.png").write_bytes(colored_bytes)
    coloring_url = f"{BASE_URL}/static/purchases/lowpoly/{token}_coloring.png"
    colored_url  = f"{BASE_URL}/static/purchases/lowpoly/{token}_colored.png"

    job = LowPolyJob(
        token=token,
        customer_email=req.customer_email,
        customer_name=req.customer_name or "",
        params_json=json.dumps(params),
        coloring_url=coloring_url,
        colored_url=colored_url,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        approval_url = await paypal_service.create_lowpoly_order(
            job_id=job.id,
            token=token,
            amount_usd=PRICE_USD,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not create payment: {e}")

    return {
        "checkout_url": approval_url,
        "price": f"${PRICE_USD:.2f}",
        "message": (
            f"Your coloring page is generated and ready! "
            f"Complete the ${PRICE_USD:.2f} payment via PayPal to receive both files "
            f"(coloring page + color reference) by email at {req.customer_email}."
        ),
    }


class LowPolyPackCheckoutRequest(BaseModel):
    image_url_1: HttpUrl = Field(..., description="URL of the first photo.")
    image_url_2: HttpUrl = Field(..., description="URL of the second photo.")
    image_url_3: HttpUrl = Field(..., description="URL of the third photo.")
    customer_email: str = Field(..., description="Email address where all 6 files will be sent.")
    customer_name: str = Field(default="")
    num_colors: int = Field(default=12, ge=2, le=32)
    density: Literal["very_low", "low", "medium", "high", "very_high", "ultra_high", "extreme"] = Field(default="medium")
    orientation: Literal["portrait", "landscape", "a4-portrait", "a4-landscape", "auto"] = Field(default="portrait")
    polygon_type: Literal["square", "hexagonal"] = Field(default="square")


@router.post("/gpt/lowpoly/checkout-pack")
async def checkout_lowpoly_pack(req: LowPolyPackCheckoutRequest, db: Session = Depends(get_db)):
    """
    Generate 3 coloring pages and create a $6.99 PayPal checkout (saves $2 vs buying individually).
    Call /gpt/lowpoly/preview first so the user approves the style. Processing takes 30–90 seconds.
    """
    urls = [str(req.image_url_1), str(req.image_url_2), str(req.image_url_3)]
    params = {
        "num_colors":       req.num_colors,
        "polygon_type":     req.polygon_type,
        "polygon_size":     DENSITY_TO_SIZE[req.density],
        "grid_opacity":     200,
        "number_opacity":   80,
        "legend_font_size": 16,
        "page_format":      ORIENTATION_TO_FORMAT[req.orientation],
        "output_width":     None,
        "output_height":    None,
    }

    loop = asyncio.get_event_loop()
    file_pairs_bytes = []
    async with _generation_sem:
        for url in urls:
            img_bytes = await _fetch_image(url)
            try:
                cb, ccb = await loop.run_in_executor(None, _run_engine, img_bytes, params)
            except ValueError as e:
                raise HTTPException(422, str(e))
            except Exception as e:
                raise HTTPException(500, f"Processing error: {e}")
            file_pairs_bytes.append((cb, ccb))

    token = str(uuid.uuid4())
    PURCHASES_DIR.mkdir(parents=True, exist_ok=True)
    saved_pairs = []
    for i, (cb, ccb) in enumerate(file_pairs_bytes):
        (PURCHASES_DIR / f"{token}_p{i+1}_coloring.png").write_bytes(cb)
        (PURCHASES_DIR / f"{token}_p{i+1}_colored.png").write_bytes(ccb)
        saved_pairs.append({
            "coloring_url": f"{BASE_URL}/static/purchases/lowpoly/{token}_p{i+1}_coloring.png",
            "colored_url":  f"{BASE_URL}/static/purchases/lowpoly/{token}_p{i+1}_colored.png",
        })

    job = LowPolyJob(
        token=token,
        customer_email=req.customer_email,
        customer_name=req.customer_name or "",
        params_json=json.dumps(params),
        coloring_url=saved_pairs[0]["coloring_url"],
        colored_url=saved_pairs[0]["colored_url"],
        extra_files_json=json.dumps(saved_pairs[1:]),
        pack_size=3,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        approval_url = await paypal_service.create_lowpoly_order(
            job_id=job.id,
            token=token,
            amount_usd=PACK_PRICE_USD,
        )
    except Exception as e:
        raise HTTPException(500, f"Could not create payment: {e}")

    return {
        "checkout_url": approval_url,
        "price": f"${PACK_PRICE_USD:.2f}",
        "savings": "$2.00 vs buying individually",
        "message": (
            f"Your 3-page color-by-number pack is ready! "
            f"Complete the ${PACK_PRICE_USD:.2f} PayPal payment to receive all 6 files "
            f"(3 coloring pages + 3 color references) by email at {req.customer_email}."
        ),
    }


@router.get("/lowpoly/paypal-return", response_class=HTMLResponse)
async def lowpoly_paypal_return(
    job: str,
    token: str,
    PayerID: str = "",
    db: Session = Depends(get_db),
):
    """PayPal redirects here after the user approves payment. Captures and fulfills."""
    lowpoly_job = db.query(LowPolyJob).filter(LowPolyJob.token == job).first()
    if not lowpoly_job:
        return HTMLResponse("<h2>Job not found.</h2>", status_code=404)

    if lowpoly_job.status != "paid":
        try:
            capture_data = await paypal_service.capture_order(token)
            if capture_data.get("status") != "COMPLETED":
                return HTMLResponse("<h2>Payment not completed. Please try again.</h2>", status_code=400)
        except Exception as e:
            return HTMLResponse(f"<h2>Payment capture failed: {e}</h2>", status_code=400)

        lowpoly_job.status = "paid"
        db.commit()
        await email_service.send_lowpoly_download_email(lowpoly_job)
        await telegram_service.notify_new_lowpoly_purchase(lowpoly_job)

    email_addr = lowpoly_job.customer_email
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Payment Confirmed — MathRelaxing</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: Georgia, "Times New Roman", serif;
    background: #f0ede8;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 24px 16px;
  }}
  .card {{
    background: #fff;
    border-radius: 4px;
    max-width: 460px;
    width: 100%;
    box-shadow: 0 2px 20px rgba(0,0,0,.10);
    overflow: hidden;
  }}
  .card-header {{
    background: #0d0d0d;
    padding: 32px 40px;
    text-align: center;
  }}
  .card-header img {{
    display: block;
    margin: 0 auto 14px;
    width: 80px;
    height: auto;
  }}
  .card-header .brand {{
    font-size: 10px;
    letter-spacing: .18em;
    text-transform: uppercase;
    color: #c8a96e;
    font-family: monospace;
  }}
  .card-header h1 {{
    margin-top: 8px;
    font-size: 1.35rem;
    font-weight: 400;
    color: #e8e4dc;
    letter-spacing: .02em;
  }}
  .card-body {{
    padding: 32px 40px 36px;
    text-align: center;
  }}
  .check {{
    width: 56px;
    height: 56px;
    border-radius: 50%;
    border: 2px solid #c8a96e;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 20px;
    font-size: 22px;
    color: #c8a96e;
  }}
  .card-body p {{
    font-size: .95rem;
    color: #555;
    line-height: 1.7;
    margin-bottom: 12px;
  }}
  .email {{
    color: #c8a96e;
    font-weight: bold;
    font-style: normal;
  }}
  .note {{
    font-size: .82rem;
    color: #aaa;
    line-height: 1.5;
    margin-top: 20px;
    font-family: -apple-system, sans-serif;
  }}
  .card-footer {{
    background: #0d0d0d;
    padding: 14px 40px;
    text-align: center;
  }}
  .card-footer a {{
    font-family: monospace;
    font-size: .7rem;
    letter-spacing: .12em;
    text-transform: uppercase;
    color: #555;
    text-decoration: none;
  }}
  .card-footer a:hover {{ color: #c8a96e; }}
</style>
</head>
<body>
<div class="card">

  <div class="card-header">
    <img src="/static/img/logo-sm.png" alt="MathRelaxing">
    <p class="brand">MathRelaxing</p>
    <h1>Payment confirmed!</h1>
  </div>

  <div class="card-body">
    <div class="check">✓</div>
    <p>Your color-by-number files are on their way to</p>
    <p><em class="email">{email_addr}</em></p>
    <p>Check your inbox — you'll receive two images:<br>
       the blank coloring page and the color reference.</p>
    <p class="note">Didn't receive the email? Check your spam folder<br>
       or reply to orders@mathrelaxing.store.</p>
  </div>

  <div class="card-footer">
    <a href="https://mathrelaxing.store">← Back to MathRelaxing</a>
  </div>

</div>
</body>
</html>""")


@router.get("/lowpoly/result/{token}")
def get_lowpoly_result(token: str, db: Session = Depends(get_db)):
    """Returns download URLs for a paid Low Poly job (called by the GPT after payment)."""
    job = db.query(LowPolyJob).filter(LowPolyJob.token == token).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status == "pending":
        raise HTTPException(status_code=402, detail="Payment not confirmed yet.")
    if job.status == "expired":
        raise HTTPException(status_code=410, detail="This download link has expired.")
    return {
        "coloring_url": job.coloring_url,
        "colored_url":  job.colored_url,
        "message": "Payment confirmed! Save both images — right-click → Save image as.",
    }


UPLOADS_DIR = Path("/var/www/mathrelaxing.store/static/uploads")

_UPLOAD_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Upload your photo — MathRelaxing</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: Georgia, "Times New Roman", serif;
    background: #f0ede8;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 24px 16px;
  }

  .card {
    background: #fff;
    border-radius: 4px;
    max-width: 460px;
    width: 100%;
    box-shadow: 0 2px 20px rgba(0,0,0,.10);
    overflow: hidden;
  }

  /* ── Header ── */
  .card-header {
    background: #0d0d0d;
    padding: 32px 40px;
    text-align: center;
  }
  .card-header img {
    display: block;
    margin: 0 auto 14px;
    width: 80px;
    height: auto;
  }
  .card-header .brand {
    font-size: 10px;
    letter-spacing: .18em;
    text-transform: uppercase;
    color: #c8a96e;
    font-family: monospace;
  }
  .card-header h1 {
    margin-top: 8px;
    font-size: 1.35rem;
    font-weight: 400;
    color: #e8e4dc;
    letter-spacing: .02em;
  }

  /* ── Body ── */
  .card-body { padding: 32px 40px 36px; }

  .subtitle {
    font-size: .9rem;
    color: #777;
    line-height: 1.65;
    margin-bottom: 24px;
  }

  /* ── Drop zone ── */
  .drop {
    border: 1.5px dashed #c8b89a;
    border-radius: 4px;
    padding: 32px 20px;
    text-align: center;
    cursor: pointer;
    transition: border-color .2s, background .2s;
    background: #faf8f5;
  }
  .drop:hover, .drop.over {
    border-color: #c8a96e;
    background: #f5efe6;
  }
  .drop input { display: none; }
  .drop-icon {
    font-size: 2rem;
    margin-bottom: 10px;
    opacity: .75;
  }
  .drop-text {
    font-size: .88rem;
    color: #888;
    font-family: -apple-system, sans-serif;
  }
  .drop-text strong { color: #c8a96e; font-weight: 600; }
  #file-name {
    margin-top: 10px;
    font-size: .8rem;
    color: #aaa;
    font-family: monospace;
  }

  /* ── Upload button ── */
  #upload-btn {
    margin-top: 20px;
    width: 100%;
    padding: 13px;
    background: #0d0d0d;
    color: #c8a96e;
    border: none;
    border-radius: 2px;
    font-family: monospace;
    font-size: .78rem;
    letter-spacing: .14em;
    text-transform: uppercase;
    cursor: pointer;
    transition: background .2s;
  }
  #upload-btn:hover:not(:disabled) { background: #2a2a2a; }
  #upload-btn:disabled { background: #ccc; color: #fff; cursor: not-allowed; }

  /* ── Result ── */
  .result { margin-top: 22px; display: none; }
  .result-label {
    font-size: .78rem;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: #999;
    font-family: monospace;
    margin-bottom: 8px;
  }
  .url-box { display: flex; gap: 8px; }
  .url-box input {
    flex: 1;
    padding: 10px 12px;
    border: 1px solid #ddd;
    border-radius: 2px;
    font-size: .82rem;
    color: #333;
    background: #fafaf8;
    font-family: monospace;
  }
  .copy-btn {
    padding: 10px 18px;
    background: #0d0d0d;
    color: #c8a96e;
    border: none;
    border-radius: 2px;
    font-family: monospace;
    font-size: .75rem;
    letter-spacing: .12em;
    text-transform: uppercase;
    cursor: pointer;
    white-space: nowrap;
    transition: background .2s;
  }
  .copy-btn:hover { background: #2a2a2a; }
  .copied { background: #2d5a3d !important; color: #e8f4ec !important; }
  .note {
    margin-top: 12px;
    font-size: .78rem;
    color: #aaa;
    line-height: 1.5;
    font-family: -apple-system, sans-serif;
  }

  /* ── Error ── */
  .error {
    margin-top: 14px;
    color: #c0392b;
    font-size: .85rem;
    display: none;
    font-family: -apple-system, sans-serif;
  }

  /* ── Spinner ── */
  .spinner {
    display: inline-block;
    width: 14px; height: 14px;
    border: 2px solid #c8a96e;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin .7s linear infinite;
    vertical-align: middle;
    margin-right: 8px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── Footer ── */
  .card-footer {
    background: #0d0d0d;
    padding: 14px 40px;
    text-align: center;
  }
  .card-footer a {
    font-family: monospace;
    font-size: .7rem;
    letter-spacing: .12em;
    text-transform: uppercase;
    color: #555;
    text-decoration: none;
  }
  .card-footer a:hover { color: #c8a96e; }
</style>
</head>
<body>
<div class="card">

  <div class="card-header">
    <img src="/static/img/logo-sm.png" alt="MathRelaxing">
    <p class="brand">MathRelaxing</p>
    <h1>Upload your photo</h1>
  </div>

  <div class="card-body">
    <p class="subtitle">
      Upload your photo to get a link you can paste into the
      Color-by-Number assistant. The link stays active for 2 hours.
    </p>

    <div class="drop" id="drop-zone">
      <input type="file" id="file-input" accept="image/jpeg,image/png">
      <div class="drop-icon">📷</div>
      <div class="drop-text">
        <strong>Click to choose</strong> or drag &amp; drop<br>
        <span style="font-size:.78rem;font-family:-apple-system,sans-serif;">JPEG or PNG &middot; max 20 MB</span>
      </div>
      <div id="file-name"></div>
    </div>

    <button id="upload-btn" disabled>Upload photo</button>
    <div class="error" id="error-msg"></div>

    <div class="result" id="result">
      <p class="result-label">Your photo link — paste this in the chat</p>
      <div class="url-box">
        <input type="text" id="url-output" readonly>
        <button class="copy-btn" id="copy-btn" onclick="copyUrl()">Copy</button>
      </div>
      <p class="note">⏱ This link expires in 2 hours. Paste it in the chat right away.</p>
    </div>
  </div>

  <div class="card-footer">
    <a href="https://mathrelaxing.store">mathrelaxing.store</a>
  </div>

</div>

<script>
const drop = document.getElementById('drop-zone');
const input = document.getElementById('file-input');
const btn = document.getElementById('upload-btn');
const fileName = document.getElementById('file-name');
const errorEl = document.getElementById('error-msg');
let selectedFile = null;

drop.addEventListener('click', () => input.click());
drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); });
drop.addEventListener('dragleave', () => drop.classList.remove('over'));
drop.addEventListener('drop', e => {
  e.preventDefault(); drop.classList.remove('over');
  const f = e.dataTransfer.files[0];
  if (f) setFile(f);
});
input.addEventListener('change', () => { if (input.files[0]) setFile(input.files[0]); });

function setFile(f) {
  if (!['image/jpeg','image/png'].includes(f.type)) {
    showError('Only JPEG and PNG files are accepted.'); return;
  }
  if (f.size > 20 * 1024 * 1024) {
    showError('File exceeds 20 MB. Please compress it first.'); return;
  }
  selectedFile = f;
  fileName.textContent = f.name + ' (' + (f.size / 1024 / 1024).toFixed(1) + ' MB)';
  btn.disabled = false;
  errorEl.style.display = 'none';
}

function showError(msg) {
  errorEl.textContent = msg; errorEl.style.display = 'block';
}

btn.addEventListener('click', async () => {
  if (!selectedFile) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Uploading…';
  errorEl.style.display = 'none';
  const fd = new FormData();
  fd.append('image', selectedFile);
  try {
    const r = await fetch('/api/lowpoly/upload', { method: 'POST', body: fd });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Upload failed');
    document.getElementById('url-output').value = data.url;
    document.getElementById('result').style.display = 'block';
    btn.innerHTML = '✅ Uploaded!';
  } catch(e) {
    showError(e.message);
    btn.disabled = false;
    btn.innerHTML = 'Upload photo';
  }
});

function copyUrl() {
  const inp = document.getElementById('url-output');
  inp.select(); document.execCommand('copy');
  const cb = document.getElementById('copy-btn');
  cb.textContent = 'Copied!'; cb.classList.add('copied');
  setTimeout(() => { cb.textContent = 'Copy'; cb.classList.remove('copied'); }, 2000);
}
</script>
</body>
</html>"""


@router.get("/lowpoly/upload", response_class=HTMLResponse)
def upload_page():
    """Simple photo upload page — user uploads their photo and gets a public URL to paste in the chat."""
    return HTMLResponse(_UPLOAD_PAGE)


@router.post("/lowpoly/upload")
async def upload_photo(image: UploadFile = File(...)):
    """Accepts a photo upload and returns a temporary public URL (expires in 2 hours)."""
    content_type = image.content_type or ""
    if "image/" not in content_type:
        raise HTTPException(400, f"File must be an image (received {content_type}).")
    img_bytes = await image.read()
    if not img_bytes:
        raise HTTPException(400, "Empty file received.")
    if len(img_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image exceeds 20 MB limit.")

    ext = ".jpg" if "jpeg" in content_type else ".png"
    file_id = str(uuid.uuid4())
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOADS_DIR / f"{file_id}{ext}").write_bytes(img_bytes)

    return {"url": f"{BASE_URL}/static/uploads/{file_id}{ext}"}


# ── Whop Low Poly Credit flow ──────────────────────────────────────────────

from models.product import LowPolyCredit
from datetime import datetime, timezone

WHOP_LOWPOLY_CHECKOUT_1 = "https://whop.com/checkout/plan_qPMvUkO7rXxOW"
WHOP_LOWPOLY_CHECKOUT_5 = "https://whop.com/checkout/plan_MJXmSbhMus5WY"


@router.get("/lowpoly/credit/{token}", response_class=HTMLResponse)
def lowpoly_credit_page(token: str, db: Session = Depends(get_db)):
    """Redemption page for a Low Poly Whop credit."""
    from fastapi.templating import Jinja2Templates
    from fastapi import Request
    credit = db.query(LowPolyCredit).filter(LowPolyCredit.token == token).first()
    if not credit:
        raise HTTPException(404, "Credit not found.")
    if credit.status == "exhausted":
        raise HTTPException(410, "This credit has already been used.")

    remaining = credit.pack_size - credit.used_count
    templates = Jinja2Templates(directory="/var/www/mathrelaxing.store/templates")
    # Build response manually to avoid needing a Request object
    from fastapi.responses import HTMLResponse as _HR
    html = templates.get_template("lowpoly_credit.html").render({
        "request": {},
        "token": token,
        "remaining": remaining,
        "pack_size": credit.pack_size,
        "customer_name": credit.customer_name,
    })
    return _HR(content=html)


@router.post("/lowpoly/credit/{token}/generate")
async def lowpoly_credit_generate(
    token: str,
    image: UploadFile = File(...),
    customer_email: str = Form(...),
    num_colors: int = Form(default=12, ge=2, le=32),
    density: str = Form(default="medium"),
    orientation: str = Form(default="portrait"),
    polygon_type: str = Form(default="square"),
    db: Session = Depends(get_db),
):
    """Generate full-res low poly from an uploaded image using one credit."""
    credit = db.query(LowPolyCredit).filter(LowPolyCredit.token == token).first()
    if not credit:
        raise HTTPException(404, "Credit not found.")
    if credit.status == "exhausted":
        raise HTTPException(410, "Credit exhausted.")
    if credit.used_count >= credit.pack_size:
        credit.status = "exhausted"
        db.commit()
        raise HTTPException(410, "All credits have been used.")

    if density not in DENSITY_TO_SIZE:
        raise HTTPException(400, f"density must be one of: {list(DENSITY_TO_SIZE)}")
    if orientation not in ORIENTATION_TO_FORMAT:
        raise HTTPException(400, f"orientation must be one of: {list(ORIENTATION_TO_FORMAT)}")
    if polygon_type not in ("square", "hexagonal"):
        raise HTTPException(400, "polygon_type must be 'square' or 'hexagonal'")

    content_type = image.content_type or ""
    if "image/" not in content_type:
        raise HTTPException(400, f"File must be an image (received {content_type}).")
    img_bytes = await image.read()
    if not img_bytes:
        raise HTTPException(400, "Empty file.")
    if len(img_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image exceeds 20 MB limit.")

    params = {
        "num_colors":      num_colors,
        "polygon_type":    polygon_type,
        "polygon_size":    DENSITY_TO_SIZE[density],
        "grid_opacity":    200,
        "number_opacity":  80,
        "legend_font_size": 16,
        "page_format":     ORIENTATION_TO_FORMAT[orientation],
        "output_width":    None,
        "output_height":   None,
    }

    loop = asyncio.get_event_loop()
    async with _generation_sem:
        try:
            coloring_bytes, colored_bytes = await loop.run_in_executor(None, _run_engine, img_bytes, params)
        except ValueError as e:
            raise HTTPException(422, str(e))
        except Exception as e:
            raise HTTPException(500, f"Processing error: {e}")

    file_token = str(uuid.uuid4())
    PURCHASES_DIR.mkdir(parents=True, exist_ok=True)
    (PURCHASES_DIR / f"{file_token}_coloring.png").write_bytes(coloring_bytes)
    (PURCHASES_DIR / f"{file_token}_colored.png").write_bytes(colored_bytes)
    coloring_url = f"{BASE_URL}/static/purchases/lowpoly/{file_token}_coloring.png"
    colored_url  = f"{BASE_URL}/static/purchases/lowpoly/{file_token}_colored.png"

    # Create a LowPolyJob so we can reuse the existing download email
    job = LowPolyJob(
        token          = file_token,
        customer_email = customer_email,
        customer_name  = credit.customer_name,
        params_json    = json.dumps(params),
        coloring_url   = coloring_url,
        colored_url    = colored_url,
        status         = "paid",
    )
    db.add(job)

    # Consume one credit
    credit.used_count += 1
    credit.used_at = datetime.now(timezone.utc)
    if credit.used_count >= credit.pack_size:
        credit.status = "exhausted"
    elif credit.used_count > 0:
        credit.status = "partial"
    db.commit()

    await email_service.send_lowpoly_download_email(job)
    await telegram_service.notify_new_lowpoly_purchase(job)

    remaining = credit.pack_size - credit.used_count
    return {
        "coloring_url": coloring_url,
        "colored_url":  colored_url,
        "remaining_credits": remaining,
        "message": f"Done! Your files have been sent to {customer_email}.",
    }
