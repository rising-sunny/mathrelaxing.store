import asyncio
import sys

import httpx

sys.path.insert(0, "/var/www/mathrelaxing.store")

from database import SessionLocal
from models.pinterest_pin import PinterestPin
from routers import pinterest as pin_api


DELETE_IDS = [
    "927037904566786203",  # older unlabeled Voronoi Organics image-pack pin
    "927037904567003586",  # duplicate Turing Coral; keep the framed labeled version
]


async def main():
    token = await pin_api._access_token()
    api_base = pin_api._api_base()
    with httpx.Client(timeout=60) as client:
        for pin_id in DELETE_IDS:
            resp = client.delete(f"{api_base}/pins/{pin_id}", headers={"Authorization": f"Bearer {token}"})
            print(pin_id, resp.status_code)
            if resp.status_code not in (200, 202, 204, 404):
                raise RuntimeError(resp.text[:500])

    db = SessionLocal()
    try:
        for pin_id in DELETE_IDS:
            rec = db.query(PinterestPin).filter(PinterestPin.pin_id == pin_id).first()
            if rec:
                rec.status = "deleted"
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
