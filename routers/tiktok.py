import base64
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field


router = APIRouter()
templates = Jinja2Templates(directory="/var/www/mathrelaxing.store/templates")
security = HTTPBasic(auto_error=False)

TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_OPEN_API = "https://open.tiktokapis.com"
DEFAULT_SCOPES = "user.info.basic,video.upload,video.publish"
DEFAULT_TOKEN_FILE = "/var/www/mathrelaxing.store/.tiktok_token.json"
DEFAULT_LAST_UPLOAD_FILE = "/var/www/mathrelaxing.store/.tiktok_last_upload.json"
ADMIN_COOKIE_NAME = "mr_tiktok_admin"
ADMIN_COOKIE_MAX_AGE = 7 * 24 * 60 * 60


class TikTokUploadDraftRequest(BaseModel):
    video_url: str = Field(..., min_length=1)
    caption: str = Field("", max_length=2200)


class TikTokDirectPostRequest(BaseModel):
    # Compliant Direct Post payload — every field is chosen by the user in the UI
    # per TikTok's Content Sharing Guidelines (no server-side defaults for
    # privacy/interactions/disclosure).
    video_url: str = Field(..., min_length=1)
    caption: str = Field("", max_length=2200)
    privacy_level: str = Field(..., min_length=1)   # user-selected; audit requires no default
    disable_comment: bool = False
    disable_duet: bool = False
    disable_stitch: bool = False
    brand_organic_toggle: bool = False   # "Your Brand"  → Promotional content
    brand_content_toggle: bool = False   # "Branded Content" → Paid partnership


class TikTokStatusRequest(BaseModel):
    publish_id: str = Field(..., min_length=1)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _base_url() -> str:
    return _env("PUBLIC_BASE_URL", "https://mathrelaxing.store").rstrip("/")


def _client_key() -> str:
    return _env("TIKTOK_CLIENT_KEY")


def _client_secret() -> str:
    return _env("TIKTOK_CLIENT_SECRET")


def _redirect_uri() -> str:
    return _env("TIKTOK_REDIRECT_URI", f"{_base_url()}/api/tiktok/oauth/callback")


def _scopes() -> str:
    return _env("TIKTOK_SCOPES", DEFAULT_SCOPES)


def _scope_list() -> list[str]:
    return [scope for scope in _scopes().replace(" ", ",").split(",") if scope]


def _token_file() -> str:
    return _env("TIKTOK_TOKEN_FILE", DEFAULT_TOKEN_FILE)


def _last_upload_file() -> str:
    return _env("TIKTOK_LAST_UPLOAD_FILE", DEFAULT_LAST_UPLOAD_FILE)


def _demo_video_url() -> str:
    return _env("TIKTOK_DEMO_VIDEO_URL", f"{_base_url()}/static/tiktok_demo_upload.mp4")


def _privacy_level() -> str:
    # Unaudited / sandbox clients may ONLY post SELF_ONLY. After TikTok audits the
    # client for video.publish, flip TIKTOK_PRIVACY_LEVEL to PUBLIC_TO_EVERYONE.
    return _env("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY")


def _admin_username() -> str:
    return _env("TIKTOK_ADMIN_USER") or _env("PINTEREST_ADMIN_USER", "mathrelaxing")


def _admin_password() -> str:
    return _env("TIKTOK_ADMIN_PASSWORD") or _env("PINTEREST_ADMIN_PASSWORD")


def _state_secret() -> str:
    return _env("TIKTOK_STATE_SECRET") or _env("PINTEREST_STATE_SECRET") or _admin_password() or _client_secret()


def _is_configured() -> bool:
    return bool(_client_key() and _client_secret() and _redirect_uri())


def _valid_admin_login(username: str, password: str) -> bool:
    expected_password = _admin_password()
    if not expected_password:
        return False
    return hmac.compare_digest(username or "", _admin_username()) and hmac.compare_digest(password or "", expected_password)


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
    return hmac.compare_digest(supplied, _admin_cookie_signature(ts, username))


def _request_is_admin(request: Request, credentials: HTTPBasicCredentials | None = None) -> bool:
    if _valid_admin_cookie(request.cookies.get(ADMIN_COOKIE_NAME)):
        return True
    if isinstance(credentials, HTTPBasicCredentials):
        return _valid_admin_login(credentials.username, credentials.password)
    return False


def _require_admin_session(
    request: Request,
    credentials: HTTPBasicCredentials | None = None,
) -> None:
    if _request_is_admin(request, credentials):
        return
    raise HTTPException(
        status_code=401,
        detail="TikTok admin credentials required",
        headers={"WWW-Authenticate": "Basic"},
    )


def _sign_state(ts: int, nonce: str) -> str:
    secret = _state_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="TikTok state secret is not configured")
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
        raise HTTPException(status_code=400, detail="Invalid TikTok OAuth state")
    if abs(int(time.time()) - ts) > 20 * 60:
        raise HTTPException(status_code=400, detail="Expired TikTok OAuth state")
    if not hmac.compare_digest(supplied, _sign_state(ts, nonce)):
        raise HTTPException(status_code=400, detail="Invalid TikTok OAuth state signature")


