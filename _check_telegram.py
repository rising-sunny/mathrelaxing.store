"""Diagnose Telegram bot flow on VPS. Does not print full bot token."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT = os.getenv("TELEGRAM_CHAT_ID", "").strip()
BASE = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""


def mask(s: str) -> str:
    if not s:
        return "(empty)"
    if len(s) < 12:
        return s[:2] + "***"
    return s[:8] + "…" + s[-4:]


async def api(method: str, **params):
    async with httpx.AsyncClient(timeout=30) as client:
        if params:
            r = await client.post(f"{BASE}/{method}", json=params)
        else:
            r = await client.get(f"{BASE}/{method}")
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:500]}
    return r.status_code, body


async def main() -> None:
    print("=== CONFIG ===")
    print("TOKEN set:", bool(TOKEN), "mask:", mask(TOKEN))
    print("CHAT_ID:", CHAT)
    print("time_utc:", datetime.now(timezone.utc).isoformat())

    if not TOKEN:
        print("FATAL: TELEGRAM_BOT_TOKEN missing")
        return

    print("\n=== getMe ===")
    code, me = await api("getMe")
    print("http", code, "ok", me.get("ok"))
    if me.get("ok"):
        res = me["result"]
        print("bot:", res.get("username"), "id:", res.get("id"), "name:", res.get("first_name"))
    else:
        print(me)
        return

    print("\n=== getWebhookInfo ===")
    code, wh = await api("getWebhookInfo")
    print("http", code)
    if wh.get("ok"):
        r = wh["result"]
        print("url:", r.get("url"))
        print("has_custom_certificate:", r.get("has_custom_certificate"))
        print("pending_update_count:", r.get("pending_update_count"))
        print("last_error_date:", r.get("last_error_date"))
        print("last_error_message:", r.get("last_error_message"))
        print("max_connections:", r.get("max_connections"))
        print("ip_address:", r.get("ip_address"))
        print("allowed_updates:", r.get("allowed_updates"))
    else:
        print(wh)

    print("\n=== getChat (configured chat) ===")
    if CHAT:
        code, chat = await api("getChat", chat_id=CHAT)
        print("http", code, "ok", chat.get("ok"))
        if chat.get("ok"):
            c = chat["result"]
            print(
                "chat type:",
                c.get("type"),
                "id:",
                c.get("id"),
                "username:",
                c.get("username"),
                "title/name:",
                c.get("title") or c.get("first_name"),
            )
        else:
            print("getChat error:", chat)
    else:
        print("CHAT_ID empty — cannot verify")

    print("\n=== services.telegram.send_message test ===")
    try:
        from services import telegram as tg

        print("module CHAT_ID:", getattr(tg, "TELEGRAM_CHAT_ID", None) or getattr(tg, "CHAT_ID", "?"))
        # inspect signature
        import inspect

        sig = inspect.signature(tg.send_message)
        print("send_message signature:", sig)
        msg = (
            f"<b>Telegram health check</b>\n"
            f"UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Bot: @{me['result'].get('username')}\n"
            f"Configured chat: <code>{CHAT}</code>\n"
            f"Status: OK from VPS diagnostic"
        )
        # try with parse_mode if supported
        try:
            result = await tg.send_message(msg, parse_mode="HTML")
            print("send_message(HTML) result:", result)
        except TypeError:
            result = await tg.send_message(msg)
            print("send_message(plain fallback) result:", result)
        except Exception as e:
            print("send_message ERROR:", type(e).__name__, e)
    except Exception as e:
        print("import/send ERROR:", type(e).__name__, e)

    print("\n=== raw sendMessage HTML ===")
    code, sent = await api(
        "sendMessage",
        chat_id=CHAT,
        text=(
            "<b>Raw API check</b>\n"
            "Si ves esto en negrita, parse_mode HTML funciona."
        ),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    print("http", code, "ok", sent.get("ok"))
    if not sent.get("ok"):
        print(sent)
    else:
        print("message_id:", sent["result"].get("message_id"))

    print("\n=== local webhook endpoint smoke ===")
    # hit local uvicorn if possible
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # public health-ish: webhook expects POST with update
            r = await client.post(
                "https://mathrelaxing.store/api/telegram/webhook",
                json={"update_id": 0, "message": {"message_id": 1, "chat": {"id": 0}, "text": "/ping"}},
            )
        print("webhook POST status:", r.status_code, "body:", r.text[:300])
    except Exception as e:
        print("webhook smoke fail:", e)

    print("\nDONE")


if __name__ == "__main__":
    asyncio.run(main())
