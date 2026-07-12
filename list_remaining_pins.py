import asyncio
import httpx
import sys

sys.path.insert(0, '/var/www/mathrelaxing.store')
from routers.pinterest import _access_token

async def main():
    token = await _access_token()
    base_url = 'https://api.pinterest.com/v5'
    
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(f'{base_url}/boards', headers={'Authorization': f'Bearer {token}'})
        boards = res.json().get('items', [])
        
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
                    print(f"ID: {pin.get('id')}")
                    print(f"Title: {pin.get('title')}")
                    print(f"Link: {pin.get('link')}")
                    print(f"Description: {pin.get('description')}")
                    print("-" * 40)
                    
                bookmark = data.get('bookmark')
                if not bookmark:
                    break

if __name__ == '__main__':
    asyncio.run(main())
