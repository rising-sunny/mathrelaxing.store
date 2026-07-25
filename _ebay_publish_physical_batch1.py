"""
Publish first physical product batch to eBay (POD / printed books).

Batch 1 (from live Etsy physical listings):
  1. Penrose Tiling Poster (default size 18x24)
  2. Euler Identity Poster (default size 18x24)
  3. Golden Ratio Sticker (default size 4x4)
  4. Fractal Flora Coloring Book — Printed Edition

Rules:
  - NO digital-download wording (EDI policy)
  - Real shipping fulfillment policy with multi-day handling (POD)
  - qty=1 per SKU (account selling-limit safety)
  - Price grossed up for eBay FVF (~13.6% + order fee)
  - Images hosted on mathrelaxing.store (downloaded from Etsy CDN)
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import shutil
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path("/var/www/mathrelaxing.store")
load_dotenv(ROOT / ".env")
os.chdir(ROOT)

import services.ebay as ebay  # noqa: E402

PUBLIC = os.getenv("PUBLIC_BASE_URL", "https://mathrelaxing.store").rstrip("/")
FEE_RATE = float(os.getenv("EBAY_FEE_RATE", "0.136"))
ORDER_FEE_LOW = 0.30
ORDER_FEE_HIGH = 0.40

# Catalog from Etsy active physical listings (manual smoke-test set)
PRODUCTS = [
    {
        "sku": "mr-phys-penrose-poster-18x24",
        "etsy_id": 4536912921,
        "title": "Penrose Tiling Poster | Geometric Math Line Art Print | Scandinavian Wall Art",
        "short_name": "Penrose Tiling Poster",
        "base_price": 26.00,  # Etsy 18x24
        "size_label": "18 x 24 in",
        "category_id": "360",  # Art > Art Prints
        "condition": "NEW",
        "aspects": {
            "Type": ["Poster"],
            "Style": ["Minimalist", "Abstract", "Modern"],
            "Subject": ["Geometric", "Mathematics"],
            "Material": ["Paper"],
            "Color": ["Black", "Ivory"],
            "Size": ["18 x 24 in"],
            "Features": ["Unframed"],
        },
        "description_html": """
<div>
<h2>Penrose Tiling Poster — Geometric Math Line Art</h2>
<p>An aperiodic Penrose tiling — a pattern of two rhombi that fills the plane and never exactly repeats, built on the golden ratio. Clean black-and-white line art on a warm ivory ground. Part of the Geometric Tilings series.</p>
<ul>
<li><b>Physical printed poster</b> — ships to your door (not a download)</li>
<li>Size: <b>18 × 24 inches</b></li>
<li>Matte poster paper, giclée-quality print on demand</li>
<li>Charcoal line work · frame not included</li>
</ul>
<h3>Shipping &amp; production</h3>
<p>Made to order (print on demand). Typical production 7–10 business days, then transit. Ships from our print partner. No digital file is included with this listing.</p>
<p>MathRelaxing — mathematics as wall art.</p>
</div>
""",
        "image_urls_etsy": [
            "https://i.etsystatic.com/66586766/r/il/85f7b4/8269247698/il_fullxfull.8269247698_1edm.jpg",
            "https://i.etsystatic.com/66586766/r/il/419534/8269248172/il_fullxfull.8269248172_4o4g.jpg",
            "https://i.etsystatic.com/66586766/r/il/56eeda/8317162693/il_fullxfull.8317162693_el22.jpg",
            "https://i.etsystatic.com/66586766/r/il/f39975/8317163357/il_fullxfull.8317163357_5j4f.jpg",
            "https://i.etsystatic.com/66586766/r/il/b92ee7/8317163769/il_fullxfull.8317163769_567d.jpg",
        ],
    },
    {
        "sku": "mr-phys-euler-poster-18x24",
        "etsy_id": 4540138522,
        "title": "Euler Identity Poster | Math Wall Art | e^(iπ) Complex Plane STEM Print",
        "short_name": "Euler Identity Poster",
        "base_price": 26.00,
        "size_label": "18 x 24 in",
        "category_id": "360",
        "condition": "NEW",
        "aspects": {
            "Type": ["Poster"],
            "Style": ["Minimalist", "Educational"],
            "Subject": ["Mathematics", "Science"],
            "Material": ["Paper"],
            "Size": ["18 x 24 in"],
            "Features": ["Unframed"],
        },
        "description_html": """
