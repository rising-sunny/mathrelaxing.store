import os
import json
import httpx
from datetime import datetime

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", ".tiktok_ads_token.json")
ADVERTISER_ID = os.getenv("TIKTOK_ADS_ADVERTISER_ID")

def get_access_token():
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, "r") as f:
        data = json.load(f)
        return data.get("access_token")

async def create_campaign(campaign_name: str = "Auto-Campaign"):
    token = get_access_token()
    if not token or not ADVERTISER_ID:
        raise Exception("Token de Ads o Advertiser ID no configurados")

    url = "https://business-api.tiktok.com/open_api/v1.3/campaign/create/"
    headers = {
        "Access-Token": token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "advertiser_id": ADVERTISER_ID,
        "campaign_name": f"{campaign_name} - {datetime.now().strftime('%Y%m%d%H%M')}",
        "objective_type": "TRAFFIC", 
        "budget_mode": "BUDGET_MODE_DAY",
        "budget": 20,
        "operation_status": "DISABLE"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        return response.json()

async def create_ad_group(campaign_id: str, group_name: str = "Auto-AdGroup"):
    token = get_access_token()
    url = "https://business-api.tiktok.com/open_api/v1.3/adgroup/create/"
    headers = {
        "Access-Token": token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "advertiser_id": ADVERTISER_ID,
        "campaign_id": campaign_id,
        "adgroup_name": f"{group_name} - {datetime.now().strftime('%Y%m%d%H%M')}",
        "placement_type": "PLACEMENT_TYPE_NORMAL",
        "budget_mode": "BUDGET_MODE_DAY",
        "budget": 20,
        "schedule_type": "SCHEDULE_START_END",
        "billing_event": "CPC",
        "bid_type": "BID_TYPE_NO_BID",
        "optimization_goal": "CLICK",
        "operation_status": "DISABLE"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        return response.json()

async def create_ad(adgroup_id: str, video_id: str, ad_name: str = "Auto-Ad"):
    token = get_access_token()
    url = "https://business-api.tiktok.com/open_api/v1.3/ad/create/"
    headers = {
        "Access-Token": token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "advertiser_id": ADVERTISER_ID,
        "adgroup_id": adgroup_id,
        "creatives": [{
            "ad_name": f"{ad_name} - {datetime.now().strftime('%Y%m%d%H%M')}",
            "video_id": video_id,
            "ad_text": "Check out these satisfying math patterns!",
            "operation_status": "DISABLE"
        }]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        return response.json()
