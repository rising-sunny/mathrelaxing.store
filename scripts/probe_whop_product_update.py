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


async def main():
    token = os.getenv("WHOP_API_KEY", "")
    db = SessionLocal()
    try:
        product = (
            db.query(DigitalProduct)
            .filter(DigitalProduct.active == True, DigitalProduct.whop_product_id.isnot(None))
            .order_by(DigitalProduct.slug)
            .first()
        )
        if not product:
            print("no product")
            return
        product_id = product.whop_product_id
        print("product", product.slug, product_id)
    finally:
        db.close()

    candidates = [
        ("v2", f"https://api.whop.com/api/v2/products/{product_id}"),
        ("v1", f"https://api.whop.com/api/v1/products/{product_id}"),
        ("root", f"https://api.whop.com/api/products/{product_id}"),
    ]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        for name, url in candidates:
            get_resp = await client.get(url, headers=headers)
            print("GET", name, get_resp.status_code)
            if get_resp.status_code < 400:
                body = get_resp.json()
                print("keys", sorted(list(body.keys()))[:12])
            patch_resp = await client.patch(
                url,
                headers=headers,
                json={"metadata": {"mathrelaxing_probe": "ok"}},
            )
            print("PATCH", name, patch_resp.status_code, patch_resp.text[:160])


if __name__ == "__main__":
    asyncio.run(main())
