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
    logger.info("1. Clearing local database (pinterest_pins)...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM pinterest_pins")
    conn.commit()
    conn.close()
    
    logger.info("2. Deleting ALL pins on Pinterest...")
    
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
                    pin_id = pin.get('id')
                    to_delete.append(pin_id)
                        
                bookmark = data.get('bookmark')
                if not bookmark:
                    break
                    
        logger.info(f"Found {len(to_delete)} total pins. Nuking everything...")
        
        deleted_count = 0
        for pin_id in set(to_delete):
            d_res = await client.delete(
                f'{base_url}/pins/{pin_id}',
                headers={'Authorization': f'Bearer {token}'}
            )
            if d_res.status_code in (200, 204, 404):
                deleted_count += 1
            await asyncio.sleep(0.5)

    logger.info(f"Done. Deleted {deleted_count} pins. Database cleared.")

if __name__ == '__main__':
    asyncio.run(main())
