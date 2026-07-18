"""
Create product-specific Meta ads on the existing SEA ad set (all PAUSED).
Campaign is OFF — safe to attach new ads without spend.

Reuses the same short reel video; each creative has its own product landing + UTMs.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from routers import meta_ads as m

CAMPAIGN_ID = "120249615423940256"
ADSET_ID = "120249615425210256"
VIDEO_ID = "1285831770087138"
POSTER_URL = "https://mathrelaxing.store/static/ads/sea_in_th_my_reel_poster.jpg"
PAGE_ID = None  # filled from env/helper

# Product-focused ads (diversified landings)
PRODUCT_ADS = [
    {
        "key": "happy_chemicals",
        "slug": "happy-chemicals-print-set",
        "name": "SEA | Happy Chemicals Print Set",
        "title": "Happy Chemicals · Math Wall Art",
        "message": (
            "Serotonin, dopamine, oxytocin & caffeine — as beautiful math art. "
            "Instant digital print set. Shop now on MathRelaxing."
        ),
    },
    {
        "key": "stem_planner",
        "slug": "stem-focus-planner-digital",
        "name": "SEA | STEM Focus Planner $2.99",
        "title": "STEM Focus Planner · $2.99",
        "message": (
            "Undated digital planner for STEM students — GoodNotes & Notability ready. "
            "Only $2.99. Instant download."
        ),
    },
    {
        "key": "unit_circle",
        "slug": "unit-circle-poster",
        "name": "SEA | Unit Circle Poster",
        "title": "Unit Circle Poster · Study Wall Art",
        "message": (
            "Clean trigonometry unit circle poster — perfect for study desks. "
            "Instant digital download from MathRelaxing."
        ),
    },
    {
        "key": "procreate_palettes",
        "slug": "fractal-color-palettes-procreate",
        "name": "SEA | Procreate Fractal Palettes $1.99",
        "title": "Fractal Palettes · Procreate $1.99",
        "message": (
            "Fractal-inspired Procreate color palettes for digital artists. "
            "Just $1.99 — instant download."
        ),
    },
    {
        "key": "celtic_coloring",
        "slug": "celtic-knot-coloring-book-digital",
        "name": "SEA | Celtic Knot Coloring $3.99",
        "title": "Celtic Knot Math Coloring · $3.99",
        "message": (
            "Celtic knot mathematics coloring book (digital). "
            "Relaxing geometric patterns — instant PDF download, $3.99."
        ),
    },
    {
        "key": "thomas_loop",
        "slug": "thomas-attractor-loop",
        "name": "SEA | Thomas Attractor Loop $4.99",
        "title": "Thomas Attractor Loop · $4.99",
        "message": (
            "Seamless mathematical animation loop (MP4). "
            "Wallpaper / reels / ambient art — instant download $4.99."
        ),
    },
]


def landing(slug: str, content: str) -> str:
    return (
        f"https://mathrelaxing.store/bundle/{slug}"
        f"?utm_source=meta&utm_medium=paid_social"
        f"&utm_campaign=sea_in_th_my_math_art&utm_content={content}"
    )


async def create_creative(token: str, act: str, page_id: str, ad: dict) -> str:
    link = landing(ad["slug"], ad["key"])
    body = {
        "name": f"{ad['name']} | Creative",
        "object_story_spec": json.dumps(
            {
                "page_id": page_id,
                "video_data": {
                    "video_id": VIDEO_ID,
                    "title": ad["title"][:255],
                    "message": ad["message"][:2000],
                    "call_to_action": {
                        "type": "SHOP_NOW",
                        "value": {"link": link},
                    },
                    "image_url": POSTER_URL,
                },
            }
        ),
    }
    cr = await m._graph_post(f"/act_{act}/adcreatives", token, body)
    return cr["id"]


async def create_ad(token: str, act: str, creative_id: str, ad: dict) -> str:
    body = {
        "name": f"{ad['name']} | PAUSED",
        "status": "PAUSED",
        "adset_id": ADSET_ID,
        "creative": json.dumps({"creative_id": creative_id}),
    }
    res = await m._graph_post(f"/act_{act}/ads", token, body)
    return res["id"]


async def pause_old_collection_ad(token: str) -> None:
    """Ensure original collection-landing ad stays paused."""
    try:
        await m._graph_post(
            "/120249623948590256",
            token,
            {"status": "PAUSED", "name": "SEA | Collection (legacy) | PAUSED"},
        )
        print("legacy ad paused/renamed")
    except Exception as e:
        print("legacy ad update warn:", e)


async def ensure_campaign_paused(token: str) -> None:
    try:
        await m._graph_post(f"/{CAMPAIGN_ID}", token, {"status": "PAUSED"})
        print("campaign confirmed PAUSED")
    except Exception as e:
        print("campaign pause warn:", e)


async def main():
    token = await m._marketing_access_token()
    act = m._ad_account_id()
    page_id = m._page_id()
    print("act", act, "page", page_id)

    await ensure_campaign_paused(token)
    await pause_old_collection_ad(token)

    results = []
    for ad in PRODUCT_ADS:
        print(f"\n=== {ad['key']} -> {ad['slug']} ===")
        try:
            cid = await create_creative(token, act, page_id, ad)
            print("creative", cid)
            aid = await create_ad(token, act, cid, ad)
            print("ad", aid)
            results.append(
                {
                    "ok": True,
                    "key": ad["key"],
                    "slug": ad["slug"],
                    "landing": landing(ad["slug"], ad["key"]),
                    "creative_id": cid,
                    "ad_id": aid,
                    "status": "PAUSED",
                }
            )
        except Exception as e:
            print("FAIL", e)
            results.append({"ok": False, "key": ad["key"], "error": str(e)[:400]})

    # list all ads on adset
    ads = await m._graph_get(
        f"/act_{act}/ads",
        token,
        {
            "fields": "id,name,status,effective_status",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": ADSET_ID}]
            ),
            "limit": 30,
        },
    )

    out = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "campaign_id": CAMPAIGN_ID,
        "adset_id": ADSET_ID,
        "campaign_status": "PAUSED",
        "note": "All new ads PAUSED. Turn campaign ACTIVE when ready; enable chosen ads.",
        "created": results,
        "adset_ads": ads.get("data"),
        "ads_manager": (
            f"https://adsmanager.facebook.com/adsmanager/manage/ads"
            f"?act={act}&selected_campaign_ids={CAMPAIGN_ID}"
        ),
    }
    os.makedirs("meta_drafts", exist_ok=True)
    path = "meta_drafts/sea_product_ads_latest.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    stamped = (
        f"meta_drafts/sea_product_ads_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    with open(stamped, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print("WROTE", path)


if __name__ == "__main__":
    asyncio.run(main())
