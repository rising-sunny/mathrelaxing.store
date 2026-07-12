import json
import os
import httpx

CLIENT_ID     = os.getenv("GUMROAD_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GUMROAD_CLIENT_SECRET", "")
REDIRECT_URI  = os.getenv("GUMROAD_REDIRECT_URI", "https://mathrelaxing.store/api/gumroad/oauth/callback")
TOKEN_FILE    = "/var/www/mathrelaxing.store/.gumroad_token.json"
PRODUCTS_FILE = "/var/www/mathrelaxing.store/.gumroad_products.json"
API_BASE      = "https://api.gumroad.com/v2"


# ── Auth ─────────────────────────────────────────────────────────────────────

def get_access_token() -> str | None:
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE) as f:
        return json.load(f).get("access_token")


def save_token(data: dict):
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def is_configured() -> bool:
    return bool(get_access_token())


def get_auth_url() -> str:
    return (
        "https://gumroad.com/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&scope=edit_products+view_sales+mark_sales_as_shipped"
    )


async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post("https://api.gumroad.com/oauth/token", data={
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri":  REDIRECT_URI,
            "code":          code,
            "grant_type":    "authorization_code",
        })
        r.raise_for_status()
        return r.json()


# ── Products map (slug → gumroad_product_id) ─────────────────────────────────

def _load_map() -> dict:
    if not os.path.exists(PRODUCTS_FILE):
        return {}
    with open(PRODUCTS_FILE) as f:
        return json.load(f)


def _save_map(m: dict):
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(m, f, indent=2)


def slug_for_gumroad_id(gid: str) -> str | None:
    for slug, v in _load_map().items():
        if v == gid:
            return slug
    return None


# ── Product status ────────────────────────────────────────────────────────────

async def get_listing_status(product) -> dict:
    m = _load_map()
    gid = m.get(product.slug)
    if not gid:
        return {"status": "not_listed", "gumroad_id": None}
    token = get_access_token()
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{API_BASE}/products/{gid}", params={"access_token": token})
        if r.status_code == 404:
            m.pop(product.slug, None)
            _save_map(m)
            return {"status": "not_listed", "gumroad_id": None}
        data = r.json().get("product", {})
        published = data.get("published", False)
        return {
            "status":       "published" if published else "unpublished",
            "gumroad_id":   gid,
            "gumroad_url":  data.get("short_url", ""),
            "sales_count":  data.get("sales_count", 0),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:120], "gumroad_id": gid}


# ── Publish / unpublish ───────────────────────────────────────────────────────

def _product_label(product) -> str:
    product_type = (getattr(product, "product_type", "") or "").lower()
    return {
        "image_pack": "Image Pack",
        "animation_pack": "Loop Animation Pack",
        "creator_assets": "Creator Assets",
        "thematic_bundle": "Digital Bundle",
    }.get(product_type, "Digital Download")


def _included_line(product) -> str:
    product_type = (getattr(product, "product_type", "") or "").lower()
    if product_type == "image_pack":
        return "High-resolution mathematical art images for wallpapers, print mockups, and visual projects"
    if product_type == "animation_pack":
        return "Seamless mathematical loop animations for video backgrounds, reels, streams, and ambient displays"
    if product_type == "creator_assets":
        return "Creator-ready mathematical visuals, loops, overlays, and source-style assets"
    return "Digital mathematical art files from MathRelaxing"


def _product_description(product) -> str:
    label = _product_label(product)
    lines = [
        f"{label}: {product.name}",
        "",
        product.description or product.name,
        "",
    ]
    lines += [
        "**What's included:**",
        f"- {_included_line(product)}",
        "- Instant download link emailed after purchase",
        "- Lifetime ownership with up to 3 downloads",
        "- Personal license unless the product page says otherwise",
        "- Generated from real equations and simulations, not stock footage",
        "",
        f"View previews and product details: https://mathrelaxing.store/bundle/{product.slug}?utm_source=gumroad&utm_medium=marketplace&utm_campaign=product_description",
    ]
    return "\n".join(lines)


async def publish_product(product) -> dict:
    token = get_access_token()
    m     = _load_map()
    gid   = m.get(product.slug)
    price_cents = max(0, int(round(product.price_usd * 100)))

    payload = {
        "access_token":   token,
        "name":           f"{product.name} | {_product_label(product)}",
        "price":          price_cents,
        "description":    _product_description(product),
        "custom_summary": f"{_product_label(product)} - {(product.description or product.name)}"[:150],
        "shown_on_profile": "true",
        "published":      "true",
    }

    async with httpx.AsyncClient(timeout=20) as c:
        if gid:
            r = await c.put(f"{API_BASE}/products/{gid}", data=payload)
            if r.is_success:
                await c.put(f"{API_BASE}/products/{gid}/enable",
                            data={"access_token": token})
        else:
            r = await c.post(f"{API_BASE}/products", data=payload)

    if not r.is_success:
        raise Exception(f"Gumroad error {r.status_code}: {r.text[:300]}")

    data = r.json().get("product", {})
    gid  = data["id"]
    if not data.get("published", False):
        async with httpx.AsyncClient(timeout=20) as c:
            enabled = await c.put(
                f"{API_BASE}/products/{gid}/enable",
                data={"access_token": token},
            )
            if enabled.is_success:
                data = enabled.json().get("product", data)
    m[product.slug] = gid
    _save_map(m)
    return {
        "gumroad_id":  gid,
        "gumroad_url": data.get("short_url", ""),
        "sales_count": data.get("sales_count", 0),
    }


async def unpublish_product(product) -> None:
    token = get_access_token()
    m     = _load_map()
    gid   = m.get(product.slug)
    if not gid:
        raise Exception("Product not listed on Gumroad")
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.put(f"{API_BASE}/products/{gid}/disable", data={"access_token": token})
    if not r.is_success:
        raise Exception(f"Gumroad error {r.status_code}: {r.text[:200]}")


# ── Sale verification (for Ping webhook) ──────────────────────────────────────

async def verify_sale(sale_id: str) -> dict | None:
    token = get_access_token()
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{API_BASE}/sales/{sale_id}", params={"access_token": token})
    if not r.is_success:
        return None
    return r.json().get("sale")
