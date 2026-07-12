"""
Domain claim flow for Pinterest. Persists the verification metatag content
between requests/restarts and exposes it for injection into base.html.

Pinterest's /user_account/websites endpoint requires user_accounts:read +
user_accounts:write scopes. The auth flow is:

  1. POST /user_account/websites {website, verification_method: "METATAG"}
     → Pinterest returns { verification_code: "<random hex>" }
  2. Site serves <meta name="p:domain_verify" content="<code>"> in <head>
  3. POST /user_account/websites again → Pinterest fetches the home page,
     looks for the metatag, and on success marks the website verified.
"""
import json
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger("pinterest_claim")

CLAIM_FILE = os.getenv(
    "PINTEREST_CLAIM_FILE",
    "/var/www/mathrelaxing.store/.pinterest_claim.json",
)
CLAIM_DOMAIN = os.getenv("PINTEREST_CLAIM_DOMAIN", "mathrelaxing.store")


def read_claim() -> dict:
    if not os.path.exists(CLAIM_FILE):
        return {}
    try:
        with open(CLAIM_FILE) as fh:
            return json.load(fh)
    except Exception:
        logger.exception("read_claim failed")
        return {}


def write_claim(data: dict) -> None:
    tmp = CLAIM_FILE + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    os.replace(tmp, CLAIM_FILE)


def get_verify_code() -> Optional[str]:
    """Return the active verification code or None — used by templates."""
    return (read_claim() or {}).get("verification_code")


async def request_verification_code(access_token: str) -> dict:
    """Step 1: GET the metatag verification code from Pinterest."""
    import httpx
    api_base = os.getenv("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{api_base}/user_account/websites/verification",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
    data = r.json() or {}
    # Pinterest returns either verification_code or a full metatag string
    code = data.get("verification_code") or ""
    metatag = data.get("metatag") or ""
    if not code and metatag:
        # Extract content="..." from the returned metatag
        import re
        m = re.search(r'content="([^"]+)"', metatag)
        if m:
            code = m.group(1)
    if not code:
        raise RuntimeError(f"No verification_code in response: {str(data)[:400]}")
    state = {
        "website": CLAIM_DOMAIN,
        "verification_code": code,
        "verification_method": "METATAG",
        "metatag_raw": metatag,
        "status": "pending",
        "requested_at": datetime.utcnow().isoformat() + "Z",
        "raw_request_response": data,
    }
    write_claim(state)
    return state


async def submit_verification(access_token: str) -> dict:
    """Step 2: ask Pinterest to fetch our home and verify the metatag.
    Pinterest needs to see <meta name="p:domain_verify" content="..."> live."""
    import httpx
    api_base = os.getenv("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
    payload = {"website": CLAIM_DOMAIN, "verification_method": "METATAG"}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{api_base}/user_account/websites",
            headers={"Authorization": f"Bearer {access_token}"},
            json=payload,
        )
    body = {}
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:500]}
    state = read_claim() or {"website": CLAIM_DOMAIN, "verification_method": "METATAG"}
    state["last_verify_attempt_at"] = datetime.utcnow().isoformat() + "Z"
    state["last_verify_status"] = r.status_code
    state["last_verify_response"] = body
    if r.status_code < 400:
        state["status"] = body.get("status", "verified")
        state["verified_at"] = body.get("verified_at") or state["last_verify_attempt_at"]
    else:
        state["status"] = "failed"
    write_claim(state)
    return state


async def list_websites(access_token: str) -> dict:
    import httpx
    api_base = os.getenv("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{api_base}/user_account/websites",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    return {"status": r.status_code, "body": r.json() if r.content else {}}
