"""Resume SEA Meta campaign after billing fix: verify account ACTIVE, attach creative+ad."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from routers import meta_ads as m

CAMPAIGN_ID = "120249615423940256"
ADSET_ID = "120249615425210256"
VIDEO_PATH = Path("static/ads/sea_in_th_my_reel_short.mp4")
POSTER_URL = "https://mathrelaxing.store/static/ads/sea_in_th_my_reel_poster.jpg"
DEST = (
    "https://mathrelaxing.store/collection/digital-downloads"
    "?utm_source=meta&utm_medium=paid_social"
    "&utm_campaign=sea_in_th_my_math_art&utm_content=short_reel"
)
RESULT_PATH = Path("meta_drafts/sea_in_th_my_created_campaign.json")

STATUS_LABELS = {
    1: "ACTIVE",
    2: "DISABLED",
    3: "UNSETTLED",
    7: "PENDING_RISK_REVIEW",
    9: "IN_GRACE_PERIOD",
    100: "PENDING_CLOSURE",
    101: "CLOSED",
}


async def upload_advideo(token: str) -> str:
    act = m._ad_account_id()
    url = f"{m._graph_base()}/act_{act}/advideos"
    async with httpx.AsyncClient(timeout=300) as client:
        with VIDEO_PATH.open("rb") as fh:
            resp = await client.post(
                url,
                data={
                    "access_token": token,
                    "title": "SEA short reel",
                    "name": "SEA short reel",
                },
                files={"source": (VIDEO_PATH.name, fh, "video/mp4")},
            )
    if resp.status_code >= 400:
        raise RuntimeError(f"advideo upload failed: {resp.status_code} {resp.text[:800]}")
    vid = resp.json().get("id")
    if not vid:
        raise RuntimeError(resp.text[:500])
    return str(vid)


async def wait_video(token: str, video_id: str, timeout_s: int = 180) -> dict:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        last = await m._graph_get(
            f"/{video_id}",
            token,
            {"fields": "id,title,status,length,picture"},
        )
        st = last.get("status") or {}
        if isinstance(st, dict):
            vs = (st.get("video_status") or "").lower()
            if vs in {"ready", "complete", "completed"} or st.get("processing_progress") == 100:
                return last
            if "error" in vs:
                raise RuntimeError(f"video error: {st}")
        elif last.get("picture") or last.get("length"):
            return last
        await asyncio.sleep(3)
    print("video wait timeout; last=", last)
    return last


async def get_page_token(user_token: str, page_id: str) -> str | None:
    pages = await m._graph_get(
        "/me/accounts",
        user_token,
        {"fields": "id,name,access_token", "limit": 50},
    )
    for p in pages.get("data") or []:
        if str(p.get("id")) == str(page_id):
            return p.get("access_token")
    return None


async def create_creative(token: str, video_id: str, page_id: str) -> dict:
    act = m._ad_account_id()
    primary = (
        "Math that feels like art. Instant digital downloads — "
        "coloring books, STEM posters, seamless fractal loops."
    )
    title = "MathRelaxing · Digital Math Art"
    # Primary path: object_story_spec video_data
    body = {
        "name": "SEA Short | Video Creative",
        "object_story_spec": json.dumps(
            {
                "page_id": page_id,
                "video_data": {
                    "video_id": video_id,
                    "message": primary,
                    "title": title,
                    "call_to_action": {"type": "SHOP_NOW", "value": {"link": DEST}},
                    "image_url": POSTER_URL,
                },
            }
        ),
    }
    try:
        return await m._graph_post(f"/act_{act}/adcreatives", token, body)
    except Exception as e1:
        print("creative attempt1 failed:", getattr(e1, "detail", e1))
        # Fallback without image_url
        body2 = {
            "name": "SEA Short | Video Creative v2",
            "object_story_spec": json.dumps(
                {
                    "page_id": page_id,
                    "video_data": {
                        "video_id": video_id,
                        "message": primary,
                        "title": title,
                        "call_to_action": {
                            "type": "SHOP_NOW",
                            "value": {"link": DEST},
                        },
                    },
                }
            ),
        }
        return await m._graph_post(f"/act_{act}/adcreatives", token, body2)


async def list_ads_for_adset(token: str, adset_id: str) -> list:
    act = m._ad_account_id()
    data = await m._graph_get(
        f"/act_{act}/ads",
        token,
        {
            "fields": "id,name,status,effective_status,creative{id,name},adset_id",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": adset_id}]
            ),
            "limit": 20,
        },
    )
    return data.get("data") or []


async def main() -> None:
    if not VIDEO_PATH.exists():
        raise SystemExit(f"Missing video: {VIDEO_PATH}")

    token = await m._marketing_access_token()
    dbg = await m._debug_token(token)
    data = dbg.get("data") if isinstance(dbg.get("data"), dict) else dbg
    print("token_valid:", data.get("is_valid"), "scopes_sample:", (data.get("scopes") or [])[:8])

    account = await m._ad_account_summary(token)
    act = m._ad_account_id()
    status = account.get("account_status")
    print(
        "account:",
        account.get("name"),
        "id=",
        act,
        "status=",
        status,
        STATUS_LABELS.get(status, "?"),
        "currency=",
        account.get("currency"),
        "balance=",
        account.get("balance"),
        "amount_spent=",
        account.get("amount_spent"),
    )
    if status != 1:
        print("WARNING: account still not ACTIVE — creatives may still fail.")

    camp = await m._graph_get(
        f"/{CAMPAIGN_ID}",
        token,
        {"fields": "id,name,status,effective_status,objective,daily_budget,lifetime_budget"},
    )
    adset = await m._graph_get(
        f"/{ADSET_ID}",
        token,
        {
            "fields": "id,name,status,effective_status,daily_budget,optimization_goal,"
            "billing_event,targeting,campaign_id"
        },
    )
    print("campaign:", json.dumps(camp, ensure_ascii=False))
    print("adset:", json.dumps({k: adset.get(k) for k in adset if k != "targeting"}, ensure_ascii=False))
    targeting = adset.get("targeting") or {}
    print(
        "targeting countries=",
        targeting.get("geo_locations", {}).get("countries"),
        "locales=",
        targeting.get("locales"),
    )

    existing_ads = await list_ads_for_adset(token, ADSET_ID)
    print("existing ads on adset:", existing_ads)

    creative_id = None
    ad_id = None
    video_id = None

    if existing_ads:
        ad_id = existing_ads[0].get("id")
        cr = (existing_ads[0].get("creative") or {}).get("id")
        creative_id = cr
        print("Ad already exists — not recreating.")
    else:
        page_id = m._page_id()
        page_token = await get_page_token(token, page_id)
        print("page_id=", page_id, "page_token=", bool(page_token))

        print("Uploading video…")
        video_id = await upload_advideo(token)
        print("video_id=", video_id)
        await wait_video(token, video_id)

        print("Creating creative…")
        creative = await create_creative(token, video_id, page_id)
        creative_id = creative.get("id")
        print("creative_id=", creative_id)

        print("Creating PAUSED ad…")
        ad = await m._graph_post(
            f"/act_{act}/ads",
            token,
            {
                "name": "MathRelaxing SEA Short | Ad PAUSED",
                "status": "PAUSED",
                "adset_id": ADSET_ID,
                "creative": json.dumps({"creative_id": creative_id}),
            },
        )
        ad_id = ad.get("id")
        print("ad_id=", ad_id)

    # Final read
    ad_detail = None
    if ad_id:
        try:
            ad_detail = await m._graph_get(
                f"/{ad_id}",
                token,
                {"fields": "id,name,status,effective_status,creative{id,name,status}"},
            )
        except Exception as e:
            print("ad detail fail", e)

    result = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "account_id": act,
        "account_status": status,
        "account_status_label": STATUS_LABELS.get(status, str(status)),
        "account_name": account.get("name"),
        "currency": account.get("currency"),
        "campaign_id": CAMPAIGN_ID,
        "campaign": camp,
        "ad_set_id": ADSET_ID,
        "adset_status": adset.get("status"),
        "adset_effective": adset.get("effective_status"),
        "video_id": video_id,
        "creative_id": creative_id,
        "ad_id": ad_id,
        "ad_detail": ad_detail,
        "destination": DEST,
        "video_url": "https://mathrelaxing.store/static/ads/sea_in_th_my_reel_short.mp4",
        "ads_manager_campaign_url": (
            f"https://adsmanager.facebook.com/adsmanager/manage/campaigns"
            f"?act={act}&selected_campaign_ids={CAMPAIGN_ID}"
        ),
        "ads_manager_adset_url": (
            f"https://adsmanager.facebook.com/adsmanager/manage/adsets"
            f"?act={act}&selected_adset_ids={ADSET_ID}"
        ),
        "ads_manager_ad_url": (
            f"https://adsmanager.facebook.com/adsmanager/manage/ads"
            f"?act={act}&selected_ad_ids={ad_id}"
            if ad_id
            else None
        ),
        "note": (
            "All objects left PAUSED. Review in Ads Manager and set ACTIVE when ready to spend."
            if status == 1
            else "Account still not ACTIVE — fix billing fully before activating."
        ),
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    stamped = RESULT_PATH.with_name(
        f"sea_in_th_my_created_campaign_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    stamped.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("WROTE", RESULT_PATH, stamped)


if __name__ == "__main__":
    asyncio.run(main())
