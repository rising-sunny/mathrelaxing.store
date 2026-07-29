import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Setup paths and environment
ROOT = Path(os.getenv("STORE_ROOT", os.getcwd()))
load_dotenv(ROOT / ".env")

# Load eBay service
sys.path.append(str(ROOT))
from services import ebay, lulu

# Load Printify service
sys.path.append(r"c:\repos\Etsy_mathrelaxing\printify")
import printify_publish as pp

SYNCED_DB = ROOT / "orders_synced.json"

# Map eBay SKU prefixes to Etsy Listing IDs (which Printify uses as external IDs)
# NOTE: Only Printify products go here. Lulu books are omitted so they are not sent to Printify.
SKU_TO_ETSY_MAP = {
    "mr-phys-penrose-poster": "4536912921",
    "mr-phys-euler-poster": "4536912943",
    "mr-phys-golden-ratio-sticker": "4540933093",
    "mr-phys-fourier-poster": "4540138384",
    "mr-phys-bauhaus-poster": "4540115383"
}

# Map eBay SKU prefixes to Lulu product slugs
SKU_TO_LULU_SLUG = {
    "mr-phys-fractal-flora-book": "mathematical-tangle-art-coloring-book",
    "mr-phys-hyperbolic-gardens-book": "hyperbolic-gardens-coloring-book"
}

def load_synced() -> set:
    if SYNCED_DB.exists():
        with open(SYNCED_DB, "r") as f:
            return set(json.load(f))
    return set()

def save_synced(synced: set):
    with open(SYNCED_DB, "w") as f:
        json.dump(list(synced), f, indent=2)

def fetch_printify_products():
    print("Fetching Printify products catalog...")
    res = pp._req("GET", f"/shops/{pp.SHOP_ID}/products.json?limit=50")
    return res.get("data", [])

def match_printify_variant(product, size_raw: str):
    """Find the specific variant ID based on size_raw like '18x24'."""
    full = pp._req("GET", f"/shops/{pp.SHOP_ID}/products/{product['id']}.json")
    for v in full.get("variants", []):
        if not v.get("is_enabled"):
            continue
        title = v['title'].replace('\u2033', 'in')
        size_part = title.split('/')[0].strip()
        v_size_raw = size_part.replace('in', '').replace(' ', '')
        if v_size_raw == size_raw:
            return v['id']
    return None

