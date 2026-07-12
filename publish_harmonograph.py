import asyncio
import os
import httpx
import logging
import sqlite3
from routers.pinterest import _access_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    api_base = "https://api.pinterest.com/v5"
    access_token = await _access_token()
    
    # 1. DELETE BAD PIN
    bad_pin_id = "927037904567727693"
    logger.info(f"Deleting bad Pin {bad_pin_id}...")
    async with httpx.AsyncClient(timeout=60) as client:
        del_res = await client.delete(
            f"{api_base}/pins/{bad_pin_id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if del_res.status_code in (204, 200, 404):
            logger.info("Bad pin deleted (or already gone).")
        else:
            logger.warning(f"Failed to delete pin: {del_res.status_code} {del_res.text}")

        # 2. GET PRODUCT INFO
        conn = sqlite3.connect('/var/www/mathrelaxing.store/mathrelaxing.db')
        c = conn.cursor()
        c.execute("SELECT slug, name, image_url FROM products WHERE slug='harmonograph-dreams-coloring-book'")
        product = c.fetchone()
        if not product:
            logger.error("Harmonograph product not found in DB!")
            return
            
        slug, name, cover_url = product
        if not cover_url:
            cover_url = "https://mathrelaxing.store/static/img/harmonograph_dreams_cover.png"
        elif cover_url.startswith('/'):
            cover_url = f"https://mathrelaxing.store{cover_url}"
            
        video_local_path = "/var/www/mathrelaxing.store/static/video/fb_harmonograph_v1.mp4"

        logger.info("Registering video upload with Pinterest...")
        res = await client.post(
            f"{api_base}/media",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"media_type": "video"}
        )
        if res.status_code >= 400:
            logger.error(f"Failed to register media: {res.text}")
            return
            
        data = res.json()
        media_id = data["media_id"]
        upload_url = data["upload_url"]
        upload_params = data["upload_parameters"]
        
        logger.info(f"Media ID: {media_id}. Uploading video file...")
        
        with open(video_local_path, "rb") as f:
            files = {"file": f}
            upload_res = await client.post(upload_url, data=upload_params, files=files)
            
        if upload_res.status_code not in (200, 204, 201):
            logger.error(f"Failed to upload video: {upload_res.status_code} {upload_res.text}")
            return
            
        logger.info("Video uploaded. Waiting for processing...")
        
        while True:
            await asyncio.sleep(3)
            status_res = await client.get(
                f"{api_base}/media/{media_id}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            status_data = status_res.json()
            status = status_data.get("status")
            if status == "succeeded":
                logger.info("Video processing succeeded!")
                break
            elif status == "failed":
                logger.error("Video processing failed.")
                return
            logger.info(f"Processing status: {status}...")

        logger.info("Creating the Pin...")
        
        boards_res = await client.get(
            f"{api_base}/boards",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        boards_data = boards_res.json()
        board_id = boards_data["items"][0]["id"]
        
        caption = "✨ Discover the physics of beauty with 'Harmonograph Dreams' coloring book. 50 unique pendulum-drawn mandalas waiting for your creativity. 🎨 Check it out at MathRelaxing.store! #Harmonograph #MathArt #ColoringBook"
        
        pin_body = {
            "board_id": board_id,
            "title": f"{name} | MathRelaxing",
            "description": caption,
            "link": f"https://mathrelaxing.store/product/{slug}",
            "media_source": {
                "source_type": "video_id",
                "cover_image_url": cover_url,
                "media_id": media_id
            }
        }
        
        pin_res = await client.post(
            f"{api_base}/pins",
            headers={"Authorization": f"Bearer {access_token}"},
            json=pin_body
        )
        if pin_res.status_code >= 400:
            logger.error(f"Failed to create Pin: {pin_res.text}")
            return
            
        pin_data = pin_res.json()
        logger.info(f"Success! Pin created with ID: {pin_data.get('id')}")
        logger.info(f"View it at: https://pinterest.com/pin/{pin_data.get('id')}")

if __name__ == "__main__":
    asyncio.run(main())
