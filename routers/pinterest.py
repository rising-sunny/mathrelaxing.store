import base64
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from database import get_db
from models.product import DigitalProduct


router = APIRouter()
templates = Jinja2Templates(directory="/var/www/mathrelaxing.store/templates")
security = HTTPBasic(auto_error=False)

DEFAULT_PINTEREST_API_BASE = "https://api.pinterest.com/v5"
PINTEREST_OAUTH_URL = "https://www.pinterest.com/oauth/"
DEFAULT_PINTEREST_SCOPES = "boards:read,boards:write,pins:read,pins:write,user_accounts:read,user_accounts:write"
DEFAULT_TOKEN_FILE = "/var/www/mathrelaxing.store/.pinterest_token.json"
ADMIN_COOKIE_NAME = "mr_pin_admin"
ADMIN_COOKIE_MAX_AGE = 7 * 24 * 60 * 60


class PinCreateRequest(BaseModel):
    board_id: str = Field(..., min_length=1)
    product_slug: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=800)
    link: str = Field(..., min_length=1)
    image_url: str = Field(..., min_length=1)


class BoardCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=180)
    description: str = Field("", max_length=500)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _base_url() -> str:
    return _env("PUBLIC_BASE_URL", "https://mathrelaxing.store").rstrip("/")


def _api_base() -> str:
    return _env("PINTEREST_API_BASE", DEFAULT_PINTEREST_API_BASE).rstrip("/")


def _api_environment() -> str:
    return "sandbox" if "api-sandbox." in _api_base() else "production"


def _scopes() -> str:
    return _env("PINTEREST_SCOPES", DEFAULT_PINTEREST_SCOPES)


def _scope_list() -> list[str]:
    return [scope for scope in _scopes().replace(" ", ",").split(",") if scope]


def _client_id() -> str:
    return _env("PINTEREST_CLIENT_ID")


def _client_secret() -> str:
    return _env("PINTEREST_CLIENT_SECRET")


def _redirect_uri() -> str:
    return _env("PINTEREST_REDIRECT_URI", f"{_base_url()}/api/pinterest/oauth/callback")


def _token_file() -> str:
    return _env("PINTEREST_TOKEN_FILE", DEFAULT_TOKEN_FILE)


def _admin_username() -> str:
    return _env("PINTEREST_ADMIN_USER", "mathrelaxing")


def _admin_password() -> str:
    return _env("PINTEREST_ADMIN_PASSWORD")


def _state_secret() -> str:
    return _env("PINTEREST_STATE_SECRET") or _admin_password() or _client_secret()


def _is_configured() -> bool:
    return bool(_client_id() and _client_secret() and _redirect_uri())


def _require_admin(credentials: HTTPBasicCredentials | None = Depends(security)) -> None:
    if _valid_basic_credentials(credentials):
        return
    raise HTTPException(
        status_code=401,
        detail="Pinterest admin credentials required",
        headers={"WWW-Authenticate": "Basic"},
    )


def _valid_basic_credentials(credentials: HTTPBasicCredentials | None) -> bool:
    expected_password = _admin_password()
    if not expected_password:
        raise HTTPException(status_code=503, detail="Pinterest admin password is not configured")
    if not credentials:
        return False
    user_ok = hmac.compare_digest(credentials.username or "", _admin_username())
    pass_ok = hmac.compare_digest(credentials.password or "", expected_password)
    return user_ok and pass_ok


def _admin_cookie_signature(ts: int, username: str) -> str:
    secret = _state_secret()
    message = f"{ts}.{username}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), message, sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _make_admin_cookie(username: str) -> str:
    ts = int(time.time())
    return f"{ts}.{username}.{_admin_cookie_signature(ts, username)}"


def _valid_admin_cookie(value: str | None) -> bool:
    if not value:
        return False
    try:
        ts_raw, username, supplied = value.split(".", 2)
        ts = int(ts_raw)
    except Exception:
        return False
    if username != _admin_username():
        return False
    if abs(int(time.time()) - ts) > ADMIN_COOKIE_MAX_AGE:
        return False
    expected = _admin_cookie_signature(ts, username)
    return hmac.compare_digest(supplied, expected)


