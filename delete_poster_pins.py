import asyncio
import httpx
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, '/var/www/mathrelaxing.store')
from routers.pinterest import _access_token

async def main():
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
                    title = pin.get('title') or ''
                    description = pin.get('description') or ''
                    
                    if 'Poster / Framed / Canvas' in title or 'Poster / Framed / Canvas' in description or 'gallery poster' in description or 'poster' in description.lower():
                        to_delete.append(pin_id)
                        
                bookmark = data.get('bookmark')
                if not bookmark:
                    break
                    
        logger.info(f"Found {len(to_delete)} pins with wrong Poster/Canvas text. Deleting...")
        
        success = 0
        for pin_id in to_delete:
            logger.info(f"Deleting pin {pin_id}...")
            d_res = await client.delete(
                f'{base_url}/pins/{pin_id}',
                headers={'Authorization': f'Bearer {token}'}
            )
            if d_res.status_code in (204, 200, 404):
                success += 1
            else:
                logger.error(f"Failed: {d_res.status_code}")
            await asyncio.sleep(0.5)

    logger.info(f"Done. Successfully deleted {success} pins.")

if __name__ == '__main__':
    asyncio.run(main())
