import asyncio
import hashlib
import hmac
import logging
import os

import httpx

PRINTFUL_API_KEY        = os.getenv("PRINTFUL_API_KEY", "")
PRINTFUL_STORE_ID       = os.getenv("PRINTFUL_STORE_ID", "")
PRINTFUL_WEBHOOK_SECRET = os.getenv("PRINTFUL_WEBHOOK_SECRET", "")

BASE_URL = "https://api.printful.com"
log = logging.getLogger(__name__)


def _headers() -> dict:
    h = {
        "Authorization": f"Bearer {PRINTFUL_API_KEY}",
        "Content-Type": "application/json",
    }
    if PRINTFUL_STORE_ID:
        h["X-PF-Store-Id"] = PRINTFUL_STORE_ID
    return h


# ── Printfile specs ───────────────────────────────────────────────────────────
# Product/variant IDs verified via Printful catalog API on 2026-05-31.
PRINTFILE_SPECS: dict[str, dict] = {
    "poster": {"width_px": 5400, "height_px": 7200, "dpi": 300},
    "sticker_kiss_3in": {"width_px": 900, "height_px": 900, "dpi": 300},
    "gaming_mouse_pad": {"width_px": 7200, "height_px": 3600, "dpi": 200},
    "mouse_pad": {"width_px": 2610, "height_px": 2130, "dpi": 300},
    "unisex_tshirt": {"width_px": 4500, "height_px": 5398, "dpi": 150},
    "unisex_hoodie": {"width_px": 1800, "height_px": 2400, "dpi": 150},
    "aop_leggings": {"width_px": 7200, "height_px": 6225, "dpi": 150},
    "aop_joggers": {"width_px": 9750, "height_px": 8100, "dpi": 150},
    "aop_sweatshirt": {"width_px": 5037, "height_px": 6600, "dpi": 150},
}

# Full-resolution spec for /render/print (fulfillment image sent to Printful)
_SPEC_POSTER = {"width_px": 5400, "height_px": 7200, "dpi": 300}
_SPEC_GAMING_MOUSE_PAD = {"width_px": 7200, "height_px": 3600, "dpi": 200}
_SPEC_MOUSE_PAD = {"width_px": 2610, "height_px": 2130, "dpi": 300}
_SPEC_NOTEBOOK = {"width_px": 1650, "height_px": 2550, "dpi": 300}
_SPEC_TSHIRT = {"width_px": 4500, "height_px": 5398, "dpi": 150}

_POSTER_PRODUCT_ID = 1
_POSTER_VARIANT_ID = 1   # 18×24″ Enhanced Matte Paper Poster
_GAMING_MOUSE_PAD_PRODUCT_ID = 583
_GAMING_MOUSE_PAD_VARIANT_ID = 14942  # 36×18″ Gaming Mouse Pad
_MOUSE_PAD_PRODUCT_ID = 518
_MOUSE_PAD_VARIANT_ID = 13097         # 8.7×7.1″ Mouse Pad
_NOTEBOOK_PRODUCT_ID = 946
_NOTEBOOK_VARIANT_ID = 24305
_TSHIRT_PRODUCT_ID = 71
_TSHIRT_VARIANTS = {"S": 4016, "M": 4017, "L": 4018, "XL": 4019, "2XL": 4020, "3XL": 5295}
_HOODIE_PRODUCT_ID = 146  # Gildan 18500 Unisex Heavy Blend Hoodie
_HOODIE_VARIANTS = {"S": 5530, "M": 5531, "L": 5532, "XL": 5533, "2XL": 5534, "3XL": 5535}  # Black
_SPEC_HOODIE = {"width_px": 1800, "height_px": 2400, "dpi": 150}
_AOP_LEGGINGS_PRODUCT_ID = 189  # All-Over Print Leggings (cut-and-sew)
_AOP_LEGGINGS_VARIANTS = {"XS": 7676, "S": 7677, "M": 7678, "L": 7679, "XL": 7680}
_SPEC_AOP_LEGGINGS = {"width_px": 7200, "height_px": 6225, "dpi": 150}
_AOP_JOGGERS_PRODUCT_ID = 784  # All-Over Print Unisex Wide-Leg Joggers
_AOP_JOGGERS_VARIANTS = {"XS": 19890, "S": 19891, "M": 19892, "L": 19893, "XL": 19894, "2XL": 19895}
_SPEC_AOP_JOGGERS = {"width_px": 9750, "height_px": 8100, "dpi": 150}
_AOP_SWEATSHIRT_PRODUCT_ID = 1418  # All-Over Print Unisex Cotton Sweatshirt
_AOP_SWEATSHIRT_VARIANTS = {"XS": 33964, "S": 33965, "M": 33966, "L": 33967, "XL": 33968, "2XL": 33969}
_SPEC_AOP_SWEATSHIRT = {"width_px": 5037, "height_px": 6600, "dpi": 150}
_STICKER_PRODUCT_ID = 358              # Kiss-Cut Stickers (Printful catalog product)
_STICKER_KISS_3IN_VARIANT_ID = 10163   # 3″×3″ White · printfile 900×900 @ 300 DPI
_SPEC_STICKER_3IN = {"width_px": 900, "height_px": 900, "dpi": 300}

