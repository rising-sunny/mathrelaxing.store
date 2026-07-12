import asyncio
from services.meta_organic_service import publish_facebook_video

async def main():
    video_url = 'https://mathrelaxing.store/static/videos/promo_v3.mp4'
    title = 'MathRelaxing - Premium Mathematical Art & POD Apparel'
    description = 'Immerse yourself in the mathematical universe. Explore our exclusive 4K digital art, premium apparel, and mesmerizing coloring books.\\n\\nVisit us: mathrelaxing.store'
    
    try:
        video_id = await publish_facebook_video(video_url, title, description)
        print(f'SUCCESS! Video posted to Facebook. Video ID: {video_id}')
    except Exception as e:
        print(f'ERROR: {e}')

if __name__ == '__main__':
    asyncio.run(main())
