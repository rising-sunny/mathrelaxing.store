import os
import json
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

router = APIRouter(prefix="/admin", tags=["admin"])

TIKTOK_ADS_APP_ID = os.getenv("TIKTOK_ADS_APP_ID")
TIKTOK_ADS_SECRET = os.getenv("TIKTOK_ADS_SECRET")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", ".tiktok_ads_token.json")

@router.get("/tiktok-ads/login")
async def tiktok_ads_login(request: Request):
    if not TIKTOK_ADS_APP_ID:
        raise HTTPException(status_code=500, detail="TIKTOK_ADS_APP_ID no esta configurado en .env")
    
    redirect_uri = f"{request.base_url}admin/tiktok-ads/callback"
    auth_url = (
        f"https://ads.tiktok.com/marketing_api/auth?"
        f"app_id={TIKTOK_ADS_APP_ID}&"
        f"redirect_uri={redirect_uri}"
    )
    return RedirectResponse(auth_url)

@router.get("/tiktok-ads/callback")
async def tiktok_ads_callback(request: Request, auth_code: str = None):
    if not auth_code:
        raise HTTPException(status_code=400, detail="No se recibio auth_code de TikTok")
    
    if not TIKTOK_ADS_APP_ID or not TIKTOK_ADS_SECRET:
        raise HTTPException(status_code=500, detail="Credenciales de TikTok Ads no configuradas")

    url = "https://business-api.tiktok.com/open_api/v1.3/oauth2/access_token/"
    
    payload = {
        "app_id": TIKTOK_ADS_APP_ID,
        "secret": TIKTOK_ADS_SECRET,
        "auth_code": auth_code
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        data = response.json()
        
    if data.get("code") != 0:
        return JSONResponse({"error": "Error obteniendo token", "details": data}, status_code=400)
        
    token_info = data.get("data", {})
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_info, f, indent=4)
        
    return JSONResponse({"message": "Autenticacion de TikTok Ads exitosa", "token_info": token_info})