RESTRICTED_COUNTRIES = {"BY", "CU", "IR", "KP", "RU", "SY"}

STATIC_SHIPPING_RATES: dict[str, dict[str, float]] = {
    "poster": {
        "US": 4.99, "CA": 5.69, "GB": 5.79, "DE": 5.79, "FR": 5.79,
        "ES": 5.79, "AU": 6.19, "JP": 6.49, "CL": 11.99, "MX": 11.99,
        "BR": 13.19, "NO": 10.49, "CH": 10.49, "DEFAULT": 13.19,
    },
    "gaming_mouse_pad": {
        "US": 11.99, "CA": 15.99, "GB": 15.99, "DE": 15.99,
        "FR": 15.99, "ES": 15.99, "AU": 26.99, "JP": 15.99,
        "CL": 15.99, "MX": 15.99, "BR": 15.99, "NO": 17.99,
        "CH": 17.99, "DEFAULT": 26.99,
    },
    "mouse_pad": {
        "US": 4.49, "CA": 6.99, "GB": 4.39, "DE": 4.59,
        "FR": 4.59, "ES": 4.59, "AU": 7.19, "JP": 4.39,
        "CL": 11.99, "MX": 11.99, "BR": 4.49, "NO": 9.99,
        "CH": 9.99, "DEFAULT": 11.99,
    },
    "spiral_notebook": {
        "US": 4.99, "CA": 8.09, "GB": 6.09, "DE": 6.09,
        "FR": 6.09, "ES": 6.09, "AU": 10.99, "JP": 6.09,
        "CL": 11.99, "MX": 11.99, "BR": 11.99, "NO": 10.49,
        "CH": 10.49, "DEFAULT": 11.99,
    },
    "unisex_tshirt": {
        "US": 4.69, "CA": 7.39, "GB": 5.49, "DE": 5.49,
        "FR": 5.49, "ES": 5.49, "AU": 8.99, "JP": 5.49,
        "CL": 11.99, "MX": 11.99, "BR": 11.99, "NO": 10.49,
        "CH": 10.49, "DEFAULT": 11.99,
    },
    "sticker_kiss_3in": {
        "US": 3.99, "CA": 4.49, "GB": 4.29, "DE": 4.29,
        "FR": 4.29, "ES": 4.29, "AU": 4.99, "JP": 4.49,
        "CL": 5.99, "MX": 5.99, "BR": 5.99, "NO": 4.99,
        "CH": 4.99, "DEFAULT": 5.99,
    },
    "sticker_pack": {
        "US": 4.49, "CA": 4.99, "GB": 4.79, "DE": 4.79,
        "FR": 4.79, "ES": 4.79, "AU": 5.49, "JP": 4.99,
        "CL": 6.99, "MX": 6.99, "BR": 6.99, "NO": 5.49,
        "CH": 5.49, "DEFAULT": 6.99,
    },
}

DELIVERY_ESTIMATES: dict[str, dict[str, tuple[int, int]]] = {
    "poster": {
        "US": (4, 6), "CA": (2, 5), "GB": (2, 4), "DE": (4, 4),
        "FR": (5, 7), "ES": (3, 3), "AU": (3, 7), "JP": (2, 3),
        "CL": (8, 14), "MX": (6, 8), "BR": (10, 25), "NO": (5, 8),
        "CH": (3, 6), "DEFAULT": (5, 25),
    },
    "gaming_mouse_pad": {
        "US": (3, 6), "CA": (5, 8), "GB": (8, 11), "DE": (9, 12),
        "FR": (10, 15), "ES": (10, 15), "AU": (10, 15), "JP": (10, 15),
        "CL": (10, 15), "MX": (10, 15), "BR": (10, 15), "NO": (10, 15),
        "CH": (10, 15), "DEFAULT": (10, 20),
    },
    "mouse_pad": {
        "US": (4, 6), "CA": (7, 10), "GB": (3, 4), "DE": (4, 4),
        "FR": (5, 7), "ES": (5, 6), "AU": (16, 17), "JP": (8, 11),
        "CL": (21, 23), "MX": (5, 7), "BR": (16, 16), "NO": (5, 8),
        "CH": (3, 6), "DEFAULT": (5, 25),
    },
    "spiral_notebook": {
        "US": (4, 6), "CA": (7, 10), "GB": (4, 6), "DE": (4, 6),
        "FR": (5, 7), "ES": (5, 7), "AU": (10, 15), "JP": (8, 11),
        "CL": (15, 20), "MX": (7, 10), "BR": (15, 20), "NO": (5, 8),
        "CH": (4, 6), "DEFAULT": (5, 25),
    },
    "unisex_tshirt": {
        "US": (4, 6), "CA": (6, 9), "GB": (4, 6), "DE": (4, 6),
        "FR": (5, 7), "ES": (5, 7), "AU": (10, 15), "JP": (8, 11),
        "CL": (15, 20), "MX": (7, 10), "BR": (15, 20), "NO": (5, 8),
        "CH": (4, 6), "DEFAULT": (5, 25),
    },
    "sticker_kiss_3in": {
        "US": (4, 8), "CA": (6, 10), "GB": (5, 8), "DE": (5, 8),
        "FR": (6, 9), "ES": (6, 9), "AU": (10, 15), "JP": (8, 12),
        "CL": (12, 20), "MX": (7, 12), "BR": (12, 20), "NO": (6, 10),
        "CH": (5, 8), "DEFAULT": (7, 20),
    },
    "sticker_pack": {
        "US": (5, 9), "CA": (7, 11), "GB": (6, 9), "DE": (6, 9),
        "FR": (7, 10), "ES": (7, 10), "AU": (11, 16), "JP": (9, 13),
        "CL": (13, 21), "MX": (8, 13), "BR": (13, 21), "NO": (7, 11),
        "CH": (6, 9), "DEFAULT": (8, 21),
    },
}


