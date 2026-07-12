import base64
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse, urlencode

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from database import get_db
from models.product import DigitalProduct


router = APIRouter()
templates = Jinja2Templates(directory="/var/www/mathrelaxing.store/templates")

GRAPH_HOST = "https://graph.facebook.com"
OAUTH_HOST = "https://www.facebook.com"
DEFAULT_GRAPH_VERSION = "v19.0"
DEFAULT_SCOPES = "ads_management,ads_read,business_management,pages_show_list,pages_read_engagement,pages_manage_ads"
DEFAULT_TOKEN_FILE = "/var/www/mathrelaxing.store/.meta_ads_token.json"
DEFAULT_SYSTEM_TOKEN_FILE = "/var/www/mathrelaxing.store/.meta_system_user_token.json"
ADMIN_COOKIE_NAME = "mr_meta_ads_admin"
ADMIN_COOKIE_MAX_AGE = 7 * 24 * 60 * 60
ZERO_DECIMAL_CURRENCIES = {
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "JPY",
    "KMF",
    "KRW",
    "MGA",
    "PYG",
    "RWF",
    "UGX",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
}


class MetaInterest(BaseModel):
    id: str
    name: str


class MetaDraftRequest(BaseModel):
    product_slug: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=80)
    primary_text: str = Field(..., min_length=1, max_length=500)
    destination_url: str = Field(..., min_length=1)
    image_url: str = Field(..., min_length=1)
    daily_budget_amount: float | None = Field(None, ge=1, le=1000000)
    daily_budget_usd: float | None = Field(None, ge=1, le=1000)
    countries: list[str] = Field(default_factory=lambda: ["US"])
    interests: list[MetaInterest] = Field(default_factory=list)
    age_min: int = Field(default=25, ge=18, le=65)
    age_max: int = Field(default=65, ge=18, le=65)
    genders: list[int] = Field(default_factory=list)  # 1=male, 2=female, []=all
    locales: list[int] = Field(default_factory=list)  # Meta language IDs


class MetaCreatePausedCampaignRequest(MetaDraftRequest):
    confirm_paused_creation: bool = False


class MetaInterestSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=100)
    limit: int = Field(default=10, ge=1, le=25)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _base_url() -> str:
    return _env("PUBLIC_BASE_URL", "https://mathrelaxing.store").rstrip("/")


def _graph_version() -> str:
    return _env("META_GRAPH_VERSION", DEFAULT_GRAPH_VERSION).lstrip("/")


def _graph_base() -> str:
    return f"{GRAPH_HOST}/{_graph_version()}"


def _client_id() -> str:
    return _env("META_APP_ID")


def _client_secret() -> str:
    return _env("META_APP_SECRET")


def _ad_account_id() -> str:
    return _env("META_AD_ACCOUNT_ID").replace("act_", "")


def _page_id() -> str:
    return _env("META_PAGE_ID", "61583717482595")


def _pixel_id() -> str:
    return _env("META_PIXEL_ID")


def _redirect_uri() -> str:
    return _env("META_REDIRECT_URI", f"{_base_url()}/api/meta/oauth/callback")


def _token_file() -> str:
    return _env("META_TOKEN_FILE", DEFAULT_TOKEN_FILE)


def _system_token_file() -> str:
    return _env("META_SYSTEM_TOKEN_FILE", DEFAULT_SYSTEM_TOKEN_FILE)


def _scopes() -> str:
    return _env("META_SCOPES", DEFAULT_SCOPES)


def _scope_list() -> list[str]:
    return [scope for scope in _scopes().replace(" ", ",").split(",") if scope]


def _admin_username() -> str:
    return _env("META_ADS_ADMIN_USER") or _env("PINTEREST_ADMIN_USER", "mathrelaxing")


def _admin_password() -> str:
    return _env("META_ADS_ADMIN_PASSWORD") or _env("PINTEREST_ADMIN_PASSWORD")


