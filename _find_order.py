"""Find order/purchase by id fragment."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv("/var/www/mathrelaxing.store/.env")
os.chdir("/var/www/mathrelaxing.store")

from database import SessionLocal, engine  # noqa: E402

NEEDLE = "4125528649"

db = SessionLocal()
tables = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
print("tables:", [t[0] for t in tables])

for (table,) in tables:
    cols = db.execute(text(f"PRAGMA table_info({table})")).fetchall()
    col_names = [c[1] for c in cols]
    # search text-like columns
    text_cols = [
        c
        for c in col_names
        if any(
            x in c.lower()
            for x in (
                "id",
                "order",
                "email",
                "name",
                "ref",
                "lemon",
                "paypal",
                "source",
                "note",
                "message",
                "slug",
                "title",
            )
        )
    ]
    if not text_cols:
        continue
    wheres = " OR ".join([f"cast({c} as text) LIKE :n" for c in text_cols])
    try:
        rows = db.execute(
            text(f"SELECT * FROM {table} WHERE {wheres} LIMIT 10"),
            {"n": f"%{NEEDLE}%"},
        ).fetchall()
        if rows:
            print(f"\nHIT {table} cols={col_names}")
            for r in rows:
                print(dict(r._mapping) if hasattr(r, "_mapping") else r)
    except Exception as e:
        print(table, "skip", e)

# also recent digital purchases
for table in ("purchases", "orders", "order_items"):
    if table not in [t[0] for t in tables]:
        continue
    try:
        rows = db.execute(
            text(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 15")
        ).fetchall()
        print(f"\n=== recent {table} ===")
        for r in rows:
            d = dict(r._mapping)
            # compact
            print(
                {
                    k: d[k]
                    for k in d
                    if k
                    in (
                        "id",
                        "lemon_order_id",
                        "paypal_order_id",
                        "customer_email",
                        "customer_name",
                        "status",
                        "ref_source",
                        "product_id",
                        "created_at",
                        "total",
                        "amount",
                    )
                    or "order" in k
                    or "email" in k
                }
            )
    except Exception as e:
        print("recent", table, e)

db.close()