# Single source of truth for mockup cache invalidation. Bump this ONE value
# whenever the renderer, print files, or mockup routing change. It feeds three
# layers at once so there is no manual cache-purging or path-guessing:
#   1. the server-side mockup cache_key (routers/render.py) — invalidates disk cache
#   2. the image_url sent to Printful — forces Printful to re-fetch the source art
#   3. the <img>/JS URLs in templates/product.html — busts the browser cache
# Because the disk cache_key embeds this, bumping it alone is enough; you no
# longer need to rm the mockup_cache directory by hand.
MOCKUP_VERSION = "9"


# ── Format ────────────────────────────────────────────────────────────────────
FORMATS: list[dict] = [
    {
        "id":                  "poster",
        "label":               "Art Print",
        "size":                "18 × 24 in",
        "material":            "Enhanced matte paper · 200gsm · archival · unframed",
        "description":         "Archival-quality art print on enhanced matte paper at 300 DPI. Ready for custom framing.",
        "price_usd":           34.0,
        "base_cost":           12.89,
        "shipping_us":         4.99,
        "shipping_intl":       13.19,
        "ships_worldwide":     True,
        "excluded_countries":  sorted(RESTRICTED_COUNTRIES),
        "printful_variant_id": _POSTER_VARIANT_ID,
        "printful_product_id": _POSTER_PRODUCT_ID,
        "print_specs":         _SPEC_POSTER,
    },
    {
        "id":                  "gaming_mouse_pad",
        "label":               "Gaming Mouse Pad",
        "size":                "36 × 18 in",
        "material":            "Polyester top · rubber non-slip base · stitched edges",
        "description":         "Large desk mat with vivid edge-to-edge sublimation print, non-slip rubber base, and stitched rounded edges.",
        "price_usd":           46.0,
        "base_cost":           19.33,
        "shipping_us":         11.99,
        "shipping_intl":       26.99,
        "ships_worldwide":     True,
        "excluded_countries":  sorted(RESTRICTED_COUNTRIES),
        "printful_variant_id": _GAMING_MOUSE_PAD_VARIANT_ID,
        "printful_product_id": _GAMING_MOUSE_PAD_PRODUCT_ID,
        "print_specs":         _SPEC_GAMING_MOUSE_PAD,
    },
    {
        "id":                  "mouse_pad",
        "label":               "Mouse Pad",
        "size":                "8.7 × 7.1 in",
        "material":            "Soft polyester surface · natural rubber base",
        "description":         "Compact desk mouse pad with a soft surface, rounded edges, and a full-color mathematical artwork print.",
        "price_usd":           27.0,
        "base_cost":           9.13,
        "shipping_us":         4.49,
        "shipping_intl":       11.99,
        "ships_worldwide":     True,
        "excluded_countries":  sorted(RESTRICTED_COUNTRIES),
        "printful_variant_id": _MOUSE_PAD_VARIANT_ID,
        "printful_product_id": _MOUSE_PAD_PRODUCT_ID,
        "print_specs":         _SPEC_MOUSE_PAD,
    },
    {
        "id":                  "spiral_notebook",
        "label":               "Spiral Notebook",
        "size":                "5.5 × 8.5 in",
        "material":            "140 dotted or lined pages · 100% paper · soft-touch cover",
        "description":         "Premium spiral notebook featuring edge-to-edge mathematical art on the cover, bound with a black metallic spiral.",
        "price_usd":           30.0,
        "base_cost":           8.29,
        "shipping_us":         4.99,
        "shipping_intl":       11.99,
        "ships_worldwide":     True,
        "excluded_countries":  sorted(RESTRICTED_COUNTRIES),
        "printful_variant_id": _NOTEBOOK_VARIANT_ID,
        "printful_product_id": _NOTEBOOK_PRODUCT_ID,
        "print_specs":         _SPEC_NOTEBOOK,
    },
    {
        "id":                  "unisex_tshirt",
        "label":               "Unisex T-Shirt (Black)",
        "size":                "S – 3XL",
        "material":            "100% combed and ring-spun cotton · Pre-shrunk",
        "description":         "Premium Bella+Canvas 3001 unisex staple t-shirt in Black. Soft, lightweight, and features a vibrant direct-to-garment print.",
        "price_usd":           29.0,
        "base_cost":           12.95,
        "shipping_us":         4.69,
        "shipping_intl":       11.99,
        "ships_worldwide":     True,
        "excluded_countries":  sorted(RESTRICTED_COUNTRIES),
        "printful_variants":   _TSHIRT_VARIANTS,
        "printful_product_id": _TSHIRT_PRODUCT_ID,
        "print_specs":         _SPEC_TSHIRT,
    },
    {
        "id":                  "unisex_hoodie",
        "label":               "Unisex Hoodie (Black)",
        "size":                "S – 3XL",
        "material":            "50% cotton / 50% polyester · Heavy blend fleece",
        "description":         "Cozy Gildan 18500 unisex heavy-blend hoodie in Black, with a vibrant direct-to-garment print and a soft fleece interior.",
        "price_usd":           52.0,
        "base_cost":           22.19,
        "shipping_us":         8.49,
        "shipping_intl":       16.99,
        "ships_worldwide":     True,
        "excluded_countries":  sorted(RESTRICTED_COUNTRIES),
        "printful_variants":   _HOODIE_VARIANTS,
        "printful_product_id": _HOODIE_PRODUCT_ID,
        "print_specs":         _SPEC_HOODIE,
    },
    {
        "id":                  "aop_leggings",
        "label":               "All-Over Leggings",
        "size":                "XS – XL",
        "material":            "82% polyester / 18% spandex · Four-way stretch",
        "description":         "All-over-print leggings — a full-bleed mathematical pattern wrapping the entire garment, cut-and-sewn for a seamless wrap. Buttery four-way stretch.",
        "price_usd":           56.0,
        "base_cost":           23.41,
        "shipping_us":         6.99,
        "shipping_intl":       12.99,
        "ships_worldwide":     True,
        "excluded_countries":  sorted(RESTRICTED_COUNTRIES),
        "printful_variants":   _AOP_LEGGINGS_VARIANTS,
        "printful_product_id": _AOP_LEGGINGS_PRODUCT_ID,
        "print_specs":         _SPEC_AOP_LEGGINGS,
        "aop":                 True,
        "aop_placements":      ["default"],
    },
    {
        "id":                  "aop_joggers",
        "label":               "All-Over Joggers",
        "size":                "XS – 2XL",
        "material":            "Soft-brushed polyester · Wide-leg relaxed fit",
        "description":         "All-over-print wide-leg joggers — a full-bleed mathematical pattern across front and back, cut-and-sewn for a seamless wrap.",
        "price_usd":           68.0,
        "base_cost":           39.73,
        "shipping_us":         8.99,
        "shipping_intl":       14.99,
        "ships_worldwide":     True,
        "excluded_countries":  sorted(RESTRICTED_COUNTRIES),
        "printful_variants":   _AOP_JOGGERS_VARIANTS,
        "printful_product_id": _AOP_JOGGERS_PRODUCT_ID,
        "print_specs":         _SPEC_AOP_JOGGERS,
        "aop":                 True,
        "aop_placements":      ["front", "back"],
    },
    {
        "id":                  "aop_sweatshirt",
        "label":               "All-Over Sweatshirt",
        "size":                "XS – 2XL",
        "material":            "Cotton-feel fabric · Crew-neck pullover",
        "description":         "All-over-print crew-neck sweatshirt — a full-bleed mathematical pattern across every panel, cut-and-sewn for a seamless wrap.",
        "price_usd":           67.0,
        "base_cost":           38.99,
        "shipping_us":         8.99,
        "shipping_intl":       14.99,
        "ships_worldwide":     True,
        "excluded_countries":  sorted(RESTRICTED_COUNTRIES),
        "printful_variants":   _AOP_SWEATSHIRT_VARIANTS,
        "printful_product_id": _AOP_SWEATSHIRT_PRODUCT_ID,
        "print_specs":         _SPEC_AOP_SWEATSHIRT,
        "aop":                 True,
        "aop_placements":      ["front_dtfabric", "back_dtfabric", "sleeve_left_dtfabric", "sleeve_right_dtfabric"],
    },
    {
        "id":                  "sticker_kiss_3in",
        "label":               "Kiss-Cut Sticker",
        "size":                "3 × 3 in",
        "material":            "Durable matte vinyl · kiss-cut with a thin white border",
        "description":         "Premium kiss-cut vinyl sticker featuring a real mathematical design. Water- and scratch-resistant — great on laptops, bottles, and notebooks.",
        "price_usd":           5.99,
        "base_cost":           1.49,
        "shipping_us":         3.99,
        "shipping_intl":       4.99,
        "ships_worldwide":     True,
        "excluded_countries":  sorted(RESTRICTED_COUNTRIES),
        "printful_variant_id": _STICKER_KISS_3IN_VARIANT_ID,
        "printful_product_id": _STICKER_PRODUCT_ID,
        "print_specs":         _SPEC_STICKER_3IN,
    },
    {
        "id":                  "sticker_pack",
        "label":               "Sticker Pack",
        "size":                "3 × 3 in each",
        "material":            "Durable matte vinyl · kiss-cut · multiple designs shipped together",
        "description":         "A discounted set of our real-math kiss-cut vinyl stickers, shipped together. The exact designs depend on the pack.",
        "price_usd":           12.99,   # placeholder; per-pack price comes from the Product
        "base_cost":           4.47,
        "shipping_us":         3.99,
        "shipping_intl":       4.99,
        "ships_worldwide":     True,
        "excluded_countries":  sorted(RESTRICTED_COUNTRIES),
        "printful_variant_id": _STICKER_KISS_3IN_VARIANT_ID,
        "printful_product_id": _STICKER_PRODUCT_ID,
        "print_specs":         _SPEC_STICKER_3IN,
        "pack":                True,
    },
]

