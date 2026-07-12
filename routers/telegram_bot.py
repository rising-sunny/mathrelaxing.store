"""Telegram bot webhook — /stats command (multi-channel sales breakdown)."""
import os
import sqlite3
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Request

TZ  = ZoneInfo("America/Santiago")
UTC = ZoneInfo("UTC")

router = APIRouter()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
DB             = "/var/www/mathrelaxing.store/mathrelaxing.db"
NGINX_LOG      = "/var/log/nginx/access.log"
NGINX_LOG_PREV = "/var/log/nginx/access.log.1"

LOWPOLY_PRICE = 2.99

# Purchase `source` labels that are NOT one of the off-site channels are treated
# as direct web sales (paypal / lemon / whop / direct / legacy / physical-web…).
OFFSITE_SOURCES = ("bonanza", "gumroad", "lowpoly")


def _now_chile() -> datetime:
    return datetime.now(TZ)


def _today_start_utc() -> str:
    """UTC timestamp string for the start of the current Chile day."""
    start_cl = _now_chile().replace(hour=0, minute=0, second=0, microsecond=0)
    return start_cl.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _nginx_count_24h(pattern: str) -> int:
    utc_now   = datetime.now(UTC)
    utc_start = utc_now - timedelta(hours=24)
    count = 0
    for log_file in [NGINX_LOG_PREV, NGINX_LOG]:
        if not os.path.exists(log_file):
            continue
        try:
            result = subprocess.run(
                ["grep", pattern, log_file],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                try:
                    ts_str = line.split("[")[1].split("]")[0]
                    ts = datetime.strptime(ts_str, "%d/%b/%Y:%H:%M:%S %z")
                    if ts >= utc_start:
                        count += 1
                except Exception:
                    pass
        except Exception:
            pass
    return count


def _channel_stats() -> dict:
    """Carts / checkouts / purchases split by sales channel.

    - Web directa: full browser funnel (carts, checkouts) + on-site purchases
      (any purchase source that is not an off-site channel).
    - Bonanza / Gumroad: completed purchases only (sales happen off-site).
    - GPT Store: lowpoly tool — purchases from `lowpoly_jobs`, plus the
      conversation/preview/checkout funnel counted from nginx (24h).
    """
    start = _today_start_utc()
    s: dict = {}
    try:
        conn = sqlite3.connect(DB)

        def one(q, args=()):
            return conn.execute(q, args).fetchone()[0] or 0

        # ── Web browser funnel today (carts / checkouts) ──
        s["web_carts"] = one(
            "SELECT COUNT(DISTINCT session_id) FROM live_events "
            "WHERE ts>=? AND event_type IN ('add_to_cart','cart_view')", (start,))
        s["web_checkouts"] = one(
            "SELECT COUNT(DISTINCT session_id) FROM live_events "
            "WHERE ts>=? AND event_type IN ('checkout_start','payment_redirect')", (start,))

        # ── Purchases by channel (live_events) ──
        offsite_in = "(" + ",".join("?" * len(OFFSITE_SOURCES)) + ")"

        def purch(where, args, today=True):
            t = "AND ts>=?" if today else ""
            a = (args + (start,)) if today else args
            c = one(f"SELECT COUNT(*) FROM live_events WHERE event_type='purchase' AND {where} {t}", a)
            r = one(f"SELECT COALESCE(SUM(value_usd),0) FROM live_events WHERE event_type='purchase' AND {where} {t}", a)
            return c, float(r)

        s["web_p"],  s["web_r"]  = purch(f"COALESCE(source,'') NOT IN {offsite_in}", OFFSITE_SOURCES)
        s["bz_p"],   s["bz_r"]   = purch("source='bonanza'", ())
        s["gum_p"],  s["gum_r"]  = purch("source='gumroad'", ())
        s["web_pT"], s["web_rT"] = purch(f"COALESCE(source,'') NOT IN {offsite_in}", OFFSITE_SOURCES, today=False)
        s["bz_pT"],  s["bz_rT"]  = purch("source='bonanza'", (), today=False)
        s["gum_pT"], s["gum_rT"] = purch("source='gumroad'", (), today=False)

        # ── GPT Store (lowpoly) purchases from the authoritative jobs table ──
        s["gpt_p"]  = one("SELECT COUNT(*) FROM lowpoly_jobs WHERE status='paid' AND created_at>=?", (start,))
        s["gpt_pT"] = one("SELECT COUNT(*) FROM lowpoly_jobs WHERE status='paid'")
        s["gpt_r"]  = s["gpt_p"]  * LOWPOLY_PRICE
        s["gpt_rT"] = s["gpt_pT"] * LOWPOLY_PRICE

        conn.close()
    except Exception:
        # Never let a stats query break the webhook; show zeros.
        for k in ("web_carts","web_checkouts","web_p","web_r","bz_p","bz_r","gum_p","gum_r",
                  "web_pT","web_rT","bz_pT","bz_rT","gum_pT","gum_rT","gpt_p","gpt_pT","gpt_r","gpt_rT"):
            s.setdefault(k, 0)

    # ── GPT funnel from nginx (24h) ──
    s["gpt_conv"]      = _nginx_count_24h("gpt/lowpoly/guide")
    s["gpt_previews"]  = _nginx_count_24h("gpt/lowpoly/preview")
    s["gpt_checkouts"] = _nginx_count_24h("gpt/lowpoly/checkout")
    return s


def _build_stats_message() -> str:
    s = _channel_stats()
    today = _now_chile().strftime("%d %b %Y")

    tp = s["web_p"] + s["bz_p"] + s["gum_p"] + s["gpt_p"]
    tr = s["web_r"] + s["bz_r"] + s["gum_r"] + s["gpt_r"]
    ap = s["web_pT"] + s["bz_pT"] + s["gum_pT"] + s["gpt_pT"]
    ar = s["web_rT"] + s["bz_rT"] + s["gum_rT"] + s["gpt_rT"]

    return (
        f"📊 <b>Stats — hoy {today}</b>\n"
        f"<i>🛒 carrito · 💳 checkout · ✅ compra</i>\n\n"
        f"🌐 <b>Web directa</b>\n"
        f"🛒 {s['web_carts']} · 💳 {s['web_checkouts']} · ✅ {s['web_p']} (${s['web_r']:.0f})\n\n"
        f"🛍 <b>Bonanza</b>\n"
        f"🛒 — · 💳 — · ✅ {s['bz_p']} (${s['bz_r']:.0f})\n\n"
        f"🤖 <b>GPT Store</b>\n"
        f"🛒 — · 💳 {s['gpt_checkouts']} · ✅ {s['gpt_p']} (${s['gpt_r']:.0f})\n"
        f"<i>💬 {s['gpt_conv']} convs · 👁 {s['gpt_previews']} previews (24h)</i>\n\n"
        f"🍋 <b>Gumroad</b>\n"
        f"🛒 — · 💳 — · ✅ {s['gum_p']} (${s['gum_r']:.0f})\n\n"
        f"━━━━━━━━━━\n"
        f"Σ <b>hoy:</b> {tp} compras · ${tr:.0f}\n"
        f"📦 <b>histórico:</b> {ap} compras · ${ar:.0f}"
    )


async def _reply(chat_id: str, text: str):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=10,
        )


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = str(message.get("chat", {}).get("id", ""))
    text = (message.get("text") or "").strip()

    if chat_id != str(TELEGRAM_CHAT_ID):
        return {"ok": True}

    if text.startswith("/stats"):
        await _reply(chat_id, _build_stats_message())
    elif text.startswith("/start"):
        await _reply(chat_id,
                     "👋 Bot de MathRelaxing conectado.\n\n"
                     "Comando disponible:\n• /stats — ventas por canal (web, Bonanza, GPT, Gumroad)")

    return {"ok": True}
