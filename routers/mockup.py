from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import Response, JSONResponse
import io
import json
from typing import Optional

router = APIRouter()


@router.get("/mockup/gallery")
async def mockup_gallery(
    product: Optional[str] = Query(None, description="Product slug to preview")
):
    """Lista los tipos de mockups disponibles."""
    from services.mockup_compositor import verify_mockups_exist, PRODUCT_CONFIGS
    
    available = verify_mockups_exist()
    
    formats = []
    for fmt_id, config in PRODUCT_CONFIGS.items():
        # Verificar si tenemos al menos un mockup para este formato
        has_mockups = any(
            available.get(fmt_id, {}).get(k, {}).get("exists", False)
            for k in config["files"].keys()
        )
        
        formats.append({
            "id": fmt_id,
            "name": config["name"],
            "size": config["size"],
            "available": has_mockups,
            "mockup_types": list(config["files"].keys()),
            "preview_url": f"/api/mockup?product={product or 'lorenz-classic'}&format={fmt_id}&type=wall_scene" if has_mockups else None
        })
    
    return {
        "formats": formats,
        "product": product,
        "note": "Las imágenes de mockup deben subirse a /static/mockups/gelato-canvas/"
    }


@router.get("/mockup")
async def get_mockup(
    product: str = Query(..., description="Product slug (ej: lorenz-classic)"),
    format: str = Query("canvas", description="Formato: canvas"),
    type: str = Query("wall_scene", description="Tipo: wall_scene, 3d_view, detail, edge, back"),
    width: int = Query(1200, description="Ancho del artwork generado")
):
    """
    Genera un mockup real combinando el arte matemático con fotos reales de Gelato.
    
    Tipos disponibles:
    - wall_scene: Canvas en pared de ladrillo (ambiente)
    - 3d_view: Vista 3D angular del canvas
    - detail: Detalle de textura
    - edge: Detalle de borde/esquina
    - back: Vista trasera con sistema de montaje
    """
    from services.renderer import render_equation
    from services.mockup_compositor import (
        create_wall_mockup, 
        create_3d_mockup,
        create_detail_mockup,
        verify_mockups_exist
    )
    from database import SessionLocal
    from models.product import Product
    
    # Verificar disponibilidad de mockups
    available = verify_mockups_exist()
    if not available.get(format, {}).get("files", {}).get(type, {}).get("exists", False):
        raise HTTPException(
            status_code=404, 
            detail=f"Mockup no disponible. Sube la imagen a /static/mockups/gelato-canvas/{type}.jpg"
        )
    
    try:
        # Obtener producto de la base de datos
        db = SessionLocal()
        try:
            prod = db.query(Product).filter(Product.slug == product).first()
            if not prod:
                raise HTTPException(status_code=404, detail=f"Producto no encontrado: {product}")
            
            params = json.loads(prod.params_json)
            equation_type = prod.equation_type
        finally:
            db.close()
        
        # Calcular dimensiones (4:5 ratio para 16x20")
        height = int(width * 1.25)
        
        # Generar artwork
        artwork_bytes = render_equation(
            equation_type=equation_type,
            params=params,
            width=width,
            height=height,
            hq=True
        )
        
        # Crear mockup según el tipo solicitado
        if type == "wall_scene":
            mockup_bytes = create_wall_mockup(artwork_bytes, shadow=True)
        elif type == "3d_view":
            mockup_bytes = create_3d_mockup(artwork_bytes)
        elif type in ("detail", "edge", "back"):
            mockup_bytes = create_detail_mockup(artwork_bytes, detail_type=type)
        else:
            raise HTTPException(status_code=400, detail=f"Tipo de mockup desconocido: {type}")
        
        return Response(content=mockup_bytes, media_type="image/png")
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Imagen de mockup no encontrada. {str(e)}. Sube las imágenes de Gelato a /static/mockups/gelato-canvas/"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando mockup: {str(e)}")


@router.get("/mockup/status")
async def mockup_status():
    """Verifica qué imágenes de mockup están disponibles."""
    from services.mockup_compositor import verify_mockups_exist
    
    status = verify_mockups_exist()
    
    # Contar cuántos tenemos
    total = 0
    available = 0
    for product_type, files in status.items():
        for file_type, info in files.items():
            total += 1
            if info["exists"]:
                available += 1
    
    return {
        "mockups_available": f"{available}/{total}",
        "details": status,
        "upload_path": "/var/www/mathrelaxing.store/static/mockups/gelato-canvas/",
        "required_files": [
            "canvas-wall-scene.jpg - Canvas en pared (ambiente)",
            "canvas-3d-view.jpg - Vista 3D angular",
            "canvas-detail.jpg - Detalle de textura",
            "canvas-edge.jpg - Detalle de borde",
            "canvas-back.jpg - Vista trasera con montaje"
        ]
    }
