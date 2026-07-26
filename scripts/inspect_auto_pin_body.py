"""Dry-run inspector for the Etsy-based auto-pin flow.

Lists the shop's active Etsy listings and prints the Pinterest pin body that
would be created for the first few — WITHOUT creating any pins. Handy to verify
Etsy auth, image resolution and copy before a real cycle runs.

Reads the Etsy token from ETSY_TOKEN_FILE (see services/etsy_client.py).

Usage:  python scripts/inspect_auto_pin_body.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.getenv("APP_DIR", "/var/www/mathrelaxing.store"))

from services import etsy_client
from services.pinterest_jobs import _build_pin_body


async def main(n: int = 5) -> None:
    if not etsy_client.is_configured():
        print("Etsy not configured (no token file / api key). Set ETSY_TOKEN_FILE.")
        return
    shop_id = await etsy_client.get_shop_id()
    listings = await etsy_client.list_active_listings(limit_total=n)
    print(f"shop_id={shop_id}  active_listings_fetched={len(listings)}\n")
    for listing in listings[:n]:
        body = await _build_pin_body(listing, "BOARD_ID_PLACEHOLDER")
        print("---", listing.get("listing_id"), "|", (listing.get("title") or "")[:60])
        if not body:
            print("  (skipped: no image)")
            continue
        print("  title:      ", body["title"])
        print("  image:      ", body["media_source"]["url"])
        print("  link:       ", body["link"])
        print("  description:", body["description"][:180].replace("\n", " "))


if __name__ == "__main__":
    asyncio.run(main())
