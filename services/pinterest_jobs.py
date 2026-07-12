"""
Auto-pinning job for Pinterest. Selects active products that haven't been pinned
recently and creates fresh pin variants.

Strategy:
  - Each product has 3 visual variants (see services.pinterest_renderer)
  - We re-pin the same (product, variant) at most every REPIN_COOLDOWN_DAYS
  - Cycles run every PIN_CYCLE_INTERVAL_HOURS
"""
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Optional
import asyncio

import httpx

from database import SessionLocal
from models.pinterest_pin import PinterestPin
from models.pinterest_board import PinterestBoard
from models.product import DigitalProduct, Product
from services import pinterest_renderer

logger = logging.getLogger("pinterest_jobs")

MAX_PINS_PER_CYCLE = int(os.getenv("PINTEREST_PINS_PER_CYCLE", "3"))
REPIN_COOLDOWN_DAYS = int(os.getenv("PINTEREST_REPIN_COOLDOWN_DAYS", "14"))
PIN_CYCLE_INTERVAL_HOURS = int(os.getenv("PINTEREST_CYCLE_HOURS", "4"))
DEFAULT_BOARD_ID = os.getenv("PINTEREST_DEFAULT_BOARD_ID", "")
PIN_RENDER_VERSION = "product-label-v3-20260704"

DESCRIPTION_TEMPLATES_DIGITAL = [
    "Digital download bundle — {name}. Generative mathematical art inspired by chaos theory. "
    "High-resolution digital pack from ${price}.\n\nFull catalog at mathrelaxing.store.",
    "{name} — Algorithmic artwork from the {collection} collection. "
    "Print-ready pack, perfect for creators. From ${price}.\n\nDiscover more at mathrelaxing.store.",
]

DESCRIPTION_TEMPLATES_APPAREL = [
    "Premium mathematical apparel — {name}. High-quality fabric printed with generative art. "
    "From ${price}.\n\nOrder yours at mathrelaxing.store.",
    "{name} — Wearable mathematics. Algorithmic artwork printed on premium apparel. "
    "Ships worldwide. From ${price}.\n\nmathrelaxing.store.",
]

DESCRIPTION_TEMPLATES_DESKMAT = [
    "Premium Desk Mat — {name}. Elevate your workspace with generative mathematical art. "
    "From ${price}.\n\nOrder yours at mathrelaxing.store.",
    "{name} — Algorithmic desk mat for gaming and studio setups. "
    "Ships worldwide. From ${price}.\n\nmathrelaxing.store.",
]

DESCRIPTION_TEMPLATES_COLORING = [
    "Mathematical Coloring Book — {name}. Relax and color generative fractal geometry. "
    "Free shipping on physical books. From ${price}.\n\nmathrelaxing.store.",
    "{name} — 50 hand-crafted line-art designs generated from real math equations. "
    "From ${price}.\n\nmathrelaxing.store.",
]

def _product_label(ptype: str, collection: str) -> str:
    collection = collection.lower() if collection else ""
    if ptype == "digital":
        return "Digital Bundle"
    if "desk-mat" in collection or "desk-mats" in collection:
        return "Desk Mat"
    if "coloring" in collection:
        return "Coloring Book"
    if "apparel" in collection:
        return "Premium Apparel"
    return "MathRelaxing Product"

def _select_candidates(db, *, limit: int) -> list[tuple[str, object, int]]:
    cutoff = datetime.utcnow() - timedelta(days=REPIN_COOLDOWN_DAYS)

    # Note: We now allow 'digital-downloads' if they are marked active
    digital = db.query(DigitalProduct).filter(DigitalProduct.active == True).all()
    physical = db.query(Product).filter(Product.active == True).all()
    
    all_products = [("digital", p) for p in digital] + [("physical", p) for p in physical]
    if not all_products:
        return []

    num_variants = len(pinterest_renderer.VARIANTS)
    candidates = []
    
    for ptype, p in all_products:
        for v in range(num_variants):
            last = db.query(PinterestPin.created_at).filter(
                PinterestPin.product_slug == p.slug,
                PinterestPin.variant_idx == v,
                PinterestPin.status == "active",
            ).order_by(PinterestPin.created_at.desc()).first()
            
            last_ts = last[0] if last else None
            if last_ts is None or last_ts < cutoff:
                candidates.append((ptype, p, v, last_ts))

    if not candidates:
        return []

    random.shuffle(candidates)
    candidates.sort(key=lambda c: (c[3] is not None, c[3] or datetime.min))
    return [(c[0], c[1], c[2]) for c in candidates[:limit]]


