import asyncio
import sys

# Ensure the parent directory is in the sys.path for absolute imports
sys.path.insert(0, '/var/www/mathrelaxing.store')

from services.meta_organic_service import publish_facebook_photo

async def main():
    image_url = "https://mathrelaxing.store/static/previews/aizawa-copper.jpg"
    message = "✨ ¡Prueba de automatización exitosa! El sistema de MathRelaxing ahora puede publicar directamente en la página. ✨\n\nDescubre la colección Aizawa Copper en mathrelaxing.store"
    
    try:
        print("Iniciando publicación en Facebook...")
        post_id = await publish_facebook_photo(image_url, message)
        print(f"\n✅ ¡ÉXITO! El post se ha publicado correctamente.")
        print(f"ID del Post en Facebook: {post_id}")
        print("Ve a revisar tu página de Facebook para verlo en vivo.")
    except Exception as e:
        print(f"\n❌ ERROR AL PUBLICAR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
