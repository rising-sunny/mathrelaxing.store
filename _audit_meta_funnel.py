"""Deep funnel audit for Meta SEA campaign traffic."""
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
since = now - timedelta(days=7)

print("now_utc", now)
print("window_days", 7)

# Meta campaign traffic
print("\n=== META CAMPAIGN VOLUME ===")
for r in db.execute(
    text(
        """
        SELECT COALESCE(campaign,'(none)') camp, COALESCE(source,'(none)') src,
               COALESCE(medium,'(none)') med,
               COUNT(*) ev, COUNT(DISTINCT session_id) sess
        FROM live_events
        WHERE ts >= :t
          AND (
            campaign LIKE '%sea%' OR campaign LIKE '%meta%'
            OR lower(COALESCE(source,'')) IN ('meta','facebook','fb','instagram','ig')
            OR path LIKE '%utm_source=meta%' OR path LIKE '%fbclid=%'
          )
        GROUP BY 1,2,3 ORDER BY sess DESC
        """
    ),
    {"t": since},
):
    print(f"  camp={r[0]} src={r[1]} med={r[2]} sessions={r[4]} events={r[3]}")

# Funnel by country for meta traffic
print("\n=== FUNNEL BY COUNTRY (meta/paid/fbclid, 7d) ===")
meta_filter = """
  ts >= :t AND (
    campaign LIKE '%sea%' OR lower(COALESCE(source,'')) IN ('meta','facebook','fb','instagram','ig')
    OR lower(COALESCE(medium,'')) LIKE '%paid%'
    OR path LIKE '%utm_source=meta%' OR path LIKE '%fbclid=%'
  )
"""
for r in db.execute(
    text(
        f"""
        SELECT COALESCE(country,'??') cc,
               COUNT(DISTINCT session_id) sessions,
               SUM(CASE WHEN event_type='pageview' THEN 1 ELSE 0 END) pv,
               SUM(CASE WHEN event_type='product_view' THEN 1 ELSE 0 END) pview,
               SUM(CASE WHEN event_type='add_to_cart' THEN 1 ELSE 0 END) atc,
               SUM(CASE WHEN event_type='cart_view' THEN 1 ELSE 0 END) cart,
               SUM(CASE WHEN event_type='checkout_start' THEN 1 ELSE 0 END) chk,
               SUM(CASE WHEN event_type='payment_redirect' THEN 1 ELSE 0 END) pay,
               SUM(CASE WHEN event_type='purchase' THEN 1 ELSE 0 END) purch
        FROM live_events
        WHERE {meta_filter}
        GROUP BY cc ORDER BY sessions DESC LIMIT 15
        """
    ),
    {"t": since},
):
    print(
        f"  {r[0]}: sess={r[1]} pv={r[2]} pview={r[3]} atc={r[4]} cart={r[5]} "
        f"checkout={r[6]} pay={r[7]} purchase={r[8]}"
    )

# Paths / landings
print("\n=== LANDING PATHS (meta, 7d) ===")
for r in db.execute(
    text(
        f"""
        SELECT
          CASE WHEN instr(path,'?')>0 THEN substr(path,1,instr(path,'?')-1) ELSE path END p,
          COUNT(DISTINCT session_id) s, COUNT(*) e
        FROM live_events
        WHERE {meta_filter} AND event_type='pageview'
        GROUP BY p ORDER BY s DESC LIMIT 20
        """
    ),
    {"t": since},
):
    print(f"  {r[1]:4d} sess  {r[0]}")

# utm_content / product
print("\n=== PRODUCT VIEWS (meta sessions attribution by source/campaign) ===")
for r in db.execute(
    text(
        f"""
        SELECT COALESCE(product_slug,'(null)'), COUNT(*), COUNT(DISTINCT session_id)
        FROM live_events
        WHERE {meta_filter} AND event_type='product_view'
        GROUP BY 1 ORDER BY 2 DESC LIMIT 15
        """
    ),
    {"t": since},
):
    print(f"  {r[0]}: ev={r[1]} sess={r[2]}")

