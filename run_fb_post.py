import asyncio
from services.meta_organic_service import publish_facebook_video

async def main():
    video_url = "https://mathrelaxing.store/static/videos/tiktok_hyperbolic_v2.mp4"
    title = "Hyperbolic Gardens Coloring Book"
    caption = (
        "Discover the beauty of non-euclidean geometry! 🌌✨\n"
        "Our new 'Hyperbolic Gardens' coloring book features 50 hand-drawn mathematical designs, "
        "including mesmerizing Poincaré disks and intricate tessellations.\n\n"
        "Watch as the colors come alive procedurally! 🎨\n"
        "Shop now: https://mathrelaxing.store/product/hyperbolic-gardens-coloring-book\n\n"
        "#MathArt #ColoringBook #Mindfulness #HyperbolicGeometry #CreativeArt #Relaxation"
    )

    print("Publishing to Facebook Page via Meta API...")
    try:
        post_id = await publish_facebook_video(video_url, title, caption)
        print(f"Success! Facebook Post ID: {post_id}")
    except Exception as e:
        print(f"Failed to publish: {e}")

if __name__ == '__main__':
    asyncio.run(main())
