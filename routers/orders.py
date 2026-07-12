import json
import os

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from database import get_db
from models.product import DigitalProduct, Purchase, Product, Order
from services import telegram
from services import paypal as paypal_svc
from services import email as email_svc

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# ── Physical order (Art Print / Printful) ────────────────────────────────────

class ShippingAddress(BaseModel):
    first_name: str
    last_name:  str
    address1:   str
    address2:   str = ""
    city:       str
    state:      str = ""
    zip:        str
    country:    str = "US"
    phone:      str = ""   # Lulu (book) requires a courier phone; optional otherwise


def _resolve_provider(format_id: str):
    """Map a physical format id to its fulfilment provider module + format dict.
    The book ships via Lulu; posters / desk-mats via Printful."""
    from services import lulu, printful
    if format_id in lulu.FORMATS_BY_ID:
        return lulu, lulu.FORMATS_BY_ID[format_id]
    fmt = printful.FORMATS_BY_ID.get(format_id)
    if fmt:
        return printful, fmt
    return None, None

class CreatePhysicalOrderRequest(BaseModel):
    product_slug:    str
    customer_name:   str
    customer_email:  str
    shipping:        ShippingAddress
    format_id:       str = "poster"
    size:            Optional[str] = None

class CaptureOrderRequest(BaseModel):
    paypal_order_id: str
    order_id:        int


