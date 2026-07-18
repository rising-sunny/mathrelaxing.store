"""Fix delivery: CONTENT_VIEW + 1-day attribution; optional LINK_CLICKS fallback."""
import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
from routers import meta_ads as m

NEW = "120249651488300256"
CAMP = "120249615423940256"
PIXEL = "951904300717194"


async def try_post(token, path, body, label):
    try:
        r = await m._graph_post(path, token, body)
        print(f"OK  {label}: {r}")
        return True, r
    except Exception as e:
        print(f"FAIL {label}: {str(getattr(e, 'detail', e))[:450]}")
        return False, None


async def main():
    token = await m._marketing_access_token()

    targeting = {
        "geo_locations": {"countries": ["US", "GB", "AU"]},
        "age_min": 18,
        "age_max": 55,
        "targeting_automation": {"advantage_audience": 0},
    }

    # Attempt 1: CONTENT_VIEW (more frequent than PURCHASE)
    ok, _ = await try_post(
        token,
        f"/{NEW}",
        {
            "name": "MR | US-UK-AU | Optimize CONTENT_VIEW",
            "optimization_goal": "OFFSITE_CONVERSIONS",
            "billing_event": "IMPRESSIONS",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "promoted_object": json.dumps(
                {"pixel_id": PIXEL, "custom_event_type": "CONTENT_VIEW"}
            ),
            "attribution_spec": json.dumps(
                [{"event_type": "CLICK_THROUGH", "window_days": 1}]
            ),
            "targeting": json.dumps(targeting),
            "status": "ACTIVE",
        },
        "CONTENT_VIEW + 1d attribution",
    )

    if not ok:
        # Attempt 2: LINK_CLICKS with 1d attribution, no promoted_object event
        ok, _ = await try_post(
            token,
            f"/{NEW}",
            {
                "name": "MR | US-UK-AU | Optimize LINK_CLICKS",
                "optimization_goal": "LINK_CLICKS",
                "billing_event": "IMPRESSIONS",
                "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                "attribution_spec": json.dumps(
                    [{"event_type": "CLICK_THROUGH", "window_days": 1}]
                ),
                "targeting": json.dumps(targeting),
                "status": "ACTIVE",
            },
            "LINK_CLICKS + 1d attribution",
        )

    if not ok:
        # Attempt 3: ADD_TO_CART mid-funnel
        ok, _ = await try_post(
            token,
            f"/{NEW}",
            {
                "name": "MR | US-UK-AU | Optimize ADD_TO_CART",
                "optimization_goal": "OFFSITE_CONVERSIONS",
                "billing_event": "IMPRESSIONS",
                "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                "promoted_object": json.dumps(
                    {"pixel_id": PIXEL, "custom_event_type": "ADD_TO_CART"}
                ),
                "attribution_spec": json.dumps(
                    [{"event_type": "CLICK_THROUGH", "window_days": 1}]
                ),
                "targeting": json.dumps(targeting),
                "status": "ACTIVE",
            },
            "ADD_TO_CART + 1d",
        )

    if not ok:
        # Attempt 4: enable advantage audience for more delivery
        ok, _ = await try_post(
            token,
            f"/{NEW}",
            {
                "name": "MR | US-UK-AU | Advantage + PURCHASE",
                "optimization_goal": "OFFSITE_CONVERSIONS",
                "promoted_object": json.dumps(
                    {"pixel_id": PIXEL, "custom_event_type": "PURCHASE"}
                ),
                "targeting": json.dumps(
                    {
                        "geo_locations": {"countries": ["US", "GB", "AU"]},
                        "age_min": 18,
                        "age_max": 65,
                        "targeting_automation": {"advantage_audience": 1},
                    }
                ),
                "status": "ACTIVE",
            },
            "Advantage audience + wider age",
        )

    await try_post(token, f"/{CAMP}", {"status": "ACTIVE"}, "campaign ACTIVE")
    await try_post(token, f"/{NEW}", {"status": "ACTIVE"}, "adset ACTIVE")

    nas = await m._graph_get(
        f"/{NEW}",
        token,
        {
            "fields": "id,name,status,effective_status,optimization_goal,daily_budget,"
            "budget_remaining,promoted_object,targeting,attribution_spec,bid_strategy"
        },
    )
    print("\nFINAL", json.dumps(nas, indent=2, default=str))

    # insights again
    for node, label in [(NEW, "adset"), (CAMP, "campaign")]:
        d = await m._graph_get(
            f"/{node}/insights",
            token,
            {
                "fields": "impressions,spend,clicks,inline_link_clicks",
                "date_preset": "today",
            },
        )
        print(f"insights {label}:", d.get("data"))

    with open("meta_drafts/delivery_fix2.json", "w") as f:
        json.dump(nas, f, indent=2, default=str)
    print("DONE")


asyncio.run(main())