def _build_pin_body(ptype: str, product, variant_idx: int, board_id: str) -> dict:
    base = os.getenv("PINTEREST_PUBLIC_BASE_URL", "https://mathrelaxing.store")
    collection = (product.collection or "").lower()
    label = _product_label(ptype, collection)
    
    image_url = (f"{base}/api/render/pinterest?product={product.slug}"
                 f"&variant={variant_idx}&v={PIN_RENDER_VERSION}")
                 
    link_path = "/bundle/" if ptype == "digital" else "/product/"
    link = (f"{base}{link_path}{product.slug}"
            f"?utm_source=pinterest&utm_medium=organic&utm_campaign=auto_pin_v{variant_idx}")
            
    price = int(product.price_usd or 0)
    
    if ptype == "digital":
        templates = DESCRIPTION_TEMPLATES_DIGITAL
    elif "apparel" in collection:
        templates = DESCRIPTION_TEMPLATES_APPAREL
    elif "desk-mat" in collection or "desk-mats" in collection:
        templates = DESCRIPTION_TEMPLATES_DESKMAT
    elif "coloring" in collection:
        templates = DESCRIPTION_TEMPLATES_COLORING
    else:
        templates = DESCRIPTION_TEMPLATES_APPAREL # Fallback
        
    template = templates[variant_idx % len(templates)]
    description = template.format(name=product.name, collection=collection.replace("-", " "), price=price)[:495]
    
    title_suffix = f" | {label}"
    title = (product.name[: max(1, 100 - len(title_suffix))] + title_suffix)[:100]
    
    return {
        "board_id": board_id,
        "title": title,
        "description": description,
        "link": link,
        "media_source": {
            "source_type": "image_url",
            "url": image_url,
            "is_standard": True,
        },
    }

