"""Reconcile Meta 'today' insights vs live_events reality."""
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


async def main():
    token = await m._marketing_access_token()
    act = m._ad_account_id()

    print("=== SERVER TIME ===")
    print("utc_now", datetime.now(timezone.utc).isoformat())

    # Account timezone
    try:
        acc = await m._graph_get(
            f"/act_{act}",
            token,
            {"fields": "id,name,account_status,currency,timezone_name,timezone_offset_hours_utc"},
        )
        print("account", json.dumps(acc, indent=2))
    except Exception as e:
        print("acc err", e)
        acc = {}

    # Campaign status
    camp = await m._graph_get(
        f"/{CAMPAIGN}", token, {"fields": "id,name,status,effective_status"}
    )
    adset = await m._graph_get(
        f"/{NEW_ADSET}",
        token,
        {"fields": "id,name,status,effective_status,targeting,daily_budget"},
    )
    print("\ncampaign", camp)
    print("adset", adset.get("status"), adset.get("effective_status"), adset.get("daily_budget"))
    print("geo", (adset.get("targeting") or {}).get("geo_locations"))

    # Insights with explicit time ranges
    print("\n=== META INSIGHTS ===")
    for preset in ("today", "yesterday", "last_3d"):
        data = await m._graph_get(
            f"/{CAMPAIGN}/insights",
            token,
            {
                "fields": "impressions,clicks,spend,cpc,ctr,inline_link_clicks,"
                "unique_inline_link_clicks,actions,date_start,date_stop",
                "date_preset": preset,
            },
        )
        rows = data.get("data") or []
        print(f"\n{preset}: raw_rows={len(rows)}")
        for r in rows:
            print(json.dumps(r, indent=2))

    # Insights only new ad set
    print("\n=== NEW ADSET INSIGHTS today ===")
    try:
        data = await m._graph_get(
            f"/{NEW_ADSET}/insights",
            token,
            {
                "fields": "impressions,clicks,spend,inline_link_clicks,actions,date_start,date_stop",
                "date_preset": "today",
            },
        )
        print(json.dumps(data, indent=2))
    except Exception as e:
        print("new adset insights err", e)

    # Ads insights today on campaign level broken by ad
    print("\n=== AD INSIGHTS today ===")
    try:
        data = await m._graph_get(
            f"/{CAMPAIGN}/insights",
            token,
            {
                "fields": "ad_id,ad_name,adset_id,impressions,clicks,spend,inline_link_clicks,actions",
                "date_preset": "today",
                "level": "ad",
                "limit": 30,
            },
        )
        for r in data.get("data") or []:
            print(
                f"  adset={r.get('adset_id')} spend={r.get('spend')} "
                f"impr={r.get('impressions')} link={r.get('inline_link_clicks')} | {r.get('ad_name')}"
            )
        if not data.get("data"):
            print("  (empty)")
    except Exception as e:
        print("err", e)

    # LIVE side
    db = SessionLocal()
    now = datetime.utcnow()
    print("\n=== LIVE RECENT (all pageviews last 6h) ===")
    rows = db.execute(
        text(
            """
            SELECT ts, event_type, path, source, medium, campaign, country, city, session_id, ua_class
            FROM live_events
            WHERE ts >= :t
            ORDER BY ts DESC LIMIT 40
            """
        ),
        {"t": now - timedelta(hours=6)},
    ).fetchall()
    print(f"count_last_6h_any={len(rows)}")
    for r in rows[:25]:
        print(
            f"  {r[0]} | {r[1]:12s} | {(r[2] or '')[:55]:55s} | "
            f"src={r[3]} camp={r[5]} | {r[6]} {r[7]} | ua={r[9]}"
        )

    print("\n=== LIVE meta/fbclid last 6h ===")
    rows = db.execute(
        text(
            """
            SELECT ts, path, source, campaign, country, session_id
            FROM live_events
            WHERE ts >= :t AND (
              path LIKE '%utm_source=meta%' OR path LIKE '%fbclid=%'
              OR lower(COALESCE(source,'')) IN ('meta','facebook','fb','instagram','ig')
              OR campaign LIKE '%sea%' OR campaign LIKE '%math_art%'
            )
            ORDER BY ts DESC LIMIT 30
            """
        ),
        {"t": now - timedelta(hours=6)},
    ).fetchall()
    print(f"count={len(rows)}")
    for r in rows:
        print(f"  {r[0]} | {(r[1] or '')[:60]} | {r[2]}/{r[3]} | {r[4]}")

    print("\n=== LIVE last event overall ===")
    last = db.execute(text("SELECT ts, event_type, path, country, source FROM live_events ORDER BY id DESC LIMIT 5")).fetchall()
    for r in last:
        print(f"  {r[0]} | {r[1]} | {(r[2] or '')[:50]} | {r[3]} | {r[4]}")

    # counts since campaign re-activate approx
    for label, since in [
        ("since 2026-07-18 16:20 UTC (after optimize)", datetime(2026, 7, 18, 16, 20, 0)),
        ("last 2 hours", now - timedelta(hours=2)),
        ("today UTC midnight", now.replace(hour=0, minute=0, second=0, microsecond=0)),
    ]:
        n = db.execute(
            text(
                """
                SELECT COUNT(*), COUNT(DISTINCT session_id)
                FROM live_events WHERE ts >= :t AND event_type='pageview'
                """
            ),
            {"t": since},
        ).first()
        meta_n = db.execute(
            text(
                """
                SELECT COUNT(*), COUNT(DISTINCT session_id)
                FROM live_events
                WHERE ts >= :t AND event_type='pageview' AND (
                  path LIKE '%utm_source=meta%' OR path LIKE '%fbclid=%'
                  OR lower(COALESCE(source,'')) IN ('meta','facebook','fb','instagram')
                )
                """
            ),
            {"t": since},
        ).first()
        print(f"\n{label}: all_pv={n[0]} all_sess={n[1]} | meta_pv={meta_n[0]} meta_sess={meta_n[1]}")

    # Ignore config
    print("\n=== LIVE IGNORE ===")
    print("LIVE_IGNORE_IPS set", bool(os.getenv("LIVE_IGNORE_IPS")))

    db.close()


if __name__ == "__main__":
    asyncio.run(main())
