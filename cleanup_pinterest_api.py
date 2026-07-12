import asyncio
import httpx
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, '/var/www/mathrelaxing.store')
from routers.pinterest import _access_token

async def main():
    logger.info("Starting deep Pinterest cleanup process via API...")
    try:
        token = await _access_token()
    except Exception as e:
        logger.error(f"Failed to get Pinterest token: {e}")
        return

    base_url = 'https://api.pinterest.com/v5'
    
    async with httpx.AsyncClient(timeout=30) as client:
        # Get boards
        res = await client.get(f'{base_url}/boards', headers={'Authorization': f'Bearer {token}'})
        boards = res.json().get('items', [])
        
        pins_to_delete = []
        
        for board in boards:
            board_id = board['id']
            bookmark = None
            
            while True:
                params = {'page_size': 100}
                if bookmark:
                    params['bookmark'] = bookmark
                    
                p_res = await client.get(f'{base_url}/boards/{board_id}/pins', headers={'Authorization': f'Bearer {token}'}, params=params)
                if p_res.status_code != 200:
                    logger.error(f'Error getting pins: {p_res.text}')
                    break
                    
                data = p_res.json()
                pins = data.get('items', [])
                
                for pin in pins:
                    link = pin.get('link') or ''
                    pin_id = pin.get('id')
                    
                    if '/bundle/' in link or '/collection/strange-attractors' in link or '/collection/fractal-' in link or '/collection/voronoi-' in link or '/collection/chladni-' in link or '/collection/de-jong-' in link or '/collection/complex-plane' in link or '/collection/radial-symmetry' in link:
                        pins_to_delete.append(pin_id)
                        
                bookmark = data.get('bookmark')
                if not bookmark:
                    break
                    
        logger.info(f"Found {len(pins_to_delete)} orphan digital pins to delete.")
        
        success_count = 0
        fail_count = 0
        
        for pin_id in pins_to_delete:
            logger.info(f"Deleting pin {pin_id}...")
            res = await client.delete(
                f'{base_url}/pins/{pin_id}',
                headers={'Authorization': f'Bearer {token}'}
            )
            
            if res.status_code in (204, 200, 404):
                success_count += 1
            elif res.status_code == 429:
                logger.error("Rate limit reached. Aborting.")
                break
            else:
                logger.error(f"Failed to delete pin {pin_id}: HTTP {res.status_code} - {res.text}")
                fail_count += 1
                
            await asyncio.sleep(0.5)

    logger.info(f"Cleanup finished. Successfully deleted: {success_count}. Failed: {fail_count}.")

if __name__ == '__main__':
    asyncio.run(main())
