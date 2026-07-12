import asyncio
from meta_organic_service import publish_instagram_media

async def main():
    video_url = "https://mathrelaxing.store/static/videos/tiktok_hyperbolic_v2.mp4"
    caption = "🎨 Explore infinite geometry with our new 'Hyperbolic Gardens' coloring book! 50 unique Escher-style patterns to relax and color. Get yours at MathRelaxing.store! ✨ #MathArt #ColoringBook #SacredGeometry #HyperbolicGeometry"
    
    print("Publishing to Instagram Reels...")
    try:
        post_id = await publish_instagram_media(
            media_url=video_url,
            caption=caption,
            is_video=True
        )
        print(f"Success! Instagram Post ID: {post_id}")
    except Exception as e:
        print(f"Failed to post: {e}")

if __name__ == "__main__":
    asyncio.run(main())