def _read_json_file(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None


def _write_json_file(path: str, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, sort_keys=True)
    os.chmod(path, 0o600)


def _read_token() -> dict[str, Any] | None:
    return _read_json_file(_token_file())


def _write_token(data: dict[str, Any]) -> None:
    data = dict(data)
    data["saved_at"] = datetime.now(timezone.utc).isoformat()
    if data.get("expires_in"):
        data["expires_at"] = int(time.time()) + int(data["expires_in"])
    if data.get("refresh_expires_in"):
        data["refresh_expires_at"] = int(time.time()) + int(data["refresh_expires_in"])
    _write_json_file(_token_file(), data)


def _token_preview(token: dict[str, Any] | None) -> dict[str, Any] | None:
    if not token:
        return None
    return {
        "open_id": token.get("open_id"),
        "scope": token.get("scope"),
        "token_type": token.get("token_type"),
        "expires_at": token.get("expires_at"),
        "refresh_expires_at": token.get("refresh_expires_at"),
        "saved_at": token.get("saved_at"),
        "user": token.get("user"),
    }


def _validate_site_url(url: str) -> None:
    parsed = urlparse(url)
    allowed = urlparse(_base_url()).netloc
    if parsed.scheme != "https" or parsed.netloc != allowed:
        raise HTTPException(status_code=400, detail=f"Video URL must use verified domain {_base_url()}")


async def _token_request(payload: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{TIKTOK_OPEN_API}/v2/oauth/token/",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
        )
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text[:800]}
    if response.status_code >= 400 or data.get("error"):
        raise HTTPException(status_code=400, detail={"provider": "tiktok", "response": data})
    return data


