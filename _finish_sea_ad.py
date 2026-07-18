"""Attach creative/ad to the already-created SEA campaign+adset if possible."""
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from routers import meta_ads as m

CAMPAIGN_ID = "120249615423940256"
ADSET_ID = "120249615425210256"
VIDEO_ID = "1815216556304554"  # from last run
POSTER_URL = "https://mathrelaxing.store/static/ads/sea_in_th_my_reel_poster.jpg"
DEST = "https://mathrelaxing.store/collection/digital-downloads?utm_source=meta&utm_medium=paid_social&utm_campaign=sea_in_th_my_math_art&utm_content=short_reel"


async def main() -> None:
    token = await m._marketing_access_token()
    act = m._ad_account_id()

    # Inspect existing objects
    camp = await m._graph_get(
        f"/{CAMPAIGN_ID}",
        token,
        {"fields": "id,name,status,effective_status,objective"},
    )
    adset = await m._graph_get(
        f"/{ADSET_ID}",
        token,
        {"fields": "id,name,status,effective_status,daily_budget,targeting,optimization_goal"},
    )
    print("campaign:", camp)
    print("adset:", adset)

    # Try create ad creative via page unpublished video post then use object_story_id
    page_id = m._page_id()
    print("page_id", page_id)

    # Get page access token from /me/accounts
    pages = await m._graph_get(
        "/me/accounts",
        token,
        {"fields": "id,name,access_token", "limit": 50},
    )
    page_token = None
    for p in pages.get("data") or []:
        if str(p.get("id")) == str(page_id):
            page_token = p.get("access_token")
            break
    print("page_token found:", bool(page_token))

    creative_id = None
    ad_id = None

    if page_token:
        # Publish unpublished page video (is_published=false) then promote
        try:
            # Upload video to page
            import httpx

            video_path = Path("static/ads/sea_in_th_my_reel_short.mp4")
            async with httpx.AsyncClient(timeout=300) as client:
                with video_path.open("rb") as fh:
                    resp = await client.post(
                        f"{m._graph_base()}/{page_id}/videos",
                        data={
                            "access_token": page_token,
                            "title": "MathRelaxing · Digital Math Art",
                            "description": (
                                "Math that feels like art. Instant digital downloads — "
                                "coloring books, STEM posters, fractal loops.\n"
                                f"{DEST}"
                            ),
                            "published": "false",
                        },
                        files={"source": (video_path.name, fh, "video/mp4")},
                    )
            print("page video upload status", resp.status_code, resp.text[:500])
            if resp.status_code < 400:
                page_video_id = resp.json().get("id")
                print("page_video_id", page_video_id)
                # Create creative from object_story_id if we get a post id
                # For unpublished videos, Graph may return video id; create feed post?
                # Alternative: ad creative with object_story_spec video_data using page token
                try:
                    creative = await m._graph_post(
                        f"/act_{act}/adcreatives",
                        token,
                        {
                            "name": "SEA Short | Page Video Creative",
                            "object_story_spec": json.dumps(
                                {
                                    "page_id": page_id,
                                    "video_data": {
                                        "video_id": page_video_id or VIDEO_ID,
                                        "message": (
                                            "Math that feels like art. Instant digital downloads — "
                                            "coloring books, STEM posters, seamless fractal loops."
                                        ),
                                        "title": "MathRelaxing · Digital Math Art",
                                        "call_to_action": {
                                            "type": "SHOP_NOW",
                                            "value": {"link": DEST},
                                        },
                                        "image_url": POSTER_URL,
                                    },
                                }
                            ),
                        },
                    )
                    creative_id = creative["id"]
                    print("creative_id", creative_id)
                except Exception as e:
                    print("creative with page video failed", getattr(e, "detail", e))
        except Exception as e:
            print("page video path failed", e)

    if not creative_id:
        # Last resort: reuse any existing creative from account
        try:
            creatives = await m._graph_get(
                f"/act_{act}/adcreatives",
                token,
                {"fields": "id,name,status,object_type", "limit": 10},
            )
            print("existing creatives sample:", creatives.get("data"))
        except Exception as e:
            print("list creatives fail", getattr(e, "detail", e))

    if creative_id:
        try:
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
            ad_id = ad["id"]
            print("ad_id", ad_id)
        except Exception as e:
            print("create ad fail", getattr(e, "detail", e))

    result = {
        "campaign_id": CAMPAIGN_ID,
        "ad_set_id": ADSET_ID,
        "creative_id": creative_id,
        "ad_id": ad_id,
        "ads_manager_campaign_url": (
            f"https://adsmanager.facebook.com/adsmanager/manage/campaigns"
            f"?act={act}&selected_campaign_ids={CAMPAIGN_ID}"
        ),
        "ads_manager_adset_url": (
            f"https://adsmanager.facebook.com/adsmanager/manage/adsets"
            f"?act={act}&selected_adset_ids={ADSET_ID}"
        ),
        "video_url": "https://mathrelaxing.store/static/ads/sea_in_th_my_reel_short.mp4",
        "account_status": 3,
        "note": (
            "Campaign + ad set exist PAUSED. Creative/ad may require fixing billing "
            "(UNSETTLED) or manual attach in Ads Manager."
        ),
    }
    Path("meta_drafts/sea_in_th_my_created_campaign.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
