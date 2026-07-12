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
    logger.info("1. Deactivating non-apparel/book physical products in DB...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check what is currently active
    c.execute("SELECT id, slug, collection FROM products WHERE active=1")
    active_products = c.fetchall()
    
    for pid, slug, coll in active_products:
        # Keep only apparel and coloring books active
        if coll not in ('apparel', 'coloring-books', 'coloring-book') and 'apparel' not in slug and 'coloring-book' not in slug:
            logger.info(f"Deactivating product {slug} (collection: {coll})")
            c.execute("UPDATE products SET active=0 WHERE id=?", (pid,))
            
    conn.commit()
    conn.close()
    
    logger.info("2. Deleting any pin matching Desk Mat, Coloring Book (digital?), Physical Product, or just not matching apparel...")
    
    token = await _access_token()
    base_url = 'https://api.pinterest.com/v5'
    
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(f'{base_url}/boards', headers={'Authorization': f'Bearer {token}'})
        boards = res.json().get('items', [])
        
        to_delete = []
        
        for board in boards:
            board_id = board['id']
            bookmark = None
            while True:
                params = {'page_size': 100}
                if bookmark:
                    params['bookmark'] = bookmark
                    
                p_res = await client.get(f'{base_url}/boards/{board_id}/pins', headers={'Authorization': f'Bearer {token}'}, params=params)
                if p_res.status_code != 200:
                    break
                    
                data = p_res.json()
                pins = data.get('items', [])
                
                for pin in pins:
                    title = pin.get('title') or ''
                    description = pin.get('description') or ''
                    pin_id = pin.get('id')
                    
                    if 'Desk Mat' in title or 'Desk Mat' in description or 'Physical Product' in title or 'Physical Product' in description:
                        to_delete.append(pin_id)
                        
                bookmark = data.get('bookmark')
                if not bookmark:
                    break
                    
        logger.info(f"Found {len(to_delete)} remaining invalid pins. Deleting...")
        for pin_id in set(to_delete):
            d_res = await client.delete(
                f'{base_url}/pins/{pin_id}',
                headers={'Authorization': f'Bearer {token}'}
            )
            await asyncio.sleep(0.5)

    logger.info("Done.")

if __name__ == '__main__':
    asyncio.run(main())
