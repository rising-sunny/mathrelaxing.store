"""Whop integration service."""
import hashlib
import hmac
import os

import httpx

WHOP_API_KEY    = os.getenv("WHOP_API_KEY", "")
WHOP_COMPANY_ID = os.getenv("WHOP_COMPANY_ID", "")
WHOP_WEBHOOK_SECRET = os.getenv("WHOP_WEBHOOK_SECRET", "")

_BASE_V2 = "https://api.whop.com/api/v2"


def _headers() -> dict:
    return {"Authorization": f"Bearer {WHOP_API_KEY}", "Content-Type": "application/json"}


def verify_webhook(payload: bytes, signature: str) -> bool:
    """Verify Whop webhook HMAC-SHA256 signature.
    Whop sends: whop-signature: sha256=<hex_digest>
    """
    if not WHOP_WEBHOOK_SECRET:
        return True  # skip in dev
    expected = hmac.new(
        WHOP_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    # Strip optional "sha256=" prefix from incoming signature
    incoming = signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, incoming)


async def get_plans() -> list:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{_BASE_V2}/plans", headers=_headers(), timeout=10)
        r.raise_for_status()
        return r.json().get("data", [])


async def create_plan(product_id: str, price_usd: float, name: str) -> dict:
    """Create a one-time payment plan on Whop for a given product_id."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE_V2}/plans",
            headers=_headers(),
            json={
                "product_id": product_id,
                "plan_type": "one_time",
                "initial_price": price_usd,
                "currency": "usd",
                "billing_period": 0,
                "internal_notes": name,
            },
            timeout=10,
        )
        r.raise_for_status()
        return r.json()


async def get_membership(membership_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE_V2}/memberships/{membership_id}",
            headers=_headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
