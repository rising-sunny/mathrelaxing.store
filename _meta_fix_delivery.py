"""Diagnose + fix zero delivery on US-UK-AU ad set."""
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

CAMP = "120249615423940256"
NEW = "120249651488300256"
OLD = "120249615425210256"


async def try_post(token, path, body, label):
    try:
        r = await m._graph_post(path, token, body)
        print(f"OK  {label}: {r}")
        return True, r
    except Exception as e:
        d = getattr(e, "detail", str(e))
        print(f"FAIL {label}: {str(d)[:500]}")
        return False, d


async def get(token, path, fields):
    return await m._graph_get(path, token, {"fields": fields})


async def main():
    token = await m._marketing_access_token()
    act = m._ad_account_id()
    acc = await m._ad_account_summary(token)
    print("account_status", acc.get("account_status"), acc.get("currency"))

    # Deep ad set fields
    fields = (
        "id,name,status,effective_status,configured_status,daily_budget,lifetime_budget,"
        "billing_event,optimization_goal,bid_amount,bid_strategy,destination_type,"
        "promoted_object,targeting,pacing_type,budget_remaining,start_time,end_time,"
        "learning_stage_info,issues_info,is_dynamic_creative,multi_optimization_goal_weight,"
        "attribution_spec,dsa_beneficiary,dsa_payor"
    )
    print("\n=== NEW ADSET FULL ===")
    nas = await get(token, f"/{NEW}", fields)
    print(json.dumps(nas, indent=2, default=str)[:4000])

    print("\n=== CAMPAIGN FULL ===")
    camp = await get(
        token,
        f"/{CAMP}",
        "id,name,status,effective_status,objective,buying_type,bid_strategy,"
        "daily_budget,lifetime_budget,pacing_type,special_ad_categories,issues_info",
    )
    print(json.dumps(camp, indent=2, default=str))

    # Ads with review feedback
    print("\n=== NEW ADS DEEP ===")
    ads = await m._graph_get(
        f"/act_{act}/ads",
        token,
        {
            "fields": "id,name,status,effective_status,configured_status,issues_info,"
            "ad_review_feedback,bid_amount,conversion_domain,tracking_specs,"
            "creative{id,status,object_type,effective_object_story_id}",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": NEW}]
            ),
            "limit": 10,
        },
    )
    for a in ads.get("data") or []:
        print(json.dumps(a, indent=2, default=str)[:1500])
        print("---")

    # Delivery estimate
    print("\n=== DELIVERY ESTIMATE ===")
    try:
        est = await m._graph_get(
            f"/{NEW}/delivery_estimate",
            token,
            {
                "optimization_goal": nas.get("optimization_goal") or "OFFSITE_CONVERSIONS",
                "targeting_spec": json.dumps(nas.get("targeting") or {}),
            },
        )
        print(json.dumps(est, indent=2, default=str)[:2000])
    except Exception as e:
        print("estimate err", getattr(e, "detail", e))

    # Try reachestimate
    try:
        re_ = await m._graph_get(
            f"/act_{act}/reachestimate",
            token,
            {"targeting_spec": json.dumps(nas.get("targeting") or {})},
        )
        print("reachestimate", json.dumps(re_, indent=2, default=str)[:1500])
    except Exception as e:
        print("reachestimate err", getattr(e, "detail", e))

    # Insights empty confirm
    for node, label in [(NEW, "new_adset"), (CAMP, "campaign")]:
        d = await m._graph_get(
            f"/{node}/insights",
            token,
            {
                "fields": "impressions,spend,clicks,inline_link_clicks",
                "date_preset": "today",
                "level": "adset" if node == NEW else "campaign",
            },
        )
        print(f"insights today {label}:", d.get("data"))

    # ---- FIX ATTEMPTS ----
    print("\n=== APPLY FIXES ===")
    # 1) Switch optimization to LINK_CLICKS (more delivery for cold traffic)
    #    Keep pixel for tracking but don't require purchase optimization
    targeting = nas.get("targeting") or {}
    # Ensure advantage_audience present
    ta = targeting.get("targeting_automation") or {}
    ta["advantage_audience"] = ta.get("advantage_audience", 0)
    targeting["targeting_automation"] = ta
    # Expand age slightly for delivery
    targeting["age_min"] = 18
    targeting["age_max"] = 55
    # countries already US GB AU

    # Meta often needs promoted_object only for conversion goals.
    # For LINK_CLICKS we can omit custom_event_type purchase requirement.
    fix_body = {
        "optimization_goal": "LINK_CLICKS",
        "billing_event": "IMPRESSIONS",
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "destination_type": "WEBSITE",
        "targeting": json.dumps(targeting),
        "status": "ACTIVE",
        "name": "MR | US-UK-AU Product Ads | LINK_CLICKS",
    }
    # Remove purchase optimization dependency: clear promoted_object custom event
    # by setting only pixel if required - try without first
    ok, _ = await try_post(token, f"/{NEW}", fix_body, "switch to LINK_CLICKS")

    if not ok:
        # With promoted_object pixel only (no purchase event)
        fix_body2 = dict(fix_body)
        fix_body2["promoted_object"] = json.dumps({"pixel_id": "951904300717194"})
        ok, _ = await try_post(token, f"/{NEW}", fix_body2, "LINK_CLICKS + pixel only")

    if not ok:
        # LANDING_PAGE_VIEWS
        fix_body3 = {
            "optimization_goal": "LANDING_PAGE_VIEWS",
            "billing_event": "IMPRESSIONS",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "targeting": json.dumps(targeting),
            "status": "ACTIVE",
            "name": "MR | US-UK-AU Product Ads | LPV",
            "promoted_object": json.dumps({"pixel_id": "951904300717194"}),
        }
        ok, _ = await try_post(token, f"/{NEW}", fix_body3, "LANDING_PAGE_VIEWS")

    if not ok:
        # Keep OFFSITE_CONVERSIONS but use VIEW_CONTENT which may fire more often
        fix_body4 = {
            "optimization_goal": "OFFSITE_CONVERSIONS",
            "billing_event": "IMPRESSIONS",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "promoted_object": json.dumps(
                {
                    "pixel_id": "951904300717194",
                    "custom_event_type": "VIEW_CONTENT",
                }
            ),
            "targeting": json.dumps(targeting),
            "status": "ACTIVE",
            "name": "MR | US-UK-AU Product Ads | VIEW_CONTENT",
        }
        ok, _ = await try_post(token, f"/{NEW}", fix_body4, "VIEW_CONTENT conversions")

    # Ensure campaign + ads ACTIVE
    await try_post(token, f"/{CAMP}", {"status": "ACTIVE"}, "campaign ACTIVE")
    await try_post(token, f"/{NEW}", {"status": "ACTIVE"}, "adset ACTIVE")
    ads2 = await m._graph_get(
        f"/act_{act}/ads",
        token,
        {
            "fields": "id,name,status,effective_status",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": NEW}]
            ),
        },
    )
    for a in ads2.get("data") or []:
        if a.get("status") != "ACTIVE":
            await try_post(token, f"/{a['id']}", {"status": "ACTIVE"}, f"ad {a.get('name')}")
        else:
            print("ad already ACTIVE", a.get("name"), a.get("effective_status"))

    # Double-check old stays paused
    await try_post(token, f"/{OLD}", {"status": "PAUSED"}, "old India adset PAUSED")

    # Final read
    nas2 = await get(
        token,
        f"/{NEW}",
        "id,name,status,effective_status,optimization_goal,daily_budget,"
        "promoted_object,targeting,bid_strategy,billing_event",
    )
    print("\n=== FINAL NEW ADSET ===")
    print(json.dumps(nas2, indent=2, default=str))

    out = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "adset": nas2,
        "ads": ads2.get("data"),
        "note": "Switched delivery goal for cold traffic; India adset remains paused.",
    }
    os.makedirs("meta_drafts", exist_ok=True)
    with open("meta_drafts/delivery_fix_latest.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("WROTE meta_drafts/delivery_fix_latest.json")
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
