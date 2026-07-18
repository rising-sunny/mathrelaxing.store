"""
Create SEA (IN/TH/MY) Meta campaign in PAUSED status using the short reel video.

Bypasses the web admin cookie; uses VPS env + tokens.
Allows UNSETTLED accounts (still creates PAUSED objects; no delivery until billing fixed).

  .venv/bin/python _create_sea_paused_campaign.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from routers import meta_ads as m

DRAFT_PATH = Path("meta_drafts/sea_in_th_my_draft_latest.json")
VIDEO_PATH = Path("static/ads/sea_in_th_my_reel_short.mp4")
POSTER_URL = "https://mathrelaxing.store/static/ads/sea_in_th_my_reel_poster.jpg"
RESULT_PATH = Path("meta_drafts/sea_in_th_my_created_campaign.json")


async def upload_video(token: str, path: Path, title: str) -> str:
    """Upload local video file to ad account; return video_id."""
    act = m._ad_account_id()
    url = f"{m._graph_base()}/act_{act}/advideos"
    async with httpx.AsyncClient(timeout=300) as client:
        with path.open("rb") as fh:
            files = {"source": (path.name, fh, "video/mp4")}
            data = {
                "access_token": token,
                "title": title[:100],
                "name": title[:100],
            }
            resp = await client.post(url, data=data, files=files)
    if resp.status_code >= 400:
        raise RuntimeError(f"Video upload failed: {resp.status_code} {resp.text[:800]}")
    body = resp.json()
    vid = body.get("id")
    if not vid:
        raise RuntimeError(f"No video id in response: {body}")
    return str(vid)


async def wait_video_ready(token: str, video_id: str, timeout_s: int = 180) -> dict:
    """Poll video status until ready (or timeout)."""
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        last = await m._graph_get(
            f"/{video_id}",
            token=token,
            params={"fields": "id,title,status,length,picture"},
        )
        status = last.get("status") or {}
        # status can be dict with video_status or string
        if isinstance(status, dict):
            vs = (status.get("video_status") or status.get("uploading_phase") or "").lower()
            if vs in {"ready", "complete", "completed"} or status.get("processing_progress") == 100:
                return last
            if "error" in vs:
                raise RuntimeError(f"Video processing error: {status}")
        else:
            # some responses just return id once processable
            if last.get("picture") or last.get("length"):
                return last
        await asyncio.sleep(3)
    print("WARNING: video wait timed out; proceeding anyway. last=", last)
    return last


async def create() -> dict:
    if not DRAFT_PATH.exists():
        raise SystemExit(f"Missing draft: {DRAFT_PATH}")
    if not VIDEO_PATH.exists():
        raise SystemExit(f"Missing video: {VIDEO_PATH}")

    draft = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))
    payload = draft["api_draft_payload"]
    copy = draft.get("copy") or {}
    interests = draft.get("interests_selected") or payload.get("interests") or []
    locales = payload.get("locales") or [6, 24, 46, 35, 41]

    # Prefer short-reel friendly copy
    title = (copy.get("headline_en") or payload.get("title") or "MathRelaxing Digital Math Art")[:80]
    primary = (copy.get("primary_en") or payload.get("primary_text") or "")[:500]
    dest = (
        copy.get("landing")
        or payload.get("destination_url")
        or "https://mathrelaxing.store/collection/digital-downloads?utm_source=meta&utm_medium=paid_social&utm_campaign=sea_in_th_my_math_art&utm_content=short_reel"
    )
    # Ensure destination is HTTPS mathrelaxing
    m._validate_site_url(dest, "Destination URL")
    m._validate_site_url(POSTER_URL, "Poster URL")

    token = await m._marketing_access_token()
    dbg = await m._debug_token(token)
    data = dbg.get("data") if isinstance(dbg.get("data"), dict) else dbg
    if not data.get("is_valid"):
        raise SystemExit(f"Token invalid: {data}")

    account = await m._ad_account_summary(token)
    currency = account.get("currency") or "CLP"
    status = account.get("account_status")
    print("account:", account.get("name"), "status=", status, "currency=", currency)
    if status != 1:
        print(
            "WARNING: ad account not ACTIVE (UNSETTLED/other). "
            "Creating PAUSED objects anyway — delivery may be blocked until billing is fixed."
        )

    budget_amount = float(
        draft.get("budget_and_bidding", {})
        .get("recommended", {})
        .get("daily_budget_clp_test")
        or payload.get("daily_budget_amount")
        or 11400
    )
    daily_budget = m._budget_to_meta_units(budget_amount, currency)
    print("daily_budget:", budget_amount, currency, "-> meta units", daily_budget)

    # 1) Upload video
    print("Uploading short reel…", VIDEO_PATH)
    video_id = await upload_video(token, VIDEO_PATH, f"SEA short reel {int(time.time())}")
    print("video_id:", video_id)
    await wait_video_ready(token, video_id)

    # 2) Optional poster as image hash for thumbnail
    try:
        image_hash = await m._upload_ad_image(
            token, POSTER_URL, f"sea-poster-{int(time.time())}.jpg"
        )
        print("image_hash:", image_hash)
    except Exception as e:
        print("poster upload failed, continuing without hash:", e)
        image_hash = None

    stamp = time.strftime("%Y%m%d-%H%M", time.gmtime())
    campaign_name = f"MR | SEA IN-TH-MY Math Art Short | {stamp} | PAUSED"

    # Targeting
    targeting: dict = {
        "geo_locations": {"countries": ["IN", "TH", "MY"]},
        "age_min": int(payload.get("age_min") or 22),
        "age_max": int(payload.get("age_max") or 55),
        "targeting_automation": {"advantage_audience": 0},
        "locales": [int(x) for x in locales],
    }
    if interests:
        targeting["flexible_spec"] = [
            {
                "interests": [
                    {"id": str(i["id"]), "name": i.get("name") or ""}
                    for i in interests
                    if i.get("id")
                ]
            }
        ]

    video_data: dict = {
        "video_id": video_id,
        "message": primary,
        "title": title[:255],
        "call_to_action": {
            "type": "SHOP_NOW",
            "value": {"link": dest},
        },
        "link_description": "Instant digital download · mathrelaxing.store",
    }
    if image_hash:
        video_data["image_hash"] = image_hash
    else:
        video_data["image_url"] = POSTER_URL

    creative_spec = {
        "name": f"{title[:40]} | SEA Short Reel Creative",
        "object_story_spec": {
            "page_id": m._page_id(),
            "video_data": video_data,
        },
    }

    campaign_spec = {
        "name": campaign_name,
        "objective": "OUTCOME_SALES",
        "status": "PAUSED",
        "special_ad_categories": [],
        "buying_type": "AUCTION",
        # Required by Meta when using ad set budgets (not CBO)
        "is_adset_budget_sharing_enabled": "false",
        "dsa_beneficiary": "MathRelaxing",
        "dsa_payor": "MathRelaxing",
    }

    adset_spec = {
        "name": f"{campaign_name} | IN-TH-MY",
        "status": "PAUSED",
        "daily_budget": daily_budget,
        "billing_event": "IMPRESSIONS",
        "optimization_goal": "OFFSITE_CONVERSIONS",
        "destination_type": "WEBSITE",
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "dsa_beneficiary": "MathRelaxing",
        "dsa_payor": "MathRelaxing",
        "promoted_object": {
            "pixel_id": m._pixel_id(),
            "custom_event_type": "PURCHASE",
        },
        "targeting": targeting,
    }

    # _graph_post uses form data - nested structures often need JSON strings
    act = m._ad_account_id()
    created: list[dict] = []

    async def post(path: str, data: dict) -> dict:
        # Flatten nested dicts to JSON strings for form encoding
        flat = {}
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                flat[k] = json.dumps(v)
            elif v is None:
                continue
            else:
                flat[k] = v
        return await m._graph_post(path, token, flat)

    # Create campaign first (works even when some creative ops are restricted)
    print("Creating campaign…")
    campaign = await post(f"/act_{act}/campaigns", campaign_spec)
    campaign_id = campaign["id"]
    created.append({"type": "campaign", "id": campaign_id})
    print("campaign_id:", campaign_id)

    print("Creating ad set…")
    adset_spec["campaign_id"] = campaign_id
    try:
        ad_set = await post(f"/act_{act}/adsets", adset_spec)
    except Exception as e1:
        # Thailand sometimes requires regional regulation identities; retry without locales first
        print("ad set first attempt failed:", getattr(e1, "detail", e1))
        # Try with advantage+ simplified targeting if regulation blocks
        simple_targeting = {
            "geo_locations": {"countries": ["IN", "TH", "MY"]},
            "age_min": 22,
            "age_max": 55,
        }
        adset_spec["targeting"] = simple_targeting
        print("retrying ad set with simplified targeting…")
        ad_set = await post(f"/act_{act}/adsets", adset_spec)
    ad_set_id = ad_set["id"]
    created.append({"type": "ad_set", "id": ad_set_id})
    print("ad_set_id:", ad_set_id)

    print("Creating creative…")
    try:
        creative = await post(f"/act_{act}/adcreatives", creative_spec)
    except Exception as e_cre:
        print("video creative failed:", getattr(e_cre, "detail", e_cre))
        print("falling back to image link creative…")
        # Fallback: image-only link ad using poster
        link_data = {
            "link": dest,
            "message": primary,
            "name": title,
            "call_to_action": {"type": "SHOP_NOW", "value": {"link": dest}},
        }
        if image_hash:
            link_data["image_hash"] = image_hash
        else:
            link_data["picture"] = POSTER_URL
        creative = await post(
            f"/act_{act}/adcreatives",
            {
                "name": f"{title[:40]} | SEA Image Creative",
                "object_story_spec": {
                    "page_id": m._page_id(),
                    "link_data": link_data,
                },
            },
        )
    creative_id = creative["id"]
    created.append({"type": "creative", "id": creative_id})
    print("creative_id:", creative_id)

    print("Creating ad…")
    ad = await post(
        f"/act_{act}/ads",
        {
            "name": f"{title[:40]} | SEA Short Ad",
            "status": "PAUSED",
            "adset_id": ad_set_id,
            "creative": {"creative_id": creative_id},
        },
    )
    ad_id = ad["id"]
    created.append({"type": "ad", "id": ad_id})
    print("ad_id:", ad_id)

    link = (
        f"https://adsmanager.facebook.com/adsmanager/manage/campaigns"
        f"?act={act}&selected_campaign_ids={campaign_id}"
    )
    ad_link = (
        f"https://adsmanager.facebook.com/adsmanager/manage/ads"
        f"?act={act}&selected_ad_ids={ad_id}"
    )

    result = {
        "ok": True,
        "mode": "created_paused",
        "account_status": status,
        "currency": currency,
        "daily_budget_amount": budget_amount,
        "daily_budget_meta_units": daily_budget,
        "video_id": video_id,
        "created": created,
        "campaign_id": campaign_id,
        "ad_set_id": ad_set_id,
        "ad_id": ad_id,
        "creative_id": creative_id,
        "ads_manager_campaign_url": link,
        "ads_manager_ad_url": ad_link,
        "video_url": "https://mathrelaxing.store/static/ads/sea_in_th_my_reel_short.mp4",
        "destination_url": dest,
        "targeting": targeting,
        "campaign_name": campaign_name,
        "note": "All objects PAUSED. Resolve UNSETTLED billing before activating.",
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    # also stamp a dated copy
    stamped = Path(f"meta_drafts/sea_in_th_my_created_campaign_{stamp.replace(':', '')}.json")
    stamped.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== SUCCESS ===")
    print("Campaign:", campaign_name)
    print("Link:", link)
    print("Ad link:", ad_link)
    print("Saved:", RESULT_PATH)
    return result


if __name__ == "__main__":
    try:
        asyncio.run(create())
    except Exception as e:
        print("FAILED:", type(e).__name__, e)
        # print HTTP detail if any
        if hasattr(e, "detail"):
            print("detail:", e.detail)
        raise