FORMATS_BY_ID: dict[str, dict] = {f["id"]: f for f in FORMATS}


# Per-format physical detail: fit note, care instructions, and size charts
# (apparel measurements from Printful supplier data, inches). Merged into the
# format dicts below so product pages can show real product information.
FORMAT_DETAILS: dict[str, dict] = {
    "unisex_tshirt": {
        "fit": "Unisex regular fit. Runs true to size; size up for a relaxed look.",
        "care": ["Machine wash cold, inside-out, gentle cycle",
                 "Tumble dry low", "Do not iron directly on the design",
                 "Do not bleach or dry-clean"],
        "size_chart": {
            "caption": "Garment measurements, laid flat (inches)",
            "headers": ["S", "M", "L", "XL", "2XL", "3XL"],
            "rows": [["Chest (in)", ["34", "38", "42", "46", "50", "54"]],
                     ["Length (in)", ["28", "29", "30", "31", "32", "33"]]],
        },
    },
    "unisex_hoodie": {
        "fit": "Unisex classic fit with a roomy body. Size down for a slimmer fit.",
        "care": ["Machine wash cold, inside-out, gentle cycle",
                 "Tumble dry low", "Do not iron directly on the design",
                 "Do not bleach or dry-clean"],
        "size_chart": {
            "caption": "Garment measurements, laid flat (inches)",
            "headers": ["S", "M", "L", "XL", "2XL", "3XL"],
            "rows": [["Chest (in)", ["38", "42", "46", "50", "54", "58"]],
                     ["Length (in)", ["27", "28", "29", "30", "31", "32"]],
                     ["Sleeve (in)", ["33.5", "34.5", "35.5", "36.5", "37.5", "38.5"]]],
        },
    },
    "aop_sweatshirt": {
        "fit": "Unisex relaxed fit. Cut-and-sewn; chart shows BODY measurements — pick the size matching your body.",
        "care": ["Machine wash cold, inside-out, gentle cycle",
                 "Hang dry recommended (tumble dry low if needed)",
                 "Iron inside-out on low if needed", "Do not bleach or dry-clean"],
        "size_chart": {
            "caption": "Body measurements to choose your size (inches)",
            "headers": ["XS", "S", "M", "L", "XL", "2XL"],
            "rows": [["Chest (in)", ["36", "38", "39", "43", "46", "49"]],
                     ["Waist (in)", ["30", "31", "33", "36", "39", "43"]],
                     ["Hips (in)", ["37", "39", "40", "43", "46", "50"]]],
        },
    },
    "poster": {
        "care": ["Handle by the edges to avoid fingerprints",
                 "Frame behind glass to protect from dust and UV",
                 "Ships rolled in a protective tube"],
    },
    "gaming_mouse_pad": {
        "care": ["Spot-clean with a damp cloth and mild soap",
                 "Air-dry flat — do not machine wash", "Non-slip rubber base"],
    },
    "mouse_pad": {
        "care": ["Spot-clean with a damp cloth", "Air-dry flat", "Non-slip rubber base"],
    },
    "spiral_notebook": {
        "care": ["Wipe the cover clean with a dry cloth", "Keep away from moisture"],
    },
}
for _fid, _d in FORMAT_DETAILS.items():
    if _fid in FORMATS_BY_ID:
        FORMATS_BY_ID[_fid].update(_d)


