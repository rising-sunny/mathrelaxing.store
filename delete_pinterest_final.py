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
    token = await _access_token()
    base_url = 'https://api.pinterest.com/v5'
    
    # Get active slugs
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT slug FROM products WHERE active=1")
    active_slugs = {row[0] for row in c.fetchall()}
    conn.close()
    
    valid_collections = {'apparel', 'coloring-books', 'coloring-book'}
    
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
                    link = pin.get('link') or ''
                    pin_id = pin.get('id')
                    
                    is_safe = False
                    if link == 'https://mathrelaxing.store' or link == 'https://mathrelaxing.store/':
                        is_safe = True
                    elif '/product/' in link:
                        slug_part = link.split('/product/')[1].split('?')[0].strip('/')
                        if slug_part in active_slugs:
                            is_safe = True
                    elif '/collection/' in link:
                        slug_part = link.split('/collection/')[1].split('?')[0].strip('/')
                        if slug_part in valid_collections:
                            is_safe = True
                    elif '/blog' in link or '/about' in link or '/contact' in link or '/terms' in link or '/privacy' in link:
                        is_safe = True
                        
                    if not is_safe:
                        to_delete.append((pin_id, link))
                        
                bookmark = data.get('bookmark')
                if not bookmark:
                    break
                    
        logger.info(f"Deleting {len(to_delete)} stray pins...")
        
        for pin_id, link in to_delete:
            logger.info(f"Deleting pin {pin_id} ({link})...")
            d_res = await client.delete(
                f'{base_url}/pins/{pin_id}',
                headers={'Authorization': f'Bearer {token}'}
            )
            if d_res.status_code in (204, 200, 404):
                logger.info(f"Successfully deleted.")
            else:
                logger.error(f"Failed: {d_res.status_code}")
            await asyncio.sleep(0.5)

    logger.info("Done.")

if __name__ == '__main__':
    asyncio.run(main())
