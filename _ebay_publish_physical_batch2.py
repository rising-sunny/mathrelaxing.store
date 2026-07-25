"""
Publish physical batch 2 to eBay (3 listings).

Already live (batch 1):
  penrose poster, euler poster, golden-ratio sticker, fractal-flora book

Batch 2:
  1. Fourier Series Poster 18x24
  2. Bauhaus Geometric Poster 18x24
  3. Hyperbolic Gardens Coloring Book (printed)

Same rules as batch 1: physical-only copy (no EDI), POD free-ship policy,
qty=1, FVF gross-up, images hosted on mathrelaxing.store.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path("/var/www/mathrelaxing.store")
load_dotenv(ROOT / ".env")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

# Reuse batch-1 helpers
import _ebay_publish_physical_batch1 as b1  # noqa: E402
import services.ebay as ebay  # noqa: E402

# base_price chosen so free-ship list price lands near batch-1 peers
# (posters ~$44.99, books ~$22.99 after FVF gross-up).
PRODUCTS = [
    {
        "sku": "mr-phys-fourier-poster-18x24",
        "etsy_id": 4540138384,
        "title": "Fourier Series Poster | Math Wall Art Scientific Plate | Square Wave STEM Print",
        "short_name": "Fourier Series Poster",
        "base_price": 38.00,
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
<h2>Fourier Series Poster — Square-Wave Harmonics</h2>
<p>A scientific-plate wall print of the Fourier series that builds a square wave from sine harmonics. Cream graph-paper ground, precise LaTeX-style equations, and a clear STEM aesthetic for study, classroom, or studio.</p>
<ul>
<li><b>Physical printed poster</b> — ships to your address (not a download)</li>
<li>Size: <b>18 × 24 inches</b></li>
<li>Matte poster paper, print on demand</li>
<li>Frame not included</li>
</ul>
<h3>Shipping &amp; production</h3>
<p>Made to order. Typical production 7–10 business days after purchase, then transit. No digital file is included with this listing.</p>
<p>MathRelaxing — code-drawn mathematics for your walls.</p>
</div>
""",
        "image_urls_etsy": [
            "https://i.etsystatic.com/66586766/r/il/c44a89/8317159957/il_fullxfull.8317159957_qoym.jpg",
            "https://i.etsystatic.com/66586766/r/il/a9a536/8317160415/il_fullxfull.8317160415_hyyg.jpg",
            "https://i.etsystatic.com/66586766/r/il/a09dba/8269247130/il_fullxfull.8269247130_9r79.jpg",
            "https://i.etsystatic.com/66586766/r/il/e5ab19/8269247702/il_fullxfull.8269247702_t0mp.jpg",
            "https://i.etsystatic.com/66586766/r/il/e91b29/8269248016/il_fullxfull.8269248016_j804.jpg",
            "https://i.etsystatic.com/66586766/r/il/437bfa/8269248586/il_fullxfull.8269248586_shkv.jpg",
        ],
    },
    {
        "sku": "mr-phys-bauhaus-poster-18x24",
        "etsy_id": 4540115383,
        "title": "Bauhaus Poster | Geometric Wall Art Circles and Bars | Navy Cream Modern Print",
        "short_name": "Bauhaus Geometric Poster",
        "base_price": 38.00,
        "size_label": "18 x 24 in",
        "category_id": "360",
        "condition": "NEW",
        "aspects": {
            "Type": ["Poster"],
            "Style": ["Bauhaus", "Minimalist", "Modern"],
            "Subject": ["Geometric", "Abstract"],
            "Material": ["Paper"],
            "Color": ["Navy", "Cream", "Gold"],
            "Size": ["18 x 24 in"],
            "Features": ["Unframed"],
        },
        "description_html": """
<div>
<h2>Bauhaus Geometric Poster — Circles &amp; Bars</h2>
<p>Modern geometric wall art in navy, cream, and gold: circles, bars, and balance in the Bauhaus spirit. Clean math-informed composition for living rooms, offices, and studios.</p>
<ul>
<li><b>Physical printed poster</b> — ships to your door (not a download)</li>
<li>Size: <b>18 × 24 inches</b></li>
<li>Matte poster, giclée-quality print on demand</li>
<li>Frame not included</li>
</ul>
<h3>Shipping &amp; production</h3>
<p>Made to order (print on demand). Typical production 7–10 business days, then transit. No digital file is included.</p>
<p>MathRelaxing — geometry as wall art.</p>
</div>
""",
        "image_urls_etsy": [
            "https://i.etsystatic.com/66586766/r/il/f009ac/8317158795/il_fullxfull.8317158795_38kj.jpg",
            "https://i.etsystatic.com/66586766/r/il/43f012/8317159083/il_fullxfull.8317159083_3hkv.jpg",
            "https://i.etsystatic.com/66586766/r/il/4e1ad1/8317159449/il_fullxfull.8317159449_jezi.jpg",
            "https://i.etsystatic.com/66586766/r/il/6ef615/8317159777/il_fullxfull.8317159777_6h7x.jpg",
            "https://i.etsystatic.com/66586766/r/il/cf1973/8317160161/il_fullxfull.8317160161_keln.jpg",
            "https://i.etsystatic.com/66586766/r/il/4ddf1e/8269247106/il_fullxfull.8269247106_de8y.jpg",
        ],
    },
    {
        "sku": "mr-phys-hyperbolic-gardens-book",
        "etsy_id": 4533722112,
        "title": "Hyperbolic Gardens Coloring Book | Printed Physical Edition | 50 Escher-Style Designs",
        "short_name": "Hyperbolic Gardens Printed Coloring Book",
        "base_price": 18.99,
        "size_label": "8.5 x 11 in book",
        "category_id": "261186",
        "condition": "NEW",
        "aspects": {
            "Book Title": ["Hyperbolic Gardens Coloring Book"],
            "Author": ["MathRelaxing"],
            "Format": ["Paperback"],
            "Language": ["English"],
            "Topic": ["Art", "Mathematics"],
            "Type": ["Coloring Book"],
            "Publisher": ["MathRelaxing"],
        },
        "description_html": """
<div>
<h2>Hyperbolic Gardens Coloring Book — Printed Physical Edition</h2>
<p><b>Printed paperback coloring book</b> that ships to your door. Fifty Escher-style hyperbolic and tessellation line-art designs — mathematical gardens for long, calm coloring sessions.</p>
<ul>
<li><b>Physical book</b> — perfect-bound, approx. 8.5 × 11 in</li>
<li>50 original tessellation / hyperbolic designs</li>
<li>Printed on demand and shipped to you</li>
<li><b>No digital PDF / no download</b> is included with this listing</li>
</ul>
<h3>Shipping &amp; production</h3>
<p>Made to order. Allow production time plus transit. Ideal STEM / teacher / relaxation gift.</p>
<p>MathRelaxing.</p>
</div>
""",
        "image_urls_etsy": [
            "https://i.etsystatic.com/66586766/r/il/fdd9a7/8268587585/il_fullxfull.8268587585_kzyv.jpg",
            "https://i.etsystatic.com/66586766/r/il/464cc3/8220661126/il_fullxfull.8220661126_k9om.jpg",
            "https://i.etsystatic.com/66586766/r/il/b6468f/8220661162/il_fullxfull.8220661162_9m7p.jpg",
            "https://i.etsystatic.com/66586766/r/il/e4a431/8220661202/il_fullxfull.8220661202_sq0j.jpg",
        ],
    },
]


