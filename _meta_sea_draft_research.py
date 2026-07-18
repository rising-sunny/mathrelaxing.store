"""
Research + draft Meta ad for India / Thailand / Malaysia.

- Searches locales + interests via Marketing API
- Builds a paused-ready plan (draft_only — does NOT create campaigns)
- Picks visual assets (videos + hero images) for a multi-product reel

Run on VPS:
  cd /var/www/mathrelaxing.store && .venv/bin/python _meta_sea_draft_research.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from routers import meta_ads as m
from database import SessionLocal
from models.product import DigitalProduct

OUT = Path("/var/www/mathrelaxing.store/meta_drafts")
OUT.mkdir(exist_ok=True)

# Interest queries tuned for MathRelaxing (STEM / math art / digital downloads / mindfulness)
INTEREST_QUERIES = [
    "Mathematics",
    "Sacred geometry",
    "Fractal",
    "Adult coloring book",
    "Coloring book",
    "Digital art",
    "Generative art",
    "STEM education",
    "Science education",
    "Meditation",
    "Mindfulness",
    "Wall art",
    "Home decor",
    "Procreate",
    "iPad",
    "GoodNotes",
    "Graphic design",
    "Abstract art",
    "Geometry",
    "Physics",
    "Engineering",
    "Online shopping",
    "Etsy",
    "Digital download",
    "Printable",
    "Self-care",
    "Yoga",
]

LOCALE_QUERIES = ["English", "Hindi", "Thai", "Malay", "Bahasa"]

# Visual reel candidates (public HTTPS URLs under the store)
VIDEO_CANDIDATES = [
    "https://mathrelaxing.store/static/video/thomas_attractor_loop.mp4",
    "https://mathrelaxing.store/static/video/fractal_flora_promo.mp4",
    "https://mathrelaxing.store/static/video/fb_chladni.mp4",
    "https://mathrelaxing.store/static/video/fb_harmonograph_v1.mp4",
    "https://mathrelaxing.store/static/digital/julia-set-loop/00_preview.mp4",
    "https://mathrelaxing.store/static/digital/voronoi-cell-garden-loop/00_preview.mp4",
    "https://mathrelaxing.store/static/dejong_loop_1080.mp4",
    "https://mathrelaxing.store/static/examples/lorenz_flow_1080p30.mp4",
    "https://mathrelaxing.store/static/examples/clifford_spiral_1080p60.mp4",
]

# Benchmarks (USD, 2026 public Meta country CPM/CPC ranges)
# Sources: AdAmigo / Lebesgue country benchmarks 2026
BENCHMARKS_USD = {
    "IN": {"cpm": 2.0, "cpm_range": (1.36, 3.2), "cpc": 0.20, "cpc_range": (0.10, 0.35)},
    "TH": {"cpm": 3.9, "cpm_range": (3.2, 4.8), "cpc": 0.40, "cpc_range": (0.25, 0.60)},
    "MY": {"cpm": 4.8, "cpm_range": (4.0, 6.0), "cpc": 0.55, "cpc_range": (0.35, 0.80)},
}


def pick_products(db) -> list[dict]:
    """Prefer visual math-art products suited to SEA impulse digital purchase."""
    preferred_slugs = [
        "julia-set-loop",
        "voronoi-cell-garden-loop",
        "thomas-attractor-loop",
        "de-jong-attractor-loop",
        "fractal-flora-coloring-book-digital",
        "sacred-geometry-coloring-book-digital",
        "happy-chemicals-print-set",
        "bauhaus-print-set",
        "spiral-tilings-coloring-book-digital",
        "unit-circle-poster",
        "computer-science-poster-set",
        "lorenz-attractor-print-set",
        "clifford-attractor-print-set",
    ]
    by_slug = {
        p.slug: p
        for p in db.query(DigitalProduct).filter(DigitalProduct.active == True).all()
    }
    picked = []
    for s in preferred_slugs:
        if s in by_slug:
            picked.append(m._product_payload(by_slug[s]))
    return picked


async def search_locales(token: str) -> list[dict]:
    found = []
    seen = set()
    for q in LOCALE_QUERIES:
        data = await m._graph_get(
            "/search",
            token,
            {"type": "adlocale", "q": q, "limit": 25},
        )
        for row in data.get("data") or []:
            key = row.get("key")
            if key in seen:
                continue
            seen.add(key)
            found.append(row)
    return found


def filter_target_locales(locales: list[dict]) -> list[dict]:
    """Keep English + Hindi + Thai + Malay. Exclude Malayalam (false positive)."""
    want = []
    for row in locales:
        name = (row.get("name") or "").lower()
        key = row.get("key")
        if "malayalam" in name:
            continue
        if any(
            x in name
            for x in (
                "english (us)",
                "english (uk)",
                "english (all)",
                "hindi",
                "thai",
            )
        ) or name.strip() in ("malay", "bahasa malaysia", "bahasa melayu"):
            want.append({"key": key, "name": row.get("name")})
        elif name == "malay" or name.startswith("malay ("):
            want.append({"key": key, "name": row.get("name")})
    # Prefer a compact set
    priority = []
    for needle in (
        "English (US)",
        "English (UK)",
        "Hindi",
        "Thai",
        "Malay",
    ):
        for row in want:
            n = row["name"] or ""
            if needle.lower() in n.lower() and "malayalam" not in n.lower() and row not in priority:
                priority.append(row)
    return priority or want


async def search_interests(token: str) -> list[dict]:
    bag = []
    seen = set()
    for q in INTEREST_QUERIES:
        try:
            rows = await m._search_meta_interests(token, q, limit=8)
        except Exception as e:
            bag.append({"query": q, "error": str(e)[:200]})
            continue
        for r in rows:
            iid = str(r.get("id"))
            if iid in seen:
                continue
            seen.add(iid)
            bag.append(
                {
                    "query": q,
                    "id": iid,
                    "name": r.get("name"),
                    "audience_lower": r.get("audience_size_lower_bound"),
                    "audience_upper": r.get("audience_size_upper_bound"),
                    "path": r.get("path"),
                    "topic": r.get("topic"),
                }
            )
        await asyncio.sleep(0.15)  # gentle rate limit
    return bag


def score_interest(row: dict) -> float:
    """Prefer mid-size, on-brand interests; demote weak/off-brand labels."""
    name = (row.get("name") or "").lower()
    if row.get("error"):
        return -1
    # hard rejects
    for bad in (
        "coupon",
        "deal",
        "women in stem",
        "systems engineering",
        "computer engineering",
        "interior decor brand",
        "decor home ideas",
        "home decorating ideas",
        "audio equipment",
        "yoga pants",
        "hot yoga",
        "hatha yoga",
        "kundalini",
        "ashtanga",
        "retailer",
    ):
        if bad in name:
            return -1
    brand_hits = sum(
        1
        for k in (
            "math",
            "fractal",
            "geometry",
            "coloring",
            "stem",
            "science",
            "meditation",
            "mindful",
            "digital art",
            "generative",
            "procreate",
            "wall art",
            "abstract",
            "physics",
            "ipad",
            "goodnotes",
            "printable",
            "download",
            "etsy",
            "yoga",
            "self-care",
            "graphic design",
        )
        if k in name
    )
    # mild bonus for clean home decor (not coupon/interior retail)
    if name in ("home decor", "home décor") or name == "wall art":
        brand_hits += 1
    mid = (row.get("audience_lower") or 0) + (row.get("audience_upper") or 0)
    size_score = 1.0
    if mid:
        avg = mid / 2
        if avg < 10_000:
            size_score = 0.2
        elif avg < 50_000:
            size_score = 0.6
        elif avg < 50_000_000:
            size_score = 1.0
        else:
            size_score = 0.5
    return brand_hits * 3 + size_score


def select_interests(rows: list[dict], n: int = 12) -> list[dict]:
    """Curate: one best hit per priority query, then fill by score."""
    candidates = [r for r in rows if r.get("id") and not r.get("error") and score_interest(r) >= 0]
    # Prefer exact/near-exact interest names from Meta taxonomy
    preferred_names = {
        "coloring book",
        "digital art",
        "abstract art",
        "mathematics",
        "geometry",
        "meditation",
        "mindfulness",
        "graphic design",
        "physics",
        "etsy",
        "wall art",
        "home decor",
        "home décor",
        "science",
        "stem",
        "fractal art",
        "sacred geometry",
        "generative art",
        "ipad",
        "procreate",
    }
    by_name = {}
    for r in candidates:
        nm = (r.get("name") or "").strip().lower()
        if nm in preferred_names:
            by_name[nm] = r

    picked: list[dict] = []
    seen_ids = set()
    for nm in preferred_names:
        r = by_name.get(nm)
        if r and r["id"] not in seen_ids:
            picked.append(r)
            seen_ids.add(r["id"])

    # One best per original query (skip Yoga spam — keep Meditation only)
    priority_queries = [
        "Mathematics",
        "Sacred geometry",
        "Fractal",
        "Adult coloring book",
        "Coloring book",
        "Digital art",
        "Generative art",
        "STEM education",
        "Science education",
        "Meditation",
        "Mindfulness",
        "Wall art",
        "Home decor",
        "Procreate",
        "iPad",
        "Graphic design",
        "Abstract art",
        "Geometry",
        "Physics",
        "Etsy",
        "Digital download",
        "Printable",
        "Self-care",
    ]
    for q in priority_queries:
        pool = [r for r in candidates if r.get("query") == q and r["id"] not in seen_ids]
        if not pool:
            continue
        # for yoga-ish queries only allow pure meditation/mindfulness names
        if q in ("Yoga",):
            continue
        pool.sort(key=score_interest, reverse=True)
        best = pool[0]
        # skip if name is pure yoga style
        nlow = (best.get("name") or "").lower()
        if "yoga" in nlow and "meditation" not in nlow:
            continue
        picked.append(best)
        seen_ids.add(best["id"])
        if len(picked) >= n:
            break

    if len(picked) < n:
        rest = sorted(
            [r for r in candidates if r["id"] not in seen_ids],
            key=score_interest,
            reverse=True,
        )
        for r in rest:
            nlow = (r.get("name") or "").lower()
            if "yoga" in nlow and "meditation" not in nlow:
                continue
            picked.append(r)
            if len(picked) >= n:
                break
    return picked[:n]


def budget_plan_clp() -> dict:
    """
    Account currency is CLP (zero-decimal).
    Approximate USDCLP ~ 950 used for planning (verify live FX).
    """
    usdclp = 950.0
    # Traffic mix: India heavy (volume) + TH + MY
    mix = {"IN": 0.55, "TH": 0.25, "MY": 0.20}
    blend_cpm = sum(BENCHMARKS_USD[c]["cpm"] * w for c, w in mix.items())
    blend_cpc = sum(BENCHMARKS_USD[c]["cpc"] * w for c, w in mix.items())

    # Learning-phase daily budget: enough for ~50+ conversions/week OR
    # solid volume for testing (~3–5k impressions/day blended)
    # At $3 CPM, $15/day ≈ 5k impressions.
    daily_usd_test = 12.0
    daily_usd_scale = 25.0
    daily_clp_test = int(round(daily_usd_test * usdclp))
    daily_clp_scale = int(round(daily_usd_scale * usdclp))

    # Product AOV ~ $5–10 for digital downloads
    target_cpa_usd = 4.0
    est_clicks_test = daily_usd_test / blend_cpc if blend_cpc else 0
    est_impr_test = (daily_usd_test / blend_cpm) * 1000 if blend_cpm else 0

    return {
        "currency": "CLP",
        "usdclp_assumed": usdclp,
        "country_mix": mix,
        "blended_cpm_usd": round(blend_cpm, 2),
        "blended_cpc_usd": round(blend_cpc, 2),
        "country_benchmarks_usd": BENCHMARKS_USD,
        "recommended": {
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "rationale": (
                "Advantage Campaign Budget / lowest cost without bid cap is best for "
                "new geo tests with sparse conversion history. Manual bid caps risk "
                "under-delivery in low-CPM markets (IN) and high variance (TH/MY)."
            ),
            "optimization_goal": "OFFSITE_CONVERSIONS",
            "custom_event": "PURCHASE",
            "billing_event": "IMPRESSIONS",
            "daily_budget_clp_test": daily_clp_test,
            "daily_budget_clp_scale": daily_clp_scale,
            "daily_budget_usd_test": daily_usd_test,
            "daily_budget_usd_scale": daily_usd_scale,
            "target_cpa_usd": target_cpa_usd,
            "est_daily_impressions_test": int(est_impr_test),
            "est_daily_clicks_test": int(est_clicks_test),
            "learning_note": (
                "Keep creative + targeting stable for 3–5 days / ~50 purchase events "
                "before major edits. If account remains UNSETTLED, delivery may be limited."
            ),
        },
    }


def copy_pack() -> dict:
    """Primary English copy + localized variants for multi-language creative."""
    return {
        "primary_en": (
            "Math that feels like art. Instant digital downloads — coloring books, "
            "STEM posters, seamless fractal loops. Print at home or color on iPad. "
            "From ₹ / ฿ / RM-friendly prices · personal use forever."
        ),
        "headline_en": "MathRelaxing · Digital Math Art",
        "primary_hi": (
            "गणित जो कला जैसा लगे। इंस्टेंट डिजिटल डाउनलोड — कलरिंग बुक्स, STEM पोस्टर, "
            "फ्रैक्टल लूप्स। घर पर प्रिंट करें या iPad पर कलर करें।"
        ),
        "headline_hi": "MathRelaxing · गणित कला",
        "primary_th": (
            "คณิตศาสตร์ที่สวยเหมือนศิลปะ ดาวน์โหลดทันที — สมุดระบายสี โปสเตอร์ STEM "
            "และลูปแฟรกทัล พิมพ์ที่บ้านหรือระบายบน iPad ได้เลย"
        ),
        "headline_th": "MathRelaxing · ศิลปะคณิตศาสตร์",
        "primary_ms": (
            "Matematik yang indah seperti seni. Muat turun digital segera — buku mewarna, "
            "poster STEM, gelung fraktal. Cetak di rumah atau warnakan di iPad."
        ),
        "headline_ms": "MathRelaxing · Seni Matematik",
        "cta": "SHOP_NOW",
        "landing": "https://mathrelaxing.store/collection/digital-downloads?utm_source=meta&utm_medium=paid_social&utm_campaign=sea_in_th_my_math_art&utm_content=draft_reel",
    }


def creative_plan(products: list[dict]) -> dict:
    images = []
    for p in products[:8]:
        images.append(
            {
                "product_slug": p["slug"],
                "name": p["name"],
                "price_usd": p["price_usd"],
                "image_url": p.get("image_url"),
                "destination_url": p.get("destination_url"),
            }
        )
    videos = []
    for url in VIDEO_CANDIDATES:
        # existence check local path
        path = url.replace("https://mathrelaxing.store", "/var/www/mathrelaxing.store")
        videos.append({"url": url, "exists": Path(path).exists()})
    return {
        "format_recommendation": "video_view_through_to_carousel_or_single_video",
        "primary_format": (
            "1) Best: short vertical/square product reel (15–30s) stitching 4–6 product loops "
            "(Thomas, Julia, Voronoi, De Jong, Fractal Flora, Chladni) + end card SHOP_NOW. "
            "2) Fallback supported by current API: single hero image + strong primary text. "
            "3) Carousel of 5 product covers for catalog browsing."
        ),
        "video_assets": videos,
        "image_assets": images,
        "hero_image_for_api_draft": images[0]["image_url"] if images else None,
        "note": (
            "Current create-paused-campaign endpoint only uploads a single image creative. "
            "This draft documents the multi-product reel; implement video_data/carousel as next step."
        ),
    }


async def main() -> None:
    print("=== Meta SEA draft research ===")
    token = await m._marketing_access_token()
    account = await m._ad_account_summary(token)
    print("account:", account.get("name"), "status=", account.get("account_status"), "currency=", account.get("currency"))

    locales_raw = await search_locales(token)
    locales = filter_target_locales(locales_raw)
    print("locales selected:", locales)

    print("searching interests…")
    interests_raw = await search_interests(token)
    interests = select_interests(interests_raw, n=12)
    print("top interests:")
    for i in interests:
        print(f"  {i.get('id')} | {i.get('name')} | q={i.get('query')}")

    db = SessionLocal()
    try:
        products = pick_products(db)
    finally:
        db.close()
    print(f"products in reel: {len(products)}")

    budgets = budget_plan_clp()
    copy = copy_pack()
    creative = creative_plan(products)

    # Build MetaDraftRequest-compatible plan
    draft_payload = {
        "product_slug": products[0]["slug"] if products else "julia-set-loop",
        "title": copy["headline_en"][:80],
        "primary_text": copy["primary_en"][:500],
        "destination_url": copy["landing"],
        "image_url": creative["hero_image_for_api_draft"]
        or "https://mathrelaxing.store/static/previews/julia-set-loop.jpg",
        "daily_budget_amount": budgets["recommended"]["daily_budget_clp_test"],
        "countries": ["IN", "TH", "MY"],
        "interests": [{"id": i["id"], "name": i["name"]} for i in interests if i.get("id")],
        "age_min": 22,
        "age_max": 55,
        "genders": [],
        "locales": [int(x["key"]) for x in locales if x.get("key") is not None],
    }

    from routers.meta_ads import MetaDraftRequest

    payload = MetaDraftRequest(**draft_payload)
    plan = m._meta_plan(payload, currency=account.get("currency") or "CLP")

    # Enrich plan with research
    document = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "draft_only",
        "warning_account_status": account.get("account_status"),
        "warning_note": (
            "Ad account is UNSETTLED (status 3) — Meta may limit delivery until billing is fixed. "
            "Draft does not create spend."
        ),
        "market_strategy": {
            "geo": ["IN", "TH", "MY"],
            "why": (
                "India = low CPM volume + huge English/Hindi STEM student base. "
                "Thailand & Malaysia = higher purchasing power, bilingual, strong mobile commerce. "
                "Digital downloads avoid cross-border shipping friction."
            ),
            "languages": "English + Hindi + Thai + Malay (locale targeting + multi-language creative copy)",
            "age": "22–55 (students, young professionals, hobbyists, parents buying STEM gifts)",
            "placements": "Advantage+ placements; creative designed square/vertical first (Reels/FB/IG feed)",
        },
        "budget_and_bidding": budgets,
        "locales_all_found": locales_raw[:40],
        "locales_selected": locales,
        "interests_selected": interests,
        "interests_raw_count": len(interests_raw),
        "copy": copy,
        "creative": creative,
        "products": products,
        "api_draft_payload": draft_payload,
        "meta_plan": plan,
        "next_steps": [
            "1. Fix ad account billing (UNSETTLED) before any ACTIVE spend.",
            "2. Optional: stitch VIDEO_CANDIDATES into one 20s reel with end card.",
            "3. Review draft in /admin/meta-ads or this JSON.",
            "4. When ready, call create-paused-campaign with confirm_paused_creation=true (image creative).",
            "5. Add multi-language asset customization for HI/TH/MS headlines in Ads Manager.",
            "6. Day 1–3: test budget CLP daily_budget_clp_test; kill under-CTR creatives; scale winners.",
        ],
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = OUT / f"sea_in_th_my_draft_{stamp}.json"
    out_path.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    latest = OUT / "sea_in_th_my_draft_latest.json"
    latest.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nWrote", out_path)
    print("Latest", latest)
    print("\n=== SUMMARY ===")
    print("countries:", draft_payload["countries"])
    print("locales:", draft_payload["locales"])
    print("interests:", len(draft_payload["interests"]))
    print("daily_budget_clp:", draft_payload["daily_budget_amount"])
    print("bid:", plan["ad_set"]["bid_strategy"])
    print("objective:", plan["campaign"]["objective"])
    print("status:", plan["campaign"]["status"])


if __name__ == "__main__":
    asyncio.run(main())
