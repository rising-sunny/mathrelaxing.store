"""Activate SEA campaign + adset + ad."""
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
AD_ID = "120249623948590256"


async def activate(obj_id: str, token: str, label: str) -> dict:
    try:
        result = await m._graph_post(f"/{obj_id}", token, {"status": "ACTIVE"})
        print(f"{label} activate response:", result)
    except Exception as e:
        print(f"{label} activate FAILED:", getattr(e, "detail", e))
        raise
    detail = await m._graph_get(
        f"/{obj_id}",
        token,
        {"fields": "id,name,status,effective_status"},
    )
    print(f"{label} now:", json.dumps(detail, ensure_ascii=False))
    return detail


async def main() -> None:
    token = await m._marketing_access_token()
    account = await m._ad_account_summary(token)
    status = account.get("account_status")
    print(f"account_status={status} name={account.get('name')}")
    if status != 1:
        raise SystemExit(f"Account not ACTIVE (status={status}); abort activate")

    camp = await activate(CAMPAIGN_ID, token, "campaign")
    adset = await activate(ADSET_ID, token, "adset")
    ad = await activate(AD_ID, token, "ad")

    out = {
        "campaign": camp,
        "adset": adset,
        "ad": ad,
        "ads_manager": (
            f"https://adsmanager.facebook.com/adsmanager/manage/campaigns"
            f"?act={m._ad_account_id()}&selected_campaign_ids={CAMPAIGN_ID}"
        ),
    }
    path = "meta_drafts/sea_in_th_my_activated.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("WROTE", path)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
