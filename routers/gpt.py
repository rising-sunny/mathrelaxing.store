"""GPT-facing API endpoints for MathRelaxing digital product discovery and preview generation."""

import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from models.product import DigitalProduct

router = APIRouter()

PRODUCT_TYPE_LABELS = {
    "image_pack": "Image Pack",
    "animation_pack": "Animation / Loop Pack",
    "creator_assets": "Creator Assets",
    "thematic_bundle": "Thematic Bundle",
}


@router.get("/gpt/products")
def list_products(
    collection: str | None = Query(None, description="Filter by collection slug"),
    product_type: str | None = Query(None, description="Filter by product type"),
    db: Session = Depends(get_db),
):
    """List all digital products with metadata. Used by GPT to browse catalog."""
    q = db.query(DigitalProduct).filter(DigitalProduct.active == True)
    if collection:
        q = q.filter(DigitalProduct.collection == collection)
    if product_type:
        q = q.filter(DigitalProduct.product_type == product_type)

    products = q.all()
    return {
        "products": [
            {
                "slug": p.slug,
                "name": p.name,
                "type": PRODUCT_TYPE_LABELS.get(p.product_type, p.product_type),
                "collection": p.collection,
                "equation_type": p.equation_type,
                "description": p.description,
                "price_usd": p.price_usd,
                "license_type": p.license_type,
                "file_size": p.file_size,
                "contents": json.loads(p.contents_json) if p.contents_json else [],
                "cover_image": p.cover_image,
                "store_url": f"https://mathrelaxing.store/bundle/{p.slug}",
                "preview_url": f"https://mathrelaxing.store/api/render/preview?product={p.slug}",
            }
            for p in products
        ],
        "total": len(products),
    }


@router.get("/gpt/collections")
def list_collections(db: Session = Depends(get_db)):
    """List all collections with sample previews."""
    from main import COLLECTIONS

    result = []
    for slug, info in COLLECTIONS.items():
        sample = (
            db.query(DigitalProduct)
            .filter(DigitalProduct.collection == slug, DigitalProduct.active == True)
            .first()
        )
        result.append(
            {
                "slug": slug,
                "name": info.get("name", slug),
                "description": info.get("description", ""),
                "equation": info.get("equation", ""),
                "product_count": db.query(DigitalProduct)
                .filter(DigitalProduct.collection == slug, DigitalProduct.active == True)
                .count(),
                "sample_preview": (
                    f"https://mathrelaxing.store/api/render/preview?product={sample.slug}"
                    if sample
                    else None
                ),
                "store_url": f"https://mathrelaxing.store/collection/{slug}",
            }
        )
    return {"collections": result, "total": len(result)}


@router.get("/gpt/preview")
def generate_preview(
    product: str = Query(..., description="Product slug to generate preview for"),
    ref: str = Query("gpt", description="Referral source"),
    db: Session = Depends(get_db),
):
    """Generate a preview image URL and store link for a given product.
    Returns watermarked/low-res preview. Full resolution only in purchased bundle."""
    p = db.query(DigitalProduct).filter(
        DigitalProduct.slug == product,
        DigitalProduct.active == True,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")

    return {
        "product_slug": p.slug,
        "product_name": p.name,
        "product_type": PRODUCT_TYPE_LABELS.get(p.product_type, p.product_type),
        "description": p.description,
        "price_usd": p.price_usd,
        "preview_url": f"https://mathrelaxing.store/api/render/preview?product={p.slug}&ref={ref}",
        "store_url": f"https://mathrelaxing.store/bundle/{p.slug}?ref={ref}",
        "message": (
            f"Here's a preview of '{p.name}' — a {PRODUCT_TYPE_LABELS.get(p.product_type, p.product_type)} "
            f"for ${p.price_usd:.0f}. Visit the store to purchase the full high-resolution bundle."
        ),
    }


@router.post("/gpt/generate")
def generate_custom_preview(
    equation_type: str = Query(..., description="Equation type (e.g. lorenz, julia, clifford)"),
    params: dict | None = None,
    ref: str = Query("gpt", description="Referral source"),
    db: Session = Depends(get_db),
):
    """Generate a custom preview from equation parameters and return a link to the
    most relevant bundle on the store."""
    # Find the most relevant product for this equation type
    product = (
        db.query(DigitalProduct)
        .filter(
            DigitalProduct.equation_type == equation_type,
            DigitalProduct.active == True,
        )
        .first()
    )

    # Fallback: find any product in a matching collection
    if not product:
        collection_map = {
            "lorenz": "strange-attractors",
            "clifford": "strange-attractors",
            "aizawa": "strange-attractors",
            "de_jong": "de-jong-attractors",
            "julia": "fractal-series",
            "mandelbrot": "fractal-series",
            "superformula": "radial-symmetry",
            "rose": "radial-symmetry",
            "gray-scott": "reaction-diffusion",
            "mobius-grid": "complex-plane-geometry",
            "joukowski": "complex-plane-geometry",
            "turing": "turing-patterns",
            "voronoi": "voronoi-organics",
            "chladni": "chladni-figures",
        }
        collection = collection_map.get(equation_type)
        if collection:
            product = (
                db.query(DigitalProduct)
                .filter(DigitalProduct.collection == collection, DigitalProduct.active == True)
                .first()
            )

    # Build preview URL with custom params
    preview_params = ""
    if params:
        param_parts = "&".join(f"{k}={v}" for k, v in params.items())
        preview_params = f"&{param_parts}"

    preview_url = f"https://mathrelaxing.store/api/render/preview?eq={equation_type}{preview_params}&ref={ref}"

    if product:
        return {
            "preview_url": preview_url,
            "product_slug": product.slug,
            "product_name": product.name,
            "product_type": PRODUCT_TYPE_LABELS.get(product.product_type, product.product_type),
            "price_usd": product.price_usd,
            "store_url": f"https://mathrelaxing.store/bundle/{product.slug}?ref={ref}",
            "message": (
                f"I've generated a preview using the {equation_type} system. "
                f"The full high-resolution bundle '{product.name}' is available for ${product.price_usd:.0f}."
            ),
        }
    else:
        return {
            "preview_url": preview_url,
            "store_url": f"https://mathrelaxing.store?ref={ref}",
            "message": (
                f"I've generated a preview using the {equation_type} system. "
                f"Visit MathRelaxing.store to browse our full collection of digital math art bundles."
            ),
        }