def _state_secret() -> str:
    return _env("META_STATE_SECRET") or _env("PINTEREST_STATE_SECRET") or _admin_password() or _client_secret()


def _is_configured() -> bool:
    return bool(_client_id() and _client_secret() and _ad_account_id() and _page_id())


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


def _valid_admin_login(username: str, password: str) -> bool:
    expected_password = _admin_password()
    if not expected_password:
        raise HTTPException(status_code=503, detail="Meta Ads admin password is not configured")
    return hmac.compare_digest(username or "", _admin_username()) and hmac.compare_digest(password or "", expected_password)


def _require_admin_session(request: Request) -> None:
    if _valid_admin_cookie(request.cookies.get(ADMIN_COOKIE_NAME)):
        return
    raise HTTPException(status_code=401, detail="Meta Ads admin login required")


def _sign_state(ts: int, nonce: str) -> str:
    secret = _state_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="Meta OAuth state secret is not configured")
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


def _read_system_token() -> dict[str, Any] | None:
    path = _system_token_file()
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


def _token_preview(token: dict[str, Any] | None) -> dict[str, Any] | None:
    if not token:
        return None
    return {
        "saved_at": token.get("saved_at"),
        "expires_at": token.get("expires_at"),
        "token_type": token.get("token_type"),
    }


async def _graph_get(path: str, token: str | None = None, params: dict[str, Any] | None = None) -> Any:
    query = dict(params or {})
    if token:
        query["access_token"] = token
    url = path if path.startswith("http") else f"{_graph_base()}{path}"
    async with httpx.AsyncClient(timeout=40) as client:
        resp = await client.get(url, params=query)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


async def _graph_post(path: str, token: str | None = None, data: dict[str, Any] | None = None) -> Any:
    payload: dict[str, Any] = {}
    for key, value in dict(data or {}).items():
        if isinstance(value, (dict, list)):
            payload[key] = json.dumps(value, separators=(",", ":"))
        else:
            payload[key] = value
    if token:
        payload["access_token"] = token
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{_graph_base()}{path}", data=payload)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


async def _exchange_code(code: str) -> dict[str, Any]:
    if not _is_configured():
        raise HTTPException(status_code=503, detail="Meta OAuth is not configured")

    short_lived = await _graph_get(
        "/oauth/access_token",
        params={
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "redirect_uri": _redirect_uri(),
            "code": code,
        },
    )
    access_token = short_lived.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="Meta did not return an access token")

    long_lived = await _graph_get(
        "/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "fb_exchange_token": access_token,
        },
    )
    token = long_lived if long_lived.get("access_token") else short_lived
    _write_token(token)
    return token


async def _access_token() -> str:
    token = _read_token()
    if not token or not token.get("access_token"):
        raise HTTPException(status_code=401, detail="Meta is not connected")
    return token["access_token"]


async def _marketing_access_token() -> str:
    token = _read_token()
    if token and token.get("access_token"):
        return token["access_token"]
    system_token = _read_system_token()
    if system_token and system_token.get("access_token"):
        return system_token["access_token"]
    raise HTTPException(status_code=401, detail="Meta is not connected")


async def _safe_meta_call(label: str, call):
    try:
        data = await call()
        return {"ok": True, "data": data}
    except HTTPException as exc:
        return {"ok": False, "error": exc.detail, "status_code": exc.status_code}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def _debug_token(token: str) -> dict[str, Any]:
    app_token = f"{_client_id()}|{_client_secret()}"
    data = await _graph_get(
        "/debug_token",
        params={
            "input_token": token,
            "access_token": app_token,
        },
    )
    return data.get("data") or data


