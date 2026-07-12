import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.product import Product

router = APIRouter()


@router.get("/products")
def list_products(
    collection: str = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Product).filter(Product.active == True)
    if collection:
        q = q.filter(Product.collection == collection)
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [_serialize(p) for p in items],
    }


@router.get("/products/{slug}")
def get_product(slug: str, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.slug == slug).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return _serialize(p)


def _serialize(p: Product):
    return {
        "id": p.id,
        "slug": p.slug,
        "name": p.name,
        "collection": p.collection,
        "equation_type": p.equation_type,
        "description": p.description,
        "params": json.loads(p.params_json),
        "price_usd": p.price_usd,
        "image_url": p.image_url,
    }
