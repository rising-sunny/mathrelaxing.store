"""
Auto-pinning job for Pinterest. Selects active Etsy listings that haven't been
pinned recently and creates fresh pins that link straight to the Etsy listing.

Strategy:
  - Source of truth is the shop's active listings on Etsy (services.etsy_client).
  - We re-pin the same listing at most every REPIN_COOLDOWN_DAYS.
  - Each cycle also prunes pins whose Etsy listing is no longer active.
  - Cycles run every PIN_CYCLE_INTERVAL_HOURS (driven by main._pinterest_auto_pin_loop).

Pins are tracked in the PinterestPin table, reusing its columns:
  product_slug = str(listing_id), product_type = "etsy", variant_idx = 0.
"""
import asyncio
import logging
import os
import random
import time
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Optional

import httpx

from database import SessionLocal
from models.pinterest_pin import PinterestPin
from models.pinterest_board import PinterestBoard
from services import etsy_client

logger = logging.getLogger("pinterest_jobs")

MAX_PINS_PER_CYCLE = int(os.getenv("PINTEREST_PINS_PER_CYCLE", "3"))
REPIN_COOLDOWN_DAYS = int(os.getenv("PINTEREST_REPIN_COOLDOWN_DAYS", "14"))
PIN_CYCLE_INTERVAL_HOURS = int(os.getenv("PINTEREST_CYCLE_HOURS", "4"))
DEFAULT_BOARD_ID = os.getenv("PINTEREST_DEFAULT_BOARD_ID", "")
ETSY_BOARD_NAME = os.getenv("PINTEREST_ETSY_BOARD_NAME", "MathRelaxing on Etsy")
MAX_ETSY_LISTINGS = int(os.getenv("PINTEREST_ETSY_MAX_LISTINGS", "250"))

ETSY_PRODUCT_TYPE = "etsy"
PIN_CTA = "Shop the full collection on Etsy."


# ---------------------------------------------------------------------------
# Etsy listing selection + pin body
# ---------------------------------------------------------------------------
def _listing_id(listing: dict) -> str:
    return str(listing.get("listing_id") or "")


def _listing_link(listing: dict) -> str:
    url = (listing.get("url") or "").strip()
    if not url:
        lid = _listing_id(listing)
        url = f"https://www.etsy.com/listing/{lid}"
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}utm_source=pinterest&utm_medium=organic&utm_campaign=auto_pin"


def _select_candidates(db, listings: list[dict], *, limit: int) -> list[dict]:
    """Pick listings not pinned within the cooldown window, oldest-pinned first."""
    cutoff = datetime.utcnow() - timedelta(days=REPIN_COOLDOWN_DAYS)
    scored: list[tuple[bool, datetime, dict]] = []

    for listing in listings:
        lid = _listing_id(listing)
        if not lid:
            continue
        last = (
            db.query(PinterestPin.created_at)
            .filter(
                PinterestPin.product_slug == lid,
                PinterestPin.product_type == ETSY_PRODUCT_TYPE,
                PinterestPin.status == "active",
            )
            .order_by(PinterestPin.created_at.desc())
            .first()
        )
        last_ts = last[0] if last else None
        if last_ts is None or last_ts < cutoff:
            scored.append((last_ts is not None, last_ts or datetime.min, listing))

    if not scored:
        return []

    random.shuffle(scored)  # break ties among never-pinned listings
    scored.sort(key=lambda s: (s[0], s[1]))  # never-pinned first, then oldest
    return [s[2] for s in scored[:limit]]


async def _build_pin_body(listing: dict, board_id: str) -> Optional[dict]:
    image_url = await etsy_client.primary_image_url(listing)
    if not image_url:
        return None

    title = (listing.get("title") or "").strip()[:100] or "MathRelaxing Art"

    description = (listing.get("description") or "").strip()
    if len(description) > 440:
        description = description[:437].rstrip() + "..."
    description = (f"{description}\n\n{PIN_CTA}" if description else PIN_CTA)[:495]

    return {
        "board_id": board_id,
        "title": title,
        "description": description,
        "link": _listing_link(listing),
        "media_source": {
            "source_type": "image_url",
            "url": image_url,
            "is_standard": True,
        },
    }


