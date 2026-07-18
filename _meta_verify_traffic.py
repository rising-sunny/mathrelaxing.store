import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
from routers import meta_ads as m

CAMP = "120249652184960256"
ADSET = "120249652185170256"
SALES = "120249615423940256"


async def main():
    t = await m._marketing_access_token()
    act = m._ad_account_id()
    print("camp", await m._graph_get(f"/{CAMP}", t, {"fields": "id,name,status,effective_status,objective"}))
    print(
        "adset",
        await m._graph_get(
            f"/{ADSET}",
            t,
            {
                "fields": "id,name,status,effective_status,optimization_goal,daily_budget,targeting"
            },
        ),
    )
    print(
        "sales",
        await m._graph_get(f"/{SALES}", t, {"fields": "id,name,status,effective_status"}),
    )
    ads = await m._graph_get(
        f"/act_{act}/ads",
        t,
        {
            "fields": "id,name,status,effective_status",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": ADSET}]
            ),
            "limit": 10,
        },
    )
    for a in ads.get("data") or []:
        print("ad", a)
    ins = await m._graph_get(
        f"/{ADSET}/insights",
        t,
        {"fields": "impressions,spend,clicks,inline_link_clicks", "date_preset": "today"},
    )
    print("insights", ins.get("data"))


asyncio.run(main())