_GARMENT_FORMATS = {"tshirt": "unisex_tshirt", "hoodie": "unisex_hoodie",
                    "aop_leggings": "aop_leggings", "aop_joggers": "aop_joggers",
                    "aop_sweatshirt": "aop_sweatshirt"}


def format_for_garment(garment: str) -> dict:
    """Apparel format dict for a product's garment ('tshirt', 'hoodie', 'aop_leggings')."""
    return FORMATS_BY_ID[_GARMENT_FORMATS.get(garment, "unisex_tshirt")]

POSTER_FORMAT_IDS = ("poster",)
DESK_MAT_FORMAT_IDS = ("gaming_mouse_pad", "mouse_pad")
NOTEBOOK_FORMAT_IDS = ("spiral_notebook",)
APPAREL_FORMAT_IDS = ("unisex_tshirt",)
STICKER_FORMAT_IDS = ("sticker_kiss_3in",)
STICKER_PACK_FORMAT_IDS = ("sticker_pack",)

# Legacy alias
PRINT_SPECS: dict[str, dict] = {f["id"]: f["print_specs"] for f in FORMATS}


def formats_for_collection(collection: str) -> list[dict]:
    if collection == "desk-mats":
        format_ids = DESK_MAT_FORMAT_IDS
    elif collection == "notebooks":
        format_ids = NOTEBOOK_FORMAT_IDS
    elif collection == "apparel":
        format_ids = APPAREL_FORMAT_IDS
    elif collection == "stickers":
        format_ids = STICKER_FORMAT_IDS
    elif collection == "sticker-packs":
        format_ids = STICKER_PACK_FORMAT_IDS
    else:
        format_ids = POSTER_FORMAT_IDS
    return [FORMATS_BY_ID[format_id] for format_id in format_ids]

