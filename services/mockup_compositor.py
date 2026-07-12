"""
Compositor de mockups usando imágenes reales de Gelato.
Combina las generaciones matemáticas con fotos reales de productos.
"""

import io
import json
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter

# Paths
BASE_DIR = Path(__file__).parent.parent
MOCKUP_DIR = BASE_DIR / "static" / "mockups"

# Configuración de productos disponibles
PRODUCT_CONFIGS = {
    "canvas": {
        "name": "Gallery Canvas",
        "size": "16×20 inch",
        "aspect_ratio": 0.8,  # width/height = 4/5
        "files": {
            "wall_scene": MOCKUP_DIR / "gelato-canvas" / "canvas-wall-scene.jpg",
            "3d_view": MOCKUP_DIR / "gelato-canvas" / "canvas-3d-view.jpg",
            "detail": MOCKUP_DIR / "gelato-canvas" / "canvas-detail.jpg",
            "edge": MOCKUP_DIR / "gelato-canvas" / "canvas-edge.jpg",
            "back": MOCKUP_DIR / "gelato-canvas" / "canvas-back.jpg",
        },
        # Coordenadas donde insertar el arte en cada mockup (left, top, right, bottom)
        "art_regions": {
            "wall_scene": (380, 230, 580, 480),  # Aproximado para la imagen de pared
            "3d_view": (150, 80, 450, 480),     # Aproximado para vista 3D
        }
    }
}


def get_mockup_path(format_id: str, mockup_type: str = "wall_scene") -> Optional[Path]:
    """Obtiene la ruta de un mockup específico."""
    config = PRODUCT_CONFIGS.get(format_id)
    if not config:
        return None
    return config["files"].get(mockup_type)


def create_wall_mockup(
    artwork_bytes: bytes,
    product_type: str = "canvas",
    shadow: bool = True
) -> bytes:
    """
    Crea un mockup con la imagen en una pared (escena de ambiente).
    
    Args:
        artwork_bytes: Bytes de la imagen matemática generada
        product_type: Tipo de producto ('canvas', 'framed', 'acrylic')
        shadow: Si aplicar sombra realista
    
    Returns:
        Bytes de la imagen compuesta
    """
    from PIL import Image, ImageEnhance
    
    # Cargar escena de pared
    wall_path = MOCKUP_DIR / "gelato-canvas" / "canvas-wall-scene.jpg"
    if not wall_path.exists():
        raise FileNotFoundError(f"Mockup no encontrado: {wall_path}")
    
    scene = Image.open(wall_path).convert("RGBA")
    
    # Cargar artwork
    artwork = Image.open(io.BytesIO(artwork_bytes)).convert("RGBA")
    
    # Dimensiones objetivo basadas en la región definida
    art_region = PRODUCT_CONFIGS["canvas"]["art_regions"]["wall_scene"]
    target_width = art_region[2] - art_region[0]
    target_height = art_region[3] - art_region[1]
    
    # Redimensionar artwork manteniendo proporción
    artwork_resized = _resize_to_fit(artwork, target_width, target_height)
    
    # Crear capa para el artwork con perspectiva si es necesario
    # Para la pared plana, no necesitamos transformación de perspectiva compleja
    
    # Posición centrada en la región
    art_w, art_h = artwork_resized.size
    x = art_region[0] + (target_width - art_w) // 2
    y = art_region[1] + (target_height - art_h) // 2
    
    # Aplicar sombra sutil si se solicita
    if shadow:
        shadow_layer = _create_drop_shadow(art_w, art_h, offset=(8, 8), blur=15)
        scene.paste(shadow_layer, (x + 5, y + 5), shadow_layer)
    
    # Pegar artwork
    scene.paste(artwork_resized, (x, y), artwork_resized)
    
    # Guardar resultado
    output = io.BytesIO()
    scene.save(output, format="PNG", quality=95)
    return output.getvalue()


