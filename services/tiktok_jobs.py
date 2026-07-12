"""
Auto-posting job for TikTok.
Selects products and posts them as TikTok videos using the Direct Post API.
Uses a pre-generated video (e.g. tiktok_chladni.mp4) and dynamically selects captions.
"""
import logging
import os
import random
from datetime import datetime

from database import SessionLocal
from models.tiktok_post import TikTokPost
from models.product import Product
from routers.tiktok import _ensure_access_token, _tiktok_post, _is_configured, _privacy_level

logger = logging.getLogger("tiktok_jobs")

TIKTOK_CYCLE_HOURS = int(os.getenv("TIKTOK_CYCLE_HOURS", "24"))

CAPTIONS = [
    "Discover a new way to relax. 🎧✨ Instead of typical designs, the Sacred Harmonics Coloring Book features 50 real acoustic resonance patterns (Chladni figures) mapped directly onto paper. Let the hidden geometry of sound waves guide your coloring journey.\n\n📚 Get yours here with FREE shipping: mathrelaxing.store/book\n\n#ColoringBook #Mindfulness #SacredGeometry #ArtTherapy #Relaxing #AdultColoringBook #ChladniFigures #MathArt #SoundHealing",
    
    "Have you ever wondered what sound looks like? 🎵 The Sacred Harmonics Coloring Book takes real acoustic frequencies and turns them into 50 beautiful geometric patterns for you to color. A unique, mindful experience where science meets art. 🎨\n\n📦 Available now with FREE shipping: mathrelaxing.store/book\n\n#ColoringBook #SacredGeometry #SoundWaves #Physics #Mathematics #Chladni #ColoringForAdults #Creativity #STEAM",
]

async def run_auto_post_cycle() -> dict:
    if not _is_configured():
        return {"skipped": "TikTok not configured"}

    db = SessionLocal()
    try:
        # We only post the sacred harmonics book for now
        product = db.query(Product).filter(Product.slug == "sacred-harmonics-coloring-book").first()
        if not product:
            return {"skipped": "Target product not found"}

        # For Option B, we use the existing generated video
        video_url = os.getenv("TIKTOK_DEMO_VIDEO_URL", "https://mathrelaxing.store/static/video/tiktok_chladni.mp4")

        # Check if we already posted recently (cooldown: e.g. 7 days or we just post anyway?)
        # Since we use the SAME video, posting too often might get flagged. Let's add a 3 day cooldown.
        cooldown_days = 3
        last_post = db.query(TikTokPost).filter(
            TikTokPost.product_slug == product.slug,
            TikTokPost.status == "published"
        ).order_by(TikTokPost.created_at.desc()).first()

        if last_post and (datetime.utcnow() - last_post.created_at).days < cooldown_days:
            return {"skipped": f"Cooldown active (last posted {(datetime.utcnow() - last_post.created_at).days} days ago)"}

        caption = random.choice(CAPTIONS)

        # Get Token
        try:
            token = await _ensure_access_token()
        except Exception as e:
            return {"skipped": f"Failed to get token: {e}"}

        # Direct Publish API request (video.publish scope)
        payload = {
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": video_url
            },
            "post_info": {
                "title": caption,
                "privacy_level": _privacy_level(),
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000
            }
        }

        result = await _tiktok_post(
            "/v2/post/publish/video/init/",
            token["access_token"],
            payload
        )

        publish_id = result.get("data", {}).get("publish_id")

        post_record = TikTokPost(
            product_slug=product.slug,
            video_url=video_url,
            publish_id=publish_id,
            status="published",
            caption=caption,
        )
        db.add(post_record)
        db.commit()

        return {"created": 1, "publish_id": publish_id}

    except Exception as e:
        logger.error(f"TikTok auto post failed: {e}", exc_info=True)
        return {"failed": 1, "error": str(e)}
    finally:
        db.close()
