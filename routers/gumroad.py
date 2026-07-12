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
from models.product import DigitalProduct, Purchase
from services import gumroad as gumroad_svc

router = APIRouter()
templates = Jinja2Templates(directory="/var/www/mathrelaxing.store/templates")

ADMIN_COOKIE = "mr_gumroad_admin"
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
        raise HTTPException(status_code=302, headers={"Location": "/admin/gumroad/login"})


# ── OAuth flow ────────────────────────────────────────────────────────────────

@router.get("/admin/gumroad/connect")
async def gumroad_connect(request: Request):
    _require_admin(request)
    return RedirectResponse(gumroad_svc.get_auth_url(), status_code=303)


@router.get("/api/gumroad/oauth/callback")
async def gumroad_oauth_callback(code: str, request: Request):
    try:
        data = await gumroad_svc.exchange_code(code)
        gumroad_svc.save_token(data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OAuth error: {e}")
    return RedirectResponse("/admin/gumroad", status_code=303)


# ── Admin pages ───────────────────────────────────────────────────────────────

@router.get("/admin/gumroad")
async def gumroad_admin(request: Request):
    if not _valid_cookie(request.cookies.get(ADMIN_COOKIE)):
        return RedirectResponse("/admin/gumroad/login", status_code=303)
    connected = gumroad_svc.is_configured()
    return templates.TemplateResponse("admin_gumroad.html", {
        "request": request,
        "connected": connected,
    })


@router.get("/admin/gumroad/login")
async def gumroad_login_page(request: Request):
    if _valid_cookie(request.cookies.get(ADMIN_COOKIE)):
        return RedirectResponse("/admin/gumroad", status_code=303)
    return templates.TemplateResponse("admin_meta_ads_login.html", {
        "request": request,
        "title": "Gumroad Console",
        "action": "/admin/gumroad/login",
    })


@router.post("/admin/gumroad/login")
async def gumroad_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if not _valid_login(username, password):
        return templates.TemplateResponse("admin_meta_ads_login.html", {
            "request": request,
            "title": "Gumroad Console",
            "action": "/admin/gumroad/login",
            "error": "Invalid credentials",
        }, status_code=401)
    resp = RedirectResponse("/admin/gumroad", status_code=303)
    resp.set_cookie(ADMIN_COOKIE, _make_cookie(username), max_age=ADMIN_MAX_AGE, httponly=True, samesite="lax")
    return resp


@router.get("/admin/gumroad/logout")
async def gumroad_logout():
    resp = RedirectResponse("/admin/gumroad/login", status_code=303)
    resp.delete_cookie(ADMIN_COOKIE)
    return resp


# ── API endpoints ─────────────────────────────────────────────────────────────

@router.get("/api/gumroad/status")
async def gumroad_status(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    if not gumroad_svc.is_configured():
        raise HTTPException(status_code=503, detail="Gumroad not connected. Visit /admin/gumroad to connect.")

    products = db.query(DigitalProduct).filter(DigitalProduct.active == True).all()
    results = []
    for p in products:
        try:
            listing = await gumroad_svc.get_listing_status(p)
        except Exception as e:
            listing = {"status": "error", "error": str(e)[:120]}
        results.append({
            "slug":         p.slug,
            "name":         p.name,
            "price_usd":    p.price_usd,
            "product_type": p.product_type,
            **listing,
        })
    return {"products": results}


@router.post("/api/gumroad/publish/{slug}")
async def gumroad_publish(slug: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    product = db.query(DigitalProduct).filter(DigitalProduct.slug == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        result = await gumroad_svc.publish_product(product)
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/api/gumroad/unpublish/{slug}")
async def gumroad_unpublish(slug: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    product = db.query(DigitalProduct).filter(DigitalProduct.slug == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        await gumroad_svc.unpublish_product(product)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/api/gumroad/publish-all")
async def gumroad_publish_all(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    products = db.query(DigitalProduct).filter(DigitalProduct.active == True).all()
    results = []
    for p in products:
        try:
            r = await gumroad_svc.publish_product(p)
            results.append({"slug": p.slug, "ok": True, **r})
        except Exception as e:
            results.append({"slug": p.slug, "ok": False, "error": str(e)[:200]})
    return {"results": results}


# ── Ping webhook (Gumroad sale notifications) ─────────────────────────────────

@router.post("/api/gumroad/ping")
async def gumroad_ping(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    sale_id    = form.get("sale_id", "")
    product_id = form.get("product_id", "")
    email      = (form.get("email") or "").strip().lower()
    name       = (form.get("full_name") or form.get("email") or "").strip()
    price_cents = int(form.get("price", 0) or 0)

    # Verify sale with Gumroad API
    sale = await gumroad_svc.verify_sale(sale_id)
    if not sale:
        raise HTTPException(status_code=400, detail="Sale verification failed")

    # Find the product by Gumroad product ID
    slug = gumroad_svc.slug_for_gumroad_id(product_id)
    if not slug:
        # Unknown product — still acknowledge
        return {"ok": True, "note": "unknown product"}

    product = db.query(DigitalProduct).filter(DigitalProduct.slug == slug).first()
    if not product:
        return {"ok": True, "note": "product not in db"}

    # Avoid duplicate processing
    existing = db.query(Purchase).filter(
        Purchase.customer_email == email,
        Purchase.status == "paid",
        Purchase.product_id == product.id,
        Purchase.ref_source == "gumroad",
    ).first()
    if existing:
        return {"ok": True, "note": "duplicate"}

    from datetime import datetime, timedelta
    purchase = Purchase(
        product_id     = product.id,
        customer_email = email,
        customer_name  = name,
        ref_source     = "gumroad",
        status         = "paid",
        item_index     = None,
    )
    purchase.expires_at = datetime.utcnow() + timedelta(days=30)
    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    import asyncio
    from services import email as email_svc, telegram
    asyncio.create_task(email_svc.send_digital_purchase_email(purchase, product))
    asyncio.create_task(telegram.notify_new_digital_purchase(purchase, product))

    return {"ok": True, "purchase_id": purchase.id}
