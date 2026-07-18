"""Probe minimal inventory create on mathrelaxing to surface real error."""
import asyncio
import json
import os
import sys

import httpx

sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")
from dotenv import load_dotenv
from importlib import reload

load_dotenv(".env")
import services.ebay as ebay

reload(ebay)


async def put(sku, body):
    token = await ebay.get_access_token()
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.put(
            f"{ebay.API_BASE}/sell/inventory/v1/inventory_item/{sku}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Content-Language": "en-US",
            },
            json=body,
        )
    print("status", r.status_code)
    print(r.text[:800])
    return r.status_code


async def main():
    print("privilege", await ebay._get("/sell/account/v1/privilege"))
    print("payments", await ebay._get("/sell/account/v1/payments_program/EBAY_US/EBAY_PAYMENTS"))

    bodies = [
        (
            "minimal",
            {
                "availability": {"shipToLocationAvailability": {"quantity": 1}},
                "condition": "NEW",
                "product": {
                    "title": "MathRelaxing Test Digital Item",
                    "description": "Test digital download listing.",
                    "imageUrls": [
                        "https://mathrelaxing.store/static/bonanza/hyperbolic-gardens-digital.jpg"
                    ],
                },
            },
        ),
        (
            "with_aspects",
            {
                "availability": {"shipToLocationAvailability": {"quantity": 1}},
                "condition": "NEW",
                "product": {
                    "title": "MathRelaxing Hyperbolic Gardens Digital",
                    "description": "Digital coloring book download. Instant delivery by email.",
                    "aspects": {
                        "Brand": ["MathRelaxing"],
                        "Type": ["Digital Download"],
                    },
                    "imageUrls": [
                        "https://mathrelaxing.store/static/bonanza/hyperbolic-gardens-digital.jpg"
                    ],
                },
            },
        ),
    ]
    for name, body in bodies:
        print(f"\n=== {name} ===")
        await put(f"mr-test-{name}", body)

    # list inventory
    try:
        inv = await ebay._get("/sell/inventory/v1/inventory_item", {"limit": "5"})
        print("\ninventory", inv.get("total"), inv.get("inventoryItems"))
    except Exception as e:
        print("list inv", e)


asyncio.run(main())
