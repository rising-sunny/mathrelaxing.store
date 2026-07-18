import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
from routers import meta_ads as m

IDS = [
    "120249640557690256",
    "120249640552280256",
    "120249640551080256",
]


async def main():
    token = await m._marketing_access_token()
    for i in IDS:
        await m._graph_post(f"/{i}", token, {"status": "PAUSED"})
        d = await m._graph_get(
            f"/{i}", token, {"fields": "id,name,status,effective_status"}
        )
        print("OK", d.get("name"), d.get("status"), d.get("effective_status"))


asyncio.run(main())
