"""Republish all active digital products to Bonanza with scrubbed descriptions."""
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from importlib import reload

sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")
from dotenv import load_dotenv

load_dotenv(".env")
import services.bonanza as B

reload(B)

from database import SessionLocal
from models.product import DigitalProduct

BANNED = re.compile(r"download\s+link|\bpdfs?\b", re.I)


async def main():
    db = SessionLocal()
    products = (
        db.query(DigitalProduct)
        .filter(DigitalProduct.active == True)
        .order_by(DigitalProduct.slug)
        .all()
    )
    print(f"active={len(products)}")

    # Sanity: sample scrubbed description
    sample = products[0]
    desc = B._product_description(sample)
    title = B._safe_title(sample)
    print("sample title:", title)
    print("banned in title?", bool(BANNED.search(title)))
    print("banned in desc?", bool(BANNED.search(desc)))
    if BANNED.search(desc):
        print("DESC STILL HAS BANNED WORDS:")
        for m in BANNED.finditer(desc):
            print(" ", m.group(), "at", m.start())
        raise SystemExit("scrub failed")

    results = []
    for i, p in enumerate(products, 1):
        row = {"slug": p.slug}
        try:
            # Verify scrub on each
            d = B._product_description(p)
            t = B._safe_title(p)
            if BANNED.search(d) or BANNED.search(t):
                raise RuntimeError(f"banned words remain title={t!r}")
            r = await B.publish_product(p)
            row.update({"ok": True, **{k: r.get(k) for k in ("item_id", "selling_state", "listing_url")}})
            print(f"[{i}/{len(products)}] OK {p.slug} state={r.get('selling_state')} id={r.get('item_id')}")
        except Exception as e:
            row.update({"ok": False, "error": str(e)[:300]})
            print(f"[{i}/{len(products)}] FAIL {p.slug}: {e}")
        results.append(row)
        await asyncio.sleep(0.35)

    # Status counts
    counts = {}
    for p in products:
        try:
            st = await B.get_listing_status(p)
            s = st.get("status") or "?"
        except Exception:
            s = "error"
        counts[s] = counts.get(s, 0) + 1
        await asyncio.sleep(0.12)

    ok = sum(1 for r in results if r.get("ok"))
    report = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "total": len(results),
        "status_counts": counts,
        "results": results,
        "note": "Removed download link / pdf wording per Bonanza support (Kel). Reply to support to re-review.",
    }
    os.makedirs("meta_drafts", exist_ok=True)
    path = "meta_drafts/bonanza_rescrub_latest.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps({"ok": ok, "total": len(results), "status_counts": counts}, indent=2))
    print("WROTE", path)
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