def _request_is_admin(request: Request, credentials: HTTPBasicCredentials | None = None) -> bool:
    return _valid_admin_cookie(request.cookies.get(ADMIN_COOKIE_NAME)) or _valid_basic_credentials(credentials)


def _require_admin_session(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
) -> None:
    if _request_is_admin(request, credentials):
        return
    raise HTTPException(
        status_code=401,
        detail="Pinterest admin credentials required",
        headers={"WWW-Authenticate": "Basic"},
    )


def _basic_auth_header() -> str:
    raw = f"{_client_id()}:{_client_secret()}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _sign_state(ts: int, nonce: str) -> str:
    secret = _state_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="Pinterest state secret is not configured")
    message = f"{ts}.{nonce}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), message, sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _make_state() -> str:
    ts = int(time.time())
    nonce = secrets.token_urlsafe(18)
    return f"{ts}.{nonce}.{_sign_state(ts, nonce)}"


def _validate_state(state: str) -> None:
    try:
        ts_raw, nonce, supplied = state.split(".", 2)
        ts = int(ts_raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    if abs(int(time.time()) - ts) > 20 * 60:
        raise HTTPException(status_code=400, detail="Expired OAuth state")
    expected = _sign_state(ts, nonce)
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=400, detail="Invalid OAuth state signature")


def _read_token() -> dict[str, Any] | None:
    path = _token_file()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_token(data: dict[str, Any]) -> None:
    path = _token_file()
    data = dict(data)
    data["saved_at"] = datetime.now(timezone.utc).isoformat()
    if data.get("expires_in"):
        data["expires_at"] = int(time.time()) + int(data["expires_in"])
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, path)
    os.chmod(path, 0o600)


async def _exchange_code(code: str) -> dict[str, Any]:
    if not _is_configured():
        raise HTTPException(status_code=503, detail="Pinterest OAuth is not configured")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_api_base()}/oauth/token",
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": _redirect_uri(),
            },
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    token = resp.json()
    _write_token(token)
    return token


async def _refresh_token(token: dict[str, Any]) -> dict[str, Any]:
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Pinterest refresh token is missing")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_api_base()}/oauth/token",
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": _scopes(),
            },
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    new_token = resp.json()
    _write_token(new_token)
    return new_token


async def _access_token() -> str:
    token = _read_token()
    if not token or not token.get("access_token"):
        raise HTTPException(status_code=401, detail="Pinterest is not connected")
    expires_at = int(token.get("expires_at") or 0)
    if expires_at and expires_at - int(time.time()) < 24 * 60 * 60:
        token = await _refresh_token(token)
    return token["access_token"]


