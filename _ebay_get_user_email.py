"""One-shot: print eBay account UserID + Email via Trading API GetUser."""
import asyncio
import os
import re
import sys

import httpx

# VPS paths
sys.path.insert(0, os.getcwd())
from services import ebay  # noqa: E402


async def main():
    token = await ebay.get_access_token()
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<GetUserRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
        "<DetailLevel>ReturnAll</DetailLevel>"
        "</GetUserRequest>"
    )
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            "https://api.ebay.com/ws/api.dll",
            headers={
                "X-EBAY-API-SITEID": "0",
                "X-EBAY-API-COMPATIBILITY-LEVEL": "1193",
                "X-EBAY-API-CALL-NAME": "GetUser",
                "X-EBAY-API-IAF-TOKEN": token,
                "Content-Type": "text/xml",
            },
            content=xml,
        )
    text = r.text
    out = "/tmp/ebay_getuser.xml"
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print("status_code", r.status_code)
    for tag in ("UserID", "Email", "Status", "RegistrationDate", "Site", "UserFirstName", "UserLastName"):
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, re.I | re.S)
        if m:
            val = re.sub(r"<[^>]+>", " ", m.group(1)).strip()
            print(f"{tag}: {val[:300]}")
    m = re.search(r"<Store>.*?<Name>(.*?)</Name>", text, re.I | re.S)
    if m:
        print("StoreName:", m.group(1))
    m = re.search(r"<Store>.*?<URL>(.*?)</URL>", text, re.I | re.S)
    if m:
        print("StoreURL:", m.group(1))
    if "Success" not in text[:800]:
        print("RAW_HEAD:", text[:600])


if __name__ == "__main__":
    asyncio.run(main())