def _product_payload(product: DigitalProduct) -> dict[str, Any]:
    link = f"{_base_url()}/bundle/{product.slug}?utm_source=meta&utm_medium=paid_social&utm_campaign=meta_ads_manager"
    image_url = _product_image_url(product)
    description = (product.description or "").strip()
    if len(description) > 360:
        description = description[:357].rstrip() + "..."
    primary_text = f"{description}\n\nExplore mathematical art at MathRelaxing." if description else "Explore mathematical art at MathRelaxing."
    return {
        "slug": product.slug,
        "name": product.name,
        "product_type": product.product_type,
        "collection": product.collection,
        "price_usd": product.price_usd,
        "title": product.name[:80],
        "primary_text": primary_text,
        "destination_url": link,
        "image_url": image_url,
    }


def _product_image_url(product: DigitalProduct) -> str:
    for value in (product.thumbnail_url, product.cover_image):
        if not value:
            continue
        if value.startswith("https://"):
            return value
        if value.startswith("/"):
            return f"{_base_url()}{value}"

    static_root = "/var/www/mathrelaxing.store/static/previews"
    for filename in (
        f"{product.slug}_0.jpg",
        f"{product.slug}.jpg",
        f"{product.slug}_1.jpg",
        f"{product.slug}_0.png",
    ):
        if os.path.exists(os.path.join(static_root, filename)):
            return f"{_base_url()}/static/previews/{filename}"

    return f"{_base_url()}/api/render/preview?product={product.slug}&v=meta"


def _budget_amount(payload: MetaDraftRequest) -> float:
    if payload.daily_budget_amount is not None:
        return payload.daily_budget_amount
    if payload.daily_budget_usd is not None:
        return payload.daily_budget_usd
    return 5000.0


def _budget_to_meta_units(amount: float, currency: str) -> int:
    factor = 1 if currency.upper() in ZERO_DECIMAL_CURRENCIES else 100
    return max(1, int(round(amount * factor)))


def _validate_site_url(value: str, label: str) -> None:
    parsed = urlparse(value)
    base = urlparse(_base_url())
    base_host = (base.hostname or "mathrelaxing.store").lower()
    allowed_hosts = {base_host}
    if base_host.startswith("www."):
        allowed_hosts.add(base_host.removeprefix("www."))
    else:
        allowed_hosts.add(f"www.{base_host}")
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in allowed_hosts:
        raise HTTPException(status_code=400, detail=f"{label} must be an HTTPS MathRelaxing URL")


async def _ad_account_summary(token: str) -> dict[str, Any]:
    return await _graph_get(
        f"/act_{_ad_account_id()}",
        token,
        {"fields": "id,name,account_status,currency,timezone_name,disable_reason"},
    )


