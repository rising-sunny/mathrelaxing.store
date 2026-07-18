"""Create fresh US-UK-AU ad set optimized for LINK_CLICKS (better cold delivery)."""
import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
from routers import meta_ads as m

CAMP = "120249615423940256"
STUCK = "120249651488300256"  # purchase opt, almost no delivery
SOURCE_ADS = [
    ("120249651489580256", "Celtic Knot Coloring $3.99"),
    ("120249651490920256", "STEM Focus Planner $2.99"),
    ("120249651491660256", "Happy Chemicals Print Set"),
]


async def try_post(token, path, body, label):
    try:
        r = await m._graph_post(path, token, body)
        print(f"OK  {label}: {r}")
        return True, r
    except Exception as e:
        print(f"FAIL {label}: {str(getattr(e, 'detail', e))[:500]}")
        return False, None


async def main():
    token = await m._marketing_access_token()
    act = m._ad_account_id()
    acc = await m._ad_account_summary(token)
    print("account", acc.get("account_status"))

    targeting = {
        "geo_locations": {"countries": ["US", "GB", "AU"]},
        "age_min": 18,
        "age_max": 55,
        "targeting_automation": {"advantage_audience": 1},
    }

    # Create LINK_CLICKS ad set with 1-day attribution from birth
    body = {
        "name": "MR | US-UK-AU | LINK_CLICKS delivery",
        "campaign_id": CAMP,
        "status": "ACTIVE",
        "daily_budget": "11400",
        "billing_event": "IMPRESSIONS",
        "optimization_goal": "LINK_CLICKS",
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "destination_type": "WEBSITE",
        "targeting": json.dumps(targeting),
        "attribution_spec": json.dumps(
            [{"event_type": "CLICK_THROUGH", "window_days": 1}]
        ),
    }
    ok, res = await try_post(token, f"/act_{act}/adsets", body, "create LINK_CLICKS adset")
    if not ok:
        # Without destination_type
        body.pop("destination_type", None)
        ok, res = await try_post(token, f"/act_{act}/adsets", body, "create LINK_CLICKS v2")
    if not ok:
        # With pixel as promoted object for website
        body["promoted_object"] = json.dumps({"pixel_id": "951904300717194"})
        ok, res = await try_post(token, f"/act_{act}/adsets", body, "create LINK_CLICKS + pixel")

    if not ok or not isinstance(res, dict) or not res.get("id"):
        # LANDING_PAGE_VIEWS variant
        body = {
            "name": "MR | US-UK-AU | LANDING_PAGE_VIEWS",
            "campaign_id": CAMP,
            "status": "ACTIVE",
            "daily_budget": "11400",
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "LANDING_PAGE_VIEWS",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "targeting": json.dumps(targeting),
            "promoted_object": json.dumps({"pixel_id": "951904300717194"}),
            "attribution_spec": json.dumps(
                [{"event_type": "CLICK_THROUGH", "window_days": 1}]
            ),
        }
        ok, res = await try_post(token, f"/act_{act}/adsets", body, "create LPV adset")

    if not ok or not res or not res.get("id"):
        raise SystemExit("Could not create delivery ad set")

    new_id = res["id"]
    print("NEW_ADSET", new_id)

    # Pause stuck purchase adset so budget focuses on new one
    await try_post(token, f"/{STUCK}", {"status": "PAUSED"}, "pause stuck PURCHASE adset")

    created = []
    for aid, name in SOURCE_ADS:
        ad = await m._graph_get(f"/{aid}", token, {"fields": "id,creative{id}"})
        cr = (ad.get("creative") or {}).get("id")
        if not cr:
            print("no creative", name)
            continue
        ok, r = await try_post(
            token,
            f"/act_{act}/ads",
            {
                "name": f"US-UK-AU Traffic | {name}",
                "adset_id": new_id,
                "status": "ACTIVE",
                "creative": json.dumps({"creative_id": cr}),
            },
            f"ad {name}",
        )
        if ok and r:
            created.append({"name": name, "ad_id": r.get("id"), "creative_id": cr})

    await try_post(token, f"/{CAMP}", {"status": "ACTIVE"}, "campaign ACTIVE")
    await try_post(token, f"/{new_id}", {"status": "ACTIVE"}, "new adset ACTIVE")

    nas = await m._graph_get(
        f"/{new_id}",
        token,
        {
            "fields": "id,name,status,effective_status,optimization_goal,daily_budget,"
            "targeting,attribution_spec,promoted_object"
        },
    )
    ads = await m._graph_get(
        f"/act_{act}/ads",
        token,
        {
            "fields": "id,name,status,effective_status",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": new_id}]
            ),
        },
    )
    out = {
        "new_adset": nas,
        "ads": ads.get("data"),
        "created": created,
        "paused_stuck_adset": STUCK,
        "ads_manager": (
            f"https://adsmanager.facebook.com/adsmanager/manage/adsets"
            f"?act={act}&selected_campaign_ids={CAMP}"
        ),
    }
    os.makedirs("meta_drafts", exist_ok=True)
    with open("meta_drafts/link_clicks_adset.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps(out, indent=2, default=str))
    print("DONE")


asyncio.run(main())
