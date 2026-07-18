import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
from routers import meta_ads as m

CAMPAIGN = "120249615423940256"
NEW_ADSET = "120249651488300256"


async def main():
    token = await m._marketing_access_token()
    act = m._ad_account_id()
    acc = await m._ad_account_summary(token)
    print("account_status", acc.get("account_status"), acc.get("name"))
    if acc.get("account_status") != 1:
        raise SystemExit(f"Account not ACTIVE: {acc.get('account_status')}")

    await m._graph_post(f"/{CAMPAIGN}", token, {"status": "ACTIVE"})
    await m._graph_post(f"/{NEW_ADSET}", token, {"status": "ACTIVE"})

    camp = await m._graph_get(
        f"/{CAMPAIGN}", token, {"fields": "id,name,status,effective_status"}
    )
    adset = await m._graph_get(
        f"/{NEW_ADSET}",
        token,
        {"fields": "id,name,status,effective_status,daily_budget,targeting"},
    )
    ads = await m._graph_get(
        f"/act_{act}/ads",
        token,
        {
            "fields": "id,name,status,effective_status",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": NEW_ADSET}]
            ),
            "limit": 10,
        },
    )
    print("campaign", camp)
    print(
        "adset",
        adset.get("status"),
        adset.get("effective_status"),
        "geo",
        (adset.get("targeting") or {}).get("geo_locations"),
        "budget",
        adset.get("daily_budget"),
    )
    for a in ads.get("data") or []:
        print("ad", a.get("status"), a.get("effective_status"), a.get("name"))
    print(
        "url",
        f"https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={act}&selected_campaign_ids={CAMPAIGN}",
    )


asyncio.run(main())
