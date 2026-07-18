"""Try partial Meta updates while account UNSETTLED; create new US-UK-AU ad set if needed."""
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
OLD_ADSET_ID = "120249615425210256"

ACTIVE_ADS = [
    ("120249640557690256", "Celtic Knot"),
    ("120249640552280256", "STEM Planner"),
    ("120249640551080256", "Happy Chemicals"),
]
PAUSE_ADS = [
    ("120249640554330256", "Unit Circle"),
    ("120249640555810256", "Procreate"),
    ("120249640559780256", "Thomas Loop"),
    ("120249623948590256", "Legacy collection"),
]


async def try_post(token, path, body, label):
    try:
        r = await m._graph_post(path, token, body)
        print(f"OK  {label}: {r}")
        return True, r
    except Exception as e:
        detail = getattr(e, "detail", str(e))
        print(f"FAIL {label}: {detail}"[:500])
        return False, detail


async def main():
    token = await m._marketing_access_token()
    act = m._ad_account_id()
    acc = await m._ad_account_summary(token)
    print("account_status", acc.get("account_status"), "(3=UNSETTLED)")

    # Pause old IN/TH/MY ad set entirely (stops India spend)
    print("\n=== PAUSE OLD SEA AD SET ===")
    await try_post(token, f"/{OLD_ADSET_ID}", {"status": "PAUSED"}, "pause old adset")

    # Pause non-winner ads
    print("\n=== PAUSE WEAK ADS ===")
    for aid, name in PAUSE_ADS:
        await try_post(token, f"/{aid}", {"status": "PAUSED"}, f"pause {name}")

    # Try keep winners active (may still be under paused ad set)
    print("\n=== ACTIVATE WINNER ADS (on old set) ===")
    for aid, name in ACTIVE_ADS:
        await try_post(token, f"/{aid}", {"status": "ACTIVE"}, f"active {name}")

    # Create NEW ad set with US/UK/AU
    print("\n=== CREATE NEW AD SET US-UK-AU ===")
    targeting = {
        "geo_locations": {"countries": ["US", "GB", "AU"]},
        "age_min": 18,
        "age_max": 45,
    }
    # Copy budget from old if possible
    old = await m._graph_get(
        f"/{OLD_ADSET_ID}",
        token,
        {"fields": "daily_budget,optimization_goal,billing_event,bid_strategy,promoted_object,attribution_spec"},
    )
    print("old adset fields", {k: old.get(k) for k in old if k != "targeting"})

    new_adset_body = {
        "name": "MR | US-UK-AU Product Ads | ACTIVE",
        "campaign_id": CAMPAIGN_ID,
        "status": "PAUSED",  # create paused first
        "daily_budget": str(old.get("daily_budget") or "11400"),
        "billing_event": old.get("billing_event") or "IMPRESSIONS",
        "optimization_goal": old.get("optimization_goal") or "OFFSITE_CONVERSIONS",
        "bid_strategy": old.get("bid_strategy") or "LOWEST_COST_WITHOUT_CAP",
        "targeting": json.dumps(targeting),
        # required for OUTCOME_SALES sometimes
        "promoted_object": json.dumps(old.get("promoted_object") or {}),
    }
    # Clean empty promoted_object
    if new_adset_body["promoted_object"] in ("{}", "null"):
        # try get from campaign
        camp = await m._graph_get(
            f"/{CAMPAIGN_ID}",
            token,
            {"fields": "id,objective,promoted_object"},
        )
        print("campaign", camp)
        if camp.get("promoted_object"):
            new_adset_body["promoted_object"] = json.dumps(camp["promoted_object"])
        else:
            del new_adset_body["promoted_object"]

    ok, res = await try_post(
        token, f"/act_{act}/adsets", new_adset_body, "create US-UK-AU adset"
    )
    new_adset_id = None
    if ok and isinstance(res, dict):
        new_adset_id = res.get("id")

    # If create failed due to missing fields, try with is_adset_budget_sharing etc
    if not new_adset_id:
        print("retry create with destination_type")
        new_adset_body2 = {
            "name": "MR | US-UK-AU Product Ads | ACTIVE",
            "campaign_id": CAMPAIGN_ID,
            "status": "PAUSED",
            "daily_budget": str(old.get("daily_budget") or "11400"),
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "LINK_CLICKS",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "targeting": json.dumps(targeting),
            "destination_type": "WEBSITE",
        }
        ok, res = await try_post(
            token, f"/act_{act}/adsets", new_adset_body2, "create adset v2 LINK_CLICKS"
        )
        if ok and isinstance(res, dict):
            new_adset_id = res.get("id")

    created_ads = []
    if new_adset_id:
        print("new_adset_id", new_adset_id)
        # Copy creatives from winner ads into new ad set
        for aid, name in ACTIVE_ADS:
            try:
                ad = await m._graph_get(
                    f"/{aid}",
                    token,
                    {"fields": "id,name,creative{id}"},
                )
                cr_id = (ad.get("creative") or {}).get("id")
                print(f"  source ad {name} creative={cr_id}")
                if not cr_id:
                    continue
                body = {
                    "name": f"SEA US-UK-AU | {name} | PAUSED",
                    "adset_id": new_adset_id,
                    "status": "PAUSED",
                    "creative": json.dumps({"creative_id": cr_id}),
                }
                ok, r = await try_post(token, f"/act_{act}/ads", body, f"clone {name}")
                if ok and isinstance(r, dict):
                    created_ads.append({"name": name, "ad_id": r.get("id"), "creative_id": cr_id})
            except Exception as e:
                print("clone fail", name, e)

        # Activate new ad set + ads if account allows
        await try_post(token, f"/{new_adset_id}", {"status": "ACTIVE"}, "activate new adset")
        for a in created_ads:
            await try_post(token, f"/{a['ad_id']}", {"status": "ACTIVE"}, f"activate {a['name']}")

    # Campaign status
    await try_post(
        token,
        f"/{CAMPAIGN_ID}",
        {"status": "ACTIVE", "name": "MR | US-UK-AU Digital Products | Sales"},
        "campaign active",
    )

    # Final snapshot
    camp = await m._graph_get(
        f"/{CAMPAIGN_ID}", token, {"fields": "id,name,status,effective_status"}
    )
    old_as = await m._graph_get(
        f"/{OLD_ADSET_ID}",
        token,
        {"fields": "id,name,status,effective_status,targeting"},
    )
    out = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "account_status": acc.get("account_status"),
        "account_status_note": "3=UNSETTLED blocks some write actions / delivery",
        "campaign": camp,
        "old_adset": {
            "id": OLD_ADSET_ID,
            "status": old_as.get("status"),
            "effective": old_as.get("effective_status"),
            "countries": (old_as.get("targeting") or {}).get("geo_locations"),
        },
        "new_adset_id": new_adset_id,
        "created_ads": created_ads,
        "ads_manager": (
            f"https://adsmanager.facebook.com/adsmanager/manage/campaigns"
            f"?act={act}&selected_campaign_ids={CAMPAIGN_ID}"
        ),
    }
    if new_adset_id:
        nas = await m._graph_get(
            f"/{new_adset_id}",
            token,
            {"fields": "id,name,status,effective_status,targeting,daily_budget"},
        )
        out["new_adset"] = nas

    os.makedirs("meta_drafts", exist_ok=True)
    with open("meta_drafts/sea_optimized_us_uk_au.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
