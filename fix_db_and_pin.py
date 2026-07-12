import asyncio
import httpx
import sqlite3
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, '/var/www/mathrelaxing.store')
from routers.pinterest import _access_token

DB_PATH = '/var/www/mathrelaxing.store/mathrelaxing.db'

async def main():
    logger.info("1. Fixing database (setting active=0 for all non-books/apparel)")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Execute a bulk update for everything that is not apparel or a book
    c.execute("""
        UPDATE products 
        SET active = 0 
        WHERE collection NOT IN ('apparel', 'coloring-books', 'coloring-book')
    """)
    conn.commit()
    conn.close()
    
    logger.info("2. Deleting broken pin 927037904567715205")
    token = await _access_token()
    base_url = 'https://api.pinterest.com/v5'
    
    async with httpx.AsyncClient(timeout=30) as client:
        d_res = await client.delete(
            f'{base_url}/pins/927037904567715205',
            headers={'Authorization': f'Bearer {token}'}
        )
        logger.info(f"Pin deletion status: {d_res.status_code}")

    logger.info("Done.")

if __name__ == '__main__':
    asyncio.run(main())
