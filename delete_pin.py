import asyncio
import httpx
from routers.pinterest import _access_token

async def main():
    t = await _access_token()
    async with httpx.AsyncClient() as c:
        res = await c.delete(
            'https://api.pinterest.com/v5/pins/927037904567355820',
            headers={'Authorization': f'Bearer {t}'}
        )
        print(f"Delete status: {res.status_code}")

if __name__ == "__main__":
    asyncio.run(main())
