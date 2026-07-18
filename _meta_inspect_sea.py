import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from routers import meta_ads as m

CAMPAIGN = "120249615423940256"
ADSET = "120249615425210256"


async def main():
    token = await m._marketing_access_token()
    act = m._ad_account_id()
    camp = await m._graph_get(
        f"/{CAMPAIGN}",
        token,
        {"fields": "id,name,status,effective_status,objective"},
    )
    adset = await m._graph_get(
        f"/{ADSET}",
        token,
        {
            "fields": "id,name,status,effective_status,daily_budget,targeting,"
            "promoted_object,optimization_goal,billing_event"
        },
    )
    ads = await m._graph_get(
        f"/act_{act}/ads",
        token,
        {
            "fields": "id,name,status,effective_status,creative{id,name,object_story_spec,video_id,thumbnail_url}",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": ADSET}]
            ),
            "limit": 20,
        },
    )
    print("campaign", json.dumps(camp, indent=2))
    print(
        "adset",
        adset.get("status"),
        adset.get("effective_status"),
        "budget",
        adset.get("daily_budget"),
    )
    print("ads", len(ads.get("data") or []))
    for a in ads.get("data") or []:
        cr = a.get("creative") or {}
        print("---")
        print(a.get("id"), a.get("name"), a.get("status"), a.get("effective_status"))
        print("creative", cr.get("id"), cr.get("name"))
        print(json.dumps(cr.get("object_story_spec"), indent=2, default=str)[:1500])


asyncio.run(main())