# ---------------------------------------------------------------------------
# Pinterest board helpers
# ---------------------------------------------------------------------------
async def _list_all_boards(access_token: str) -> list[dict]:
    api_base = os.getenv("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
    items: list[dict] = []
    bookmark = None
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params = {"page_size": 100}
            if bookmark:
                params["bookmark"] = bookmark
            r = await client.get(
                f"{api_base}/boards",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            if r.status_code != 200:
                break
            body = r.json() or {}
            items.extend(body.get("items") or [])
            bookmark = body.get("bookmark")
            if not bookmark:
                break
    return items


async def _get_default_board_id(access_token: str) -> Optional[str]:
    if DEFAULT_BOARD_ID:
        return DEFAULT_BOARD_ID
    items = await _list_all_boards(access_token)
    return items[0].get("id") if items else None


async def ensure_etsy_board(access_token: str) -> str:
    """Resolve the board that Etsy pins go to. Priority:
    PINTEREST_DEFAULT_BOARD_ID → cached board → existing board by name →
    freshly created board. All Etsy pins share one board."""
    if DEFAULT_BOARD_ID:
        return DEFAULT_BOARD_ID

    cache_key = "__etsy__"
    db = SessionLocal()
    try:
        cached = (
            db.query(PinterestBoard)
            .filter(PinterestBoard.collection_slug == cache_key)
            .first()
        )
        if cached:
            return cached.board_id
    finally:
        db.close()

    for b in await _list_all_boards(access_token):
        if (b.get("name") or "").strip().lower() == ETSY_BOARD_NAME.lower():
            _remember_board(cache_key, b["id"])
            return b["id"]

    api_base = os.getenv("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
    body = {"name": ETSY_BOARD_NAME, "description": "Math art & printables, shop on Etsy.", "privacy": "PUBLIC"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{api_base}/boards",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
    if r.status_code >= 400:
        return await _get_default_board_id(access_token) or ""
    board_id = (r.json() or {}).get("id") or ""
    if board_id:
        _remember_board(cache_key, board_id)
    return board_id or (await _get_default_board_id(access_token) or "")


def _remember_board(collection_slug: str, board_id: str) -> None:
    db = SessionLocal()
    try:
        existing = (
            db.query(PinterestBoard)
            .filter(PinterestBoard.collection_slug == collection_slug)
            .first()
        )
        if existing:
            existing.board_id = board_id
        else:
            db.add(PinterestBoard(collection_slug=collection_slug, board_id=board_id))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pinterest pin API
# ---------------------------------------------------------------------------
async def _create_pin_remote(body: dict, access_token: str) -> dict:
    api_base = os.getenv("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{api_base}/pins",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
    if r.status_code >= 400:
        raise RuntimeError(f"Pinterest API HTTP {r.status_code}: {r.text[:500]}")
    return r.json() if r.content else {}


async def _delete_pin_remote(pin_id: str, access_token: str) -> bool:
    """Delete a pin from Pinterest. 404 = already gone, treated as success."""
    api_base = os.getenv("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(
            f"{api_base}/pins/{pin_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    return r.status_code in (200, 202, 204, 404)


# ---------------------------------------------------------------------------
# Prune + cycle
# ---------------------------------------------------------------------------
async def prune_retired_etsy_pins(pin_token: str, active_ids: set[str], db) -> dict:
    """Delete any Etsy pin we created whose listing is no longer active on Etsy.
    Uses our own PinterestPin records as the work list (one delete per stale pin).
    Web-product pins from the old flow are left untouched."""
    stale = (
        db.query(PinterestPin)
        .filter(
            PinterestPin.product_type == ETSY_PRODUCT_TYPE,
            PinterestPin.status == "active",
        )
        .all()
    )
    pruned = 0
    for pin in stale:
        if pin.product_slug in active_ids:
            continue
        if pin.pin_id and await _delete_pin_remote(str(pin.pin_id), pin_token):
            pin.status = "deleted"
            db.commit()
            pruned += 1
            logger.info("pruned pin %s for retired etsy listing %s", pin.pin_id, pin.product_slug)
        elif not pin.pin_id:
            pin.status = "deleted"
            db.commit()
    return {"pruned": pruned}


async def run_auto_pin_cycle() -> dict:
    from routers.pinterest import _access_token as _pin_access_token, _read_token as _pin_read_token

    if not _pin_read_token():
        return {"skipped": "pinterest_not_connected", "created": 0}
    if not etsy_client.is_configured():
        return {"skipped": "etsy_not_configured", "created": 0}

    try:
        pin_token = await _pin_access_token()
    except Exception:
        return {"skipped": "pinterest_token_error", "created": 0}

    try:
        listings = await etsy_client.list_active_listings(limit_total=MAX_ETSY_LISTINGS)
    except Exception as exc:
        logger.warning("etsy list_active_listings failed: %s", exc)
        return {"skipped": "etsy_fetch_error", "error": str(exc)[:300], "created": 0}

    if not listings:
        return {"skipped": "no_active_listings", "created": 0}

    active_ids = {_listing_id(l) for l in listings if _listing_id(l)}

    db = SessionLocal()
    summary = {"created": 0, "failed": 0, "pruned": 0, "pins": []}
    try:
        try:
            summary["pruned"] = (await prune_retired_etsy_pins(pin_token, active_ids, db)).get("pruned", 0)
        except Exception as exc:
            logger.warning("prune_retired_etsy_pins failed: %s", exc)

        candidates = _select_candidates(db, listings, limit=MAX_PINS_PER_CYCLE)
        if not candidates:
            summary["skipped"] = "no_candidates"
            return summary

        board_id = await ensure_etsy_board(pin_token)
        if not board_id:
            summary["skipped"] = "no_board"
            return summary

        for listing in candidates:
            lid = _listing_id(listing)
            body = await _build_pin_body(listing, board_id)
            if not body:
                summary["failed"] += 1
                logger.warning("no image for etsy listing %s; skipped", lid)
                continue

            record = PinterestPin(
                product_slug=lid,
                product_type=ETSY_PRODUCT_TYPE,
                variant_idx=0,
                board_id=board_id,
                image_url=body["media_source"]["url"],
                title=body["title"],
                description=body["description"],
                link_url=body["link"],
                status="active",
            )
            try:
                result = await _create_pin_remote(body, pin_token)
                record.pin_id = str(result.get("id") or "")
                db.add(record)
                db.commit()
                db.refresh(record)
                summary["created"] += 1
                summary["pins"].append({"pin_id": record.pin_id, "listing_id": lid})
            except Exception as exc:
                record.status = "failed"
                record.error = str(exc)[:2000]
                db.add(record)
                db.commit()
                summary["failed"] += 1
    finally:
        db.close()
    return summary


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
_ANALYTICS_TTL = 600  # 10-minute server-side cache
_analytics_cache: dict = {"ts": 0.0, "days": None, "data": None}


def _extract_summary_metrics(body: dict) -> dict:
    """Pull the summary-metrics dict out of a Pinterest pin-analytics payload,
    tolerating the shapes the API returns ({"all": {"summary_metrics": {...}}})."""
    if not isinstance(body, dict):
        return {}
    node = body.get("all") if isinstance(body.get("all"), dict) else body
    for key in ("summary_metrics", "lifetime_metrics"):
        sm = node.get(key)
        if isinstance(sm, dict) and sm:
            return sm
    return {k: v for k, v in node.items() if isinstance(v, (int, float))}


async def _fetch_pin_analytics(pin_id: str, access_token: str,
                               start: str, end: str) -> tuple[Optional[dict], int]:
    api_base = os.getenv("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
    params = {
        "start_date": start,
        "end_date": end,
        "metric_types": "IMPRESSION,SAVE,PIN_CLICK,OUTBOUND_CLICK",
        "app_types": "ALL",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{api_base}/pins/{pin_id}/analytics",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
    if r.status_code != 200:
        return None, r.status_code
    return (r.json() if r.content else {}), 200


def _agg_rows(mapping: dict, key_name: str) -> list[dict]:
    rows = []
    for k, c in mapping.items():
        rows.append({
            key_name: k,
            "pins": c["pins"],
            "impressions": c["impressions"],
            "saves": c["saves"],
            "pin_clicks": c["pin_clicks"],
            "outbound_clicks": c["outbound_clicks"],
        })
    rows.sort(key=lambda r: (r["outbound_clicks"], r["impressions"]), reverse=True)
    return rows


async def collect_all_pin_analytics(days: int = 30) -> dict:
    """Aggregate Pinterest analytics for every active pin we created, over the
    last `days`. Cached server-side for 10 min. Response shape matches
    templates/admin_pinterest_analytics.html."""
    now = time.time()
    cache = _analytics_cache
    if (cache["data"] is not None and cache["days"] == days
            and now - cache["ts"] < _ANALYTICS_TTL):
        return cache["data"]

    from routers.pinterest import _access_token as _pin_access_token, _read_token as _pin_read_token
    if not _pin_read_token():
        return {"error": "Pinterest not connected", "totals": {}, "per_pin": []}
    try:
        token = await _pin_access_token()
    except Exception as exc:
        return {"error": f"token: {exc}", "totals": {}, "per_pin": []}

    end_d = date.today()
    start_d = end_d - timedelta(days=max(1, min(days, 90)))
    start_s, end_s = start_d.isoformat(), end_d.isoformat()

    db = SessionLocal()
    try:
        pins = (
            db.query(PinterestPin)
            .filter(
                PinterestPin.status == "active",
                PinterestPin.pin_id.isnot(None),
                PinterestPin.pin_id != "",
            )
            .order_by(PinterestPin.created_at.desc())
            .limit(300)
            .all()
        )
        per_pin: list[dict] = []
        by_product: dict[str, Counter] = {}
        by_variant: dict[int, Counter] = {}
        totals = Counter()
        fetched = 0

        for p in pins:
            body, code = await _fetch_pin_analytics(p.pin_id, token, start_s, end_s)
            ok = code == 200
            sm = _extract_summary_metrics(body) if ok else {}
            if ok:
                fetched += 1

            imp = int(sm.get("IMPRESSION", 0) or 0)
            sav = int(sm.get("SAVE", 0) or 0)
            clk = int(sm.get("PIN_CLICK", 0) or 0)
            out = int(sm.get("OUTBOUND_CLICK", 0) or 0)

            totals["impressions"] += imp
            totals["saves"] += sav
            totals["pin_clicks"] += clk
            totals["outbound_clicks"] += out

            prod = by_product.setdefault(p.product_slug or "?", Counter())
            prod["pins"] += 1
            prod["impressions"] += imp
            prod["saves"] += sav
            prod["pin_clicks"] += clk
            prod["outbound_clicks"] += out

            vidx = int(p.variant_idx or 0)
            var = by_variant.setdefault(vidx, Counter())
            var["pins"] += 1
            var["impressions"] += imp
            var["saves"] += sav
            var["pin_clicks"] += clk
            var["outbound_clicks"] += out

            per_pin.append({
                "pin_id": p.pin_id,
                "product_slug": p.product_slug,
                "variant_idx": vidx,
                "impressions": imp,
                "saves": sav,
                "pin_clicks": clk,
                "outbound_clicks": out,
                "created_at": (p.created_at.isoformat() + "Z") if p.created_at else None,
                "fetched": ok,
            })
            await asyncio.sleep(0.15)  # gentle throttle

        data = {
            "days": days,
            "start": start_s,
            "end": end_s,
            "total_pins": len(pins),
            "fetched_pins": fetched,
            "totals": {
                "impressions": totals["impressions"],
                "saves": totals["saves"],
                "pin_clicks": totals["pin_clicks"],
                "outbound_clicks": totals["outbound_clicks"],
            },
            "by_variant": _agg_rows(by_variant, "variant_idx"),
            "by_product": _agg_rows(by_product, "product_slug"),
            "per_pin": per_pin,
        }
        cache.update({"ts": now, "days": days, "data": data})
        return data
    finally:
        db.close()
