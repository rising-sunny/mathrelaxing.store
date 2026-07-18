import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv("/var/www/mathrelaxing.store/.env")
sys.path.insert(0, "/var/www/mathrelaxing.store")
os.chdir("/var/www/mathrelaxing.store")

from routers import meta_ads as m


async def try_token(label: str, token: str) -> None:
    print("===", label, "===")
    try:
        dbg = await m._debug_token(token)
        data = dbg.get("data") if isinstance(dbg.get("data"), dict) else dbg
        print("valid", data.get("is_valid"), "type", data.get("type"))
        print("scopes", data.get("scopes"))
        act = m._ad_account_id()
        try:
            perms = await m._graph_get(
                f"/act_{act}",
                token=token,
                params={"fields": "id,account_status,user_tasks,name"},
            )
            print("account", perms)
        except Exception as e:
            print("account fail", getattr(e, "detail", e))
        try:
            r = await m._graph_post(
                f"/act_{act}/campaigns",
                token,
                {
                    "name": "MR | PERM TEST DELETE ME | PAUSED",
                    "objective": "OUTCOME_TRAFFIC",
                    "status": "PAUSED",
                    "special_ad_categories": [],
                },
            )
            print("CREATE OK", r)
            try:
                await m._graph_post(f"/{r['id']}", token, {"status": "DELETED"})
                print("deleted test campaign")
            except Exception as e2:
                print("delete fail", getattr(e2, "detail", e2))
        except Exception as e:
            print("CREATE FAIL", getattr(e, "detail", e))
    except Exception as e:
        print("token fail", e)


async def main() -> None:
    user = m._read_token() or {}
    sys_t = m._read_system_token() or {}
    if user.get("access_token"):
        await try_token("USER", user["access_token"])
    if sys_t.get("access_token"):
        await try_token("SYSTEM", sys_t["access_token"])
    tok = await m._marketing_access_token()
    await try_token("MARKETING_FN", tok)


if __name__ == "__main__":
    asyncio.run(main())