async def main():
    if not ebay.is_configured():
        raise SystemExit("eBay not configured")
    print("limits", await ebay.get_selling_limits())
    for p in PRODUCTS:
        print(
            f"  plan {p['sku']}: base=${p['base_price']:.2f} "
            f"list~${b1.gross_up(p['base_price']):.2f}  {p['title'][:55]}"
        )

    fulfillment_id = await b1.get_or_create_physical_fulfillment_policy()
    payment_id, return_id = await b1.get_payment_return_policies()
    print("policies", fulfillment_id, payment_id, return_id)

    results = []
    for prod in PRODUCTS:
        try:
            r = await b1.publish_one(prod, fulfillment_id, payment_id, return_id)
            results.append(r)
        except Exception as e:
            print(f"  ERROR {prod['sku']}: {e}")
            import traceback

            traceback.print_exc()
            results.append({"sku": prod["sku"], "ok": False, "error": str(e)[:300]})
        await asyncio.sleep(0.5)

    print("\n=== BATCH 2 SUMMARY ===")
    ok_n = 0
    for r in results:
        if r.get("ok"):
            ok_n += 1
            print(
                f"  OK ${r.get('list_price')} hold={r.get('on_hold')} "
                f"https://www.ebay.com/itm/{r.get('listing_id')}  {r.get('title')}"
            )
        else:
            print(f"  FAIL {r.get('sku')}: {r.get('error')}")
    print(f"published {ok_n}/{len(results)}")
    return results


if __name__ == "__main__":
    asyncio.run(main())
