import hashlib
import hmac
import os
import secrets
import time

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models.product import DigitalProduct
from services import ebay as ebay_svc

router = APIRouter()
templates = Jinja2Templates(directory="/var/www/mathrelaxing.store/templates")

ADMIN_COOKIE = "mr_ebay_admin"
ADMIN_MAX_AGE = 7 * 24 * 3600


def _admin_password() -> str:
    return os.getenv("PINTEREST_ADMIN_PASSWORD", "") or os.getenv("META_ADS_ADMIN_PASSWORD", "")


def _admin_user() -> str:
    return os.getenv("PINTEREST_ADMIN_USER", "mathrelaxing")


def _cookie_sig(ts: int, username: str) -> str:
    key = (_admin_password() + str(ts) + username).encode()
    return hmac.new(key, digestmod=hashlib.sha256).hexdigest()[:32]


def _make_cookie(username: str) -> str:
    ts = int(time.time())
    return f"{ts}.{username}.{_cookie_sig(ts, username)}"


def _valid_cookie(value: str | None) -> bool:
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
    return secrets.compare_digest(username, _admin_user()) and secrets.compare_digest(password, expected)


def _require_admin(request: Request) -> None:
    if not _valid_cookie(request.cookies.get(ADMIN_COOKIE)):
        raise HTTPException(status_code=302, headers={"Location": "/admin/ebay/login"})


# ── Admin pages ───────────────────────────────────────────────────────────────

@router.get("/admin/ebay")
async def ebay_admin(request: Request):
    if not _valid_cookie(request.cookies.get(ADMIN_COOKIE)):
        return RedirectResponse("/admin/ebay/login", status_code=303)
    return templates.TemplateResponse("admin_ebay.html", {"request": request})


@router.get("/admin/ebay/login")
async def ebay_login_page(request: Request):
    if _valid_cookie(request.cookies.get(ADMIN_COOKIE)):
        return RedirectResponse("/admin/ebay", status_code=303)
    return templates.TemplateResponse("admin_meta_ads_login.html", {
        "request": request,
        "title": "eBay Console",
        "action": "/admin/ebay/login",
    })


@router.post("/admin/ebay/login")
async def ebay_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if not _valid_login(username, password):
        return templates.TemplateResponse("admin_meta_ads_login.html", {
            "request": request,
            "title": "eBay Console",
            "action": "/admin/ebay/login",
            "error": "Invalid credentials",
        }, status_code=401)
    resp = RedirectResponse("/admin/ebay", status_code=303)
    resp.set_cookie(ADMIN_COOKIE, _make_cookie(username), max_age=ADMIN_MAX_AGE, httponly=True, samesite="lax")
    return resp


@router.get("/admin/ebay/logout")
async def ebay_logout():
    resp = RedirectResponse("/admin/ebay/login", status_code=303)
    resp.delete_cookie(ADMIN_COOKIE)
    return resp


# ── API endpoints ─────────────────────────────────────────────────────────────

@router.get("/api/ebay/status")
async def ebay_status(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    if not ebay_svc.is_configured():
        raise HTTPException(status_code=503, detail="eBay credentials not configured")

    products = db.query(DigitalProduct).filter(DigitalProduct.active == True).all()
    results = []
    for p in products:
        try:
            listing = await ebay_svc.get_listing_status(p)
        except Exception as e:
            listing = {"status": "error", "error": str(e)[:120]}
        results.append({
            "slug": p.slug,
            "name": p.name,
            "price_usd": p.price_usd,
            "product_type": p.product_type,
            **listing,
        })
    return {"products": results}


@router.post("/api/ebay/publish/{slug}")
async def ebay_publish(slug: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    product = db.query(DigitalProduct).filter(DigitalProduct.slug == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        result = await ebay_svc.publish_product(product)
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/api/ebay/unpublish/{slug}")
async def ebay_unpublish(slug: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    product = db.query(DigitalProduct).filter(DigitalProduct.slug == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        await ebay_svc.unpublish_product(product)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/api/ebay/publish-all")
async def ebay_publish_all(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    products = db.query(DigitalProduct).filter(DigitalProduct.active == True).all()
    results = []
    for p in products:
        try:
            r = await ebay_svc.publish_product(p)
            results.append({"slug": p.slug, "ok": True, **r})
        except Exception as e:
            results.append({"slug": p.slug, "ok": False, "error": str(e)[:200]})
    return {"results": results}


@router.get("/api/ebay/orders")
async def ebay_orders(request: Request):
    _require_admin(request)
    try:
        orders = await ebay_svc.get_recent_orders(limit=25)
        return {"orders": orders}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/api/ebay/fulfill-orders")
async def ebay_fulfill_orders(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    try:
        results = await ebay_svc.fulfill_new_orders(db)
        return {"ok": True, "fulfilled": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