async def _list_all_boards(access_token: str) -> list[dict]:
    api_base = os.getenv("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
    items = []
    bookmark = None
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params = {"page_size": 100}
            if bookmark: params["bookmark"] = bookmark
            r = await client.get(f"{api_base}/boards", headers={"Authorization": f"Bearer {access_token}"}, params=params)
            if r.status_code != 200: break
            body = r.json() or {}
            items.extend(body.get("items") or [])
            bookmark = body.get("bookmark")
            if not bookmark: break
    return items

async def _get_default_board_id(access_token: str) -> Optional[str]:
    if DEFAULT_BOARD_ID: return DEFAULT_BOARD_ID
    items = await _list_all_boards(access_token)
    return items[0].get("id") if items else None

def _collection_to_board_name(collection_slug: str) -> str:
    if not collection_slug: return "MathRelaxing Store"
    return " ".join(w.capitalize() for w in collection_slug.replace("_", "-").split("-"))

async def ensure_collection_board(access_token: str, collection_slug: str) -> str:
    if not collection_slug: return await _get_default_board_id(access_token) or ""
    db = SessionLocal()
    try:
        cached = db.query(PinterestBoard).filter(PinterestBoard.collection_slug == collection_slug).first()
        if cached: return cached.board_id
    finally:
        db.close()

    board_name = _collection_to_board_name(collection_slug)
    existing_boards = await _list_all_boards(access_token)
    for b in existing_boards:
        if (b.get("name") or "").strip().lower() == board_name.lower():
            return b["id"]

    api_base = os.getenv("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
    body = {"name": board_name, "description": f"Collection: {board_name}", "privacy": "PUBLIC"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{api_base}/boards", headers={"Authorization": f"Bearer {access_token}"}, json=body)
    if r.status_code >= 400:
        return await _get_default_board_id(access_token) or ""
    return (r.json() or {}).get("id") or (await _get_default_board_id(access_token) or "")

async def _create_pin_remote(body: dict, access_token: str) -> dict:
    api_base = os.getenv("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{api_base}/pins", headers={"Authorization": f"Bearer {access_token}"}, json=body)
    if r.status_code >= 400:
        raise RuntimeError(f"Pinterest API HTTP {r.status_code}: {r.text[:500]}")
    return r.json() if r.content else {}


async def _delete_pin_remote(pin_id: str, access_token: str) -> bool:
    """Delete a pin from Pinterest. 404 = already gone, treated as success."""
    api_base = os.getenv("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(f"{api_base}/pins/{pin_id}",
                                headers={"Authorization": f"Bearer {access_token}"})
    return r.status_code in (200, 202, 204, 404)


async def prune_retired_pins(access_token: str, db) -> dict:
    """Keep Pinterest in sync with the published catalog: delete any pin whose link
    points to a product that is no longer active on the site. This is what prevents
    the account from advertising retired/unpublished products. Runs each cycle.
    Collection pins (link contains /collection/) are left alone."""
    from models.product import Product, DigitalProduct
    active = set()
    for Model in (DigitalProduct, Product):
        for row in db.query(Model.slug).filter(Model.active == True).all():
            active.add(row[0])

    api_base = os.getenv("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
    pruned = 0
    bookmark = None
    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(30):  # safety cap on pagination
            params = {"page_size": 100}
            if bookmark:
                params["bookmark"] = bookmark
            r = await client.get(f"{api_base}/pins",
                                  headers={"Authorization": f"Bearer {access_token}"},
                                  params=params)
            if r.status_code != 200:
                break
            data = r.json()
            for pin in data.get("items", []):
                link = (pin.get("link") or "").split("?")[0].rstrip("/")
                slug = None
                for pre in ("/product/", "/bundle/", "/book/"):
                    if pre in link:
                        slug = link.split(pre, 1)[1]
                        break
                if slug and slug not in active:
                    pid = pin.get("id")
                    if pid and await _delete_pin_remote(str(pid), access_token):
                        pruned += 1
                        db.query(PinterestPin).filter(
                            PinterestPin.pin_id == str(pid)
                        ).update({"status": "deleted"})
                        db.commit()
                        logging.getLogger("pinterest").info(
                            "pruned retired pin %s (product %s)", pid, slug)
            bookmark = data.get("bookmark")
            if not bookmark:
                break
    return {"pruned": pruned}


async def run_auto_pin_cycle() -> dict:
    from routers.pinterest import _access_token, _read_token
    if not _read_token(): return {"skipped": "not_connected", "created": 0}
    try:
        access_token = await _access_token()
    except Exception:
        return {"skipped": "token_error", "created": 0}

    db = SessionLocal()
    summary = {"created": 0, "failed": 0, "pruned": 0, "pins": []}
    try:
        # Sync first: remove pins for products that were retired since being pinned.
        try:
            summary["pruned"] = (await prune_retired_pins(access_token, db)).get("pruned", 0)
        except Exception as e:
            logging.getLogger("pinterest").warning("prune_retired_pins failed: %s", e)

        candidates = _select_candidates(db, limit=MAX_PINS_PER_CYCLE)
        if not candidates:
            summary["skipped"] = "no_candidates"
            return summary

        for ptype, product, variant in candidates:
            try:
                board_id = await ensure_collection_board(access_token, product.collection or "")
            except:
                board_id = await _get_default_board_id(access_token) or ""
            
            if not board_id: continue
            
            body = _build_pin_body(ptype, product, variant, board_id)
            record = PinterestPin(
                product_slug=product.slug, product_type=ptype, variant_idx=variant,
                board_id=board_id, image_url=body["media_source"]["url"],
                title=body["title"], description=body["description"],
                link_url=body["link"], status="active"
            )
            try:
                result = await _create_pin_remote(body, access_token)
                record.pin_id = str(result.get("id") or "")
                db.add(record); db.commit(); db.refresh(record)
                summary["created"] += 1
                summary["pins"].append({"pin_id": record.pin_id, "product": product.slug})
            except Exception as e:
                record.status = "failed"
                record.error = str(e)[:2000]
                db.add(record); db.commit()
                summary["failed"] += 1
    finally:
        db.close()
    return summary
