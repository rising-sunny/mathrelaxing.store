import asyncio
import sys

sys.path.insert(0, '/var/www/mathrelaxing.store')
from services.bonanza import _request, _credentials

async def main():
    print("Enviando updateBoothRequest a Bonanza...")
    try:
        data = await _request("updateBoothRequest", {
            "requesterCredentials": _credentials(),
        })
        print(f"Respuesta de Bonanza: {data}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
