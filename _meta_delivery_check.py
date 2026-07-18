import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
from routers import meta_ads as m

NEW = "120249651488300256"
OLD = "120249615425210256"
CAMP = "120249615423940256"


async def main():
    token = await m._marketing_access_token()
    act = m._ad_account_id()

    for label, aid in [("NEW", NEW), ("OLD", OLD)]:
        a = await m._graph_get(
            f"/{aid}",
            token,
            {
                "fields": "id,name,status,effective_status,daily_budget,lifetime_budget,"
                "learning_stage_info,issues_info,configured_status"
            },
        )
        print(f"\n=== {label} ADSET ===")
        print(json.dumps(a, indent=2, default=str)[:2000])

    ads = await m._graph_get(
        f"/act_{act}/ads",
        token,
        {
            "fields": "id,name,status,effective_status,issues_info,ad_review_feedback,"
            "configured_status,creative{id,status,thumbnail_url}",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": NEW}]
            ),
            "limit": 10,
        },
    )
    print("\n=== NEW ADS ===")
    for a in ads.get("data") or []:
        print(json.dumps(a, indent=2, default=str)[:1200])
        print("---")

    # lifetime insights new adset
    print("\n=== NEW ADSET insights lifetime / maximum ===")
    for preset in ("today", "last_3d", "maximum"):
        try:
            d = await m._graph_get(
                f"/{NEW}/insights",
                token,
                {
                    "fields": "impressions,clicks,spend,inline_link_clicks,date_start,date_stop",
                    "date_preset": preset,
                },
            )
            print(preset, d.get("data"))
        except Exception as e:
            print(preset, e)

    # campaign delivery estimate?
    camp = await m._graph_get(
        f"/{CAMP}",
        token,
        {"fields": "id,name,status,effective_status,issues_info"},
    )
    print("\n=== CAMPAIGN ===")
    print(json.dumps(camp, indent=2, default=str))


asyncio.run(main())
