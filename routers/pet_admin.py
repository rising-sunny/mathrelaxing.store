"""
pet_admin.py — internal admin page to turn a customer pet photo into a
paint-by-numbers download bundle.

Flow: staff logs in (shared admin cookie), uploads the buyer's photo, the
server renders the multi-size bundle and returns a private, unguessable
download link to paste into the Etsy message. The download link itself is
public (the buyer clicks it) but keyed by a random token.
"""
import asyncio
import hashlib
import hmac
import os
import secrets
import time

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services.pet_paintbynumbers import build_bundle, _orientation

router = APIRouter()

# Same signed-cookie scheme, cookie name and secret as the other admin consoles
# (routers/bonanza.py), so a single sign-in covers them all. Kept inline here so
# this router stays decoupled from the Bonanza/DB import chain.
ADMIN_COOKIE = "mr_bonanza_admin"
ADMIN_MAX_AGE = 7 * 24 * 3600


def _admin_password() -> str:
    return (
        os.getenv("BONANZA_ADMIN_PASSWORD", "")
        or os.getenv("PINTEREST_ADMIN_PASSWORD", "")
        or os.getenv("META_ADS_ADMIN_PASSWORD", "")
    )


def _admin_user() -> str:
    return os.getenv("BONANZA_ADMIN_USER", os.getenv("PINTEREST_ADMIN_USER", "mathrelaxing"))


def _cookie_sig(ts: int, username: str) -> str:
    key = (_admin_password() + str(ts) + username).encode()
    return hmac.new(key, digestmod=hashlib.sha256).hexdigest()[:32]


def _make_cookie(username: str) -> str:
    ts = int(time.time())
    return f"{ts}.{username}.{_cookie_sig(ts, username)}"


def _valid_cookie(value) -> bool:
    if not value:
        return False
    parts = value.split(".")
    if len(parts) != 3:
        return False
    ts_str, username, sig = parts
    try:
        ts = int(ts_str)
    except ValueError:
        return False
    if time.time() - ts > ADMIN_MAX_AGE:
        return False
    return secrets.compare_digest(sig, _cookie_sig(ts, username))


def _valid_login(username: str, password: str) -> bool:
    expected = _admin_password()
    if not expected:
        return False
    return (secrets.compare_digest(username, _admin_user())
            and secrets.compare_digest(password, expected))

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(_BASE, "templates"))

# bundles live outside /static so they are only reachable via the token route
PET_DATA_DIR = os.path.join(_BASE, "data", "petpbn")
BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://mathrelaxing.store")
MAX_IMAGE_BYTES = 25 * 1024 * 1024
# cap the on-server render at A2 / 24x18in — A1 PNGs are too memory-heavy here
WEB_MAX_LONG_PX = 7200
_render_sem = asyncio.Semaphore(1)


def _require(request: Request):
    if not _valid_cookie(request.cookies.get(ADMIN_COOKIE)):
        raise HTTPException(status_code=302, headers={"Location": "/admin/pet/login"})


@router.get("/admin/pet/login")
async def pet_login_page(request: Request):
    if _valid_cookie(request.cookies.get(ADMIN_COOKIE)):
        return RedirectResponse("/admin/pet", status_code=303)
    return templates.TemplateResponse("admin_pet_login.html", {"request": request})


@router.post("/admin/pet/login")
async def pet_login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if not _valid_login(username, password):
        return templates.TemplateResponse(
            "admin_pet_login.html", {"request": request, "error": "Invalid credentials"},
            status_code=401)
    resp = RedirectResponse("/admin/pet", status_code=303)
    resp.set_cookie(ADMIN_COOKIE, _make_cookie(username), max_age=ADMIN_MAX_AGE,
                    httponly=True, samesite="lax")
    return resp


@router.get("/admin/pet/logout")
async def pet_logout():
    resp = RedirectResponse("/admin/pet/login", status_code=303)
    resp.delete_cookie(ADMIN_COOKIE)
    return resp


@router.get("/admin/pet")
async def pet_admin(request: Request):
    if not _valid_cookie(request.cookies.get(ADMIN_COOKIE)):
        return RedirectResponse("/admin/pet/login", status_code=303)
    return templates.TemplateResponse("admin_pet.html", {"request": request})


@router.post("/admin/pet/generate")
async def pet_generate(
    request: Request,
    photo: UploadFile = File(...),
    colors: int = Form(16),
    density: int = Form(85),
):
    _require(request)
    image_bytes = await photo.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 25 MB).")

    colors = max(6, min(int(colors), 24))
    density = max(40, min(int(density), 130))

    token = secrets.token_urlsafe(9)
    out_dir = os.path.join(PET_DATA_DIR, token)
    try:
        async with _render_sem:
            zpath = await asyncio.to_thread(
                build_bundle, image_bytes, out_dir,
                num_colors=colors, base_cells_long=density,
                max_long_px=WEB_MAX_LONG_PX)
    except Exception as e:  # noqa: BLE001 — surface a clean message to the operator
        raise HTTPException(status_code=422, detail=f"Could not process this photo: {e}")

    sizes = sorted(
        f[len("paint-by-numbers_"):-len("_NUMBERED.png")]
        for f in os.listdir(out_dir) if f.endswith("_NUMBERED.png"))
    with open(os.path.join(out_dir, "_meta.txt"), "w") as f:
        f.write(f"{int(time.time())}\n{photo.filename}\n")

    return templates.TemplateResponse("admin_pet.html", {
        "request": request,
        "result": {
            "link": f"{BASE_URL}/pet/dl/{token}",
            "orientation": _orientation(*_img_size(image_bytes)),
            "sizes": sizes,
            "kb": os.path.getsize(zpath) // 1024,
            "filename": photo.filename,
        },
    })


@router.get("/pet/dl/{token}")
async def pet_download(token: str):
    # token is the only credential; keep it filesystem-safe
    if not token.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=404, detail="Not found.")
    zpath = os.path.join(PET_DATA_DIR, token, "pet_paintbynumbers_bundle.zip")
    if not os.path.exists(zpath):
        raise HTTPException(status_code=404, detail="This download link is invalid or has expired.")
    return FileResponse(zpath, media_type="application/zip",
                        filename="custom-pet-paint-by-numbers.zip")


def _img_size(image_bytes):
    from PIL import Image
    import io
    return Image.open(io.BytesIO(image_bytes)).size