def create_3d_mockup(
    artwork_bytes: bytes,
    angle: str = "left"
) -> bytes:
    """
    Crea un mockup 3D del canvas con ángulo.
    
    Args:
        artwork_bytes: Bytes de la imagen matemática
        angle: Ángulo de vista ('left', 'right', 'front')
    
    Returns:
        Bytes de imagen compuesta
    """
    view_3d_path = MOCKUP_DIR / "gelato-canvas" / "canvas-3d-view.jpg"
    if not view_3d_path.exists():
        raise FileNotFoundError(f"Mockup 3D no encontrado: {view_3d_path}")
    
    canvas_3d = Image.open(view_3d_path).convert("RGBA")
    artwork = Image.open(io.BytesIO(artwork_bytes)).convert("RGBA")
    
    # Región del canvas en la imagen 3D
    art_region = PRODUCT_CONFIGS["canvas"]["art_regions"]["3d_view"]
    target_width = art_region[2] - art_region[0]
    target_height = art_region[3] - art_region[1]
    
    # Redimensionar
    artwork_resized = _resize_to_fit(artwork, target_width, target_height)
    
    # Para la vista 3D, necesitamos aplicar una transformación de perspectiva
    # simplificada para que el arte siga la forma del canvas
    
    # Calcular posición
    art_w, art_h = artwork_resized.size
    x = art_region[0] + (target_width - art_w) // 2
    y = art_region[1] + (target_height - art_h) // 2
    
    # Pegar con sombra del canvas
    shadow = _create_canvas_shadow(art_w, art_h)
    canvas_3d.paste(shadow, (x + 10, y + 10), shadow)
    
    # Pegar artwork
    canvas_3d.paste(artwork_resized, (x, y), artwork_resized)
    
    # Guardar
    output = io.BytesIO()
    canvas_3d.save(output, format="PNG", quality=95)
    return output.getvalue()


def create_detail_mockup(
    artwork_bytes: bytes,
    detail_type: str = "texture"
) -> bytes:
    """
    Crea un mockup enfocado en detalles (textura, edge, etc.)
    
    Args:
        artwork_bytes: Bytes de imagen matemática
        detail_type: Tipo de detalle ('texture', 'edge', 'back')
    
    Returns:
        Bytes de imagen
    """
    detail_files = {
        "texture": "canvas-detail.jpg",
        "edge": "canvas-edge.jpg",
        "back": "canvas-back.jpg"
    }
    
    filename = detail_files.get(detail_type, "canvas-detail.jpg")
    detail_path = MOCKUP_DIR / "gelato-canvas" / filename
    
    if not detail_path.exists():
        raise FileNotFoundError(f"Detalle no encontrado: {detail_path}")
    
    detail_img = Image.open(detail_path).convert("RGBA")
    
    # Para detalles, mostramos el arte en una pequeña región
    # o simplemente retornamos la imagen de detalle como referencia
    
    output = io.BytesIO()
    detail_img.save(output, format="PNG", quality=95)
    return output.getvalue()


def _resize_to_fit(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    """Redimensiona imagen manteniendo proporción para caber en el espacio dado."""
    from PIL import Image
    
    img_w, img_h = image.size
    aspect = img_w / img_h
    target_aspect = max_width / max_height
    
    if aspect > target_aspect:
        # Más ancha que alta relativa al target
        new_w = max_width
        new_h = int(new_w / aspect)
    else:
        # Más alta que ancha
        new_h = max_height
        new_w = int(new_h * aspect)
    
    return image.resize((new_w, new_h), Image.Resampling.LANCZOS)


def _create_drop_shadow(width: int, height: int, offset: tuple = (5, 5), 
                        blur: int = 10, opacity: int = 80) -> Image.Image:
    """Crea una sombra proyectada suave."""
    shadow = Image.new('RGBA', (width + blur*2, height + blur*2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    
    # Dibujar rectángulo negro semi-transparente
    draw.rectangle(
        [blur, blur, width+blur, height+blur],
        fill=(0, 0, 0, opacity)
    )
    
    # Aplicar desenfoque gaussiano
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur // 2))
    
    return shadow


def _create_canvas_shadow(width: int, height: int) -> Image.Image:
    """Crea sombra específica para canvas 3D."""
    shadow = Image.new('RGBA', (width + 30, height + 30), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    
    # Sombra más intensa en el lado derecho/inferior (luz desde arriba-izquierda)
    for i in range(20, 0, -1):
        alpha = int(40 * (1 - i/20))
        draw.rectangle(
            [10+i, 10+i, width+20-i, height+20-i],
            outline=(0, 0, 0, alpha),
            width=1
        )
    
    return shadow.filter(ImageFilter.GaussianBlur(5))


def verify_mockups_exist() -> dict:
    """Verifica qué mockups están disponibles."""
    result = {}
    
    for product_type, config in PRODUCT_CONFIGS.items():
        result[product_type] = {}
        for name, path in config["files"].items():
            result[product_type][name] = {
                "exists": path.exists(),
                "path": str(path)
            }
    
    return result
