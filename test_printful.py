import asyncio
import os
import sys

sys.path.insert(0, '/var/www/mathrelaxing.store')

from dotenv import load_dotenv
load_dotenv('/var/www/mathrelaxing.store/.env')

from services.printful import _headers, BASE_URL
import httpx

async def test():
    print("Requesting Printfiles for 946...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{BASE_URL}/mockup-generator/printfiles/946",
            headers=_headers()
        )
        import json
        print(json.dumps(resp.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(test())
