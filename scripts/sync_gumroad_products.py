import asyncio
import os
import sys

sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from dotenv import load_dotenv

load_dotenv(".env")

from database import SessionLocal
from models.product import DigitalProduct
from services import gumroad as gumroad_svc


async def main():
    before_map = gumroad_svc._load_map()
    db = SessionLocal()
    try:
        products = (
            db.query(DigitalProduct)
            .filter(DigitalProduct.active == True)
            .order_by(DigitalProduct.product_type, DigitalProduct.slug)
            .all()
        )
    finally:
        db.close()

    print("products", len(products))
    print("mapped_before", len(before_map))
    created = []
    updated = []
    errors = []

    for idx, product in enumerate(products, 1):
        existed = bool(before_map.get(product.slug))
        try:
            result = await gumroad_svc.publish_product(product)
            row = {
                "slug": product.slug,
                "id": result.get("gumroad_id"),
                "url": result.get("gumroad_url"),
            }
            if existed:
                updated.append(row)
                print(f"[{idx:02d}] UPDATED {product.slug} {row['url'] or ''}")
            else:
                created.append(row)
                print(f"[{idx:02d}] CREATED {product.slug} {row['url'] or ''}")
        except Exception as exc:
            errors.append({"slug": product.slug, "error": str(exc)[:300]})
            print(f"[{idx:02d}] ERROR {product.slug}: {exc}")
        await asyncio.sleep(0.4)

    after_map = gumroad_svc._load_map()
    print("mapped_after", len(after_map))
    print("created_count", len(created))
    print("updated_count", len(updated))
    print("error_count", len(errors))
    if created:
        print("created_slugs", ",".join(row["slug"] for row in created))
    if errors:
        for row in errors:
            print("ERROR_DETAIL", row["slug"], row["error"])


if __name__ == "__main__":
    asyncio.run(main())
