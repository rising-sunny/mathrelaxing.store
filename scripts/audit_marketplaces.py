import asyncio
import json
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
    db = SessionLocal()
    try:
        products = (
            db.query(DigitalProduct)
            .filter(DigitalProduct.active == True)
            .order_by(DigitalProduct.product_type, DigitalProduct.slug)
            .all()
        )

        gumroad_map = {}
        if os.path.exists(".gumroad_products.json"):
            with open(".gumroad_products.json", "r", encoding="utf-8") as fh:
                gumroad_map = json.load(fh)

        print("SUMMARY")
        print("active_products", len(products))
        print("gumroad_connected", gumroad_svc.is_configured())
        print("gumroad_map_count", len(gumroad_map))
        print("whop_with_plan", sum(1 for p in products if p.whop_plan_id))
        print("whop_missing", sum(1 for p in products if not p.whop_plan_id))

        print("\nGUMROAD STATUS")
        for p in products:
            try:
                status = await gumroad_svc.get_listing_status(p)
            except Exception as exc:
                status = {"status": "error", "error": str(exc)[:160]}
            print(
                " | ".join(
                    [
                        p.slug,
                        p.name,
                        p.product_type,
                        f"${p.price_usd}",
                        status.get("status", ""),
                        "mapped=" + str(bool(gumroad_map.get(p.slug))),
                        "url=" + str(bool(status.get("gumroad_url"))),
                        ("err=" + status.get("error", "")) if status.get("error") else "",
                    ]
                )
            )

        print("\nWHOP STATUS")
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            for p in products:
                checkout_ok = False
                checkout_status = ""
                if p.whop_checkout_url:
                    try:
                        resp = await client.get(p.whop_checkout_url)
                        checkout_status = str(resp.status_code)
                        checkout_ok = resp.status_code in (200, 301, 302, 303, 307, 308)
                    except Exception as exc:
                        checkout_status = "error:" + str(exc)[:80]
                print(
                    " | ".join(
                        [
                            p.slug,
                            p.name,
                            p.product_type,
                            f"${p.price_usd}",
                            "product=" + str(bool(p.whop_product_id)),
                            "plan=" + str(bool(p.whop_plan_id)),
                            "checkout=" + str(bool(p.whop_checkout_url)),
                            "checkout_ok=" + str(checkout_ok),
                            "http=" + checkout_status,
                        ]
                    )
                )
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