# Mockup scene rotation per format
# Lifestyle = ambient/contextual scenes (desk in use, art on a wall, etc.)
# These produce richer marketing-style mockups than the bare "Flat" view.
SCENE_ROTATION: dict[str, list[str]] = {
    "poster": ["Lifestyle", "Lifestyle 2", "Lifestyle 3", "Lifestyle 4",
               "Lifestyle 5", "Lifestyle 6", "Lifestyle 7", "Lifestyle 8"],
    "gaming_mouse_pad": ["Lifestyle", "Lifestyle 2", "Lifestyle 3", "Lifestyle 4",
                         "Lifestyle 5", "Lifestyle 6", "Lifestyle 7"],
    "mouse_pad": ["Lifestyle", "Lifestyle 2"],
    "spiral_notebook": ["Flat"],
    "unisex_tshirt": [150560, 712046, 674969, 959140, 709170, 667301],
}

# Flat (no scene) variants — useful when we want a clean studio shot
FLAT_SCENES: dict[str, str] = {
    "gaming_mouse_pad-flat": "Flat",
    "mouse_pad-flat":        "Flat",
    "poster-flat":           "Flat",
    "spiral_notebook-flat":  "Flat",
    "unisex_tshirt-flat":    "Flat",
}


def get_mockup_scene(format_id: str, slug: str) -> str | int | None:
    """
    Resolve a format ID (possibly with suffix) to a Printful scene name.

    Suffix rules:
      base                                  → rotation indexed by hash(slug)
      base-flat                             → "Flat"
      base-1 .. base-N (1-indexed)          → SCENE_ROTATION[base][N-1]
      e.g. gaming_mouse_pad-3 → "Lifestyle 3"
    """
    if format_id in FLAT_SCENES:
        return FLAT_SCENES[format_id]

    # Numeric suffix: base-N
    if "-" in format_id:
        base, suffix = format_id.rsplit("-", 1)
        if suffix.isdigit():
            scenes = SCENE_ROTATION.get(base)
            if scenes:
                idx = max(0, min(len(scenes) - 1, int(suffix) - 1))
                return scenes[idx]

    scenes = SCENE_ROTATION.get(format_id)
    if not scenes:
        return None
    return scenes[hash(slug) % len(scenes)]


def scenes_for_format(format_id: str) -> list:
    """List of scene names available for a base format. Empty if none configured."""
    return list(SCENE_ROTATION.get(format_id, []))


def can_ship_to_country(country_code: str) -> bool:
    code = (country_code or "").upper()
    return len(code) == 2 and code not in RESTRICTED_COUNTRIES


def shipping_cost(country_code: str, format_id: str = "poster") -> float:
    country = (country_code or "").upper()
    if not can_ship_to_country(country):
        raise ValueError(f"Printful shipping is not available to {country_code}")
    rates = STATIC_SHIPPING_RATES.get(format_id, STATIC_SHIPPING_RATES["poster"])
    return rates.get(country, rates["DEFAULT"])


def delivery_estimate(country_code: str, format_id: str = "poster") -> tuple[int, int]:
    country = (country_code or "").upper()
    estimates = DELIVERY_ESTIMATES.get(format_id, DELIVERY_ESTIMATES["poster"])
    return estimates.get(country, estimates["DEFAULT"])


async def shipping_quote(shipping_address: dict, format_id: str = "poster") -> dict:
    country = (shipping_address.get("country") or shipping_address.get("country_code") or "").upper()
    if not can_ship_to_country(country):
        raise ValueError(f"Printful shipping is not available to {country or 'this country'}")

    fmt = FORMATS_BY_ID.get(format_id, FORMATS_BY_ID["poster"])
    fallback_min, fallback_max = delivery_estimate(country, fmt["id"])
    fallback = {
        "rate": shipping_cost(country, fmt["id"]),
        "currency": "USD",
        "minDeliveryDays": fallback_min,
        "maxDeliveryDays": fallback_max,
        "source": "static",
    }
    if not PRINTFUL_API_KEY:
        return fallback

    recipient = {
        "name": " ".join(filter(None, [
            shipping_address.get("first_name", ""),
            shipping_address.get("last_name", ""),
        ])).strip() or shipping_address.get("name", "Customer"),
        "address1": shipping_address.get("address1", ""),
        "address2": shipping_address.get("address2", ""),
        "city": shipping_address.get("city", ""),
        "state_code": shipping_address.get("state", ""),
        "zip": shipping_address.get("zip", ""),
        "country_code": country,
    }
    payload = {
        "recipient": recipient,
        "items": [{"variant_id": fmt.get("printful_variant_id") or fmt.get("printful_variants", {}).get("L"), "quantity": 1}],
        "currency": "USD",
        "locale": "en_US",
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/shipping/rates",
                headers=_headers(),
                json=payload,
                timeout=20,
            )
        if resp.status_code != 200:
            return fallback
        rates = resp.json().get("result") or []
        standard = [r for r in rates if r.get("id") == "STANDARD"] or rates
        if not standard:
            return fallback
        selected = min(standard, key=lambda r: float(r.get("rate") or 9999))
        return {
            "rate": float(selected.get("rate") or fallback["rate"]),
            "currency": selected.get("currency") or "USD",
            "minDeliveryDays": selected.get("minDeliveryDays") or fallback_min,
            "maxDeliveryDays": selected.get("maxDeliveryDays") or fallback_max,
            "source": "printful_live",
        }
    except Exception:
        return fallback


