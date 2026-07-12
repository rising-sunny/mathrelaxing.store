import os
import hashlib
import hmac
import json
import httpx

LEMON_API_KEY = os.getenv("LEMON_SQUEEZY_API_KEY", "")
LEMON_STORE_ID = os.getenv("LEMON_SQUEEZY_STORE_ID", "")
LEMON_WEBHOOK_SECRET = os.getenv("LEMON_SQUEEZY_WEBHOOK_SECRET", "")
LEMON_DEFAULT_VARIANT_ID = os.getenv("LEMON_DEFAULT_VARIANT_ID", "1556945")

HEADERS = {
    "Accept": "application/vnd.api+json",
    "Content-Type": "application/vnd.api+json",
    "Authorization": f"Bearer {LEMON_API_KEY}",
}


async def create_checkout(
    purchase_id: int,
    product,
    customer_email: str,
    customer_name: str,
    ref_source: str = "direct",
    item_name: str | None = None,
    price_override_usd: float | None = None,
) -> str:
    """Create a LemonSqueezy checkout for a digital product purchase.
    Uses custom_price with a single variant, overriding name/description per bundle."""
    if not LEMON_API_KEY or not LEMON_STORE_ID:
        return f"https://mathrelaxing.store/checkout?purchase_id={purchase_id}"

    variant_id = getattr(product, "lemon_variant_id", None) or LEMON_DEFAULT_VARIANT_ID
    price_cents = int((price_override_usd if price_override_usd is not None else product.price_usd) * 100)
    display_name = item_name if item_name else product.name
    display_desc = (
        f"Single digital image — {display_name}"
        if item_name
        else (product.description or f"Digital bundle — {product.name}")
    )
    receipt_btn = "Download Your Image" if item_name else "Download Your Bundle"
    receipt_note = (
        "Thanks for your purchase! Your image is ready for download."
        if item_name
        else "Thanks for your purchase! Your digital bundle is ready for download."
    )

    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "custom_price": price_cents,
                "product_options": {
                    "name": display_name,
                    "description": display_desc,
                    "redirect_url": f"https://mathrelaxing.store/download/{getattr(product, 'download_token', '')}",
                    "receipt_button_text": receipt_btn,
                    "receipt_link_url": f"https://mathrelaxing.store/download",
                    "receipt_thank_you_note": receipt_note,
                },
                "checkout_data": {
                    "email": customer_email,
                    "name": customer_name,
                    "custom": {
                        "purchase_id": str(purchase_id),
                        "product_slug": product.slug,
                        "ref_source": ref_source,
                    },
                },
                "checkout_options": {
                    "media": False,
                    "discount": False,
                },
            },
            "relationships": {
                "store": {"data": {"type": "stores", "id": LEMON_STORE_ID}},
                "variant": {"data": {"type": "variants", "id": variant_id}},
            },
        }
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.lemonsqueezy.com/v1/checkouts",
            headers=HEADERS,
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"]["attributes"]["url"]


def verify_webhook(signature: str, payload: str) -> bool:
    """Verify LemonSqueezy webhook signature using HMAC-SHA256."""
    if not LEMON_WEBHOOK_SECRET:
        return False
    mac = hmac.new(
        LEMON_WEBHOOK_SECRET.encode(),
        msg=payload.encode(),
        digestmod=hashlib.sha256,
    )
    return hmac.compare_digest(mac.hexdigest(), signature)


async def get_download_url(order_id: str) -> str | None:
    """Retrieve the download URL for a paid LemonSqueezy order."""
    if not LEMON_API_KEY:
        return None

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.lemonsqueezy.com/v1/orders/{order_id}",
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data["data"]["attributes"].get("first_order_item", {}).get(
            "urls", {}
        ).get("download_url")


async def list_products() -> list[dict]:
    """List all LemonSqueezy products in the store."""
    if not LEMON_API_KEY or not LEMON_STORE_ID:
        return []

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.lemonsqueezy.com/v1/products?filter[store_id]={LEMON_STORE_ID}",
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [
            {
                "id": p["id"],
                "name": p["attributes"]["name"],
                "status": p["attributes"]["status"],
                "variants": p["relationships"]["variants"]["data"],
            }
            for p in data.get("data", [])
        ]


async def create_lowpoly_checkout(
    job_id: int,
    token: str,
    customer_email: str,
    customer_name: str,
    description: str,
    price_usd: float = 2.99,
) -> str:
    """Create a LemonSqueezy checkout for a Low Poly coloring page job."""
    redirect_url = f"https://mathrelaxing.store/lowpoly/result/{token}"

    if not LEMON_API_KEY or not LEMON_STORE_ID:
        return redirect_url

    price_cents = int(price_usd * 100)
    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "custom_price": price_cents,
                "product_options": {
                    "name": "Color-by-Number Coloring Page",
                    "description": description,
                    "redirect_url": redirect_url,
                    "receipt_button_text": "View My Coloring Page",
                    "receipt_link_url": redirect_url,
                    "receipt_thank_you_note": "Thanks! Check your email — your download links are on their way.",
                },
                "checkout_data": {
                    "email": customer_email,
                    "name": customer_name,
                    "custom": {
                        "job_type": "lowpoly",
                        "job_id": str(job_id),
                        "token": token,
                    },
                },
                "checkout_options": {"media": False, "discount": False},
            },
            "relationships": {
                "store":   {"data": {"type": "stores",   "id": LEMON_STORE_ID}},
                "variant": {"data": {"type": "variants", "id": LEMON_DEFAULT_VARIANT_ID}},
            },
        }
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.lemonsqueezy.com/v1/checkouts",
            headers=HEADERS,
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"]["attributes"]["url"]
