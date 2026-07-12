import os
import json
import requests
from dotenv import dotenv_values

def main():
    env = dotenv_values('/var/www/mathrelaxing.store/.env')
    page_id = env.get('META_PAGE_ID')
    token_file = env.get('META_TOKEN_FILE')

    if not page_id or not token_file:
        print("Error: META_PAGE_ID or META_TOKEN_FILE missing in .env")
        return

    with open(token_file, 'r') as f:
        data = json.load(f)
        access_token = data.get('access_token')

    if not access_token:
        print("Error: access_token not found in token file")
        return

    # Fetch Page Access Token using User Access Token
    token_url = f"https://graph.facebook.com/v19.0/{page_id}?fields=access_token&access_token={access_token}"
    token_res = requests.get(token_url)
    if token_res.status_code == 200:
        page_token_data = token_res.json()
        page_access_token = page_token_data.get('access_token')
        if page_access_token:
            access_token = page_access_token
            print("Successfully retrieved Page Access Token.")
        else:
            print("Warning: Could not extract Page Access Token, using User Access Token instead.")
    else:
        print(f"Failed to retrieve Page Access Token: {token_res.text}")

    video_path = '/var/www/mathrelaxing.store/static/videos/tiktok_hyperbolic_v2.mp4'
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        return

    url = f"https://graph.facebook.com/v19.0/{page_id}/videos"
    
    caption = (
        "Discover the beauty of non-euclidean geometry! 🌌✨\n"
        "Our new 'Hyperbolic Gardens' coloring book features 50 hand-drawn mathematical designs, "
        "including mesmerizing Poincaré disks and intricate tessellations.\n\n"
        "Watch as the colors come alive procedurally! 🎨\n"
        "Shop now: https://mathrelaxing.store/product/hyperbolic-gardens-coloring-book\n\n"
        "#MathArt #ColoringBook #Mindfulness #HyperbolicGeometry #CreativeArt #Relaxation"
    )

    payload = {
        'access_token': access_token,
        'description': caption
    }

    print(f"Uploading video to Facebook Page {page_id}...")
    with open(video_path, 'rb') as f:
        files = {'source': f}
        response = requests.post(url, data=payload, files=files)

    if response.status_code == 200:
        res = response.json()
        print(f"Success! Video ID: {res.get('id')}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

if __name__ == '__main__':
    main()
