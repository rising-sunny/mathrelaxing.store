import httpx
from fastapi import HTTPException
from typing import Any

from routers.meta_ads import _marketing_access_token, _page_id, _graph_get, _graph_post

async def get_instagram_account_id(token: str) -> str:
    page_id = _page_id()
    data = await _graph_get(
        f"/{page_id}", 
        token, 
        {"fields": "instagram_business_account", "access_token": token}
    )
    ig_account = data.get("instagram_business_account", {})
    ig_id = ig_account.get("id")
    if not ig_id:
        raise HTTPException(status_code=400, detail="No Instagram Business Account linked to this Facebook Page.")
    return ig_id

async def get_page_token(user_token: str, page_id: str) -> str:
    data = await _graph_get("/me/accounts", user_token, {"fields": "id,access_token", "limit": 200})
    for page in data.get("data", []):
        if page["id"] == page_id:
            return page["access_token"]
    raise HTTPException(status_code=403, detail="Cannot find page access token.")

async def publish_facebook_photo(image_url: str, message: str) -> str:
    user_token = await _marketing_access_token()
    page_id = _page_id()
    page_token = await get_page_token(user_token, page_id)
    
    data = await _graph_post(
        f"/{page_id}/photos",
        page_token,
        {
            "url": image_url,
            "message": message,
            "access_token": page_token
        }
    )
    return data.get("id")

async def publish_facebook_video(video_url: str, title: str, description: str) -> str:
    user_token = await _marketing_access_token()
    page_id = _page_id()
    page_token = await get_page_token(user_token, page_id)
    
    data = await _graph_post(
        f"/{page_id}/videos",
        page_token,
        {
            "file_url": video_url,
            "title": title,
            "description": description,
            "access_token": page_token
        }
    )
    return data.get("id")

async def publish_instagram_media(media_url: str, caption: str, is_video: bool = False) -> str:
    token = await _marketing_access_token()
    ig_id = await get_instagram_account_id(token)
    
    # 1. Create Media Container
    container_payload = {
        "caption": caption,
        "access_token": token
    }
    if is_video:
        container_payload["media_type"] = "REELS"
        container_payload["video_url"] = media_url
    else:
        container_payload["image_url"] = media_url

    container_res = await _graph_post(f"/{ig_id}/media", token, container_payload)
    creation_id = container_res.get("id")
    if not creation_id:
        raise HTTPException(status_code=500, detail="Failed to create Instagram media container")

    # 2. Wait for processing (specially for videos)
    import asyncio
    if is_video:
        for _ in range(20):
            await asyncio.sleep(3)
            status_res = await _graph_get(f"/{creation_id}", token, {"fields": "status_code", "access_token": token})
            if status_res.get("status_code") == "FINISHED":
                break

    # 3. Publish Container
    publish_res = await _graph_post(
        f"/{ig_id}/media_publish",
        token,
        {
            "creation_id": creation_id,
            "access_token": token
        }
    )
    return publish_res.get("id")