<div>
<h2>Euler's Identity Poster — The Most Beautiful Equation</h2>
<p>Euler's identity on the complex unit circle. Scientific-plate style wall art with cream graph paper and precise geometry. A classic gift for mathematicians, students, and teachers.</p>
<ul>
<li><b>Physical printed poster</b> — ships to your address (not a download)</li>
<li>Size: <b>18 × 24 inches</b></li>
<li>Matte poster, printed on demand</li>
<li>Frame not included</li>
</ul>
<h3>Shipping &amp; production</h3>
<p>Made to order. Typical production 7–10 business days after purchase, then shipping transit. No digital file is included with this listing.</p>
<p>MathRelaxing — code-drawn mathematics for your walls.</p>
</div>
""",
        "image_urls_etsy": [
            "https://i.etsystatic.com/66586766/r/il/ee86a9/8269246316/il_fullxfull.8269246316_qezo.jpg",
            "https://i.etsystatic.com/66586766/r/il/3b3bd7/8317160883/il_fullxfull.8317160883_1doe.jpg",
            "https://i.etsystatic.com/66586766/r/il/b8ad28/8317161327/il_fullxfull.8317161327_6jlb.jpg",
            "https://i.etsystatic.com/66586766/r/il/55054f/8269248276/il_fullxfull.8269248276_72tn.jpg",
            "https://i.etsystatic.com/66586766/r/il/0eacd0/8317162473/il_fullxfull.8317162473_6mwu.jpg",
        ],
    },
    {
        "sku": "mr-phys-golden-ratio-sticker-4x4",
        "etsy_id": 4540933093,
        "title": "Golden Ratio Sticker | Fibonacci Spiral Phi Math Vinyl Decal | Kiss-Cut",
        "short_name": "Golden Ratio Sticker",
        "base_price": 4.99,  # Etsy 4x4
        "size_label": "4 x 4 in",
        "category_id": "180959",  # Crafts > Stickers
        "condition": "NEW",
        "aspects": {
            "Type": ["Sticker"],
            "Material": ["Vinyl"],
            "Shape": ["Die Cut"],
            "Subject": ["Mathematics"],
            "Size": ["4 x 4 in"],
        },
        "description_html": """
<div>
<h2>Golden Ratio / Fibonacci Spiral Sticker</h2>
<p>Math-art kiss-cut vinyl sticker with the golden-ratio spiral. Durable, water-resistant vinyl — peel and stick on a laptop, water bottle, notebook, or phone. A geeky gift for mathematicians, teachers, and students.</p>
<ul>
<li><b>Physical vinyl sticker</b> — ships to you (not a digital file)</li>
<li>Size: <b>4 × 4 inches</b> (kiss-cut)</li>
<li>Water-resistant vinyl</li>
</ul>
<h3>Shipping &amp; production</h3>
<p>Printed on demand and shipped. No digital download is included.</p>
<p>MathRelaxing.</p>
</div>
""",
        "image_urls_etsy": [
            "https://i.etsystatic.com/66586766/r/il/8c04a6/8275519360/il_fullxfull.8275519360_81j7.jpg",
            "https://i.etsystatic.com/66586766/r/il/da6a34/8323437189/il_fullxfull.8323437189_p48u.jpg",
            "https://i.etsystatic.com/66586766/r/il/dc6a0f/8323437653/il_fullxfull.8323437653_6wt1.jpg",
            "https://i.etsystatic.com/66586766/r/il/72bb21/8323438449/il_fullxfull.8323438449_igt6.jpg",
            "https://i.etsystatic.com/66586766/r/il/bf2685/8323439411/il_fullxfull.8323439411_bikx.jpg",
        ],
    },
    {
        "sku": "mr-phys-fractal-flora-book",
        "etsy_id": 4533708985,
        "title": "Fractal Flora Coloring Book | Printed Physical Edition | 50 Botanical Designs",
        "short_name": "Fractal Flora Printed Coloring Book",
        "base_price": 18.99,
        "size_label": "8.5 x 11 in book",
        "category_id": "261186",  # Toys & Hobbies > Arts & Crafts > Drawing & Painting > Coloring Books (approx)
        "condition": "NEW",
        "aspects": {
            "Book Title": ["Fractal Flora Coloring Book"],
            "Format": ["Paperback"],
            "Language": ["English"],
            "Topic": ["Art", "Mathematics"],
            "Type": ["Coloring Book"],
        },
        "description_html": """
