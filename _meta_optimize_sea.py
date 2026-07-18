"""
Optimize SEA Meta campaign based on live funnel audit:
- Geo: US, UK, AU (pause India-heavy SEA)
- Keep 3 product ads ACTIVE; pause rest + legacy collection
- Keep campaign ACTIVE
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

# Keep winners / best intent candidates
ACTIVE_ADS = {
    "120249640557690256": "Celtic Knot Coloring $3.99",
    "120249640552280256": "STEM Focus Planner $2.99",
    "120249640551080256": "Happy Chemicals Print Set",
}

# Everything else on this ad set should be paused
PAUSE_ADS = {
    "120249640554330256": "Unit Circle Poster",
    "120249640555810256": "Procreate Fractal Palettes",
    "120249640559780256": "Thomas Attractor Loop",
    "120249623948590256": "Collection legacy",
}

NEW_TARGETING = {
    "geo_locations": {
        "countries": ["US", "GB", "AU"],
    },
    # Keep age broad; Meta optimizes within
    "age_min": 18,
    "age_max": 45,
    # English-leaning locales: English (US/UK/AU common codes)
    # 6=en_US, 24=en_GB often used; leave locales out if unsure — countries are enough
    "publisher_platforms": ["facebook", "instagram", "audience_network", "messenger"],
    "facebook_positions": ["feed", "facebook_reels", "story"],
    "instagram_positions": ["stream", "story", "reels", "profile_feed"],
    "device_platforms": ["mobile", "desktop"],
    "targeting_automation": {
        "advantage_audience": 0,
    },
}


async def set_status(token: str, obj_id: str, status: str, label: str) -> dict:
    await m._graph_post(f"/{obj_id}", token, {"status": status})
    d = await m._graph_get(
        f"/{obj_id}",
        token,
        {"fields": "id,name,status,effective_status"},
    )
    print(f"  [{status}] {label}: effective={d.get('effective_status')} name={d.get('name')}")
    return d


async def main():
    token = await m._marketing_access_token()
    act = m._ad_account_id()
    account = await m._ad_account_summary(token)
    print(
        "account",
        account.get("name"),
        "status",
        account.get("account_status"),
        "currency",
        account.get("currency"),
    )
    if account.get("account_status") != 1:
        print(
            f"WARNING: account_status={account.get('account_status')} "
            "(1=ACTIVE, 3=UNSETTLED). Attempting updates anyway; delivery may be blocked until billing is fixed."
        )

    # 1) Update ad set targeting + ensure ACTIVE
    print("\n=== UPDATE AD SET TARGETING ===")
    # Read current
    before = await m._graph_get(
        f"/{ADSET_ID}",
        token,
        {
            "fields": "id,name,status,effective_status,daily_budget,targeting,optimization_goal"
        },
    )
    print("before countries:", (before.get("targeting") or {}).get("geo_locations"))
    print("before status:", before.get("status"), before.get("effective_status"))

    # Ad set updates: targeting countries only (minimal safe patch)
    # Note: some fields cannot be mixed; update targeting then status
    try:
        await m._graph_post(
            f"/{ADSET_ID}",
            token,
            {
                "name": "MR | US-UK-AU Product Ads | MathRelaxing",
                "targeting": json.dumps(
                    {
                        "geo_locations": {"countries": ["US", "GB", "AU"]},
                        "age_min": 18,
                        "age_max": 45,
                    }
                ),
            },
        )
        print("targeting update OK (minimal)")
    except Exception as e:
        print("minimal targeting failed:", e)
        # Fallback: full-ish targeting
        await m._graph_post(
            f"/{ADSET_ID}",
            token,
            {
                "targeting": json.dumps(NEW_TARGETING),
                "name": "MR | US-UK-AU Product Ads | MathRelaxing",
            },
        )
        print("targeting update OK (full)")

    after = await m._graph_get(
        f"/{ADSET_ID}",
        token,
        {"fields": "id,name,status,targeting,daily_budget,effective_status"},
    )
    print("after name:", after.get("name"))
    print("after countries:", (after.get("targeting") or {}).get("geo_locations"))
    print("daily_budget:", after.get("daily_budget"))

    # 2) Campaign ACTIVE + rename for clarity
    print("\n=== CAMPAIGN ===")
    try:
        await m._graph_post(
            f"/{CAMPAIGN_ID}",
            token,
            {
                "status": "ACTIVE",
                "name": "MR | US-UK-AU Digital Products | Traffic/Sales",
            },
        )
    except Exception as e:
        print("campaign rename warn:", e)
        await m._graph_post(f"/{CAMPAIGN_ID}", token, {"status": "ACTIVE"})
    camp = await m._graph_get(
        f"/{CAMPAIGN_ID}",
        token,
        {"fields": "id,name,status,effective_status"},
    )
    print("campaign:", camp)

    # Ensure ad set ACTIVE
    await set_status(token, ADSET_ID, "ACTIVE", "adset")

    # 3) Ads
    print("\n=== ACTIVATE PRODUCT ADS ===")
    active_details = []
    for aid, label in ACTIVE_ADS.items():
        d = await set_status(token, aid, "ACTIVE", label)
        active_details.append(d)

    print("\n=== PAUSE OTHER ADS ===")
    paused_details = []
    for aid, label in PAUSE_ADS.items():
        d = await set_status(token, aid, "PAUSED", label)
        paused_details.append(d)

    # List all
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
        "changes": {
            "geo": ["US", "GB", "AU"],
            "paused_geo_note": "Removed IN/TH/MY from ad set targeting",
            "active_ads": list(ACTIVE_ADS.values()),
            "paused_ads": list(PAUSE_ADS.values()),
        },
        "campaign": camp,
        "adset": after,
        "active_ads": active_details,
        "paused_ads": paused_details,
        "all_ads": ads.get("data"),
        "ads_manager": (
            f"https://adsmanager.facebook.com/adsmanager/manage/ads"
            f"?act={act}&selected_campaign_ids={CAMPAIGN_ID}"
        ),
    }
    os.makedirs("meta_drafts", exist_ok=True)
    path = "meta_drafts/sea_optimized_us_uk_au.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("\nWROTE", path)
    print(json.dumps(out["changes"], indent=2))
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