async def _pinterest_request(method: str, path: str, **kwargs: Any) -> Any:
    access_token = await _access_token()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.request(
            method,
            f"{_api_base()}{path}",
            headers={"Authorization": f"Bearer {access_token}"},
            **kwargs,
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    if not resp.content:
        return {}
    return resp.json()


def _product_payload(product: DigitalProduct) -> dict[str, Any]:
    link = f"{_base_url()}/bundle/{product.slug}?utm_source=pinterest&utm_medium=organic&utm_campaign=pin_manager"
    image_url = f"{_base_url()}/api/render/preview?product={product.slug}&v=pinterest"
    description = (product.description or "").strip()
    if len(description) > 440:
        description = description[:437].rstrip() + "..."
    cta = "Explore the full mathematical art pack at MathRelaxing."
    return {
        "slug": product.slug,
        "name": product.name,
        "product_type": product.product_type,
        "collection": product.collection,
        "price_usd": product.price_usd,
        "title": product.name[:100],
        "description": f"{description}\n\n{cta}" if description else cta,
        "link": link,
        "image_url": image_url,
    }


@router.get("/admin/pinterest")
async def pinterest_admin(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
):
    if not _request_is_admin(request, credentials):
        return RedirectResponse("/admin/pinterest/login", status_code=303)
    return templates.TemplateResponse("admin_pinterest.html", {"request": request})


@router.get("/admin/pinterest/login")
async def pinterest_login_page(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
):
    if _request_is_admin(request, credentials):
        return RedirectResponse("/admin/pinterest", status_code=303)
    return templates.TemplateResponse(
        "admin_pinterest_login.html",
        {"request": request, "error": ""},
    )


@router.post("/admin/pinterest/login")
async def pinterest_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    credentials = HTTPBasicCredentials(username=username, password=password)
    if not _valid_basic_credentials(credentials):
        return templates.TemplateResponse(
            "admin_pinterest_login.html",
            {"request": request, "error": "Invalid username or password."},
            status_code=401,
        )
    response = RedirectResponse("/admin/pinterest", status_code=303)
    response.set_cookie(
        ADMIN_COOKIE_NAME,
        _make_admin_cookie(username),
        max_age=ADMIN_COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


@router.get("/admin/pinterest/logout")
async def pinterest_logout():
    response = RedirectResponse("/admin/pinterest/login", status_code=303)
    response.delete_cookie(ADMIN_COOKIE_NAME)
    return response


@router.get("/api/pinterest/oauth/start")
async def pinterest_oauth_start(_: None = Depends(_require_admin_session)):
    if not _is_configured():
        raise HTTPException(status_code=503, detail="Pinterest OAuth is not configured")
    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": _scopes(),
        "state": _make_state(),
    }
    return RedirectResponse(f"{PINTEREST_OAUTH_URL}?{urlencode(params)}")


@router.get("/api/pinterest/oauth/callback")
async def pinterest_oauth_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        raise HTTPException(status_code=400, detail=error)
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing Pinterest OAuth code or state")
    _validate_state(state)
    await _exchange_code(code)
    return RedirectResponse("/admin/pinterest?connected=1")


@router.get("/api/pinterest/status")
async def pinterest_status(_: None = Depends(_require_admin_session)):
    token = _read_token()
    connected = bool(token and token.get("access_token"))
    account = None
    if connected:
        try:
            account = await _pinterest_request("GET", "/user_account")
        except HTTPException as exc:
            account = {"error": exc.detail}
    return {
        "configured": _is_configured(),
        "connected": connected,
        "redirect_uri": _redirect_uri(),
        "api_base": _api_base(),
        "environment": _api_environment(),
        "scopes": _scope_list(),
        "expires_at": token.get("expires_at") if token else None,
        "account": account,
    }


@router.get("/api/pinterest/products")
async def pinterest_products(_: None = Depends(_require_admin_session), db=Depends(get_db)):
    products = (
        db.query(DigitalProduct)
        .filter(DigitalProduct.active == True)
        .order_by(DigitalProduct.created_at.desc())
        .all()
    )
    return {"items": [_product_payload(product) for product in products]}


@router.get("/api/pinterest/boards")
async def pinterest_boards(_: None = Depends(_require_admin_session)):
    data = await _pinterest_request("GET", "/boards", params={"page_size": 100})
    return data


@router.post("/api/pinterest/boards")
async def pinterest_create_board(payload: BoardCreateRequest, _: None = Depends(_require_admin_session)):
    body = {"name": payload.name}
    if payload.description.strip():
        body["description"] = payload.description.strip()
    created = await _pinterest_request("POST", "/boards", json=body)
    return {"ok": True, "board": created}


@router.post("/api/pinterest/pins")
async def pinterest_create_pin(payload: PinCreateRequest, _: None = Depends(_require_admin_session)):
    body = {
        "board_id": payload.board_id,
        "title": payload.title,
        "description": payload.description,
        "link": payload.link,
        "media_source": {
            "source_type": "image_url",
            "url": payload.image_url,
            "is_standard": True,
        },
    }
    created = await _pinterest_request("POST", "/pins", json=body)
    return {"ok": True, "pin": created}


@router.post("/api/pinterest/auto-pin/run")
async def pinterest_auto_pin_run(_: None = Depends(_require_admin_session)):
    """Trigger one auto-pinning cycle on demand. Creates up to MAX_PINS_PER_CYCLE pins."""
    from services import pinterest_jobs
    summary = await pinterest_jobs.run_auto_pin_cycle()
    return {"ok": True, "summary": summary}


@router.get("/api/pinterest/auto-pin/analytics")
async def pinterest_auto_pin_analytics(_: None = Depends(_require_admin_session), days: int = 30):
    """Fetch analytics for every pin we created. Cached 10 min server-side."""
    from services import pinterest_jobs
    days = max(1, min(days, 90))  # Pinterest analytics window cap
    return await pinterest_jobs.collect_all_pin_analytics(days=days)


@router.get("/admin/pinterest/analytics", response_class=HTMLResponse)
async def pinterest_analytics_page(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
):
    if not _request_is_admin(request, credentials):
        return RedirectResponse("/admin/pinterest/login", status_code=303)
    return templates.TemplateResponse("admin_pinterest_analytics.html", {"request": request})


@router.post("/api/pinterest/claim/start")
async def pinterest_claim_start(_: None = Depends(_require_admin_session)):
    """Step 1: ask Pinterest for a verification code and persist it."""
    from services import pinterest_claim
    try:
        token = await _access_token()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No token: {exc}")
    try:
        state = await pinterest_claim.request_verification_code(token)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"ok": True, "state": state}


