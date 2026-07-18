"""Create business policies after opt-in; diagnose Managed Payments."""
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


async def post_raw(path, body):
    token = await ebay.get_access_token()
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{ebay.API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Content-Language": "en-US",
            },
            json=body,
        )
    return r.status_code, r.text


async def get_raw(path, params=None):
    token = await ebay.get_access_token()
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"{ebay.API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
        )
    return r.status_code, r.text


async def main():
    print("=== payments program ===")
    print(await get_raw("/sell/account/v1/payments_program/EBAY_US/EBAY_PAYMENTS"))

    print("\n=== fulfillment create ===")
    print(
        await post_raw(
            "/sell/account/v1/fulfillment_policy",
            {
                "name": "Digital Delivery - Free",
                "description": "Instant digital delivery via email. No physical shipping.",
                "marketplaceId": "EBAY_US",
                "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES", "default": True}],
                "handlingTime": {"value": 1, "unit": "DAY"},
                "shippingOptions": [
                    {
                        "optionType": "DOMESTIC",
                        "costType": "FLAT_RATE",
                        "shippingServices": [
                            {
                                "sortOrder": 1,
                                "shippingCarrierCode": "Other",
                                "shippingServiceCode": "Other",
                                "shippingCost": {"value": "0.0", "currency": "USD"},
                                "additionalShippingCost": {"value": "0.0", "currency": "USD"},
                                "freeShipping": True,
                                "buyerResponsibleForShipping": False,
                            }
                        ],
                    }
                ],
                "globalShipping": False,
                "freightShipping": False,
                "localPickup": False,
                "pickupDropOff": False,
            },
        )
    )

    print("\n=== return create ===")
    print(
        await post_raw(
            "/sell/account/v1/return_policy",
            {
                "name": "No Returns - Digital",
                "marketplaceId": "EBAY_US",
                "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES", "default": True}],
                "returnsAccepted": False,
            },
        )
    )

    print("\n=== payment create (managed, no methods) ===")
    print(
        await post_raw(
            "/sell/account/v1/payment_policy",
            {
                "name": "eBay Managed Payments",
                "marketplaceId": "EBAY_US",
                "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES", "default": True}],
                "immediatePay": True,
            },
        )
    )

    print("\n=== list policies ===")
    for kind in ("fulfillment_policy", "payment_policy", "return_policy"):
        print(kind, await get_raw(f"/sell/account/v1/{kind}", {"marketplace_id": "EBAY_US"}))

    print("\n=== privilege ===")
    print(await get_raw("/sell/account/v1/privilege"))


asyncio.run(main())