async def sync_orders():
    print("Checking for new eBay orders...")
    # Get recent paid orders that are NOT_STARTED or IN_PROGRESS for fulfillment
    try:
        r = await ebay._get("/sell/fulfillment/v1/order", {
            "limit": 50
        })
    except Exception as e:
        import traceback
        print("Failed to fetch eBay orders:")
        traceback.print_exc()
        return

    orders = r.get("orders", [])
    
    orders = r.get("orders", [])
    
    # Filter locally
    orders = [o for o in orders if o.get("orderFulfillmentStatus") in ("NOT_STARTED", "IN_PROGRESS")]
    
    if not orders:
        print("No new unfulfilled orders found.")
        return
        
    print(f"Found {len(orders)} unfulfilled eBay orders.")

    synced = load_synced()
    printify_products = None

    for order in orders:
        order_id = order["orderId"]
        if order_id in synced:
            continue

        print(f"\nProcessing Order ID: {order_id}")
        
        # Collect print-on-demand items
        physical_lines = []
        for line in order.get("lineItems", []):
            sku = line.get("sku", "")
            if sku.startswith("mr-phys-"):
                physical_lines.append(line)
                
        if not physical_lines:
            print("No physical print-on-demand items in this order. Skipping.")
            synced.add(order_id)
            continue
            
        printify_line_items = []
        lulu_line_items = []
        
        # Lazy load Printify products if we need them
        printify_products = None

        for line in physical_lines:
            sku = line["sku"]
            quantity = line.get("quantity", 1)
            
            # e.g. mr-phys-penrose-poster-18x24 -> prefix: mr-phys-penrose-poster, size: 18x24
            # e.g. mr-phys-fractal-flora-book -> prefix: mr-phys-fractal-flora-book, size: (none, or book)
            parts = sku.rsplit("-", 1)
            prefix, size_raw = (parts[0], parts[1]) if len(parts) == 2 else (sku, "")
            
            # 1. Check if it's a Printify product
            etsy_id = SKU_TO_ETSY_MAP.get(prefix)
            if etsy_id:
                if printify_products is None:
                    printify_products = fetch_printify_products()
                p = next((x for x in printify_products if str(x.get("external", {}).get("id")) == etsy_id), None)
                if not p:
                    print(f"Printify product not found for Etsy ID: {etsy_id}")
                    continue
                variant_id = match_printify_variant(p, size_raw)
                if not variant_id:
                    print(f"Variant size {size_raw} not found for product {p['id']}")
                    continue
                printify_line_items.append({
                    "product_id": p['id'],
                    "variant_id": variant_id,
                    "quantity": quantity
                })
                continue
                
            # 2. Check if it's a Lulu book
            # For books, the whole SKU might be the prefix if there's no size, 
            # or prefix could be `mr-phys-fractal-flora-book`.
            lulu_slug = SKU_TO_LULU_SLUG.get(sku) or SKU_TO_LULU_SLUG.get(prefix)
            if lulu_slug:
                files = lulu.book_print_files(lulu_slug)
                lulu_line_items.append({
                    "external_id": f"ebay-{order_id}-{sku}",
                    "title": files["title"],
                    "printable_normalization": {
                        "cover": {"source_url": files["cover"]},
                        "interior": {"source_url": files["interior"]},
                    },
                    "pod_package_id": lulu.BOOK_POD_PACKAGE_ID,
                    "quantity": quantity,
                })
                continue
                
            print(f"No mapping found for SKU: {sku}")

        if not printify_line_items and not lulu_line_items:
            print("Could not map any items to Printify or Lulu. Skipping order creation.")
            continue

        # Extract address
        buyer = order.get("fulfillmentStartInstructions", [{}])[0].get("shippingStep", {}).get("shipTo", {})
        if not buyer:
            print("Could not extract shipping address from order.")
            continue
            
        full_name = buyer.get("fullName", "")
        # Printify needs first and last name separated
        name_parts = full_name.split(" ", 1)
        first_name = name_parts[0] if len(name_parts) > 0 else "Customer"
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        contact = buyer.get("primaryPhone", {}).get("phoneNumber", "")
        address = buyer.get("contactAddress", {})
        buyer_email = buyer.get("email", "noreply@mathrelaxing.store")
        
        address_to = {
            "first_name": first_name,
            "last_name": last_name,
            "email": buyer_email,
            "phone": contact,
            "country": address.get("countryCode", ""),
            "region": address.get("stateOrProvince", ""),
            "address1": address.get("addressLine1", ""),
            "address2": address.get("addressLine2", ""),
            "city": address.get("city", ""),
            "zip": address.get("postalCode", "")
        }

        # Dry-run logic
        is_dry_run = False
        success = False

        if printify_line_items:
            order_body = {
                "external_id": order_id,
                "label": f"eBay {order_id}",
                "line_items": printify_line_items,
                "shipping_method": 1,
                "send_shipping_notification": False,
                "address_to": address_to
            }
            print("Sending to Printify:")
            print(json.dumps(order_body, indent=2))
            if is_dry_run:
                print("[DRY RUN] Would create Printify order.")
            else:
                try:
                    res = pp.create_order(order_body)
                    print(f"SUCCESS! Printify Order ID: {res.get('id')}")
                    success = True
                except Exception as e:
                    print(f"FAILED to create Printify order: {e}")

        if lulu_line_items:
            # We construct a shipping address that Lulu's _build_recipient expects
            lulu_shipping = {
                "first_name": first_name,
                "last_name": last_name,
                "phone": contact,
                "country": address.get("countryCode", ""),
                "state": address.get("stateOrProvince", ""),
                "address1": address.get("addressLine1", ""),
                "address2": address.get("addressLine2", ""),
                "city": address.get("city", ""),
                "zip": address.get("postalCode", "")
            }
            recipient = lulu._build_recipient(lulu_shipping, buyer_email)
            
            lulu_payload = {
                "contact_email": buyer_email,
                "external_id": f"ebay-{order_id}",
                "line_items": lulu_line_items,
                "shipping_address": recipient,
                "shipping_level": lulu.SHIPPING_LEVEL,
            }
            print("Sending to Lulu:")
            print(json.dumps(lulu_payload, indent=2))
            
            if is_dry_run:
                print("[DRY RUN] Would create Lulu order.")
            else:
                try:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        token = await lulu._get_token(client)
                        resp = await client.post(
                            f"{lulu.BASE_URL}/print-jobs/",
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Content-Type": "application/json",
                                "Cache-Control": "no-cache",
                            },
                            json=lulu_payload,
                            timeout=60,
                        )
                        if resp.status_code in (200, 201):
                            data = resp.json()
                            print(f"SUCCESS! Lulu Print Job ID: {data.get('id')}")
                            success = True
                        else:
                            print(f"FAILED to create Lulu order {resp.status_code}: {resp.text[:500]}")
                except Exception as e:
                    print(f"FAILED to create Lulu order: {e}")

        if success or is_dry_run:
            synced.add(order_id)

    if not is_dry_run:
        save_synced(synced)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(sync_orders())
