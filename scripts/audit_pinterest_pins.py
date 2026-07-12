import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, "/var/www/mathrelaxing.store")

from database import SessionLocal
from models.pinterest_pin import PinterestPin
from routers import pinterest as pin_api


REPORT = Path("/var/www/mathrelaxing.store/pinterest_pin_audit_report.json")


def safe_text(value, limit=140):
    value = (value or "").replace("\n", " ").strip()
    return value if len(value) <= limit else value[: limit - 3].rstrip() + "..."


async def get_json(client, url, token, params=None):
    resp = await client.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
    )
    return resp.status_code, resp.text, resp.json() if resp.content else {}


def media_summary(item):
    media = item.get("media") or {}
    source = item.get("media_source") or {}
    keys = sorted(media.keys()) if isinstance(media, dict) else []
    source_keys = sorted(source.keys()) if isinstance(source, dict) else []
    media_type = ""
    if isinstance(media, dict):
        media_type = media.get("media_type") or media.get("type") or ""
    has_images = isinstance(media, dict) and bool(media.get("images"))
    has_video = isinstance(media, dict) and (
        bool(media.get("video_url"))
        or bool(media.get("duration"))
        or "video" in str(media_type).lower()
    )
    images = []
    if isinstance(media, dict) and isinstance(media.get("images"), dict):
        for key, value in media["images"].items():
            if isinstance(value, dict):
                images.append({
                    "key": key,
                    "url": value.get("url"),
                    "width": value.get("width"),
                    "height": value.get("height"),
                })
    return {
        "media_type": media_type,
        "media_keys": keys,
        "media_source_keys": source_keys,
        "images": images,
        "video_url": media.get("video_url") if isinstance(media, dict) else None,
        "has_images": has_images,
        "has_video": has_video,
        "has_any_media": bool(media) or bool(source),
    }


async def main():
    token = await pin_api._access_token()
    api_base = pin_api._api_base()
    report = {
        "api_base": api_base,
        "boards": [],
        "remote_pins": [],
        "local_active_records": [],
        "suspect_remote_pins": [],
        "local_missing_remote": [],
    }

    async with httpx.AsyncClient(timeout=60) as client:
        boards = []
        bookmark = None
        while True:
            params = {"page_size": 100}
            if bookmark:
                params["bookmark"] = bookmark
            status, text, body = await get_json(client, f"{api_base}/boards", token, params)
            if status >= 400:
                raise RuntimeError(f"boards HTTP {status}: {text[:300]}")
            items = body.get("items") or []
            boards.extend(items)
            bookmark = body.get("bookmark")
            if not bookmark:
                break

        report["boards"] = [
            {"id": b.get("id"), "name": b.get("name"), "privacy": b.get("privacy")}
            for b in boards
        ]

        remote_by_id = {}
        for board in boards:
            board_id = board.get("id")
            board_name = board.get("name")
            if not board_id:
                continue
            bookmark = None
            while True:
                params = {"page_size": 100}
                if bookmark:
                    params["bookmark"] = bookmark
                status, text, body = await get_json(
                    client, f"{api_base}/boards/{board_id}/pins", token, params
                )
                if status >= 400:
                    report["remote_pins"].append({
                        "board_id": board_id,
                        "board_name": board_name,
                        "error": f"HTTP {status}: {text[:300]}",
                    })
                    break
                for item in body.get("items") or []:
                    link = item.get("link") or ""
                    desc = item.get("description") or ""
                    title = item.get("title") or ""
                    looks_ours = (
                        "mathrelaxing.store" in link
                        or "mathrelaxing.store" in desc.lower()
                        or "MathRelaxing" in title
                    )
                    if not looks_ours:
                        continue
                    summary = media_summary(item)
                    row = {
                        "id": item.get("id"),
                        "board_id": board_id,
                        "board_name": board_name,
                        "title": safe_text(title),
                        "link": link,
                        **summary,
                    }
                    remote_by_id[row["id"]] = row
                    report["remote_pins"].append(row)
                    if not summary["has_any_media"] or (
                        not summary["has_images"] and not summary["has_video"]
                    ):
                        report["suspect_remote_pins"].append(row)
                bookmark = body.get("bookmark")
                if not bookmark:
                    break

    db = SessionLocal()
    try:
        records = (
            db.query(PinterestPin)
            .filter(PinterestPin.status == "active")
            .order_by(PinterestPin.created_at.desc())
            .all()
        )
        for rec in records:
            row = {
                "pin_id": rec.pin_id,
                "product_slug": rec.product_slug,
                "product_type": rec.product_type,
                "variant_idx": rec.variant_idx,
                "title": safe_text(rec.title),
                "image_url": rec.image_url,
                "link_url": rec.link_url,
                "created_at": rec.created_at.isoformat() if rec.created_at else None,
                "remote_found": bool(rec.pin_id and rec.pin_id in remote_by_id),
            }
            report["local_active_records"].append(row)
            if rec.pin_id and rec.pin_id not in remote_by_id:
                report["local_missing_remote"].append(row)
    finally:
        db.close()

    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print("boards", len(report["boards"]))
    print("remote_mathrelaxing_pins", len(report["remote_pins"]))
    print("suspect_remote_pins", len(report["suspect_remote_pins"]))
    print("local_active_records", len(report["local_active_records"]))
    print("local_missing_remote", len(report["local_missing_remote"]))
    for row in report["suspect_remote_pins"][:30]:
        print("SUSPECT", row.get("id"), row.get("board_name"), row.get("title"), row.get("link"), row.get("media_keys"), row.get("media_source_keys"))
    for row in report["local_missing_remote"][:30]:
        print("LOCAL_MISSING", row.get("pin_id"), row.get("product_slug"), row.get("title"))
    print("report", REPORT)


if __name__ == "__main__":
    asyncio.run(main())