<div>
<h2>Fractal Flora Coloring Book — Printed Physical Edition</h2>
<p><b>Printed paperback coloring book</b> that ships to your door. Fifty unique fractal and botanical line-art designs: Dragon Curves, Julia Sets, Barnsley Ferns, and more — drawn with mathematical precision.</p>
<ul>
<li><b>Physical book</b> — perfect-bound, approx. 8.5 × 11 in</li>
<li>50 original line-art designs (no color-by-number numbers)</li>
<li>Printed on demand and shipped to you</li>
<li><b>No digital PDF / no download</b> is included with this listing</li>
</ul>
<h3>Shipping &amp; production</h3>
<p>Made to order. Allow production time plus transit. Ideal STEM / teacher / relaxation gift.</p>
<p>MathRelaxing.</p>
</div>
""",
        "image_urls_etsy": [
            "https://i.etsystatic.com/66586766/r/il/e895dd/8220661306/il_fullxfull.8220661306_cro2.jpg",
            "https://i.etsystatic.com/66586766/r/il/b5509d/8268587867/il_fullxfull.8268587867_kxfm.jpg",
            "https://i.etsystatic.com/66586766/r/il/1b5ef0/8220661376/il_fullxfull.8220661376_hm50.jpg",
            "https://i.etsystatic.com/66586766/r/il/95dff4/8220661404/il_fullxfull.8220661404_62gp.jpg",
        ],
    },
]


def gross_up(base: float) -> float:
    p = (base + ORDER_FEE_LOW) / (1.0 - FEE_RATE)
    p = math.ceil(p * 100 - 1e-9) / 100
    of = ORDER_FEE_LOW if p <= 10 else ORDER_FEE_HIGH
    if of != ORDER_FEE_LOW:
        p = (base + of) / (1.0 - FEE_RATE)
        p = math.ceil(p * 100 - 1e-9) / 100
    # clean .99 for retail
    if p >= 10:
        dollars = int(p)
        cand = dollars + 0.99
        if cand < p:
            cand = dollars + 1.99
        if cand - p <= 0.50:
            p = cand
    else:
        dollars = int(p)
        cand = dollars + 0.99
        if cand >= p and cand - p <= 0.25:
            p = cand
    return round(p, 2)


def net_after(price: float) -> float:
    of = ORDER_FEE_LOW if price <= 10 else ORDER_FEE_HIGH
    return round(price - price * FEE_RATE - of, 2)


async def download_images(sku: str, urls: list[str]) -> list[str]:
    out = ROOT / "static" / "ebay" / "physical" / sku
    out.mkdir(parents=True, exist_ok=True)
    hosted = []
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        for i, url in enumerate(urls, 1):
            ext = ".jpg"
            dest = out / f"{i:02d}{ext}"
            if not dest.exists() or dest.stat().st_size < 2000:
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    dest.write_bytes(r.content)
                    print(f"  downloaded {dest.name} {len(r.content)//1024}KB")
                except Exception as e:
                    print(f"  image fail {url[:60]}: {e}")
                    continue
            if dest.is_file() and dest.stat().st_size > 2000:
                hosted.append(f"{PUBLIC}/static/ebay/physical/{sku}/{dest.name}")
    return hosted[:12]


async def get_or_create_physical_fulfillment_policy() -> str:
    """POD free-ship policy with 10-day handling (not same-day digital)."""
    name = "POD Free Shipping - 10 Day Handling"
    try:
        fp = await ebay._get(
            "/sell/account/v1/fulfillment_policy",
            {"marketplace_id": ebay.MARKETPLACE_ID},
        )
        for p in fp.get("fulfillmentPolicies") or []:
            if p.get("name") == name:
                print("fulfillment policy reuse", p.get("fulfillmentPolicyId"))
                return p["fulfillmentPolicyId"]
            # also accept any free-ship with handling >= 3 days
            ht = (p.get("handlingTime") or {}).get("value") or 0
            opts = p.get("shippingOptions") or []
            free = any(
                any(s.get("freeShipping") for s in (o.get("shippingServices") or []))
                for o in opts
            )
            if free and ht >= 3 and "digital" not in (p.get("name") or "").lower():
                print("fulfillment policy reuse", p.get("name"), p.get("fulfillmentPolicyId"))
                return p["fulfillmentPolicyId"]
    except Exception as e:
        print("list fulfillment err", e)

    body = {
        "name": name,
        "description": "Print-on-demand physical goods. Free shipping. Processing up to 10 business days.",
        "marketplaceId": ebay.MARKETPLACE_ID,
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "handlingTime": {"value": 10, "unit": "DAY"},
        "shippingOptions": [
            {
                "optionType": "DOMESTIC",
                "costType": "FLAT_RATE",
                "shippingServices": [
                    {
                        "sortOrder": 1,
                        "shippingCarrierCode": "USPS",
                        "shippingServiceCode": "USPSPriority",
                        "shippingCost": {"value": "0.0", "currency": "USD"},
                        "additionalShippingCost": {"value": "0.0", "currency": "USD"},
                        "freeShipping": True,
                        "buyerResponsibleForShipping": False,
                        "buyerResponsibleForPickup": False,
                    }
                ],
            }
        ],
        "globalShipping": False,
        "freightShipping": False,
        "pickupDropOff": False,
        "localPickup": False,
    }
    try:
        r = await ebay._post("/sell/account/v1/fulfillment_policy", body)
        fid = r.get("fulfillmentPolicyId")
        print("created fulfillment", fid)
        return fid
    except Exception as e:
        print("create fulfillment failed, falling back", e)
        # last resort: existing digital free-ship policy (still has free shipping)
        policies = await ebay.get_or_create_policies()
        return policies["fulfillment_policy_id"]


async def get_payment_return_policies() -> tuple[str, str]:
    policies = await ebay.get_or_create_policies()
    return policies["payment_policy_id"], policies["return_policy_id"]


def safe_title(title: str) -> str:
    t = re.sub(r"\s+", " ", title).strip()
    # strip digital wording if any slipped in
    for bad in ("digital download", "instant download", "PDF download", "— Digital"):
        t = re.sub(bad, "", t, flags=re.I)
    t = re.sub(r"\s+\|?\s*$", "", t).strip()
    return t[:80]


async def publish_one(prod: dict, fulfillment_id: str, payment_id: str, return_id: str) -> dict:
    sku = prod["sku"]
    base = float(prod["base_price"])
    list_price = gross_up(base)
    title = safe_title(prod["title"])
    print(f"\n=== {sku} ===")
    print(f"  etsy={prod['etsy_id']} base=${base:.2f} list=${list_price:.2f} net~${net_after(list_price):.2f}")
    print(f"  title={title}")

    images = await download_images(sku, prod["image_urls_etsy"])
    if not images:
        return {"sku": sku, "ok": False, "error": "no_images"}
    print(f"  images={len(images)}")

    # Inventory item — physical condition NEW, ship-to availability
    inv_body = {
        "product": {
            "title": title,
            "description": prod["description_html"].strip(),
            "aspects": prod["aspects"],
            "imageUrls": images,
        },
        "condition": prod.get("condition", "NEW"),
        "availability": {
            "shipToLocationAvailability": {
                "quantity": 1,  # selling-limit safe
            }
        },
        "packageWeightAndSize": {
            "weight": {"value": 8 if "sticker" in sku else (16 if "book" in sku else 12), "unit": "OUNCE"},
            "dimensions": {
                "length": 12,
                "width": 9,
                "height": 1 if "book" not in sku else 0.5,
                "unit": "INCH",
            },
        },
    }
    await ebay._put(f"/sell/inventory/v1/inventory_item/{sku}", inv_body)

    # Offer
    offers = await ebay.get_offers_for_sku(sku)
    offer_body = {
        "sku": sku,
        "marketplaceId": ebay.MARKETPLACE_ID,
        "format": "FIXED_PRICE",
        "availableQuantity": 1,
        "categoryId": str(prod["category_id"]),
        "listingDescription": prod["description_html"].strip(),
        "listingPolicies": {
            "fulfillmentPolicyId": fulfillment_id,
            "paymentPolicyId": payment_id,
            "returnPolicyId": return_id,
        },
        "pricingSummary": {
            "price": {"value": f"{list_price:.2f}", "currency": "USD"},
        },
        "merchantLocationKey": os.getenv("EBAY_MERCHANT_LOCATION_KEY", "default_location"),
        "includeCatalogProductDetails": False,
    }

    if offers:
        offer_id = offers[0]["offerId"]
        status = offers[0].get("status")
        print(f"  existing offer {offer_id} status={status}")
        try:
            await ebay._put(f"/sell/inventory/v1/offer/{offer_id}", offer_body)
        except Exception as e:
            print("  offer put warn", e)
        if status != "PUBLISHED":
            listing_id = await ebay.publish_offer(offer_id)
        else:
            listing_id = offers[0].get("listingId") or (offers[0].get("listing") or {}).get(
                "listingId"
            )
    else:
        r = await ebay._post("/sell/inventory/v1/offer", offer_body)
        offer_id = r.get("offerId")
        print(f"  created offer {offer_id}")
        listing_id = await ebay.publish_offer(offer_id)

    # verify
    offers2 = await ebay.get_offers_for_sku(sku)
    o = offers2[0] if offers2 else {}
    lid = o.get("listingId") or (o.get("listing") or {}).get("listingId") or listing_id
    hold = (o.get("listing") or {}).get("listingOnHold")
    print(f"  status={o.get('status')} listing={lid} hold={hold}")
    print(f"  url=https://www.ebay.com/itm/{lid}")
    return {
        "sku": sku,
        "ok": o.get("status") == "PUBLISHED",
        "offer_id": offer_id,
        "listing_id": lid,
        "list_price": list_price,
        "base_price": base,
        "on_hold": hold,
        "title": title,
        "etsy_id": prod["etsy_id"],
    }


async def main():
    if not ebay.is_configured():
        raise SystemExit("eBay not configured")
    print("limits", await ebay.get_selling_limits())
    fulfillment_id = await get_or_create_physical_fulfillment_policy()
    payment_id, return_id = await get_payment_return_policies()
    print("policies", fulfillment_id, payment_id, return_id)

    results = []
    for prod in PRODUCTS:
        try:
            r = await publish_one(prod, fulfillment_id, payment_id, return_id)
            results.append(r)
        except Exception as e:
            print(f"  ERROR {prod['sku']}: {e}")
            import traceback

            traceback.print_exc()
            results.append({"sku": prod["sku"], "ok": False, "error": str(e)[:300]})
        await asyncio.sleep(0.5)

    print("\n=== BATCH 1 SUMMARY ===")
    for r in results:
        if r.get("ok"):
            print(
                f"  OK ${r.get('list_price')} hold={r.get('on_hold')} "
                f"https://www.ebay.com/itm/{r.get('listing_id')}  {r.get('title')}"
            )
        else:
            print(f"  FAIL {r.get('sku')}: {r.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