def _campaign_name(title: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return f"MR | {title[:46]} | {stamp} | PAUSED"


def _meta_plan(payload: MetaDraftRequest, currency: str | None = None, image_hash: str | None = None) -> dict[str, Any]:
    campaign_name = _campaign_name(payload.title)
    budget_amount = _budget_amount(payload)
    daily_budget = _budget_to_meta_units(budget_amount, currency) if currency else None
    countries = payload.countries or ["US"]
    link_data = {
        "link": payload.destination_url,
        "message": payload.primary_text,
        "name": payload.title,
        "call_to_action": {
            "type": "SHOP_NOW",
            "value": {"link": payload.destination_url},
        },
    }
    if image_hash:
        link_data["image_hash"] = image_hash
    else:
        link_data["picture"] = payload.image_url

    object_story_spec = {
        "page_id": _page_id(),
        "link_data": link_data,
    }

    targeting: dict[str, Any] = {
        "geo_locations": {"countries": countries},
        "age_min": payload.age_min,
        "age_max": payload.age_max,
        "targeting_automation": {"advantage_audience": 0},
    }
    if payload.genders:
        targeting["genders"] = payload.genders
    if payload.locales:
        targeting["locales"] = payload.locales
    if payload.interests:
        targeting["flexible_spec"] = [
            {"interests": [{"id": i.id, "name": i.name} for i in payload.interests]}
        ]

    return {
        "campaign": {
            "name": campaign_name,
            "objective": "OUTCOME_SALES",
            "status": "PAUSED",
            "special_ad_categories": [],
            "buying_type": "AUCTION",
            "is_adset_budget_sharing_enabled": False,
            "dsa_beneficiary": "MathRelaxing",
            "dsa_payor": "MathRelaxing",
        },
        "ad_set": {
            "name": f"{campaign_name} | Broad",
            "status": "PAUSED",
            "daily_budget": daily_budget or "computed_at_create_time",
            "daily_budget_amount": budget_amount,
            "currency": currency or "account_currency",
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "OFFSITE_CONVERSIONS",
            "destination_type": "WEBSITE",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "dsa_beneficiary": "MathRelaxing",
            "dsa_payor": "MathRelaxing",
            "promoted_object": {
                "pixel_id": _pixel_id(),
                "custom_event_type": "PURCHASE",
            },
            "targeting": targeting,
        },
        "creative": {
            "name": f"{payload.title[:46]} | Creative",
            "object_story_spec": object_story_spec,
        },
        "ad": {
            "name": f"{payload.title[:48]} | Ad",
            "status": "PAUSED",
        },
    }


async def _search_meta_interests(token: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
    data = await _graph_get(
        "/search",
        token,
        {"type": "adinterest", "q": query, "limit": limit, "fields": "id,name,audience_size_lower_bound,audience_size_upper_bound,path,topic"},
    )
    return data.get("data") or []


async def _upload_ad_image(token: str, image_url: str, name: str) -> str:
    async with httpx.AsyncClient(timeout=90) as client:
        image_resp = await client.get(image_url)
        if image_resp.status_code >= 400:
            raise HTTPException(status_code=400, detail=f"Image URL could not be downloaded: {image_resp.text}")
        encoded = base64.b64encode(image_resp.content).decode("ascii")
        upload_resp = await client.post(
            f"{_graph_base()}/act_{_ad_account_id()}/adimages",
            data={
                "access_token": token,
                "bytes": encoded,
                "name": name,
            },
        )
    if upload_resp.status_code >= 400:
        raise HTTPException(status_code=upload_resp.status_code, detail=upload_resp.text)
    images = upload_resp.json().get("images") or {}
    first = next(iter(images.values()), {})
    image_hash = first.get("hash")
    if not image_hash:
        raise HTTPException(status_code=502, detail="Meta did not return an image hash")
    return image_hash


@router.get("/admin/meta-ads")
async def meta_ads_admin(request: Request):
    if not _valid_admin_cookie(request.cookies.get(ADMIN_COOKIE_NAME)):
        return RedirectResponse("/admin/meta-ads/login", status_code=303)
    return templates.TemplateResponse("admin_meta_ads.html", {"request": request})


@router.get("/admin/meta-ads/login")
async def meta_ads_login_page(request: Request):
    if _valid_admin_cookie(request.cookies.get(ADMIN_COOKIE_NAME)):
        return RedirectResponse("/admin/meta-ads", status_code=303)
    return templates.TemplateResponse("admin_meta_ads_login.html", {"request": request, "error": ""})


@router.post("/admin/meta-ads/login")
async def meta_ads_login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if not _valid_admin_login(username, password):
        return templates.TemplateResponse(
            "admin_meta_ads_login.html",
            {"request": request, "error": "Invalid username or password."},
            status_code=401,
        )
    response = RedirectResponse("/admin/meta-ads", status_code=303)
    response.set_cookie(
        ADMIN_COOKIE_NAME,
        _make_admin_cookie(username),
        max_age=ADMIN_COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


@router.get("/admin/meta-ads/logout")
async def meta_ads_logout():
    response = RedirectResponse("/admin/meta-ads/login", status_code=303)
    response.delete_cookie(ADMIN_COOKIE_NAME)
    return response


@router.get("/api/meta/oauth/start")
async def meta_oauth_start(request: Request):
    _require_admin_session(request)
    if not _is_configured():
        raise HTTPException(status_code=503, detail="Meta OAuth is not configured")
    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": ",".join(_scope_list()),
        "state": _make_state(),
    }
    return RedirectResponse(f"{OAUTH_HOST}/{_graph_version()}/dialog/oauth?{urlencode(params)}")


@router.get("/api/meta/oauth/callback")
async def meta_oauth_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        raise HTTPException(status_code=400, detail=error)
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing Meta OAuth code or state")
    _validate_state(state)
    await _exchange_code(code)
    return RedirectResponse("/admin/meta-ads?connected=1")


@router.get("/api/meta/status")
async def meta_status(request: Request):
    _require_admin_session(request)
    token = _read_token()
    connected = bool(token and token.get("access_token"))
    diagnostics: dict[str, Any] = {}

    if connected:
        access_token = token["access_token"]
        debug = await _safe_meta_call("debug_token", lambda: _debug_token(access_token))
        connected = bool(debug.get("ok") and debug.get("data", {}).get("is_valid"))
        diagnostics["token"] = debug
        diagnostics["me"] = await _safe_meta_call("me", lambda: _graph_get("/me", access_token, {"fields": "id,name"}))
        diagnostics["pages"] = await _safe_meta_call(
            "pages",
            lambda: _graph_get("/me/accounts", access_token, {"fields": "id,name,category,tasks", "limit": 200}),
        )
        diagnostics["page"] = await _safe_meta_call(
            "page",
            lambda: _graph_get(
                f"/{_page_id()}",
                access_token,
                {"fields": "id,name,category,link,picture.type(normal),instagram_business_account{id,username}"},
            ),
        )
        diagnostics["ad_account"] = await _safe_meta_call(
            "ad_account",
            lambda: _graph_get(
                f"/act_{_ad_account_id()}",
                access_token,
                {"fields": "id,name,account_status,currency,timezone_name,business{id,name},disable_reason,amount_spent,balance"},
            ),
        )
        diagnostics["pixels"] = await _safe_meta_call(
            "pixels",
            lambda: _graph_get(
                f"/act_{_ad_account_id()}/adspixels",
                access_token,
                {"fields": "id,name,last_fired_time", "limit": 100},
            ),
        )
        diagnostics["campaigns"] = await _safe_meta_call(
            "campaigns",
            lambda: _graph_get(
                f"/act_{_ad_account_id()}/campaigns",
                access_token,
                {"fields": "id,name,status,effective_status,objective,created_time", "limit": 10},
            ),
        )

    return {
        "configured": _is_configured(),
        "connected": connected,
        "graph_version": _graph_version(),
        "redirect_uri": _redirect_uri(),
        "scopes": _scope_list(),
        "ad_account_id": _ad_account_id(),
        "page_id": _page_id(),
        "pixel_id": _pixel_id(),
        "token": _token_preview(token),
        "diagnostics": diagnostics,
    }


@router.get("/api/meta/products")
async def meta_products(request: Request, db=Depends(get_db)):
    _require_admin_session(request)
    products = (
        db.query(DigitalProduct)
        .filter(DigitalProduct.active == True)
        .order_by(DigitalProduct.created_at.desc())
        .all()
    )
    return {"items": [_product_payload(product) for product in products]}


@router.post("/api/meta/search-interests")
async def meta_search_interests(payload: MetaInterestSearchRequest, request: Request):
    _require_admin_session(request)
    token = await _marketing_access_token()
    results = await _search_meta_interests(token, payload.query, payload.limit)
    return {"ok": True, "query": payload.query, "interests": results}


@router.post("/api/meta/ad-draft")
async def meta_ad_draft(payload: MetaDraftRequest, request: Request):
    _require_admin_session(request)
    token = _read_token()
    currency = None
    if token and token.get("access_token"):
        account = await _safe_meta_call("ad_account", lambda: _ad_account_summary(token["access_token"]))
        if account.get("ok"):
            currency = account.get("data", {}).get("currency")
    plan = _meta_plan(payload, currency)
    return {
        "ok": True,
        "mode": "draft_only",
        "note": "No campaign was created. Use the paused creation endpoint only after reviewing this payload.",
        **plan,
    }


@router.post("/api/meta/create-paused-campaign")
async def meta_create_paused_campaign(payload: MetaCreatePausedCampaignRequest, request: Request):
    _require_admin_session(request)
    if not payload.confirm_paused_creation:
        raise HTTPException(status_code=400, detail="Paused campaign creation must be explicitly confirmed")
    if not _is_configured():
        raise HTTPException(status_code=503, detail="Meta Ads is not configured")

    _validate_site_url(payload.destination_url, "Destination URL")
    _validate_site_url(payload.image_url, "Image URL")

    token = await _marketing_access_token()
    token_debug = await _debug_token(token)
    if not token_debug.get("is_valid"):
        raise HTTPException(status_code=401, detail="Meta token is not valid")

    account = await _ad_account_summary(token)
    if account.get("account_status") != 1:
        status_labels = {2: "DISABLED", 3: "UNSETTLED (payment issue)", 7: "PENDING_RISK_REVIEW", 9: "IN_GRACE_PERIOD", 100: "PENDING_CLOSURE", 101: "CLOSED"}
        label = status_labels.get(account.get("account_status"), f"status={account.get('account_status')}")
        raise HTTPException(status_code=400, detail=f"Ad account is not active: {label}. Resolve billing in Meta Business Suite before creating ads.")

    currency = account.get("currency") or "USD"
    image_hash = await _upload_ad_image(token, payload.image_url, f"mr-{payload.product_slug}-{int(time.time())}.jpg")
    plan = _meta_plan(payload, currency, image_hash=image_hash)
    ad_set_payload = dict(plan["ad_set"])
    ad_set_payload["daily_budget"] = _budget_to_meta_units(_budget_amount(payload), currency)
    ad_set_payload.pop("daily_budget_amount", None)
    ad_set_payload.pop("currency", None)

    created: list[dict[str, str]] = []
    try:
        creative = await _graph_post(f"/act_{_ad_account_id()}/adcreatives", token, plan["creative"])
        creative_id = creative["id"]
        created.append({"type": "creative", "id": creative_id})

        campaign = await _graph_post(f"/act_{_ad_account_id()}/campaigns", token, plan["campaign"])
        campaign_id = campaign["id"]
        created.append({"type": "campaign", "id": campaign_id})

        ad_set_payload["campaign_id"] = campaign_id
        ad_set = await _graph_post(f"/act_{_ad_account_id()}/adsets", token, ad_set_payload)
        ad_set_id = ad_set["id"]
        created.append({"type": "ad_set", "id": ad_set_id})

        ad = await _graph_post(
            f"/act_{_ad_account_id()}/ads",
            token,
            {
                **plan["ad"],
                "adset_id": ad_set_id,
                "creative": {"creative_id": creative_id},
            },
        )
        created.append({"type": "ad", "id": ad["id"]})
    except HTTPException as exc:
        rolled_back: list[dict[str, str]] = []
        for item in reversed(created):
            if item["type"] not in {"campaign", "ad_set", "ad"}:
                continue
            try:
                await _graph_post(f"/{item['id']}", token, {"status": "DELETED"})
                rolled_back.append(item)
            except Exception:
                pass
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": exc.detail,
                "created_before_error": created,
                "rolled_back": rolled_back,
                "note": "Any created delivery objects were requested in PAUSED status and then marked DELETED when possible.",
            },
        )

    return {
        "ok": True,
        "mode": "created_paused",
        "note": "Created in Meta with campaign, ad set and ad all requested as PAUSED. Review in Ads Manager before activating.",
        "ad_account": account,
        "currency": currency,
        "daily_budget_amount": _budget_amount(payload),
        "daily_budget_meta_units": ad_set_payload["daily_budget"],
        "created": created,
    }
