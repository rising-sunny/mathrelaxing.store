"""Inspect held listings vs OK ones for EDI policy issues."""
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path("/var/www/mathrelaxing.store")
load_dotenv(ROOT / ".env")
os.chdir(ROOT)

import services.ebay as ebay  # noqa: E402


async def dump(slug: str):
    sku = f"mr-{slug}"
    inv = await ebay._get(f"/sell/inventory/v1/inventory_item/{sku}")
    prod = inv.get("product") or {}
    offers = await ebay.get_offers_for_sku(sku)
    o = offers[0] if offers else {}
    listing = o.get("listing") or {}
    print("=" * 60)
    print(slug)
    print("title:", prod.get("title"))
    print(
        "hold:",
        listing.get("listingOnHold"),
        "status:",
        listing.get("listingStatus"),
        "listingId:",
        listing.get("listingId") or o.get("listingId"),
    )
    print("categoryId:", o.get("categoryId"))
    print("aspects:", json.dumps(prod.get("aspects"), indent=2))
    print("merchantLocationKey:", o.get("merchantLocationKey"))
    print("listingPolicies:", json.dumps(o.get("listingPolicies"), indent=2))
    print("format:", o.get("format"), "qty:", o.get("availableQuantity"))
    desc = prod.get("description") or ""
    print("DESC:\n", desc)
    print()


async def main():
    # also fetch fulfillment policy details
    try:
        fp = await ebay._get(
            "/sell/account/v1/fulfillment_policy",
            {"marketplace_id": "EBAY_US"},
        )
        print("FULFILLMENT POLICIES:")
        for p in fp.get("fulfillmentPolicies") or []:
            print(
                json.dumps(
                    {
                        "id": p.get("fulfillmentPolicyId"),
                        "name": p.get("name"),
                        "handlingTime": p.get("handlingTime"),
                        "shippingOptions": p.get("shippingOptions"),
                        "globalShipping": p.get("globalShipping"),
                        "freightShipping": p.get("freightShipping"),
                        "localPickup": p.get("localPickup"),
                    },
                    indent=2,
                )
            )
    except Exception as e:
        print("fp err", e)

    for slug in [
        "fractal-flora-coloring-book-digital",
        "hyperbolic-gardens-digital",
        "sacred-geometry-coloring-book-digital",
        "sacred-harmonics-digital",
        "celtic-knot-coloring-book-digital",
        "bauhaus-print-set",
    ]:
        try:
            await dump(slug)
        except Exception as e:
            print(slug, "ERR", e)


if __name__ == "__main__":
    asyncio.run(main())
