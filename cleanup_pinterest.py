import asyncio
import httpx
import sqlite3
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Mock fastapi environment to import the token easily if needed
sys.path.insert(0, '/var/www/mathrelaxing.store')
from routers.pinterest import _access_token

DB_PATH = '/var/www/mathrelaxing.store/mathrelaxing.db'

async def main():
    logger.info("Starting Pinterest cleanup process...")
    
    # 1. Get access token
    try:
        token = await _access_token()
    except Exception as e:
        logger.error(f"Failed to get Pinterest token: {e}")
        return

    # 2. Find pins to delete in the DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # We want pins for deactivated physical products OR deactivated digital products
    # We'll only select active pins ("active" status in our DB might be "active")
    c.execute('''
        SELECT id, pin_id FROM pinterest_pins 
        WHERE status != 'deleted' 
        AND (
            product_slug IN (SELECT slug FROM products WHERE active=0)
            OR product_slug IN (SELECT slug FROM digital_products WHERE active=0)
        )
    ''')
    pins_to_delete = c.fetchall()
    
    if not pins_to_delete:
        logger.info("No active pins found for deactivated products. Cleanup complete.")
        conn.close()
        return
        
    logger.info(f"Found {len(pins_to_delete)} pins to delete from Pinterest.")
    
    # 3. Delete pins via API and update DB
    success_count = 0
    fail_count = 0
    
    async with httpx.AsyncClient(timeout=30) as client:
        for db_id, pin_id in pins_to_delete:
            if not pin_id:
                # Sometimes a pin might not have a Pinterest ID yet if it failed creation
                logger.warning(f"DB ID {db_id} has no Pinterest pin_id. Marking as deleted locally.")
                c.execute("UPDATE pinterest_pins SET status='deleted' WHERE id=?", (db_id,))
                conn.commit()
                continue
                
            logger.info(f"Deleting pin {pin_id} (DB id: {db_id})...")
            res = await client.delete(
                f'https://api.pinterest.com/v5/pins/{pin_id}',
                headers={'Authorization': f'Bearer {token}'}
            )
            
            # 204 No Content is success for delete. 404 is Not Found (already deleted).
            if res.status_code in (204, 200, 404):
                if res.status_code == 404:
                    logger.warning(f"Pin {pin_id} was already deleted or not found on Pinterest.")
                else:
                    logger.info(f"Pin {pin_id} successfully deleted.")
                
                # Update DB
                c.execute("UPDATE pinterest_pins SET status='deleted' WHERE id=?", (db_id,))
                conn.commit()
                success_count += 1
            elif res.status_code == 429:
                logger.error("Rate limit reached. Aborting.")
                break
            else:
                logger.error(f"Failed to delete pin {pin_id}: HTTP {res.status_code} - {res.text}")
                fail_count += 1
                
            # Sleep slightly to respect rate limits
            await asyncio.sleep(0.5)

    conn.close()
    logger.info(f"Cleanup finished. Successfully deleted: {success_count}. Failed: {fail_count}.")

if __name__ == "__main__":
    asyncio.run(main())
