"""
Minimal read-only Etsy Open API v3 client for the Pinterest auto-pin job.

It fetches the shop's active listings (title, description, url) and, on demand,
their images, so the pinning job can publish real Etsy listings instead of
on-site products.

Credentials come from the environment + a token file (same shape as the one
produced by the Etsy tooling repo's auth.py):

  ETSY_CLIENT_ID       app keystring (x-api-key). Falls back to token's "api_key".
  ETSY_SHARED_SECRET   app shared secret (only needed if we ever re-auth; unused
                       for refresh, which requires just the client_id).
  ETSY_TOKEN_FILE      JSON: {access_token, refresh_token, expires_in, user_id, ...}
  ETSY_SHOP_ID         optional; skips the shop lookup when set.

The access token is refreshed in-place when it is close to expiring.
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger("etsy_client")

API_BASE = os.getenv("ETSY_API_BASE", "https://api.etsy.com/v3/application").rstrip("/")
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"

_SHOP_ID_CACHE: Optional[str] = None


def _token_file() -> str:
    return os.getenv("ETSY_TOKEN_FILE", "/var/www/mathrelaxing.store/.etsy_token.json").strip()


def _read_token() -> Optional[dict]:
    path = _token_file()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        logger.exception("etsy token read failed")
        return None


def _client_id(token: Optional[dict] = None) -> str:
    """Bare app keystring (client_id), used for the OAuth refresh call."""
    env = os.getenv("ETSY_CLIENT_ID", "").strip()
    if env:
        return env
    token = token if token is not None else (_read_token() or {})
    api_key = str(token.get("api_key") or "").strip()
    return api_key.split(":", 1)[0]  # tolerate a "keystring:secret" api_key


def _x_api_key(token: Optional[dict] = None) -> str:
    """Value for the x-api-key header. Etsy's standard is the bare keystring;
    some app setups use 'keystring:shared_secret'. Fully overridable via env:
      ETSY_API_KEY        -> used verbatim (highest priority)
      ETSY_CLIENT_ID (+ ETSY_SHARED_SECRET) -> 'id' or 'id:secret'
    Falls back to the token file's stored 'api_key' (already the right form)."""
    explicit = os.getenv("ETSY_API_KEY", "").strip()
    if explicit:
        return explicit
    token = token if token is not None else (_read_token() or {})
    cid = os.getenv("ETSY_CLIENT_ID", "").strip()
    secret = os.getenv("ETSY_SHARED_SECRET", "").strip()
    if cid:
        return f"{cid}:{secret}" if secret else cid
    return str(token.get("api_key") or "").strip()


def is_configured() -> bool:
    token = _read_token()
    return bool(token and token.get("access_token") and _x_api_key(token))


def _write_token(data: dict) -> None:
    path = _token_file()
    data = dict(data)
    data["saved_at"] = datetime.now(timezone.utc).isoformat()
    if data.get("expires_in"):
        data["expires_at"] = int(time.time()) + int(data["expires_in"])
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


async def _refresh(token: dict) -> dict:
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("Etsy refresh_token missing")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": _client_id(token),
                "refresh_token": refresh_token,
            },
        )
    if r.status_code >= 400:
        raise RuntimeError(f"Etsy token refresh HTTP {r.status_code}: {r.text[:300]}")
    merged = dict(token)
    merged.update(r.json())  # new access_token (+ possibly rotated refresh_token)
    _write_token(merged)
    return merged


async def _access_token() -> str:
    token = _read_token()
    if not token or not token.get("access_token"):
        raise RuntimeError("Etsy not connected (missing token file)")
    expires_at = int(token.get("expires_at") or 0)
    if expires_at and expires_at - int(time.time()) < 300:  # refresh 5 min early
        token = await _refresh(token)
    return token["access_token"]


async def _headers() -> dict:
    token = _read_token() or {}
    access = await _access_token()
    return {"x-api-key": _x_api_key(token), "Authorization": f"Bearer {access}"}


def _user_id() -> Optional[str]:
    token = _read_token() or {}
    uid = token.get("user_id")
    if uid:
        return str(uid)
    # Etsy access tokens are "<user_id>.<random>"
    head = str(token.get("access_token") or "").split(".", 1)[0]
    return head if head.isdigit() else None


async def get_shop_id() -> str:
    global _SHOP_ID_CACHE
    env_id = os.getenv("ETSY_SHOP_ID", "").strip()
    if env_id:
        return env_id
    if _SHOP_ID_CACHE:
        return _SHOP_ID_CACHE

    headers = await _headers()
    async with httpx.AsyncClient(timeout=30) as client:
        user_id = _user_id()
        if not user_id:
            me = await client.get(f"{API_BASE}/users/me", headers=headers)
            me.raise_for_status()
            user_id = str(me.json().get("user_id"))
        r = await client.get(f"{API_BASE}/users/{user_id}/shops", headers=headers)
    r.raise_for_status()
    body = r.json() or {}
    shop_id = body.get("shop_id")
    if not shop_id:
        results = body.get("results") or []
        shop_id = results[0].get("shop_id") if results else None
    if not shop_id:
        raise RuntimeError(f"Could not resolve Etsy shop_id: {str(body)[:200]}")
    _SHOP_ID_CACHE = str(shop_id)
    return _SHOP_ID_CACHE


async def list_active_listings(limit_total: int = 250) -> list[dict]:
    """Return active listings for the shop. Each item includes listing_id,
    title, description, url and (best effort) an 'images' list."""
    headers = await _headers()
    shop_id = await get_shop_id()
    out: list[dict] = []
    offset = 0
    page = 100
    async with httpx.AsyncClient(timeout=45) as client:
        while len(out) < limit_total:
            params = {"limit": page, "offset": offset, "includes": "Images"}
            r = await client.get(
                f"{API_BASE}/shops/{shop_id}/listings/active",
                headers=headers,
                params=params,
            )
            if r.status_code >= 400:
                raise RuntimeError(f"Etsy active listings HTTP {r.status_code}: {r.text[:300]}")
            body = r.json() or {}
            results = body.get("results") or []
            out.extend(results)
            count = int(body.get("count") or 0)
            offset += page
            if not results or offset >= count:
                break
    return out[:limit_total]


async def get_listing_images(listing_id: Any) -> list[dict]:
    headers = await _headers()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{API_BASE}/listings/{listing_id}/images", headers=headers)
    if r.status_code >= 400:
        raise RuntimeError(f"Etsy listing images HTTP {r.status_code}: {r.text[:300]}")
    return (r.json() or {}).get("results") or []


def _pick_image_url(images: list[dict]) -> Optional[str]:
    if not images:
        return None
    first = images[0]
    for key in ("url_fullxfull", "url_570xN", "url_680x540", "url_300x300", "url_170x135"):
        if first.get(key):
            return first[key]
    return None


async def primary_image_url(listing: dict) -> Optional[str]:
    """Best image URL for a listing. Uses images embedded via includes=Images
    when present, otherwise fetches them."""
    url = _pick_image_url(listing.get("images") or [])
    if url:
        return url
    lid = listing.get("listing_id")
    if not lid:
        return None
    try:
        return _pick_image_url(await get_listing_images(lid))
    except Exception as exc:
        logger.warning("etsy image fetch failed for listing %s: %s", lid, exc)
        return None
