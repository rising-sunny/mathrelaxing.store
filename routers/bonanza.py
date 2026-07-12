import hashlib
import hmac
import os
import secrets
import time

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models.product import DigitalProduct, Product
from services import bonanza as bonanza_svc

BOOK_SLUG = "mathematical-tangle-art-coloring-book"

router = APIRouter()
templates = Jinja2Templates(directory="/var/www/mathrelaxing.store/templates")

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
        raise HTTPException(status_code=302, headers={"Location": "/admin/bonanza/login"})


@router.get("/admin/bonanza")
async def bonanza_admin(request: Request):
    if not _valid_cookie(request.cookies.get(ADMIN_COOKIE)):
        return RedirectResponse("/admin/bonanza/login", status_code=303)
    return templates.TemplateResponse("admin_bonanza.html", {
        "request": request,
        "configured": bonanza_svc.is_configured(),
    })


@router.get("/admin/bonanza/login")
async def bonanza_login_page(request: Request):
    if _valid_cookie(request.cookies.get(ADMIN_COOKIE)):
        return RedirectResponse("/admin/bonanza", status_code=303)
    return templates.TemplateResponse("admin_bonanza_login.html", {
        "request": request,
        "title": "Bonanza Console",
        "action": "/admin/bonanza/login",
    })


@router.post("/admin/bonanza/login")
async def bonanza_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if not _valid_login(username, password):
        return templates.TemplateResponse("admin_bonanza_login.html", {
            "request": request,
            "title": "Bonanza Console",
            "action": "/admin/bonanza/login",
            "error": "Invalid credentials",
        }, status_code=401)
    resp = RedirectResponse("/admin/bonanza", status_code=303)
    resp.set_cookie(ADMIN_COOKIE, _make_cookie(username), max_age=ADMIN_MAX_AGE, httponly=True, samesite="lax")
    return resp


@router.get("/admin/bonanza/logout")
async def bonanza_logout():
    resp = RedirectResponse("/admin/bonanza/login", status_code=303)
    resp.delete_cookie(ADMIN_COOKIE)
    return resp


@router.get("/api/bonanza/status")
async def bonanza_status(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    if not bonanza_svc.is_configured():
        raise HTTPException(status_code=503, detail="Bonanza API credentials are not configured.")

    try:
        token_status = await bonanza_svc.get_token_status()
    except Exception as e:
        token_status = {"verified": "false", "error": str(e)[:180]}

    products = db.query(DigitalProduct).filter(DigitalProduct.active == True).all()
    results = []
    for product in products:
        try:
            listing = await bonanza_svc.get_listing_status(product)
        except Exception as e:
            listing = {"status": "error", "error": str(e)[:180]}
        results.append({
            "slug": product.slug,
            "name": product.name,
            "price_usd": product.price_usd,
            "bonanza_price_usd": bonanza_svc.price_for_product(product),
            "product_type": product.product_type,
            **listing,
        })
    return {"token": token_status, "fees": bonanza_svc.fee_settings(), "products": results}


@router.post("/api/bonanza/publish/{slug}")
async def bonanza_publish(slug: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    product = db.query(DigitalProduct).filter(DigitalProduct.slug == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        result = await bonanza_svc.publish_product(product)
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/api/bonanza/unpublish/{slug}")
async def bonanza_unpublish(slug: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    product = db.query(DigitalProduct).filter(DigitalProduct.slug == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        await bonanza_svc.unpublish_product(product)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/api/bonanza/publish-book")
async def bonanza_publish_book(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    product = db.query(Product).filter(Product.slug == BOOK_SLUG).first()
    if not product:
        raise HTTPException(status_code=404, detail="Book product not found")
    try:
        result = await bonanza_svc.publish_book(product)
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/api/bonanza/publish-all")
async def bonanza_publish_all(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    products = db.query(DigitalProduct).filter(DigitalProduct.active == True).all()
    results = []
    for product in products:
        try:
            result = await bonanza_svc.publish_product(product)
            results.append({"slug": product.slug, "ok": True, **result})
        except Exception as e:
            results.append({"slug": product.slug, "ok": False, "error": str(e)[:220]})
    return {"results": results}


@router.post("/api/bonanza/fulfill-now")
async def bonanza_fulfill_now(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    try:
        results = await bonanza_svc.fulfill_new_orders(db)
        return {"ok": True, "fulfilled": results}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
