"""Opt mathrelaxing into business policies and diagnose seller readiness."""
import asyncio
import json
import os
import sys
import re

import httpx

sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")
from dotenv import load_dotenv
from importlib import reload

load_dotenv(".env")
import services.ebay as ebay

reload(ebay)


async def main():
    token = await ebay.get_access_token()
    print("token ok")

    # GetUser
    xml = """<?xml version="1.0" encoding="utf-8"?>
<GetUserRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <DetailLevel>ReturnAll</DetailLevel>
</GetUserRequest>"""
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
    for tag in (
        "UserID",
        "Email",
        "Status",
        "SellerBusinessType",
        "StoreOwner",
        "GoodStanding",
        "SellerInfo",
    ):
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", r.text, re.S)
        if m and tag != "SellerInfo":
            print(f"{tag}: {re.sub(chr(10), ' ', m.group(1))[:120]}")

    print("\nprivilege before:")
    try:
        print(await ebay._get("/sell/account/v1/privilege"))
    except Exception as e:
        print("err", e)

    print("\nprograms before:")
    try:
        print(await ebay._get("/sell/account/v1/program/get_opted_in_programs"))
    except Exception as e:
        print("err", e)

    # Opt into business policies
    for program in ("SELLING_POLICY_MANAGEMENT", "OUT_OF_STOCK_CONTROL"):
        try:
            r = await ebay._post(
                "/sell/account/v1/program/opt_in",
                {"programType": program},
            )
            print(f"opt_in {program}:", r)
        except Exception as e:
            print(f"opt_in {program} FAIL:", e)

    print("\nprograms after:")
    try:
        print(await ebay._get("/sell/account/v1/program/get_opted_in_programs"))
    except Exception as e:
        print("err", e)

    print("\nprivilege after:")
    try:
        print(await ebay._get("/sell/account/v1/privilege"))
    except Exception as e:
        print("err", e)

    # Try create policies now
    print("\ntry policies:")
    try:
        pol = await ebay.get_or_create_policies()
        print("policies OK", pol)
    except Exception as e:
        print("policies FAIL", e)

    # Selling limits / payments
    for path in (
        "/sell/account/v1/payments_program/EBAY_US/EBAY_PAYMENTS",
        "/sell/account/v1/kyc",
    ):
        try:
            print(path, await ebay._get(path))
        except Exception as e:
            print(path, "FAIL", str(e)[:200])


asyncio.run(main())
