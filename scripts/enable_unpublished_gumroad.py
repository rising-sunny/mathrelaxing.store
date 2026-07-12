import asyncio
import os
import sys

import httpx

sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from dotenv import load_dotenv

load_dotenv(".env")

from database import SessionLocal
from models.product import DigitalProduct
from services import gumroad as gumroad_svc


async def main():
    token = gumroad_svc.get_access_token()
    product_map = gumroad_svc._load_map()
    db = SessionLocal()
    try:
        products = (
            db.query(DigitalProduct)
            .filter(DigitalProduct.active == True)
            .order_by(DigitalProduct.slug)
            .all()
        )
    finally:
        db.close()

    enabled = []
    already = []
    errors = []
    async with httpx.AsyncClient(timeout=20) as client:
        for product in products:
            gid = product_map.get(product.slug)
            if not gid:
                continue
            status = await gumroad_svc.get_listing_status(product)
            if status.get("status") == "published":
                already.append(product.slug)
                continue
            if status.get("status") != "unpublished":
                errors.append((product.slug, status.get("status"), status.get("error", "")))
                continue
            resp = await client.put(
                f"{gumroad_svc.API_BASE}/products/{gid}/enable",
                data={"access_token": token},
            )
            if resp.is_success:
                enabled.append(product.slug)
                print("ENABLED", product.slug)
            else:
                errors.append((product.slug, str(resp.status_code), resp.text[:200]))
            await asyncio.sleep(0.3)

    print("already_published", len(already))
    print("enabled_count", len(enabled))
    print("error_count", len(errors))
    for row in errors:
        print("ERROR", row)


if __name__ == "__main__":
    asyncio.run(main())
