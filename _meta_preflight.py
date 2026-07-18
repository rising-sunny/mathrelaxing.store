"""Pre-flight review of Meta US-UK-AU campaign before activation."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from urllib.parse import parse_qs, urlparse

import httpx
from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from routers import meta_ads as m

CAMPAIGN_ID = "120249615423940256"
NEW_ADSET_ID = "120249651488300256"
OLD_ADSET_ID = "120249615425210256"

STATUS_LABELS = {
    1: "ACTIVE",
    2: "DISABLED",
    3: "UNSETTLED",
    7: "PENDING_RISK_REVIEW",
    9: "IN_GRACE_PERIOD",
    100: "PENDING_CLOSURE",
    101: "CLOSED",
}


async def main():
    token = await m._marketing_access_token()
    act = m._ad_account_id()
    page_id = m._page_id()

    print("=== ACCOUNT ===")
    acc = await m._ad_account_summary(token)
    st = acc.get("account_status")
    print(f"name={acc.get('name')} id={act}")
    print(f"status={st} ({STATUS_LABELS.get(st, '?')}) currency={acc.get('currency')}")
    print(f"balance={acc.get('balance')} amount_spent={acc.get('amount_spent')}")
    print(f"disable_reason={acc.get('disable_reason')} funding={acc.get('funding_source_details')}")

    print("\n=== CAMPAIGN ===")
    camp = await m._graph_get(
        f"/{CAMPAIGN_ID}",
        token,
        {
            "fields": "id,name,status,effective_status,objective,daily_budget,lifetime_budget,"
            "buying_type,special_ad_categories,created_time,updated_time"
        },
    )
    print(json.dumps(camp, indent=2, default=str))

    print("\n=== NEW AD SET (should be US-UK-AU) ===")
    nas = await m._graph_get(
        f"/{NEW_ADSET_ID}",
        token,
        {
            "fields": "id,name,status,effective_status,daily_budget,lifetime_budget,billing_event,"
            "optimization_goal,bid_strategy,destination_type,promoted_object,targeting,"
            "attribution_spec,start_time,end_time,is_dynamic_creative"
        },
    )
    print(
        json.dumps(
            {k: nas.get(k) for k in nas if k != "targeting"},
            indent=2,
            default=str,
        )
    )
    t = nas.get("targeting") or {}
    print("geo:", t.get("geo_locations"))
    print("age:", t.get("age_min"), "-", t.get("age_max"))
    print("locales:", t.get("locales"))
    print("publisher_platforms:", t.get("publisher_platforms"))
    print("advantage/targeting_automation:", t.get("targeting_automation"))
    print("flexible_spec:", t.get("flexible_spec"))

    print("\n=== OLD AD SET (should be PAUSED IN/TH/MY) ===")
    oas = await m._graph_get(
        f"/{OLD_ADSET_ID}",
        token,
        {"fields": "id,name,status,effective_status,targeting,daily_budget"},
    )
    print(
        f"status={oas.get('status')} effective={oas.get('effective_status')} "
        f"name={oas.get('name')}"
    )
    print("geo:", (oas.get("targeting") or {}).get("geo_locations"))

    print("\n=== ADS ON NEW AD SET ===")
    ads = await m._graph_get(
        f"/act_{act}/ads",
        token,
        {
            "fields": "id,name,status,effective_status,creative{id,name,status,object_story_spec,"
            "thumbnail_url,video_id},preview_shareable_link",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": NEW_ADSET_ID}]
            ),
            "limit": 20,
        },
    )
    issues = []
    ad_rows = ads.get("data") or []
    print(f"count={len(ad_rows)}")
    for a in ad_rows:
        cr = a.get("creative") or {}
        oss = cr.get("object_story_spec") or {}
        if isinstance(oss, str):
            try:
                oss = json.loads(oss)
            except Exception:
                oss = {}
        vd = oss.get("video_data") or {}
        link = ((vd.get("call_to_action") or {}).get("value") or {}).get("link") or ""
        print("---")
        print(f"ad {a.get('id')} | {a.get('name')}")
        print(f"  status={a.get('status')} effective={a.get('effective_status')}")
        print(f"  creative={cr.get('id')} cr_status={cr.get('status')}")
        print(f"  title={vd.get('title')}")
        print(f"  message={(vd.get('message') or '')[:100]}")
        print(f"  video_id={vd.get('video_id')}")
        print(f"  link={link}")
        # Validate landing
        if not link:
            issues.append(f"{a.get('name')}: missing CTA link")
            continue
        u = urlparse(link)
        qs = parse_qs(u.query)
        path = u.path
        if "mathrelaxing.store" not in (u.netloc or ""):
            issues.append(f"{a.get('name')}: link not on mathrelaxing.store ({link})")
        if path.rstrip("/") == "/collection/digital-downloads":
            issues.append(f"{a.get('name')}: still points to collection")
        if "/bundle/" not in path and "/product/" not in path:
            issues.append(f"{a.get('name')}: path not product PDP ({path})")
        utm_src = (qs.get("utm_source") or [""])[0]
        utm_camp = (qs.get("utm_campaign") or [""])[0]
        utm_content = (qs.get("utm_content") or [""])[0]
        print(f"  utm_source={utm_src} campaign={utm_camp} content={utm_content}")
        if utm_src != "meta":
            issues.append(f"{a.get('name')}: utm_source should be meta")
        # HTTP check landing
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                r = await client.get(link.split("?")[0])
                print(f"  landing_http={r.status_code} final={r.url}")
                if r.status_code >= 400:
                    issues.append(f"{a.get('name')}: landing HTTP {r.status_code}")
        except Exception as e:
            issues.append(f"{a.get('name')}: landing fetch error {e}")
            print(f"  landing_err={e}")

    print("\n=== ADS STILL ON OLD AD SET ===")
    old_ads = await m._graph_get(
        f"/act_{act}/ads",
        token,
        {
            "fields": "id,name,status,effective_status",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": OLD_ADSET_ID}]
            ),
            "limit": 20,
        },
    )
    for a in old_ads.get("data") or []:
        print(
            f"  {a.get('status'):7s} {a.get('effective_status'):20s} {a.get('name')}"
        )
        if a.get("status") == "ACTIVE":
            issues.append(f"Old adset still has ACTIVE ad: {a.get('name')}")

    # Pixel
    print("\n=== PIXEL / PROMOTED OBJECT ===")
    po = nas.get("promoted_object") or {}
    print(json.dumps(po, indent=2))
    pixel_id = po.get("pixel_id")
    if pixel_id:
        try:
            px = await m._graph_get(
                f"/{pixel_id}",
                token,
                {"fields": "id,name,is_unavailable,last_fired_time"},
            )
            print("pixel:", json.dumps(px, indent=2, default=str))
        except Exception as e:
            print("pixel fetch:", e)
            issues.append(f"pixel check failed: {e}")

    # Page
    print("\n=== PAGE ===")
    print("configured page_id", page_id)
    try:
        pg = await m._graph_get(f"/{page_id}", token, {"fields": "id,name,link"})
        print(json.dumps(pg, indent=2))
    except Exception as e:
        print("page err", e)
        issues.append(f"page: {e}")

    # Budget math
    budget = int(nas.get("daily_budget") or 0)
    print("\n=== BUDGET ===")
    print(f"daily_budget_raw={budget} (account currency smallest unit usually)")
    if acc.get("currency") == "CLP":
        print(f"approx CLP/day={budget} (if already in pesos units for this API account)")
        print(f"billing_threshold note: ~5000 CLP threshold will fire often at this budget")

    print("\n=== PREFLIGHT CHECKLIST ===")
    checks = []
    checks.append(("account_active", st == 1, f"status={st}"))
    checks.append(("campaign_paused_ok", camp.get("status") == "PAUSED", camp.get("status")))
    checks.append(
        (
            "new_adset_geo_us_uk_au",
            set((t.get("geo_locations") or {}).get("countries") or []) == {"US", "GB", "AU"},
            (t.get("geo_locations") or {}).get("countries"),
        )
    )
    checks.append(
        (
            "old_adset_paused",
            oas.get("status") == "PAUSED",
            oas.get("status"),
        )
    )
    checks.append(("three_ads_on_new_set", len(ad_rows) == 3, len(ad_rows)))
    active_new = sum(1 for a in ad_rows if a.get("status") == "ACTIVE")
    checks.append(("all_new_ads_active_status", active_new == len(ad_rows) and len(ad_rows) > 0, active_new))
    checks.append(("no_blocking_issues", len(issues) == 0, issues))

    for name, ok, detail in checks:
        print(f"  [{'OK' if ok else '!!'}] {name}: {detail}")

    if issues:
        print("\nISSUES:")
        for i in issues:
            print(" -", i)
    else:
        print("\nNo critical issues found in links/structure.")

    print("\nREADY TO ACTIVATE?" )
    ready = st == 1 and camp.get("status") == "PAUSED" and oas.get("status") == "PAUSED"
    ready = ready and set((t.get("geo_locations") or {}).get("countries") or []) == {
        "US",
        "GB",
        "AU",
    }
    ready = ready and len(ad_rows) >= 3 and len(issues) == 0
    print("YES — turn campaign ACTIVE when you want spend" if ready else "NO — fix items above first")

    out = {
        "account_status": st,
        "campaign": camp,
        "new_adset_id": NEW_ADSET_ID,
        "old_adset_paused": oas.get("status") == "PAUSED",
        "ads": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "status": a.get("status"),
                "effective": a.get("effective_status"),
            }
            for a in ad_rows
        ],
        "issues": issues,
        "ready": ready,
    }
    os.makedirs("meta_drafts", exist_ok=True)
    with open("meta_drafts/preflight_latest.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("WROTE meta_drafts/preflight_latest.json")


if __name__ == "__main__":
    asyncio.run(main())
