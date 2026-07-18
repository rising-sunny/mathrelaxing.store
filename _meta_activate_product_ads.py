"""Activate SEA campaign + product ads; keep legacy collection ad paused."""
import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from routers import meta_ads as m

CAMPAIGN_ID = "120249615423940256"
ADSET_ID = "120249615425210256"
LEGACY_AD_ID = "120249623948590256"

# All 6 product ads — Meta will allocate spend; daily budget is shared at ad set.
PRODUCT_AD_IDS = [
    "120249640551080256",  # Happy Chemicals
    "120249640552280256",  # STEM Planner
    "120249640554330256",  # Unit Circle
    "120249640555810256",  # Procreate palettes
    "120249640557690256",  # Celtic coloring
    "120249640559780256",  # Thomas loop
]


async def set_status(token: str, obj_id: str, status: str, label: str) -> dict:
    try:
        await m._graph_post(f"/{obj_id}", token, {"status": status})
    except Exception as e:
        print(f"{label} set {status} FAIL:", e)
        raise
    detail = await m._graph_get(
        f"/{obj_id}",
        token,
        {"fields": "id,name,status,effective_status"},
    )
    print(f"{label}: status={detail.get('status')} effective={detail.get('effective_status')} name={detail.get('name')}")
    return detail


async def main():
    token = await m._marketing_access_token()
    act = m._ad_account_id()
    account = await m._ad_account_summary(token)
    print(
        "account",
        account.get("name"),
        "status",
        account.get("account_status"),
        "currency",
        account.get("currency"),
    )
    if account.get("account_status") != 1:
        raise SystemExit(f"Account not ACTIVE: {account.get('account_status')}")

    # Activate top-down: campaign → adset → product ads
    camp = await set_status(token, CAMPAIGN_ID, "ACTIVE", "campaign")
    adset = await set_status(token, ADSET_ID, "ACTIVE", "adset")

    # Keep legacy collection landing paused
    legacy = await set_status(token, LEGACY_AD_ID, "PAUSED", "legacy_collection")

    product_details = []
    for aid in PRODUCT_AD_IDS:
        d = await set_status(token, aid, "ACTIVE", f"ad:{aid}")
        product_details.append(d)

    # Final listing
    ads = await m._graph_get(
        f"/act_{act}/ads",
        token,
        {
            "fields": "id,name,status,effective_status",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": ADSET_ID}]
            ),
            "limit": 30,
        },
    )

    out = {
        "campaign": camp,
        "adset": adset,
        "legacy": legacy,
        "product_ads": product_details,
        "all_on_adset": ads.get("data"),
        "ads_manager": (
            f"https://adsmanager.facebook.com/adsmanager/manage/ads"
            f"?act={act}&selected_campaign_ids={CAMPAIGN_ID}"
        ),
    }
    os.makedirs("meta_drafts", exist_ok=True)
    with open("meta_drafts/sea_product_ads_activated.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
