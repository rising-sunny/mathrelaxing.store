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


API_KEY = os.getenv("WHOP_API_KEY", "")
BASE = "https://api.whop.com/api/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


async def fetch_product(client, whop_product_id):
    resp = await client.get(f"{BASE}/products/{whop_product_id}", headers=HEADERS, timeout=20)
    if resp.status_code >= 400:
        return {"id": whop_product_id, "status_code": resp.status_code, "error": resp.text[:200]}
    return resp.json()


async def main():
    db = SessionLocal()
    try:
        rows = (
            db.query(DigitalProduct)
            .filter(DigitalProduct.active == True)
            .order_by(DigitalProduct.product_type, DigitalProduct.slug)
            .all()
        )
        print("DB active digital products:", len(rows))
        print("DB with Whop product id:", sum(1 for p in rows if p.whop_product_id))
        print("DB with Whop plan id:", sum(1 for p in rows if p.whop_plan_id))
        print("DB with checkout url:", sum(1 for p in rows if p.whop_checkout_url))
        print()

        async with httpx.AsyncClient(timeout=20) as client:
            visible = 0
            invisible = 0
            missing_remote = 0
            print("SLUG | TYPE | REMOTE_VISIBILITY | PLAN | CHECKOUT | HEADLINE")
            for p in rows:
                if not p.whop_product_id:
                    print(f"{p.slug} | {p.product_type} | no_product_id | {bool(p.whop_plan_id)} | {bool(p.whop_checkout_url)} |")
                    continue
                data = await fetch_product(client, p.whop_product_id)
                if data.get("status_code"):
                    missing_remote += 1
                    print(f"{p.slug} | {p.product_type} | error:{data['status_code']} | {bool(p.whop_plan_id)} | {bool(p.whop_checkout_url)} | {data.get('error','')}")
                    continue
                visibility = data.get("visibility") or ""
                if visibility == "visible":
                    visible += 1
                else:
                    invisible += 1
                headline = (data.get("headline") or "").replace("\n", " ")[:90]
                print(f"{p.slug} | {p.product_type} | {visibility} | {bool(p.whop_plan_id)} | {bool(p.whop_checkout_url)} | {headline}")
            print()
            print("remote_visible:", visible)
            print("remote_not_visible:", invisible)
            print("remote_errors:", missing_remote)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
