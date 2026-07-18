"""Audit recent Meta/SEA traffic in live_events."""
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, "/var/www/mathrelaxing.store")
from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")

from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
now = datetime.utcnow()
h24 = now - timedelta(hours=24)
h72 = now - timedelta(hours=72)
d7 = now - timedelta(days=7)

print("now_utc", now)
print("\n=== META / PAID last 72h ===")
rows = db.execute(
    text(
        """
        SELECT ts, event_type, path, source, medium, campaign, referrer_domain,
               country, city, ua_class, product_slug, session_id
        FROM live_events
        WHERE ts >= :t
          AND (
            lower(COALESCE(source,'')) IN ('meta','facebook','fb','instagram','ig')
            OR lower(COALESCE(medium,'')) LIKE '%paid%'
            OR lower(COALESCE(medium,'')) LIKE '%cpc%'
            OR campaign LIKE '%sea%'
            OR campaign LIKE '%meta%'
            OR path LIKE '%utm_source=meta%'
            OR path LIKE '%fbclid=%'
          )
        ORDER BY ts DESC
        LIMIT 80
        """
    ),
    {"t": h72},
).fetchall()
print(f"matching_events={len(rows)}")
for r in rows[:40]:
    print(
        f"  {r[0]} | {r[1]:12s} | path={(r[2] or '')[:70]:70s} | "
        f"src={r[3]} med={r[4]} camp={r[5]} | {r[7]} {r[8]} | prod={r[10]} sid={str(r[11])[:8]}"
    )

print("\n=== paths for meta/paid 72h ===")
for r in db.execute(
    text(
        """
        SELECT
          CASE WHEN instr(path,'?')>0 THEN substr(path,1,instr(path,'?')-1) ELSE path END p,
          COUNT(*) c,
          COUNT(DISTINCT session_id) s
        FROM live_events
        WHERE ts >= :t
          AND (
            lower(COALESCE(source,'')) IN ('meta','facebook','fb','instagram','ig')
            OR lower(COALESCE(medium,'')) LIKE '%paid%'
            OR campaign LIKE '%sea%'
            OR path LIKE '%utm_source=meta%'
            OR path LIKE '%fbclid=%'
          )
        GROUP BY p ORDER BY c DESC LIMIT 20
        """
    ),
    {"t": h72},
):
    print(f"  {r[2]:3d} sess / {r[1]:3d} ev  {r[0]}")

print("\n=== funnel last 72h (all traffic) ===")
for et in (
    "pageview",
    "product_view",
    "add_to_cart",
    "cart_view",
    "checkout_start",
    "payment_redirect",
    "purchase",
):
    n = db.execute(
        text("SELECT COUNT(*) FROM live_events WHERE ts>=:t AND event_type=:e"),
        {"t": h72, "e": et},
    ).scalar()
    print(f"  {et:18s} {n}")

print("\n=== product_view last 72h ===")
for r in db.execute(
    text(
        """
        SELECT COALESCE(product_slug,'(null)'), COUNT(*), COUNT(DISTINCT session_id)
        FROM live_events
        WHERE ts>=:t AND event_type='product_view'
        GROUP BY 1 ORDER BY 2 DESC LIMIT 15
        """
    ),
    {"t": h72},
):
    print(f"  {r[0]}: events={r[1]} sessions={r[2]}")

print("\n=== campaigns last 7d ===")
for r in db.execute(
    text(
        """
        SELECT COALESCE(campaign,'(none)'), COALESCE(source,'(none)'), COALESCE(medium,'(none)'),
               COUNT(DISTINCT session_id), COUNT(*)
        FROM live_events
        WHERE ts>=:t AND (campaign IS NOT NULL OR source IS NOT NULL)
        GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 15
        """
    ),
    {"t": d7},
):
    print(f"  camp={r[0]} src={r[1]} med={r[2]} sessions={r[3]} events={r[4]}")

print("\n=== today top pages ===")
today = now.replace(hour=0, minute=0, second=0, microsecond=0)
for r in db.execute(
    text(
        """
        SELECT
          CASE WHEN instr(path,'?')>0 THEN substr(path,1,instr(path,'?')-1) ELSE path END p,
          COUNT(*), COUNT(DISTINCT session_id)
        FROM live_events
        WHERE ts>=:t AND event_type='pageview'
        GROUP BY p ORDER BY 2 DESC LIMIT 15
        """
    ),
    {"t": today},
):
    print(f"  {r[2]:3d}s / {r[1]:3d}pv  {r[0]}")

print("\n=== snapshot-ish sources today ===")
from routers.live import _build_snapshot

snap = _build_snapshot(db)
print("today", snap["today"])
print("top_sources", snap["top_sources"])
print("top_campaigns", snap["top_campaigns"])
print("top_pages", snap["top_pages"])
print("top_countries", snap["top_countries"])
print("paid_sessions_today", snap.get("paid_sessions_today"))
print("recent (12):")
for e in (snap.get("recent_events") or [])[:12]:
    print(
        f"  {e.get('type'):12s} {str(e.get('path'))[:55]:55s} src={e.get('src')} camp={e.get('campaign')} paid={e.get('is_paid')} {e.get('country')}"
    )

db.close()
