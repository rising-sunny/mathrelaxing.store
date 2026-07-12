import asyncio
from services.bonanza import _request

async def main():
    try:
        res = await _request("getBoothItemsRequest")
        items = res.get("items", [])
        if not items:
            print("No items found in Bonanza booth.")
        else:
            print(f"Found {len(items)} items:")
            for item in items:
                print(f"- {item.get('title')} (ID: {item.get('itemId')}) - Price: ${item.get('price')}")
    except Exception as e:
        print(f"Error fetching items: {e}")

if __name__ == "__main__":
    asyncio.run(main())
