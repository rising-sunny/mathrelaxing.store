"""
Apply Meta optimization after billing fixed.
- Pause old IN/TH/MY ad set
- Create US/GB/AU ad set with advantage_audience flag
- Clone 3 winner ads (Celtic, STEM planner, Happy Chemicals)
- Pause weak ads on old set
- Leave CAMPAIGN PAUSED (user turned it off)
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
OLD_ADSET_ID = "120249615425210256"

WINNERS = [
    ("120249640557690256", "Celtic Knot Coloring $3.99"),
    ("120249640552280256", "STEM Focus Planner $2.99"),
    ("120249640551080256", "Happy Chemicals Print Set"),
]
WEAK = [
    ("120249640554330256", "Unit Circle"),
    ("120249640555810256", "Procreate Palettes"),
    ("120249640559780256", "Thomas Loop"),
    ("120249623948590256", "Collection legacy"),
]


async def try_post(token, path, body, label):
    try:
        r = await m._graph_post(path, token, body)
        print(f"OK  {label}: {json.dumps(r)[:200]}")
        return True, r
    except Exception as e:
        detail = getattr(e, "detail", str(e))
        print(f"FAIL {label}: {str(detail)[:450]}")
        return False, detail


async def main():
    token = await m._marketing_access_token()
    act = m._ad_account_id()
    acc = await m._ad_account_summary(token)
    status = acc.get("account_status")
    print(f"account={acc.get('name')} status={status} currency={acc.get('currency')}")
    if status != 1:
        print("WARNING: still not ACTIVE — continuing")

    # Snapshot old ad set
    old = await m._graph_get(
        f"/{OLD_ADSET_ID}",
        token,
        {
            "fields": "id,name,status,daily_budget,optimization_goal,billing_event,"
            "bid_strategy,promoted_object,attribution_spec,targeting,effective_status"
        },
    )
    print("old adset:", old.get("name"), old.get("status"), old.get("daily_budget"))
    print("old geo:", (old.get("targeting") or {}).get("geo_locations"))

    # 1) Pause old SEA ad set (stops India)
    print("\n=== PAUSE OLD AD SET ===")
    await try_post(token, f"/{OLD_ADSET_ID}", {"status": "PAUSED"}, "pause IN/TH/MY adset")

    # 2) Pause weak ads
    print("\n=== PAUSE WEAK ADS ===")
    for aid, name in WEAK:
        await try_post(token, f"/{aid}", {"status": "PAUSED"}, f"pause {name}")

    # 3) Create new US-UK-AU ad set
    print("\n=== CREATE US-UK-AU AD SET ===")
    targeting = {
        "geo_locations": {"countries": ["US", "GB", "AU"]},
        "age_min": 18,
        "age_max": 45,
        "targeting_automation": {"advantage_audience": 0},
    }
    promoted = old.get("promoted_object") or {
        "pixel_id": "951904300717194",
        "custom_event_type": "PURCHASE",
    }
    body = {
        "name": "MR | US-UK-AU Product Ads | qty-optimized",
        "campaign_id": CAMPAIGN_ID,
        "status": "PAUSED",
        "daily_budget": str(old.get("daily_budget") or "11400"),
        "billing_event": old.get("billing_event") or "IMPRESSIONS",
        "optimization_goal": old.get("optimization_goal") or "OFFSITE_CONVERSIONS",
        "bid_strategy": old.get("bid_strategy") or "LOWEST_COST_WITHOUT_CAP",
        "targeting": json.dumps(targeting),
        "promoted_object": json.dumps(promoted),
        "destination_type": "WEBSITE",
    }
    if old.get("attribution_spec"):
        body["attribution_spec"] = json.dumps(old["attribution_spec"])

    ok, res = await try_post(token, f"/act_{act}/adsets", body, "create adset")
    new_adset_id = res.get("id") if ok and isinstance(res, dict) else None

    if not new_adset_id:
        # Retry without attribution_spec / with is_adset_budget_sharing
        body2 = dict(body)
        body2.pop("attribution_spec", None)
        body2["is_adset_budget_sharing_enabled"] = "false"
        ok, res = await try_post(token, f"/act_{act}/adsets", body2, "create adset v2")
        new_adset_id = res.get("id") if ok and isinstance(res, dict) else None

    if not new_adset_id:
        # Last resort: try editing old ad set geo in place
        print("\n=== FALLBACK: edit old adset geo ===")
        ok, _ = await try_post(
            token,
            f"/{OLD_ADSET_ID}",
            {
                "name": "MR | US-UK-AU Product Ads | qty-optimized",
                "targeting": json.dumps(targeting),
                "status": "PAUSED",
            },
            "retarget old adset to US-UK-AU",
        )
        if ok:
            new_adset_id = OLD_ADSET_ID
            # On same adset: activate winners, weak already paused
            for aid, name in WINNERS:
                await try_post(token, f"/{aid}", {"status": "ACTIVE"}, f"active {name}")
        else:
            raise SystemExit("Could not create or retarget ad set")

    created_ads = []
    if new_adset_id and new_adset_id != OLD_ADSET_ID:
        print("\n=== CLONE WINNER ADS TO NEW AD SET ===", new_adset_id)
        for aid, name in WINNERS:
            ad = await m._graph_get(f"/{aid}", token, {"fields": "id,name,creative{id}"})
            cr_id = (ad.get("creative") or {}).get("id")
            if not cr_id:
                print("no creative for", name)
                continue
            ok, r = await try_post(
                token,
                f"/act_{act}/ads",
                {
                    "name": f"US-UK-AU | {name}",
                    "adset_id": new_adset_id,
                    "status": "PAUSED",
                    "creative": json.dumps({"creative_id": cr_id}),
                },
                f"clone {name}",
            )
            if ok and isinstance(r, dict):
                created_ads.append(
                    {"name": name, "ad_id": r.get("id"), "creative_id": cr_id, "source_ad": aid}
                )
                # Activate ad (campaign still paused → no spend)
                await try_post(
                    token, f"/{r['id']}", {"status": "ACTIVE"}, f"arm {name}"
                )

        # Arm ad set ACTIVE under paused campaign
        await try_post(token, f"/{new_adset_id}", {"status": "ACTIVE"}, "arm new adset")

    # 4) Keep campaign PAUSED (user preference)
    print("\n=== CAMPAIGN (keep PAUSED) ===")
    await try_post(
        token,
        f"/{CAMPAIGN_ID}",
        {
            "status": "PAUSED",
            "name": "MR | US-UK-AU Digital Products | READY",
        },
        "campaign paused ready",
    )

    # Snapshot
    camp = await m._graph_get(
        f"/{CAMPAIGN_ID}", token, {"fields": "id,name,status,effective_status"}
    )
    out = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "account_status": status,
        "campaign": camp,
        "old_adset_id": OLD_ADSET_ID,
        "new_adset_id": new_adset_id,
        "created_ads": created_ads,
        "note": "Campaign PAUSED. Turn ACTIVE when ready to spend on US/UK/AU only.",
        "ads_manager": (
            f"https://adsmanager.facebook.com/adsmanager/manage/adsets"
            f"?act={act}&selected_campaign_ids={CAMPAIGN_ID}"
        ),
    }
    if new_adset_id:
        nas = await m._graph_get(
            f"/{new_adset_id}",
            token,
            {"fields": "id,name,status,effective_status,daily_budget,targeting"},
        )
        out["new_adset"] = {
            "id": nas.get("id"),
            "name": nas.get("name"),
            "status": nas.get("status"),
            "effective": nas.get("effective_status"),
            "budget": nas.get("daily_budget"),
            "geo": (nas.get("targeting") or {}).get("geo_locations"),
        }
    old_as = await m._graph_get(
        f"/{OLD_ADSET_ID}",
        token,
        {"fields": "id,name,status,effective_status,targeting"},
    )
    out["old_adset"] = {
        "status": old_as.get("status"),
        "effective": old_as.get("effective_status"),
        "geo": (old_as.get("targeting") or {}).get("geo_locations"),
    }

    # List ads on new adset
    if new_adset_id:
        ads = await m._graph_get(
            f"/act_{act}/ads",
            token,
            {
                "fields": "id,name,status,effective_status",
                "filtering": json.dumps(
                    [{"field": "adset.id", "operator": "EQUAL", "value": new_adset_id}]
                ),
                "limit": 20,
            },
        )
        out["new_adset_ads"] = ads.get("data")

    os.makedirs("meta_drafts", exist_ok=True)
    path = "meta_drafts/sea_optimized_us_uk_au.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print("WROTE", path)
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