async def _revoke_token(access_token: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(
            f"{TIKTOK_OPEN_API}/v2/oauth/revoke/",
            data={
                "client_key": _client_key(),
                "client_secret": _client_secret(),
                "token": access_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
        )


async def _exchange_code(code: str) -> dict[str, Any]:
    data = await _token_request(
        {
            "client_key": _client_key(),
            "client_secret": _client_secret(),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": _redirect_uri(),
        }
    )
    try:
        data["user"] = await _get_user_info(data["access_token"])
    except Exception as exc:
        data["user_error"] = str(exc)
    _write_token(data)
    return data


async def _refresh_token(token: dict[str, Any]) -> dict[str, Any]:
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="TikTok refresh token is missing; reconnect TikTok")
    data = await _token_request(
        {
            "client_key": _client_key(),
            "client_secret": _client_secret(),
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    )
    if token.get("user"):
        data["user"] = token["user"]
    _write_token(data)
    return data


async def _ensure_access_token() -> dict[str, Any]:
    token = _read_token()
    if not token or not token.get("access_token"):
        raise HTTPException(status_code=401, detail="TikTok is not connected")
    if int(token.get("expires_at") or 0) - int(time.time()) < 10 * 60:
        token = await _refresh_token(token)
    return token


async def _get_user_info(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{TIKTOK_OPEN_API}/v2/user/info/",
            params={"fields": "open_id,union_id,avatar_url,display_name"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    data = response.json()
    if response.status_code >= 400 or data.get("error", {}).get("code") not in (None, "ok"):
        raise HTTPException(status_code=400, detail={"provider": "tiktok", "response": data})
    return data.get("data", {}).get("user", data.get("data", {}))


async def _tiktok_post(path: str, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            f"{TIKTOK_OPEN_API}{path}",
            json=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
        )
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text[:800]}
    error = data.get("error") or {}
    if response.status_code >= 400 or error.get("code") not in (None, "ok"):
        raise HTTPException(status_code=400, detail={"provider": "tiktok", "response": data})
    return data


@router.get("/admin/tiktok")
async def tiktok_admin(request: Request):
    if not _valid_admin_cookie(request.cookies.get(ADMIN_COOKIE_NAME)):
        return RedirectResponse("/admin/tiktok/login", status_code=303)
    return templates.TemplateResponse("admin_tiktok.html", {"request": request})


@router.get("/admin/tiktok/login")
async def tiktok_login_page(request: Request):
    if _valid_admin_cookie(request.cookies.get(ADMIN_COOKIE_NAME)):
        return RedirectResponse("/admin/tiktok", status_code=303)
    return templates.TemplateResponse("admin_tiktok_login.html", {"request": request, "error": ""})


@router.post("/admin/tiktok/login")
async def tiktok_login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if not _valid_admin_login(username, password):
        return templates.TemplateResponse(
            "admin_tiktok_login.html",
            {"request": request, "error": "Invalid username or password."},
            status_code=401,
        )
    response = RedirectResponse("/admin/tiktok", status_code=303)
    response.set_cookie(
        ADMIN_COOKIE_NAME,
        _make_admin_cookie(username),
        max_age=ADMIN_COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


@router.get("/admin/tiktok/logout")
async def tiktok_logout():
    response = RedirectResponse("/admin/tiktok/login", status_code=303)
    response.delete_cookie(ADMIN_COOKIE_NAME)
    return response


@router.get("/api/tiktok/oauth/start")
async def tiktok_oauth_start(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
):
    _require_admin_session(request, credentials)
    if not _is_configured():
        raise HTTPException(status_code=503, detail="TikTok OAuth is not configured")
    params = {
        "client_key": _client_key(),
        "response_type": "code",
        "scope": ",".join(_scope_list()),
        "redirect_uri": _redirect_uri(),
        "state": _make_state(),
        "disable_auto_auth": "1",
    }
    return RedirectResponse(f"{TIKTOK_AUTH_URL}?{urlencode(params)}")


@router.get("/api/tiktok/oauth/callback")
async def tiktok_oauth_callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
    if error:
        raise HTTPException(status_code=400, detail=error_description or error)
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing TikTok OAuth code or state")
    _validate_state(state)
    await _exchange_code(code)
    return RedirectResponse("/admin/tiktok?connected=1", status_code=303)


@router.get("/api/tiktok/status")
async def tiktok_status(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
):
    _require_admin_session(request, credentials)
    token = _read_token()
    last_upload = _read_json_file(_last_upload_file())
    return {
        "configured": _is_configured(),
        "connected": bool(token and token.get("access_token")),
        "redirect_uri": _redirect_uri(),
        "scopes": _scope_list(),
        "demo_video_url": _demo_video_url(),
        "token": _token_preview(token),
        "last_upload": last_upload,
    }


@router.post("/api/tiktok/upload-draft")
async def tiktok_upload_draft(
    payload: TikTokUploadDraftRequest,
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
):
    _require_admin_session(request, credentials)
    _validate_site_url(payload.video_url)
    token = await _ensure_access_token()
    result = await _tiktok_post(
        "/v2/post/publish/inbox/video/init/",
        token["access_token"],
        {"source_info": {"source": "PULL_FROM_URL", "video_url": payload.video_url}},
    )
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "video_url": payload.video_url,
        "caption": payload.caption,
        "publish_id": result.get("data", {}).get("publish_id"),
        "result": result,
        "note": "Uploaded to TikTok inbox/draft flow. The creator must complete posting inside TikTok.",
    }
    _write_json_file(_last_upload_file(), record)
    return {"ok": True, **record}


@router.get("/api/tiktok/creator-info")
async def tiktok_creator_info(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
):
    """Creator's posting settings — TikTok requires querying this before showing
    the Direct Post form (nickname, allowed privacy levels, disabled interactions,
    max video duration, posting capacity)."""
    _require_admin_session(request, credentials)
    token = await _ensure_access_token()
    result = await _tiktok_post(
        "/v2/post/publish/creator_info/query/",
        token["access_token"],
        {},
    )
    return {"ok": True, "data": result.get("data", {})}


@router.post("/api/tiktok/upload-direct")
async def tiktok_upload_direct(
    payload: TikTokDirectPostRequest,
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
):
    _require_admin_session(request, credentials)
    _validate_site_url(payload.video_url)
    # Compliance guardrail from TikTok's guidelines: branded content can't be private.
    if payload.brand_content_toggle and payload.privacy_level == "SELF_ONLY":
        raise HTTPException(status_code=400, detail="Branded content visibility cannot be set to private")
    token = await _ensure_access_token()
    result = await _tiktok_post(
        "/v2/post/publish/video/init/",
        token["access_token"],
        {
            "source_info": {"source": "PULL_FROM_URL", "video_url": payload.video_url},
            "post_info": {
                "title": payload.caption,
                "privacy_level": payload.privacy_level,
                "disable_comment": payload.disable_comment,
                "disable_duet": payload.disable_duet,
                "disable_stitch": payload.disable_stitch,
                "video_cover_timestamp_ms": 1000,
                "brand_organic_toggle": payload.brand_organic_toggle,
                "brand_content_toggle": payload.brand_content_toggle,
            },
        },
    )
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "video_url": payload.video_url,
        "caption": payload.caption,
        "privacy_level": payload.privacy_level,
        "publish_id": result.get("data", {}).get("publish_id"),
        "result": result,
        "note": f"Direct Post submitted (privacy_level={payload.privacy_level}). Pending TikTok processing.",
    }
    _write_json_file(_last_upload_file(), record)
    return {"ok": True, **record}


@router.post("/api/tiktok/upload-status")
async def tiktok_upload_status(
    payload: TikTokStatusRequest,
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
):
    _require_admin_session(request, credentials)
    token = await _ensure_access_token()
    result = await _tiktok_post(
        "/v2/post/publish/status/fetch/",
        token["access_token"],
        {"publish_id": payload.publish_id},
    )
    return {"ok": True, "publish_id": payload.publish_id, "result": result}


@router.post("/api/tiktok/disconnect")
async def tiktok_disconnect(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
):
    _require_admin_session(request, credentials)
    token = _read_token()
    if token and token.get("access_token"):
        try:
            await _revoke_token(token["access_token"])
        except Exception:
            pass
    for path in (_token_file(), _last_upload_file()):
        if os.path.exists(path):
            os.remove(path)
    return {"ok": True, "connected": False}