@router.post("/api/pinterest/claim/verify")
async def pinterest_claim_verify(_: None = Depends(_require_admin_session)):
    """Step 2: ask Pinterest to fetch our home and confirm the metatag."""
    from services import pinterest_claim
    try:
        token = await _access_token()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No token: {exc}")
    state = await pinterest_claim.submit_verification(token)
    return {"ok": state.get("status") not in ("failed",), "state": state}


@router.get("/api/pinterest/claim/status")
async def pinterest_claim_status(_: None = Depends(_require_admin_session)):
    from services import pinterest_claim
    state = pinterest_claim.read_claim()
    listing = None
    try:
        token = await _access_token()
        listing = await pinterest_claim.list_websites(token)
    except Exception as exc:
        listing = {"error": str(exc)}
    return {"local_state": state, "pinterest_says": listing}


@router.get("/api/pinterest/auto-pin/status")
async def pinterest_auto_pin_status(_: None = Depends(_require_admin_session), db=Depends(get_db)):
    """Return stats about auto-pinning: total pins, recent pins, products covered."""
    from datetime import timedelta
    from sqlalchemy import func
    from models.pinterest_pin import PinterestPin

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    totals = {
        "active": db.query(func.count(PinterestPin.id)).filter(PinterestPin.status == "active").scalar() or 0,
        "failed": db.query(func.count(PinterestPin.id)).filter(PinterestPin.status == "failed").scalar() or 0,
        "last_24h": db.query(func.count(PinterestPin.id)).filter(
            PinterestPin.created_at >= last_24h, PinterestPin.status == "active").scalar() or 0,
        "last_7d": db.query(func.count(PinterestPin.id)).filter(
            PinterestPin.created_at >= last_7d, PinterestPin.status == "active").scalar() or 0,
        "products_covered": db.query(func.count(func.distinct(PinterestPin.product_slug))).filter(
            PinterestPin.status == "active").scalar() or 0,
    }
    # Coverage is measured against the Etsy shop — that is what the job pins.
    # (It used to count on-site DigitalProduct rows, which made the ratio meaningless.)
    from services import etsy_client, pinterest_jobs
    try:
        totals["total_listings"] = await etsy_client.count_active_listings()
    except Exception as exc:
        totals["total_listings"] = None
        totals["total_listings_error"] = str(exc)[:200]

    recent = db.query(PinterestPin).order_by(PinterestPin.created_at.desc()).limit(20).all()
    return {
        "totals": totals,
        "config": {
            "pins_per_cycle": pinterest_jobs.MAX_PINS_PER_CYCLE,
            "cycle_hours": pinterest_jobs.PIN_CYCLE_INTERVAL_HOURS,
            "repin_cooldown_days": pinterest_jobs.REPIN_COOLDOWN_DAYS,
            "render_pins": pinterest_jobs.RENDER_PINS,
            "default_board_id": os.getenv("PINTEREST_DEFAULT_BOARD_ID", "") or None,
        },
        "recent": [{
            "id": p.id, "pin_id": p.pin_id, "product_slug": p.product_slug,
            "variant_idx": p.variant_idx, "status": p.status,
            "error": (p.error[:200] if p.error else None),
            "created_at": p.created_at.isoformat() + "Z",
        } for p in recent],
    }