@router.post("/physical-orders/create")
async def create_physical_order(body: CreatePhysicalOrderRequest, db: Session = Depends(get_db)):
    product = db.query(Product).filter(
        Product.slug == body.product_slug,
        Product.active == True,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    provider, fmt = _resolve_provider(body.format_id)
    if not fmt:
        raise HTTPException(status_code=400, detail="Invalid physical product format")
    try:
        quote = await provider.shipping_quote(body.shipping.dict(), fmt["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Free shipping: the cost is baked into the product price, so the customer
    # is never charged shipping. (We still validate the destination above.)
    ship_usd = 0.0
    # Some products carry their real price on the Product itself rather than on
    # the shared print format: sticker packs (discounted) and coloring books
    # (the Lulu "book" format is a flat $24.99, but each book is priced
    # individually — e.g. $14.99). Charge the advertised product price for those.
    _price_from_product = product.collection in ("sticker-packs", "coloring-book", "coloring-books")
    unit_price = product.price_usd if _price_from_product else fmt["price_usd"]
    total    = unit_price + ship_usd

    addr = body.shipping.dict()
    order_params = json.loads(product.params_json or "{}")
    if body.size:
        order_params["size"] = body.size

    order = Order(
        product_id       = product.id,
        product_slug     = product.slug,
        params_json      = json.dumps(order_params),
        format_id        = fmt["id"],
        customer_email   = body.customer_email,
        customer_name    = body.customer_name,
        shipping_address = json.dumps(addr),
        status           = "pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    from services import paypal
    checkout_url = await paypal.create_order(
        order_id       = order.id,
        product        = product,
        amount_usd     = total,
        customer_email = body.customer_email,
        customer_name  = body.customer_name,
        format_id      = fmt["id"],
    )
    return {"checkout_url": checkout_url, "order_id": order.id}


@router.post("/orders/capture")
async def capture_order(body: CaptureOrderRequest, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == body.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status in {"paid", "processing", "printed", "shipped", "fulfillment_failed"}:
        return {"success": True}

    from services import paypal as pp
    try:
        result = await pp.capture_order(body.paypal_order_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"PayPal capture failed: {e}")

    status = (
        result.get("status")
        or result.get("purchase_units", [{}])[0]
        .get("payments", {})
        .get("captures", [{}])[0]
        .get("status", "")
    )
    if status.upper() != "COMPLETED":
        raise HTTPException(status_code=402, detail=f"Payment not completed: {status}")

    order.paypal_order_id = body.paypal_order_id
    order.status          = "paid"
    db.commit()

    shipping_address = json.loads(order.shipping_address or "{}")
    from services import telegram as tg
    import asyncio
    provider, _fmt = _resolve_provider(order.format_id or "poster")
    if provider is None:
        from services import printful as provider  # safe default
    asyncio.create_task(provider.create_order(order, shipping_address))
    await tg.notify_new_physical_order(order)

    return {"success": True}



SINGLE_IMAGE_PRICE_USD = 4.0

class CreatePurchaseRequest(BaseModel):
    product_slug: str
    customer_name: str = ""        # optional — captured from PayPal if empty
    customer_email: str = ""       # optional — captured from PayPal if empty
    ref_source: str = "direct"  # gpt | direct | social
    item_index: Optional[int] = None  # None = full bundle, int = single image
    coupon_code: str = ""


@router.post("/purchases/create")
@limiter.limit("20/minute")
async def create_purchase(request: Request, body: CreatePurchaseRequest, db: Session = Depends(get_db)):
    product = db.query(DigitalProduct).filter(
        DigitalProduct.slug == body.product_slug,
        DigitalProduct.active == True,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    is_single = body.item_index is not None
    item_name = None
    if is_single:
        items = json.loads(product.contents_json or "[]")
        if not (0 <= body.item_index < len(items)):
            raise HTTPException(status_code=400, detail="Invalid item index")
        item_name = items[body.item_index].get("title", product.name)

    purchase = Purchase(
        product_id=product.id,
        customer_email=body.customer_email,
        customer_name=body.customer_name,
        ref_source=body.ref_source,
        status="pending",
        item_index=body.item_index,
    )
    from datetime import datetime, timedelta
    purchase.expires_at = datetime.utcnow() + timedelta(days=14)
    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    # Apply coupon if provided
    final_price = SINGLE_IMAGE_PRICE_USD if is_single else product.price_usd
    coupon_obj = None
    if body.coupon_code:
        from models.product import Coupon
        code = body.coupon_code.strip().upper()
        coupon_obj = db.query(Coupon).filter(Coupon.code == code, Coupon.active == True).first()
        if coupon_obj:
            if coupon_obj.discount_pct > 0:
                final_price = round(final_price * (1 - coupon_obj.discount_pct/100), 2)
            elif coupon_obj.discount_fixed > 0:
                final_price = max(0.0, round(final_price - coupon_obj.discount_fixed, 2))
            coupon_obj.used_count += 1
            db.commit()

    display_name = item_name if is_single else product.name
    checkout_url = await paypal_svc.create_digital_order(
        purchase_id=purchase.id,
        product_name=display_name,
        amount_usd=final_price,
    )
    return {"checkout_url": checkout_url, "purchase_id": purchase.id}


class CapturePurchaseRequest(BaseModel):
    paypal_order_id: str
    purchase_id: int


@router.post("/purchases/capture")
async def capture_purchase(body: CapturePurchaseRequest, db: Session = Depends(get_db)):
    purchase = db.query(Purchase).filter(Purchase.id == body.purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    if purchase.status == "paid":
        return {"success": True, "download_token": purchase.download_token}

    from services import paypal as pp
    try:
        result = await pp.capture_order(body.paypal_order_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"PayPal capture failed: {e}")

    status = (
        result.get("status")
        or result.get("purchase_units", [{}])[0]
        .get("payments", {})
        .get("captures", [{}])[0]
        .get("status", "")
    )
    if status.upper() != "COMPLETED":
        raise HTTPException(status_code=402, detail=f"Payment not completed: {status}")

    purchase.paypal_order_id = body.paypal_order_id
    purchase.status = "paid"

    # If purchase was created without contact info (Express checkout),
    # populate email/name from PayPal's payer block.
    if not purchase.customer_email or not purchase.customer_name:
        payer = result.get("payer") or {}
        payer_email = (payer.get("email_address") or "").strip().lower()
        payer_name_obj = payer.get("name") or {}
        payer_name = " ".join(
            filter(None, [payer_name_obj.get("given_name"), payer_name_obj.get("surname")])
        ).strip()
        if payer_email and not purchase.customer_email:
            purchase.customer_email = payer_email
        if payer_name and not purchase.customer_name:
            purchase.customer_name = payer_name

    db.commit()

    product = db.query(DigitalProduct).filter(DigitalProduct.id == purchase.product_id).first()
    buyer_country = ((result.get("payer") or {}).get("address") or {}).get("country_code")
    import asyncio
    if purchase.customer_email:
        asyncio.create_task(email_svc.send_digital_purchase_email(purchase, product))
    asyncio.create_task(telegram.notify_new_digital_purchase(purchase, product, country=buyer_country))

    return {"success": True, "download_token": purchase.download_token}


@router.get("/purchases/{purchase_id}")
def get_purchase(purchase_id: int, db: Session = Depends(get_db)):
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    product = db.query(DigitalProduct).filter(DigitalProduct.id == purchase.product_id).first()
    return {
        "id": purchase.id,
        "status": purchase.status,
        "product_slug": product.slug if product else None,
        "product_name": product.name if product else None,
        "customer_email": purchase.customer_email,
        "download_token": purchase.download_token,
        "download_count": purchase.download_count,
        "created_at": purchase.created_at.isoformat() if purchase.created_at else None,
    }


@router.get("/download/{token}")
def get_download(token: str, db: Session = Depends(get_db)):
    purchase = db.query(Purchase).filter(Purchase.download_token == token).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Download link not found")
    if purchase.status != "paid":
        raise HTTPException(status_code=402, detail="Payment not confirmed yet")
    from datetime import datetime
    if purchase.expires_at and datetime.utcnow() > purchase.expires_at:
        raise HTTPException(status_code=410, detail="Download link expired. Contact support to renew.")
    if purchase.download_count >= purchase.max_downloads:
        raise HTTPException(status_code=410, detail="Download limit reached")

    product = db.query(DigitalProduct).filter(DigitalProduct.id == purchase.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    purchase.download_count += 1
    db.commit()

    # Build download URLs from product contents
    all_items = json.loads(product.contents_json or "[]")
    base_url = "https://mathrelaxing.store"
    tok = purchase.download_token

    # Single-image purchase: deliver only the purchased item
    if purchase.item_index is not None and 0 <= purchase.item_index < len(all_items):
        items_to_deliver = [(purchase.item_index, all_items[purchase.item_index])]
    else:
        items_to_deliver = list(enumerate(all_items))

    download_files = []
    for idx, item in items_to_deliver:
        item_type = item.get("item_type", "image")
        title = item.get("title", "")
        item_index = item.get("index", idx)  # original index for render URL

        if item_type == "file":
            # Uploaded digital deliverable (PDF/ZIP/MP4) served from private storage
            # via a token-gated endpoint so it can't be fetched without paying.
            download_files.append({
                "title": title,
                "type": "file",
                "size": item.get("size"),
                "url": f"/api/digital-file?token={tok}&index={idx}",
            })
            continue

        if item_type == "animation" and item.get("animation_key"):
            # Video download — offer all available formats
            anim_key = item["animation_key"]
            formats = {}
            for fmt in ("1080p30", "1080p60", "4k30", "4k60"):
                path = f"/var/www/mathrelaxing.store/static/videos/{anim_key}_{fmt}.mp4"
                if os.path.exists(path):
                    formats[fmt] = f"{base_url}/api/video/{anim_key}?format={fmt}"
            if not formats:
                formats["1080p30"] = f"{base_url}/api/video/{anim_key}?format=1080p30"
            download_files.append({
                "title": title,
                "type": "video",
                "animation_key": anim_key,
                "formats": formats,
                "duration_secs": item.get("duration_secs"),
                "resolution": item.get("resolution"),
            })
        else:
            # Image download — offer portrait, landscape, and square orientations
            def _hq_url(ori):
                return (
                    f"{base_url}/api/render/hq-image"
                    f"?token={tok}&product={product.slug}&index={item_index}&orientation={ori}"
                )
            download_files.append({
                "title": title,
                "type": "image",
                "orientations": {
                    "portrait":  _hq_url("portrait"),   # 3200×4000
                    "landscape": _hq_url("landscape"),  # 4000×3200
                    "square":    _hq_url("square"),     # 3200×3200
                },
            })

    return {
        "product_name": product.name,
        "product_type": product.product_type,
        "file_url": product.file_url,
        "file_size": product.file_size,
        "license_type": product.license_type,
        "downloads_remaining": purchase.max_downloads - purchase.download_count,
        "expires_at": purchase.expires_at.isoformat() if purchase.expires_at else None,
        "files": download_files,
    }


@router.get("/digital-file")
def get_digital_file(token: str, index: int = 0, db: Session = Depends(get_db)):
    """Serve an uploaded digital deliverable (PDF/ZIP/MP4) from private storage,
    gated on a valid PAID, unexpired purchase token. Files live outside the public
    static dir so they can't be downloaded without buying."""
    from fastapi.responses import FileResponse
    from datetime import datetime
    import mimetypes

    purchase = db.query(Purchase).filter(Purchase.download_token == token).first()
    if not purchase or purchase.status != "paid":
        raise HTTPException(status_code=403, detail="Invalid or unpaid download token")
    if purchase.expires_at and datetime.utcnow() > purchase.expires_at:
        raise HTTPException(status_code=410, detail="Download link expired")

    product = db.query(DigitalProduct).filter(DigitalProduct.id == purchase.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    items = json.loads(product.contents_json or "[]")
    if not (0 <= index < len(items)) or items[index].get("item_type") != "file":
        raise HTTPException(status_code=404, detail="File not found")

    fname = os.path.basename(items[index].get("filename") or "")  # block path traversal
    path = os.path.join("/var/www/mathrelaxing.store/private_downloads", fname)
    if not fname or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File missing")

    media, _ = mimetypes.guess_type(path)
    return FileResponse(path, media_type=media or "application/octet-stream", filename=fname)


# ── Legacy order endpoints (kept for compat) ──────────────────────────────

@router.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    from models.product import Order
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "id": order.id,
        "status": order.status,
        "product_slug": order.product_slug,
        "customer_email": order.customer_email,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


class ResendRequest(BaseModel):
    email: str

@router.post("/resend-download")
@limiter.limit("5/minute")
def resend_download(request: Request, req: ResendRequest, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    purchases = db.query(Purchase).filter(
        Purchase.customer_email == email,
        Purchase.status == "paid"
    ).order_by(Purchase.created_at.desc()).limit(10).all()

    if not purchases:
        return {"found": 0, "message": "No purchases found for this email.", "purchases": []}

    product_map = {}
    for p in purchases:
        if p.product_id not in product_map:
            prod = db.query(DigitalProduct).filter(DigitalProduct.id == p.product_id).first()
            product_map[p.product_id] = prod.slug if prod else str(p.product_id)

    return {
        "found": len(purchases),
        "message": f"Found {len(purchases)} purchase(s). Download links sent to {email}.",
        "purchases": [
            {
                "product_name": product_map.get(p.product_id, str(p.product_id)),
                "download_url": f"/download/{p.download_token}",
                "purchased_at": p.created_at.isoformat() if p.created_at else None,
                "expires_at": p.expires_at.isoformat() if p.expires_at else None,
            }
            for p in purchases
        ]
    }
