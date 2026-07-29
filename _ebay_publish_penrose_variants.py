import asyncio
import os
import re
import math
from pathlib import Path

from dotenv import load_dotenv
import httpx
import sys

sys.path.append(r"c:\repos\Etsy_mathrelaxing\printify")
import printify_publish as pp

ROOT = Path(os.getenv("STORE_ROOT", os.getcwd()))
load_dotenv(ROOT / ".env")
os.chdir(ROOT)

import services.ebay as ebay
from _ebay_publish_physical_batch1 import (
    gross_up, net_after, download_images, safe_title,
    get_or_create_physical_fulfillment_policy, get_payment_return_policies
)

PUBLIC = os.getenv("PUBLIC_BASE_URL", "https://mathrelaxing.store").rstrip("/")

PROD = {
    "group_sku": "mr-phys-penrose-poster-group",
    "title": "Penrose Tiling Poster | Geometric Math Line Art Print | Scandinavian Wall Art",
    "description_html": """
<div>
<h2>Penrose Tiling Poster — Geometric Math Line Art</h2>
<p>An aperiodic Penrose tiling — a pattern of two rhombi that fills the plane and never exactly repeats, built on the golden ratio. Clean black-and-white line art on a warm ivory ground. Part of the Geometric Tilings series.</p>
<ul>
<li><b>Physical printed poster</b> — ships to your door (not a download)</li>
<li>Multiple sizes available</li>
<li>Matte poster paper, giclée-quality print on demand</li>
<li>Charcoal line work · frame not included</li>
</ul>
<h3>Shipping &amp; production</h3>
<p>Made to order (print on demand). Typical production 7–10 business days, then transit. Ships from our print partner. No digital file is included with this listing.</p>
<p>MathRelaxing — mathematics as wall art.</p>
</div>
""",
    "category_id": "360",
    "aspects": {
        "Type": ["Poster"],
        "Style": ["Minimalist", "Abstract", "Modern"],
        "Subject": ["Geometric", "Mathematics"],
        "Material": ["Paper"],
        "Color": ["Black", "Ivory"],
        "Features": ["Unframed"],
    },
    "image_urls_etsy": [
        "https://i.etsystatic.com/66586766/r/il/85f7b4/8269247698/il_fullxfull.8269247698_1edm.jpg",
        "https://i.etsystatic.com/66586766/r/il/419534/8269248172/il_fullxfull.8269248172_4o4g.jpg",
        "https://i.etsystatic.com/66586766/r/il/56eeda/8317162693/il_fullxfull.8317162693_el22.jpg",
        "https://i.etsystatic.com/66586766/r/il/f39975/8317163357/il_fullxfull.8317163357_5j4f.jpg",
        "https://i.etsystatic.com/66586766/r/il/b92ee7/8317163769/il_fullxfull.8317163769_567d.jpg",
    ],
    # Variants will be populated dynamically from Printify
    "variants": []
}

async def withdraw_old_listing():
    old_sku = "mr-phys-penrose-poster-18x24"
    offers = await ebay.get_offers_for_sku(old_sku)
    for o in offers:
        if o.get("status") == "PUBLISHED":
            try:
                print(f"Withdrawing old listing: {o['offerId']}")
                await ebay.withdraw_offer(o['offerId'])
                print("Successfully withdrawn.")
            except Exception as e:
                print(f"Error withdrawing: {e}")

async def main():
    if not ebay.is_configured():
        raise SystemExit("eBay not configured")
    
    print("1. Withdrawing old single-variant listing...")
    await withdraw_old_listing()

    fulfillment_id = await get_or_create_physical_fulfillment_policy()
    payment_id, return_id = await get_payment_return_policies()

    print("2. Downloading images...")
    images = await download_images(PROD["group_sku"], PROD["image_urls_etsy"])

    print("2.5 Fetching variants from Printify...")
    res = pp._req("GET", f"/shops/{pp.SHOP_ID}/products.json?limit=50")
    products = res.get("data", [])
    p = next((x for x in products if str(x.get("external", {}).get("id")) == "4536912921"), None)
    if not p:
        raise RuntimeError("Could not find Printify product matching Etsy ID 4536912921")
    
    full = pp._req("GET", f"/shops/{pp.SHOP_ID}/products/{p['id']}.json")
    for v in full.get("variants", []):
        if v.get("is_enabled"):
            title = v['title'].replace('\u2033', 'in')
            size_part = title.split('/')[0].strip()
            size_raw = size_part.replace('in', '').replace(' ', '')
            
            # Reformat to "W x H in" for eBay consistency
            parts = size_raw.split('x')
            if len(parts) == 2:
                size_label = f"{parts[0]} x {parts[1]} in"
            else:
                size_label = size_part
                
            sku = f"mr-phys-penrose-poster-{size_raw}"
            PROD["variants"].append({
                "sku": sku,
                "size_label": size_label,
                "base_price": v['price'] / 100
            })
    
    print(f"Found {len(PROD['variants'])} variants on Printify.")

    print("3. Creating inventory items and offers for variants...")
    variant_skus = []
    
    for v in PROD["variants"]:
        sku = v["sku"]
        variant_skus.append(sku)
        list_price = gross_up(v["base_price"])
        print(f"   -> Processing {sku} (price: ${list_price})")
        
        # Create inventory item for variant
        inv_body = {
            "product": {
                "title": safe_title(PROD["title"]),
                "description": PROD["description_html"].strip(),
                "aspects": {"Size": [v["size_label"]]},
                "imageUrls": images,
            },
            "condition": "NEW",
            "availability": {
                "shipToLocationAvailability": {"quantity": 1}
            }
        }
        await ebay._put(f"/sell/inventory/v1/inventory_item/{sku}", inv_body)
        
        # Create offer for variant
        offers = await ebay.get_offers_for_sku(sku)
        offer_body = {
            "sku": sku,
            "marketplaceId": ebay.MARKETPLACE_ID,
            "format": "FIXED_PRICE",
            "availableQuantity": 1,
            "categoryId": PROD["category_id"],
            "listingDescription": PROD["description_html"].strip(),
            "listingPolicies": {
                "fulfillmentPolicyId": fulfillment_id,
                "paymentPolicyId": payment_id,
                "returnPolicyId": return_id,
            },
            "pricingSummary": {
                "price": {"value": f"{list_price:.2f}", "currency": "USD"},
            },
            "merchantLocationKey": os.getenv("EBAY_MERCHANT_LOCATION_KEY", "default_location"),
        }
        
        if offers:
            offer_id = offers[0]["offerId"]
            try:
                await ebay._put(f"/sell/inventory/v1/offer/{offer_id}", offer_body)
            except Exception as e:
                pass
        else:
            await ebay._post("/sell/inventory/v1/offer", offer_body)
            
    print("4. Creating inventory item group...")
    await ebay.upsert_inventory_item_group(
        group_id=PROD["group_sku"],
        title=safe_title(PROD["title"]),
        description=PROD["description_html"].strip(),
        image_urls=images,
        variant_skus=variant_skus,
        aspects=PROD["aspects"],
        varies_by={
            "aspectsImageVariesBy": [],
            "specifications": [
                {
                    "name": "Size",
                    "values": [v["size_label"] for v in PROD["variants"]]
                }
            ]
        }
    )
    
    print("5. Publishing offer group...")
    try:
        r = await ebay.publish_offer_group(PROD["group_sku"])
        print("Publish response:", r)
        print("SUCCESS! Published Listing ID:", r.get("listingId"))
        print(f"URL: https://www.ebay.com/itm/{r.get('listingId')}")
    except Exception as e:
        import traceback
        print("Failed to publish group:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