# ── Order creation ────────────────────────────────────────────────────────────
async def create_order(order, shipping_address: dict):
    if not PRINTFUL_API_KEY:
        await _mark_order_failed(order.id, "Printful API key is not configured")
        return None

    from models.product import Product
    from database import SessionLocal

    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == order.product_id).first()
        if not product:
            await _mark_order_failed(order.id, f"Product {order.product_id} not found")
            return None
        format_id = getattr(order, "format_id", None) or "poster"
        fmt        = FORMATS_BY_ID.get(format_id, FORMATS_BY_ID["poster"])
        
        # Determine variant (could be specific size for apparel)
        variant_id = fmt.get("printful_variant_id")
        
        # If it's an apparel format, we must extract the size from the format_id suffix or order parameters
        size_label = ""
        if not variant_id and "printful_variants" in fmt:
            import json
            try:
                params = json.loads(order.params_json)
                selected_size = params.get("size", "L")
            except Exception:
                selected_size = "L"
            
            variant_id = fmt["printful_variants"].get(selected_size)
            if not variant_id:
                variant_id = fmt["printful_variants"].get("L")
            size_label = f" - Size {selected_size}"
        
        import json as _json
        try:
            pack_members = (_json.loads(product.params_json or "{}")).get("pack_members") or []
        except Exception:
            pack_members = []

        if pack_members:
            # A sticker pack fulfils as several Kiss-Cut sticker line items — one
            # per member design — each using the sticker variant and that member's
            # print file. Retail price is split evenly across members.
            n = len(pack_members)
            unit = round(float(product.price_usd) / n, 2) if n else float(product.price_usd)
            items = []
            for m_slug in pack_members:
                m = db.query(Product).filter(Product.slug == m_slug).first()
                items.append({
                    "variant_id":   variant_id,
                    "quantity":     1,
                    "retail_price": f"{unit:.2f}",
                    "name":         f"{product.name} — {m.name if m else m_slug}",
                    "files": [{
                        "placement": "default",
                        "url": f"https://mathrelaxing.store/api/render/print?product={m_slug}&format=sticker_kiss_3in",
                    }],
                })
        else:
            if fmt.get("aop"):
                image_url = f"https://mathrelaxing.store/api/render/aop-print?product={product.slug}&v=3"
            elif fmt["id"] in ("unisex_tshirt", "unisex_hoodie"):
                image_url = f"https://mathrelaxing.store/api/render/apparel-print?product={product.slug}&v=2"
            else:
                image_url = (
                    f"https://mathrelaxing.store/api/render/print"
                    f"?product={product.slug}&format={fmt['id']}"
                )
            placements = fmt.get("aop_placements") or [
                "front" if ("notebook" in fmt["id"] or "tshirt" in fmt["id"] or "hoodie" in fmt["id"]) else "default"
            ]
            items = [{
                "variant_id":   variant_id,
                "quantity":     1,
                "retail_price": f"{fmt['price_usd']:.2f}",
                "name":         f"{product.name} — {fmt['label']}{size_label}",
                "files": [{"placement": pl, "url": image_url} for pl in placements],
            }]
    finally:
        db.close()

    name = " ".join(filter(None, [
        shipping_address.get("first_name", ""),
        shipping_address.get("last_name", ""),
    ])).strip() or shipping_address.get("name", "Customer")

    payload = {
        "external_id": f"mathrelaxing-{order.id}",
        "shipping": "STANDARD",
        "recipient": {
            "name":         name,
            "address1":     shipping_address.get("address1", ""),
            "address2":     shipping_address.get("address2", ""),
            "city":         shipping_address.get("city", ""),
            "state_code":   shipping_address.get("state", ""),
            "zip":          shipping_address.get("zip", ""),
            "country_code": shipping_address.get("country", "US"),
            "email":        order.customer_email or "",
        },
        "items": items,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{BASE_URL}/orders",
                headers=_headers(),
                params={"confirm": 1},
                json=payload,
                timeout=20,
            )
        except httpx.HTTPError as exc:
            await _mark_order_failed(order.id, f"Printful request error: {exc}")
            return None
        if resp.status_code in (200, 201):
            data  = resp.json()
            pf_id = str(data.get("result", {}).get("id", ""))
            if pf_id:
                db2 = SessionLocal()
                try:
                    o = db2.query(type(order)).filter(type(order).id == order.id).first()
                    if o:
                        o.printful_order_id = pf_id
                        o.status = "processing"
                        db2.commit()
                finally:
                    db2.close()
            return pf_id
        await _mark_order_failed(order.id, f"Printful create order failed {resp.status_code}: {resp.text[:500]}")
    return None


