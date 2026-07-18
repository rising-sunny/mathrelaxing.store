"""Overall status: Meta ads delivery + live funnel."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from routers import meta_ads as m
from database import SessionLocal
from sqlalchemy import text

CAMPAIGN = "120249615423940256"
NEW_ADSET = "120249651488300256"
OLD_ADSET = "120249615425210256"


async def meta_status():
    token = await m._marketing_access_token()
    act = m._ad_account_id()
    acc = await m._ad_account_summary(token)
    print("=== META ACCOUNT ===")
    print(
        f"name={acc.get('name')} status={acc.get('account_status')} "
        f"currency={acc.get('currency')}"
    )

    camp = await m._graph_get(
        f"/{CAMPAIGN}",
        token,
        {"fields": "id,name,status,effective_status,objective"},
    )
    print("\n=== CAMPAIGN ===")
    print(json.dumps(camp, indent=2))

    for label, aid in [("NEW US-UK-AU", NEW_ADSET), ("OLD IN-TH-MY", OLD_ADSET)]:
        a = await m._graph_get(
            f"/{aid}",
            token,
            {
                "fields": "id,name,status,effective_status,daily_budget,targeting"
            },
        )
        geo = (a.get("targeting") or {}).get("geo_locations") or {}
        print(f"\n=== ADSET {label} ===")
        print(
            f"status={a.get('status')} effective={a.get('effective_status')} "
            f"budget={a.get('daily_budget')} geo={geo.get('countries')}"
        )

    # Insights today + last 3 days
    print("\n=== INSIGHTS (campaign) ===")
    for date_preset in ("today", "yesterday", "last_3d", "last_7d"):
        try:
            data = await m._graph_get(
                f"/{CAMPAIGN}/insights",
                token,
                {
                    "fields": "impressions,clicks,spend,cpc,ctr,actions,action_values,"
                    "inline_link_clicks,unique_clicks,reach",
                    "date_preset": date_preset,
                    "level": "campaign",
                },
            )
            rows = data.get("data") or []
            if not rows:
                print(f"  {date_preset}: no data")
                continue
            r = rows[0]
            actions = {a.get("action_type"): a.get("value") for a in (r.get("actions") or [])}
            print(
                f"  {date_preset}: spend={r.get('spend')} impr={r.get('impressions')} "
                f"clicks={r.get('clicks')} link_clicks={r.get('inline_link_clicks')} "
                f"cpc={r.get('cpc')} ctr={r.get('ctr')} reach={r.get('reach')}"
            )
            interesting = {
                k: v
                for k, v in actions.items()
                if k
                and any(
                    x in k
                    for x in (
                        "purchase",
                        "add_to_cart",
                        "initiate",
                        "landing",
                        "link_click",
                        "view_content",
                        "lead",
                    )
                )
            }
            if interesting:
                print(f"    actions: {interesting}")
        except Exception as e:
            print(f"  {date_preset}: ERR {e}")

    print("\n=== INSIGHTS BY AD (last_7d) ===")
    try:
        data = await m._graph_get(
            f"/{CAMPAIGN}/insights",
            token,
            {
                "fields": "ad_id,ad_name,impressions,clicks,spend,cpc,ctr,inline_link_clicks,actions",
                "date_preset": "last_7d",
                "level": "ad",
                "limit": 20,
            },
        )
        for r in data.get("data") or []:
            print(
                f"  spend={r.get('spend'):>6} impr={r.get('impressions'):>6} "
                f"link={r.get('inline_link_clicks') or r.get('clicks')} "
                f"| {r.get('ad_name')}"
            )
    except Exception as e:
        print("ad insights ERR", e)

    # ads status
    print("\n=== ADS STATUS (new adset) ===")
    ads = await m._graph_get(
        f"/act_{act}/ads",
        token,
        {
            "fields": "id,name,status,effective_status",
            "filtering": json.dumps(
                [{"field": "adset.id", "operator": "EQUAL", "value": NEW_ADSET}]
            ),
            "limit": 10,
        },
    )
    for a in ads.get("data") or []:
        print(f"  {a.get('status'):7s} {a.get('effective_status'):20s} {a.get('name')}")


def live_status():
    db = SessionLocal()
    now = datetime.utcnow()
    h24 = now - timedelta(hours=24)
    h72 = now - timedelta(hours=72)
    since_opt = datetime(2026, 7, 18, 16, 0, 0)  # approx after US-UK-AU switch UTC

    print("\n=== LIVE: META TRAFFIC ===")
    print("now_utc", now)

    for label, since in [("24h", h24), ("72h", h72), ("since_us_uk_au(~18jul16z)", since_opt)]:
        print(f"\n-- {label} --")
        r = db.execute(
            text(
                """
                SELECT COUNT(DISTINCT session_id),
                       SUM(CASE WHEN event_type='pageview' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN event_type='product_view' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN event_type IN ('cart_view','add_to_cart') THEN 1 ELSE 0 END),
                       SUM(CASE WHEN event_type='checkout_start' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN event_type='payment_redirect' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN event_type='purchase' THEN 1 ELSE 0 END)
                FROM live_events
                WHERE ts >= :t AND (
                  campaign LIKE '%sea%' OR campaign LIKE '%math_art%'
                  OR lower(COALESCE(source,'')) IN ('meta','facebook','fb','instagram','ig')
                  OR path LIKE '%utm_source=meta%' OR path LIKE '%fbclid=%'
                )
                """
            ),
            {"t": since},
        ).first()
        print(
            f"  sess={r[0]} pv={r[1]} pview={r[2]} cart={r[3]} "
            f"checkout={r[4]} pay={r[5]} purchase={r[6]}"
        )

        print("  by country:")
        for row in db.execute(
            text(
                """
                SELECT COALESCE(country,'??'), COUNT(DISTINCT session_id)
                FROM live_events
                WHERE ts >= :t AND (
                  campaign LIKE '%sea%' OR lower(COALESCE(source,'')) IN ('meta','facebook','fb','instagram','ig')
                  OR path LIKE '%utm_source=meta%' OR path LIKE '%fbclid=%'
                )
                GROUP BY 1 ORDER BY 2 DESC LIMIT 8
                """
            ),
            {"t": since},
        ):
            print(f"    {row[0]}: {row[1]}")

        print("  top landings:")
        for row in db.execute(
            text(
                """
                SELECT CASE WHEN instr(path,'?')>0 THEN substr(path,1,instr(path,'?')-1) ELSE path END p,
                       COUNT(DISTINCT session_id)
                FROM live_events
                WHERE ts >= :t AND event_type='pageview' AND (
                  campaign LIKE '%sea%' OR lower(COALESCE(source,'')) IN ('meta','facebook','fb','instagram','ig')
                  OR path LIKE '%utm_source=meta%' OR path LIKE '%fbclid=%'
                )
                GROUP BY p ORDER BY 2 DESC LIMIT 8
                """
            ),
            {"t": since},
        ):
            print(f"    {row[1]:4d}  {row[0]}")

        print("  product_views:")
        for row in db.execute(
            text(
                """
                SELECT COALESCE(product_slug,'(null)'), COUNT(DISTINCT session_id)
                FROM live_events
                WHERE ts >= :t AND event_type='product_view' AND (
                  campaign LIKE '%sea%' OR lower(COALESCE(source,'')) IN ('meta','facebook','fb','instagram','ig')
                  OR path LIKE '%utm_source=meta%' OR path LIKE '%fbclid=%'
                )
                GROUP BY 1 ORDER BY 2 DESC LIMIT 8
                """
            ),
            {"t": since},
        ):
            print(f"    {row[1]:4d}  {row[0]}")

    print("\n=== LIVE: RECENT FUNNEL EVENTS (meta, 48h) ===")
    for row in db.execute(
        text(
            """
            SELECT ts, event_type, path, product_slug, country, city, campaign
            FROM live_events
            WHERE ts >= :t AND event_type IN (
              'product_view','cart_view','add_to_cart','checkout_start','payment_redirect','purchase'
            ) AND (
              campaign LIKE '%sea%' OR lower(COALESCE(source,'')) IN ('meta','facebook','fb','instagram','ig')
              OR path LIKE '%utm_source=meta%' OR path LIKE '%fbclid=%'
            )
            ORDER BY ts DESC LIMIT 25
            """
        ),
        {"t": now - timedelta(hours=48)},
    ):
        print(
            f"  {row[0]} | {row[1]:15s} | {(row[2] or '')[:45]:45s} | "
            f"{row[3]} | {row[4]} {row[5]}"
        )

    # overall store last 24h
    print("\n=== LIVE: SITE OVERALL 24h ===")
    r = db.execute(
        text(
            """
            SELECT COUNT(DISTINCT session_id),
                   SUM(CASE WHEN event_type='pageview' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN event_type='purchase' THEN 1 ELSE 0 END)
            FROM live_events WHERE ts >= :t AND COALESCE(ua_class,'') != 'server'
            """
        ),
        {"t": h24},
    ).first()
    print(f"  sessions={r[0]} pageviews={r[1]} purchases={r[2]}")

    db.close()


async def main():
    await meta_status()
    live_status()
    print("\nSTATUS_CHECK_DONE")


if __name__ == "__main__":
    asyncio.run(main())
