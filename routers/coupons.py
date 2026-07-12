from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models.product import Coupon
from datetime import datetime
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

class CouponRequest(BaseModel):
    code: str
    amount: float  # original total before discount

@router.post("/coupons/apply")
@limiter.limit("10/minute")
def apply_coupon(request: Request, req: CouponRequest, db: Session = Depends(get_db)):
    code = req.code.strip().upper()
    coupon = db.query(Coupon).filter(Coupon.code == code, Coupon.active == True).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon code not found or inactive.")
    if coupon.expires_at and datetime.utcnow() > coupon.expires_at:
        raise HTTPException(status_code=410, detail="Coupon has expired.")
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        raise HTTPException(status_code=409, detail="Coupon usage limit reached.")

    discount = 0.0
    if coupon.discount_pct > 0:
        discount = round(req.amount * coupon.discount_pct / 100, 2)
    elif coupon.discount_fixed > 0:
        discount = min(coupon.discount_fixed, req.amount)

    new_total = max(0.0, round(req.amount - discount, 2))
    return {
        "valid": True,
        "code": coupon.code,
        "discount_pct": coupon.discount_pct,
        "discount_fixed": coupon.discount_fixed,
        "discount_amount": discount,
        "new_total": new_total,
        "message": f"Coupon applied: -${discount:.2f}",
    }
