#!/usr/bin/env python3
"""
Create all MathRelaxing digital products on Whop and store the plan IDs in the DB.
Run once: python3 create_whop_products.py
"""
import asyncio, os, sys, time
sys.path.insert(0, '.')
os.chdir('/var/www/mathrelaxing.store')

from dotenv import load_dotenv
load_dotenv('.env')

import httpx
from database import SessionLocal
from models.product import DigitalProduct

WHOP_KEY = os.getenv("WHOP_API_KEY", "")
BIZ_ID   = os.getenv("WHOP_COMPANY_ID", "")
BASE     = "https://api.whop.com/api/v1"

HEADERS  = {
    "Authorization": f"Bearer {WHOP_KEY}",
    "Content-Type": "application/json",
}

# Product descriptions by type
TYPE_DESC = {
    "image_pack": (
        "High-resolution 4K mathematical art images generated from real equations. "
        "Includes portrait (3200×4000), landscape (4000×3200), and square (3200×3200) orientations. "
        "Instant download. Personal use license."
    ),
    "animation_pack": (
        "Seamlessly looping 4K mathematical animations generated from real equations. "
        "Available in 1080p30, 1080p60, 4K30, and 4K60 formats. "
        "Perfect for video backgrounds, digital art installations, and content creation. "
        "Instant download. Personal use license."
    ),
    "creator_assets": (
        "Complete creator asset pack: 4K images, seamless loop animations, transparent overlays, "
        "and source parameters. Generated from real mathematical equations. "
        "Commercial use license included."
    ),
}


async def create_product(client: httpx.AsyncClient, name: str, description: str) -> dict:
    r = await client.post(
        f"{BASE}/products",
        headers=HEADERS,
        json={
            "title": name,
            "visibility": "visible",
            "company_id": BIZ_ID,
            "description": description,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


async def create_plan(client: httpx.AsyncClient, product_id: str, price: float) -> dict:
    r = await client.post(
        f"{BASE}/plans",
        headers=HEADERS,
        json={
            "product_id": product_id,
            "plan_type": "one_time",
            "initial_price": price,
            "currency": "usd",
            "billing_period": 0,
            "company_id": BIZ_ID,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


async def main():
    db = SessionLocal()
    products = db.query(DigitalProduct).filter(
        DigitalProduct.active == True,
        DigitalProduct.whop_product_id == None,
    ).order_by(DigitalProduct.id).all()

    print(f"Found {len(products)} products to create on Whop.\n")

    async with httpx.AsyncClient() as client:
        for p in products:
            desc = TYPE_DESC.get(p.product_type, TYPE_DESC["image_pack"])
            print(f"[{p.id:02d}] {p.name}  (${p.price_usd})")

            try:
                # Create product
                wp = await create_product(client, p.name, desc)
                whop_product_id = wp["id"]
                print(f"     ✓ product: {whop_product_id}")

                await asyncio.sleep(0.3)  # be gentle with rate limits

                # Create plan
                plan = await create_plan(client, whop_product_id, p.price_usd)
                whop_plan_id = plan["id"]
                checkout_url = plan.get("purchase_url") or plan.get("direct_link", "")
                print(f"     ✓ plan:    {whop_plan_id}")
                print(f"     ✓ url:     {checkout_url}")

                # Save to DB
                p.whop_product_id  = whop_product_id
                p.whop_plan_id     = whop_plan_id
                p.whop_checkout_url = checkout_url
                db.commit()

                await asyncio.sleep(0.3)

            except Exception as e:
                print(f"     ✗ ERROR: {e}")
                db.rollback()

    db.close()
    print("\nDone.")

    # Print summary
    db2 = SessionLocal()
    done = db2.query(DigitalProduct).filter(DigitalProduct.whop_plan_id != None).all()
    print(f"\n{'Slug':<45} {'Whop Plan':>24}  {'Price':>6}")
    print("-" * 80)
    for p in done:
        print(f"{p.slug:<45} {p.whop_plan_id:>24}  ${p.price_usd:>5}")
    db2.close()


if __name__ == "__main__":
    # Update the existing test product (already created manually)
    db = SessionLocal()
    existing = db.query(DigitalProduct).filter(
        DigitalProduct.slug == "strange-attractors-image-pack"
    ).first()
    if existing and not existing.whop_product_id:
        existing.whop_product_id  = "prod_ieB2Tw1znoaCG"
        existing.whop_plan_id     = "plan_b9mhBRnR3yAB0"
        existing.whop_checkout_url = "https://whop.com/checkout/plan_b9mhBRnR3yAB0"
        db.commit()
        print("Linked existing test product → strange-attractors-image-pack")
    db.close()

    asyncio.run(main())