async def _mark_order_failed(order_id: int, reason: str) -> None:
    log.error("[printful] order %s fulfillment failed: %s", order_id, reason)
    from database import SessionLocal
    from models.product import Order

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order and order.status not in ("shipped", "printed", "cancelled"):
            order.status = "fulfillment_failed"
            db.commit()
    finally:
        db.close()


# ── Mockup generator ──────────────────────────────────────────────────────────
async def _run_mockup_task(
    product_id: int,
    variant_id: int,
    image_url: str,
    format_id: str = "poster",
    scene: str | int | None = None,
) -> list | None:
    """Create a Printful mockup task and return its raw `mockups` list."""
    if not PRINTFUL_API_KEY or not product_id or not variant_id:
        return None

    specs = PRINTFILE_SPECS.get(format_id, PRINTFILE_SPECS["poster"])
    pw, ph = specs["width_px"], specs["height_px"]
    position = {"area_width": pw, "area_height": ph, "width": pw, "height": ph, "top": 0, "left": 0}

    # AOP cut-and-sew garments print the pattern onto several panels at once
    # (front/back/sleeves); DTG garments use a single front placement.
    fmt_def = FORMATS_BY_ID.get(format_id, {})
    placements = fmt_def.get("aop_placements")
    if not placements:
        placements = ["front" if ("notebook" in format_id or "tshirt" in format_id or "hoodie" in format_id) else "default"]
    files = [{"placement": pl, "image_url": image_url, "position": position} for pl in placements]

    payload = {
        "variant_ids": [variant_id],
        "format":      "jpg",
        "width":       1500,
        "files":       files,
    }
    if scene:
        if isinstance(scene, int):
            payload["template_ids"] = [scene]
        else:
            payload["option_groups"] = [scene]

    async with httpx.AsyncClient() as client:
        resp = None
        for attempt in range(3):
            resp = await client.post(
                f"{BASE_URL}/mockup-generator/create-task/{product_id}",
                headers=_headers(),
                json=payload,
                timeout=30,
            )
            if resp.status_code == 200:
                break
            if resp.status_code == 429:
                await asyncio.sleep(15 * (attempt + 1))
            else:
                return None
        if not resp or resp.status_code != 200:
            return None

        task_key = resp.json().get("result", {}).get("task_key", "")
        if not task_key:
            return None

        for _ in range(30):
            await asyncio.sleep(2)
            poll = await client.get(
                f"{BASE_URL}/mockup-generator/task",
                headers=_headers(),
                params={"task_key": task_key},
                timeout=10,
            )
            if poll.status_code != 200:
                continue
            result = poll.json().get("result", {})
            if result.get("status") == "completed":
                return result.get("mockups", [])
            if result.get("status") == "failed":
                return None
    return None


async def generate_mockup(
    product_id: int,
    variant_id: int,
    image_url: str,
    format_id: str = "poster",
    scene: str | int | None = None,
) -> bytes | None:
    mockups = await _run_mockup_task(product_id, variant_id, image_url, format_id, scene)
    if not mockups:
        return None
    url = mockups[0].get("mockup_url", "")
    if not url:
        return None
    async with httpx.AsyncClient() as client:
        img = await client.get(url, timeout=20)
        return img.content if img.status_code == 200 else None


async def generate_mockup_views(
    product_id: int,
    variant_id: int,
    image_url: str,
    format_id: str = "unisex_tshirt",
) -> list:
    """All distinct mockup views from one task (Front/Back/Left/Right/…), ordered
    one-per-angle first so adjacent gallery thumbnails are never the same shot."""
    mockups = await _run_mockup_task(product_id, variant_id, image_url, format_id)
    if not mockups:
        return []
    primary, leftover, seen_titles, seen_urls = [], [], set(), set()
    for m in mockups:
        entries = []
        if m.get("mockup_url"):
            entries.append((m.get("placement") or "Front", m["mockup_url"]))
        for e in m.get("extra", []):
            if e.get("url"):
                entries.append((e.get("title") or "View", e["url"]))
        for title, url in entries:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            tkey = title.strip().lower()
            if tkey not in seen_titles:
                seen_titles.add(tkey)
                primary.append(url)
            else:
                leftover.append(url)
    return primary + leftover


# ── Webhook signature verification ───────────────────────────────────────────
def verify_webhook(body: bytes, signature: str) -> bool:
    if not PRINTFUL_WEBHOOK_SECRET:
        return False
    expected = hmac.new(
        PRINTFUL_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


# ── Printful order status → internal status ───────────────────────────────────
PRINTFUL_STATUS_MAP = {
    "pending":   "processing",
    "inprocess": "processing",
    "fulfilled": "printed",
    "shipped":   "shipped",
    "canceled":  "cancelled",
    "failed":    "failed",
}
