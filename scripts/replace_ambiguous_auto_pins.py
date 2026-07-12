import asyncio
import sys
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

sys.path.insert(0, "/var/www/mathrelaxing.store")

from database import SessionLocal
from models.pinterest_pin import PinterestPin
from routers import pinterest as pin_api


STAMP = "product-label-v2-20260604"


def cachebust(url: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["v"] = STAMP
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def should_replace(pin: PinterestPin) -> bool:
    if pin.status != "active" or not pin.pin_id:
        return False
    image_url = pin.image_url or ""
    return "/api/render/pinterest" in image_url


async def main():
    token = await pin_api._access_token()
    api_base = pin_api._api_base()

    db = SessionLocal()
    try:
        old_pins = (
            db.query(PinterestPin)
            .filter(PinterestPin.status == "active", PinterestPin.pin_id.isnot(None))
            .order_by(PinterestPin.created_at.desc())
            .all()
        )
        old_pins = [pin for pin in old_pins if should_replace(pin)]
        print("to_replace", len(old_pins))
        for pin in old_pins:
            print("OLD", pin.pin_id, pin.product_type, pin.product_slug, pin.variant_idx, pin.title)
    finally:
        db.close()

    replaced = []
    with httpx.Client(timeout=90) as client:
        for old in old_pins:
            new_image_url = cachebust(old.image_url or "")
            body = {
                "board_id": old.board_id,
                "title": (old.title or "")[:100],
                "description": old.description or "",
                "link": old.link_url or "",
                "media_source": {
                    "source_type": "image_url",
                    "url": new_image_url,
                    "is_standard": True,
                },
            }
            create = client.post(
                f"{api_base}/pins",
                headers={"Authorization": f"Bearer {token}"},
                json=body,
            )
            if create.status_code >= 400:
                raise RuntimeError(f"create replacement for {old.pin_id} HTTP {create.status_code}: {create.text[:500]}")
            created = create.json() if create.content else {}
            new_pin_id = created.get("id")
            if not new_pin_id:
                raise RuntimeError(f"replacement for {old.pin_id} missing id: {created}")

            delete = client.delete(
                f"{api_base}/pins/{old.pin_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if delete.status_code not in (200, 202, 204, 404):
                raise RuntimeError(f"delete old {old.pin_id} HTTP {delete.status_code}: {delete.text[:500]}")

            db = SessionLocal()
            try:
                current = db.query(PinterestPin).filter(PinterestPin.id == old.id).first()
                if current:
                    current.status = "deleted"
                db.add(
                    PinterestPin(
                        product_slug=old.product_slug,
                        product_type=old.product_type,
                        variant_idx=old.variant_idx,
                        board_id=old.board_id,
                        pin_id=new_pin_id,
                        image_url=new_image_url,
                        title=old.title,
                        description=old.description,
                        link_url=old.link_url,
                        status="active",
                        created_at=datetime.utcnow(),
                    )
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

            replaced.append((old.pin_id, new_pin_id, old.product_slug, old.title))
            print("REPLACED", old.pin_id, "->", new_pin_id, old.product_slug, old.title)

    print("replaced_count", len(replaced))


if __name__ == "__main__":
    asyncio.run(main())
