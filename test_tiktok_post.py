import asyncio
from services.tiktok_jobs import run_auto_post_cycle

async def main():
    print("Iniciando prueba de post en TikTok...")
    result = await run_auto_post_cycle()
    print("Resultado del post:", result)

if __name__ == "__main__":
    asyncio.run(main())
