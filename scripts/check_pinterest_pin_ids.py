import asyncio
import sys

import httpx

sys.path.insert(0, "/var/www/mathrelaxing.store")

from routers import pinterest as pin_api


PIN_IDS = [
    "927037904567003582",
    "927037904567003580",
    "927037904567003575",
]


async def main():
    token = await pin_api._access_token()
    api_base = pin_api._api_base()
    async with httpx.AsyncClient(timeout=30) as client:
        for pin_id in PIN_IDS:
            resp = await client.get(
                f"{api_base}/pins/{pin_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            print(pin_id, resp.status_code)
            if resp.status_code < 400 and resp.content:
                body = resp.json()
                print(" title=", body.get("title"))
                print(" link=", body.get("link"))
                media = body.get("media") or {}
                print(" media_type=", media.get("media_type"), "has_images=", bool(media.get("images")))
            else:
                print(resp.text[:300])


if __name__ == "__main__":
    asyncio.run(main())
