"""Inspect eBay payment policies (Managed Payments / Payoneer is account-level)."""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from services import ebay  # noqa: E402


async def main():
    pp = await ebay._get("/sell/account/v1/payment_policy", {"marketplace_id": "EBAY_US"})
    policies = pp.get("paymentPolicies") or []
    print("count:", len(policies))
    print(json.dumps(policies, indent=2)[:5000])
    print("note: payout method (Payoneer #) is NOT in this API — Seller Hub only")
    print("ops note PAYONEER_ACCOUNT:", getattr(ebay, "PAYONEER_ACCOUNT", "?"))


if __name__ == "__main__":
    asyncio.run(main())
