import json
import os

import httpx

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET", "")
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "live")
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")

BASE_URL = (
    "https://api-m.paypal.com"
    if PAYPAL_MODE == "live"
    else "https://api-m.sandbox.paypal.com"
)


async def _get_access_token() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={"grant_type": "client_credentials"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


def _payer_action_url(data: dict) -> str:
    for link in data.get("links", []):
        if link.get("rel") == "payer-action":
            return link["href"]
    raise RuntimeError(f"PayPal did not return payer-action URL: {data}")


async def create_order(
    order_id: int,
    product,
    amount_usd: float,
    customer_email: str,
    customer_name: str,
    format_id: str = "canvas",
) -> tuple[str, str]:
    """Create a physical-product PayPal order.

    Returns (checkout_url, paypal_order_id).
    """
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        return f"https://mathrelaxing.store/checkout?order_id={order_id}", ""

    token = await _get_access_token()
    return_url = f"https://mathrelaxing.store/checkout/return?order_id={order_id}"
    cancel_url = "https://mathrelaxing.store/checkout"

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": str(order_id),
                "custom_id": f"order:{order_id}",
                "description": f"{product.name} — {format_id}",
                "amount": {
                    "currency_code": "USD",
                    "value": f"{amount_usd:.2f}",
                },
            }
        ],
        "payment_source": {
            "paypal": {
                "experience_context": {
                    "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
                    "brand_name": "MathRelaxing",
                    "locale": "en-US",
                    "landing_page": "LOGIN",
                    "user_action": "PAY_NOW",
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                }
            }
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/v2/checkout/orders",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

    return _payer_action_url(data), data.get("id") or ""


async def capture_order(paypal_order_id: str) -> dict:
    token = await _get_access_token()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/v2/checkout/orders/{paypal_order_id}/capture",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


async def get_order(paypal_order_id: str) -> dict:
    """Fetch a PayPal checkout order by id (for webhook fallback matching)."""
    token = await _get_access_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/v2/checkout/orders/{paypal_order_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


async def verify_webhook_signature(headers: dict, body: bytes) -> bool:
    if not PAYPAL_WEBHOOK_ID:
        return True  # skip verification if not configured yet

    try:
        token = await _get_access_token()
        payload = {
            "auth_algo": headers.get("paypal-auth-algo", ""),
            "cert_url": headers.get("paypal-cert-url", ""),
            "transmission_id": headers.get("paypal-transmission-id", ""),
            "transmission_sig": headers.get("paypal-transmission-sig", ""),
            "transmission_time": headers.get("paypal-transmission-time", ""),
            "webhook_id": PAYPAL_WEBHOOK_ID,
            "webhook_event": json.loads(body),
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/v1/notifications/verify-webhook-signature",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("verification_status") == "SUCCESS"
    except Exception:
        pass
    return False


async def create_digital_order(purchase_id: int, product_name: str, amount_usd: float) -> tuple[str, str]:
    """Create a PayPal order for a digital product purchase.

    Returns (checkout_url, paypal_order_id).
    """
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        return f"https://mathrelaxing.store/checkout?purchase_id={purchase_id}", ""

    token = await _get_access_token()
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": str(purchase_id),
            "custom_id": f"purchase:{purchase_id}",
            "description": f"{product_name} — MathRelaxing Digital",
            "amount": {"currency_code": "USD", "value": f"{amount_usd:.2f}"},
        }],
        "payment_source": {
            "paypal": {
                "experience_context": {
                    "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
                    "brand_name": "MathRelaxing",
                    "locale": "en-US",
                    "landing_page": "LOGIN",
                    "user_action": "PAY_NOW",
                    "return_url": f"https://mathrelaxing.store/checkout/return?purchase_id={purchase_id}",
                    "cancel_url": "https://mathrelaxing.store/checkout",
                }
            }
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/v2/checkout/orders",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

    return _payer_action_url(data), data.get("id") or ""


async def create_lowpoly_order(job_id: int, token: str, amount_usd: float) -> tuple[str, str]:
    """Create a PayPal order for a Low Poly coloring page job.

    Returns (checkout_url, paypal_order_id).
    """
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        return f"https://mathrelaxing.store/lowpoly/result/{token}", ""

    access_token = await _get_access_token()
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": str(job_id),
            "custom_id": f"lowpoly:{job_id}",
            "description": "Color-by-Number Coloring Page — MathRelaxing",
            "amount": {"currency_code": "USD", "value": f"{amount_usd:.2f}"},
        }],
        "payment_source": {
            "paypal": {
                "experience_context": {
                    "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
                    "brand_name": "MathRelaxing",
                    "locale": "en-US",
                    "landing_page": "LOGIN",
                    "user_action": "PAY_NOW",
                    "return_url": f"https://mathrelaxing.store/api/lowpoly/paypal-return?job={token}",
                    "cancel_url": "https://mathrelaxing.store",
                }
            }
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/v2/checkout/orders",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

    return _payer_action_url(data), data.get("id") or ""
