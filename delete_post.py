import asyncio
import sys

sys.path.insert(0, '/var/www/mathrelaxing.store')

from services.meta_organic_service import _marketing_access_token, _page_id, get_page_token
import httpx
from routers.meta_ads import _graph_base

async def main():
    try:
        user_token = await _marketing_access_token()
        page_id = _page_id()
        page_token = await get_page_token(user_token, page_id)
        
        post_id = "122212850510768710"
        print(f"Iniciando borrado del post de prueba {post_id}...")
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.delete(f"{_graph_base()}/{post_id}", params={"access_token": page_token})
            
        if resp.status_code < 400:
            print("✅ Post eliminado con éxito de Facebook.")
        else:
            print(f"❌ Error al borrar: {resp.text}")
            
    except Exception as e:
        print(f"❌ Excepción: {e}")

if __name__ == "__main__":
    asyncio.run(main())
