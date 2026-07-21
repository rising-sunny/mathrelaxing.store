"""
_hc_finish_after_billing.py - finish the Happy Chemicals campaign (ALL PAUSED, no spend).

Campaign 120249688582940256 and ad set 120249688589040256 already exist (PAUSED).
Creative/ad creation is blocked while the ad account is UNSETTLED (status 3):
settle the outstanding balance in Ads Manager, then run this on the VPS:

    .venv/bin/python _hc_finish_after_billing.py

It creates the two creatives (proven reel + product carousel) and two PAUSED ads,
then saves meta_drafts/hc_lpv_us4_created.json. Activation stays manual.

Evidence-driven parameters:
- Product: happy-chemicals-print-set (best paid CTR in US/GB/AU: 17.9% all-clicks,
  31 link clicks / 26 LPVs on ~CLP 3.064 spend; 9 Etsy sales-adjacent signals).
- Objective OUTCOME_TRAFFIC + LANDING_PAGE_VIEWS: pixel has zero Purchase history,
  so purchase optimization stalls (observed: "PAUSED (low delivery)"). LPV is the
  highest-intent goal that still delivers.
- Geo US/GB/AU/CA, age 25-54, Advantage+ audience ON seeded with science/decor
  interests (the winning adset ran Advantage+ with auto placements).
- Budget CLP 10.000/day (~USD 10.5), lowest cost, auto placements.
- 2 creatives: proven reel video + new product carousel (5 square cards).
"""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/var/www/mathrelaxing.store")
import os
os.chdir("/var/www/mathrelaxing.store")
from dotenv import load_dotenv
load_dotenv(".env")

from routers import meta_ads as m

PAGE_ID = "533073909895353"
VIDEO_ID = "1285831770087138"
POSTER = "https://mathrelaxing.store/static/ads/sea_in_th_my_reel_poster.jpg"
BASE = "https://mathrelaxing.store/bundle/happy-chemicals-print-set"
UTM = "utm_source=meta&utm_medium=paid_social&utm_campaign=hc_lpv_us4"

IMG = "https://mathrelaxing.store/static/digital/happy-chemicals-print-set"

INTEREST_QUERIES = ["Neuroscience", "Psychology", "Chemistry", "Home decor", "Science"]

PRIMARY = (
    "Your brain chemistry, framed. Serotonin, dopamine, oxytocin & caffeine as "
    "minimalist molecular wall art - a 4-print science set for your desk, office "
    "or classroom. Instant digital download, print at home today. $3.99."
)
TITLE = "Happy Chemicals | 4 Molecule Prints - $3.99"

CARDS = [
    ("01_hero.jpg", "Happy Chemicals Print Set", "4 molecule prints, instant download, $3.99", "hero"),
    ("04_serotonin.jpg", "Serotonin", "The mood stabilizer - as wall art", "serotonin"),
    ("05_dopamine.jpg", "Dopamine", "The reward molecule - as wall art", "dopamine"),
    ("06_oxytocin.jpg", "Oxytocin", "The bonding hormone - as wall art", "oxytocin"),
    ("07_caffeine.jpg", "Caffeine", "Honorary happy chemical - as wall art", "caffeine"),
]


def link(content: str) -> str:
    return f"{BASE}?{UTM}&utm_content={content}"


async def post(path: str, token: str, data: dict) -> dict:
    flat = {}
    for k, v in data.items():
        flat[k] = json.dumps(v) if isinstance(v, (dict, list)) else v
    return await m._graph_post(path, token, flat)


async def main():
    tok = await m._marketing_access_token()
    acct = m._ad_account_id()
    act = acct if acct.startswith("act_") else f"act_{acct}"

    # 1. Resolve interest IDs
    interests = []
    for q in INTEREST_QUERIES:
        r = await m._graph_get("/search", tok, {"type": "adinterest", "q": q, "limit": 3})
        for cand in r.get("data", []):
            if cand.get("name", "").lower() == q.lower():
                interests.append({"id": str(cand["id"]), "name": cand["name"]})
                break
    print("interests:", json.dumps(interests))

    # 2. Campaign (PAUSED) â€” already created on a previous run
    campaign = {"id": "120249688582940256"}
    print("campaign (reused):", campaign["id"])

    # 3. Ad set (PAUSED)
    targeting = {
        "geo_locations": {"countries": ["US", "GB", "AU", "CA"]},
        "age_min": 25,
        "targeting_automation": {"advantage_audience": 1},
        "flexible_spec": [{"interests": interests}],
    }
    adset = {"id": "120249688589040256"}
    print("adset (reused):", adset["id"])

    # 4a. Creative A â€” proven reel video, fresh copy + UTMs
    creative_a = await post(f"/{act}/adcreatives", tok, {
        "name": "HC | Reel | LPV us4",
        "object_story_spec": {
            "page_id": PAGE_ID,
            "video_data": {
                "video_id": VIDEO_ID,
                "title": TITLE,
                "message": PRIMARY,
                "call_to_action": {"type": "SHOP_NOW", "value": {"link": link("reel")}},
                "image_url": POSTER,
            },
        },
    })
    print("creative reel:", creative_a["id"])

    # 4b. Creative B â€” product carousel (square listing images)
    children = [
        {
            "link": link(f"carousel_{tag}"),
            "name": name,
            "description": desc,
            "picture": f"{IMG}/{img}",
            "call_to_action": {"type": "SHOP_NOW", "value": {"link": link(f"carousel_{tag}")}},
        }
        for img, name, desc, tag in CARDS
    ]
    creative_b = await post(f"/{act}/adcreatives", tok, {
        "name": "HC | Carousel | LPV us4",
        "object_story_spec": {
            "page_id": PAGE_ID,
            "link_data": {
                "link": link("carousel"),
                "message": PRIMARY,
                "multi_share_optimized": True,
                "multi_share_end_card": False,
                "child_attachments": children,
            },
        },
    })
    print("creative carousel:", creative_b["id"])

    # 5. Ads (PAUSED)
    ads = []
    for name, cre in [
        ("HC | Reel video | PAUSED", creative_a["id"]),
        ("HC | Product carousel | PAUSED", creative_b["id"]),
    ]:
        ad = await post(f"/{act}/ads", tok, {
            "name": name,
            "adset_id": adset["id"],
            "creative": {"creative_id": cre},
            "status": "PAUSED",
        })
        ads.append({"name": name, "id": ad["id"], "creative_id": cre})
        print("ad:", name, ad["id"])

    result = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "campaign": campaign,
        "adset": adset,
        "targeting": targeting,
        "interests": interests,
        "creatives": {"reel": creative_a["id"], "carousel": creative_b["id"]},
        "ads": ads,
        "daily_budget_clp": 10000,
        "landing": link("<content>"),
        "note": "ALL PAUSED. Account status UNSETTLED (3) - settle billing before activating.",
        "ads_manager": (
            "https://adsmanager.facebook.com/adsmanager/manage/adsets?act=1636887674121801"
            f"&selected_campaign_ids={campaign['id']}"
        ),
    }
    out = Path("meta_drafts/hc_lpv_us4_created.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nSaved:", out)
    print(json.dumps(result, indent=1)[:1200])


asyncio.run(main())