# cart sessions detail
print("\n=== CART / CHECKOUT EVENTS (meta, 7d) ===")
for r in db.execute(
    text(
        f"""
        SELECT ts, event_type, path, product_slug, source, campaign, country, city, session_id, value_usd
        FROM live_events
        WHERE {meta_filter}
          AND event_type IN ('add_to_cart','cart_view','checkout_start','payment_redirect','purchase')
        ORDER BY ts DESC LIMIT 30
        """
    ),
    {"t": since},
):
    print(
        f"  {r[0]} | {r[1]:15s} | {(r[2] or '')[:50]:50s} | prod={r[3]} | "
        f"{r[6]} {r[7]} | camp={r[5]} | sid={str(r[8])[:8]} | ${r[9]}"
    )

# Sessions that only hit collection vs product
print("\n=== SESSION DEPTH (meta, sample logic) ===")
rows = db.execute(
    text(
        f"""
        SELECT session_id,
               COUNT(*) n,
               SUM(CASE WHEN event_type='pageview' THEN 1 ELSE 0 END) pv,
               SUM(CASE WHEN event_type='product_view' THEN 1 ELSE 0 END) pview,
               SUM(CASE WHEN path LIKE '%/bundle/%' OR path LIKE '%/product/%' THEN 1 ELSE 0 END) pdp,
               SUM(CASE WHEN path LIKE '%collection%' THEN 1 ELSE 0 END) coll,
               MAX(country) cc,
               GROUP_CONCAT(DISTINCT event_type) types
        FROM live_events
        WHERE {meta_filter}
        GROUP BY session_id
        """
    ),
    {"t": since},
).fetchall()
total = len(rows)
only_coll = sum(1 for r in rows if r[5] > 0 and r[4] == 0 and r[3] == 0)
with_pdp = sum(1 for r in rows if r[4] > 0 or r[3] > 0)
with_cart = sum(1 for r in rows if r[7] and ("cart" in r[7] or "checkout" in r[7] or "add_to_cart" in r[7]))
multi = sum(1 for r in rows if r[1] >= 3)
print(f"  sessions={total}")
print(f"  only_collection_no_pdp={only_coll} ({100*only_coll/max(total,1):.1f}%)")
print(f"  reached_pdp_or_product_view={with_pdp} ({100*with_pdp/max(total,1):.1f}%)")
print(f"  cartish={with_cart}")
print(f"  multi_event_3plus={multi} ({100*multi/max(total,1):.1f}%)")

# Device
print("\n=== DEVICE (meta) ===")
for r in db.execute(
    text(
        f"""
        SELECT COALESCE(ua_class,'?'), COUNT(DISTINCT session_id)
        FROM live_events WHERE {meta_filter}
        GROUP BY 1 ORDER BY 2 DESC
        """
    ),
    {"t": since},
):
    print(f"  {r[0]}: {r[1]}")

# Content keys from path utm_content
print("\n=== utm_content in path (if present) ===")
for r in db.execute(
    text(
        f"""
        SELECT path, COUNT(DISTINCT session_id) s
        FROM live_events
        WHERE {meta_filter} AND path LIKE '%utm_content=%'
        GROUP BY path ORDER BY s DESC LIMIT 15
        """
    ),
    {"t": since},
):
    p = r[0] or ""
    # extract utm_content roughly
    import re
    m = re.search(r"utm_content=([^&]+)", p)
    content = m.group(1) if m else "?"
    path_base = p.split("?")[0]
    print(f"  {r[1]:4d}  content={content:20s}  {path_base}")

# All traffic India vs others conversion context
print("\n=== ALL TRAFFIC INDIA vs OTHER (7d) funnel ===")
for r in db.execute(
    text(
        """
        SELECT CASE WHEN country='IN' THEN 'IN' ELSE 'OTHER' END g,
               COUNT(DISTINCT session_id),
               SUM(CASE WHEN event_type='product_view' THEN 1 ELSE 0 END),
               SUM(CASE WHEN event_type IN ('cart_view','add_to_cart') THEN 1 ELSE 0 END),
               SUM(CASE WHEN event_type='checkout_start' THEN 1 ELSE 0 END),
               SUM(CASE WHEN event_type='purchase' THEN 1 ELSE 0 END)
        FROM live_events WHERE ts>=:t
        GROUP BY 1
        """
    ),
    {"t": since},
):
    print(f"  {r[0]}: sess={r[1]} pview={r[2]} cartish={r[3]} checkout={r[4]} purchase={r[5]}")

db.close()
print("\nDONE")
