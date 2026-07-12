import asyncio
import sys

sys.path.insert(0, '/var/www/mathrelaxing.store')

from services.meta_organic_service import publish_facebook_video

async def main():
    video_url = "https://mathrelaxing.store/static/video/tiktok_chladni_v2.mp4"
    title = "The Mesmerizing Patterns of Sound"
    description = "Discover the hidden geometry of sound! 🎶✨ Watch as acoustic frequencies transform sand into perfect mathematical symmetry. This is the magic of Chladni figures—where math meets art.\n\nExplore more satisfying mathematical art and grab our exclusive coloring books at mathrelaxing.store! 📘\n\n#MathArt #Chladni #Cymatics #Satisfying #SacredGeometry #Physics #STEM #MathRelaxing"
    
    try:
        print(f"Iniciando publicación del video: {video_url}")
        post_id = await publish_facebook_video(video_url, title, description)
        print(f"\n✅ ¡ÉXITO! El video se ha publicado correctamente en Facebook.")
        print(f"ID del Video: {post_id}")
    except Exception as e:
        print(f"\n❌ ERROR AL PUBLICAR EL VIDEO: {e}")

if __name__ == "__main__":
    asyncio.run(main())
