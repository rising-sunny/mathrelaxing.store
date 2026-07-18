"""New OUTCOME_TRAFFIC campaign for US-UK-AU with LINK_CLICKS (cold traffic delivery)."""
import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
from routers import meta_ads as m

SALES_CAMP = "120249615423940256"
STUCK_ADSET = "120249651488300256"
CREATIVE_SOURCES = [
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
    print("account", (await m._ad_account_summary(token)).get("account_status"))

    # Pause sales campaign temporarily? Keep it active but pause stuck adset.
    await try_post(token, f"/{STUCK_ADSET}", {"status": "PAUSED"}, "pause stuck sales adset")

    # Create TRAFFIC campaign
    ok, camp = await try_post(
        token,
        f"/act_{act}/campaigns",
        {
            "name": "MR | US-UK-AU Traffic | Product PDPs",
            "objective": "OUTCOME_TRAFFIC",
            "status": "ACTIVE",
            "special_ad_categories": json.dumps([]),
            "is_adset_budget_sharing_enabled": "false",
        },
        "create TRAFFIC campaign",
    )
    if not ok or not camp:
        raise SystemExit("campaign create failed")
    camp_id = camp["id"]

    targeting = {
        "geo_locations": {"countries": ["US", "GB", "AU"]},
        "age_min": 18,
        "age_max": 65,  # required if advantage_audience=1
        "targeting_automation": {"advantage_audience": 1},
    }

    ok, adset = await try_post(
        token,
        f"/act_{act}/adsets",
        {
            "name": "US-UK-AU | LINK_CLICKS | Advantage",
            "campaign_id": camp_id,
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
        },
        "create LINK_CLICKS adset",
    )

    if not ok:
        # try without destination_type
        ok, adset = await try_post(
            token,
            f"/act_{act}/adsets",
            {
                "name": "US-UK-AU | LINK_CLICKS | Advantage",
                "campaign_id": camp_id,
                "status": "ACTIVE",
                "daily_budget": "11400",
                "billing_event": "IMPRESSIONS",
                "optimization_goal": "LINK_CLICKS",
                "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                "targeting": json.dumps(targeting),
            },
            "create LINK_CLICKS adset v2",
        )

    if not ok or not adset:
        # LANDING_PAGE_VIEWS under TRAFFIC
        ok, adset = await try_post(
            token,
            f"/act_{act}/adsets",
            {
                "name": "US-UK-AU | LANDING_PAGE_VIEWS",
                "campaign_id": camp_id,
                "status": "ACTIVE",
                "daily_budget": "11400",
                "billing_event": "IMPRESSIONS",
                "optimization_goal": "LANDING_PAGE_VIEWS",
                "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                "targeting": json.dumps(targeting),
                "promoted_object": json.dumps({"pixel_id": "951904300717194"}),
            },
            "create LPV under TRAFFIC",
        )

    if not ok or not adset:
        raise SystemExit("adset create failed")

    adset_id = adset["id"]
    created = []
    for aid, name in CREATIVE_SOURCES:
        ad = await m._graph_get(f"/{aid}", token, {"fields": "creative{id}"})
        cr = (ad.get("creative") or {}).get("id")
        ok, r = await try_post(
            token,
            f"/act_{act}/ads",
            {
                "name": f"Traffic | {name}",
                "adset_id": adset_id,
                "status": "ACTIVE",
                "creative": json.dumps({"creative_id": cr}),
            },
            f"ad {name}",
        )
        if ok and r:
            created.append({"name": name, "id": r.get("id")})

    # Pause old sales campaign to focus budget (user has one account budget)
    await try_post(
        token,
        f"/{SALES_CAMP}",
        {"status": "PAUSED", "name": "MR | US-UK-AU Sales PURCHASE | PAUSED (low delivery)"},
        "pause sales campaign",
    )

    # Verify
    camp_f = await m._graph_get(
        f"/{camp_id}", token, {"fields": "id,name,status,effective_status,objective"}
    )
    as_f = await m._graph_get(
        f"/{adset_id}",
        token,
        {
            "fields": "id,name,status,effective_status,optimization_goal,daily_budget,targeting"
        },
    )
    ads = await m._graph_get(
        f"/act_{act}/ads",
        token,
        {
            "fields": "id,name,status,effective_status",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": adset_id}]
            ),
        },
    )
    out = {
        "traffic_campaign": camp_f,
        "adset": as_f,
        "ads": ads.get("data"),
        "created": created,
        "sales_campaign_paused": SALES_CAMP,
        "url": f"https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={act}&selected_campaign_ids={camp_id}",
    }
    os.makedirs("meta_drafts", exist_ok=True)
    with open("meta_drafts/traffic_campaign_latest.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps(out, indent=2, default=str))
    print("DONE")


asyncio.run(main())
