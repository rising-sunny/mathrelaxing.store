import sys
sys.path.insert(0, '/var/www/mathrelaxing.store')

from database import SessionLocal
from models.product import Product

def create_exclusive_notebooks():
    db = SessionLocal()
    try:
        # Delete old notebooks if any
        db.query(Product).filter(Product.collection == 'notebooks').delete()
        
        # 1. Fibonacci
        fibo = Product(
            slug="fibonacci-gold-notebook",
            name="Fibonacci Gold",
            collection="notebooks",
            equation_type="superformula", # We can use superformula tuned to a spiral
            description="Elegant golden logarithmic spiral notebook.",
            params_json='{"m": {"value": 1.0}, "n1": {"value": 1.0}, "n2": {"value": 1.0}, "n3": {"value": 1.0}, "turns": {"value": 15.0}, "wave_freq": {"value": 0.0}, "zoom": {"value": 1.0}, "cx": {"value": 0.0}, "cy": {"value": 0.0}, "color_start": {"value": "#c8a96e"}, "color_end": {"value": "#e8e4dc"}, "background_color": {"value": "#0a0a0a"}}',
            price_usd=24.99,
            image_url="https://mathrelaxing.store/api/render/preview?product=fibonacci-gold-notebook",
            active=True
        )
        
        # 2. Poincare
        poincare = Product(
            slug="poincare-abyss-notebook",
            name="Poincaré Abyss",
            collection="notebooks",
            equation_type="kleinian-inversion",
            description="Deep indigo and cyan Kleinian inversion circle packing.",
            params_json='{"depth": {"value": 6}, "a_re": {"value": 1.0}, "a_im": {"value": 0.0}, "b_re": {"value": 0.0}, "b_im": {"value": 0.0}, "c_re": {"value": 0.0}, "c_im": {"value": 1.0}, "d_re": {"value": 1.0}, "d_im": {"value": 0.0}, "color_start": {"value": "#06b6d4"}, "color_end": {"value": "#1e3a8a"}, "background_color": {"value": "#050505"}}',
            price_usd=24.99,
            image_url="https://mathrelaxing.store/api/render/preview?product=poincare-abyss-notebook",
            active=True
        )
        
        # 3. Aizawa
        aizawa = Product(
            slug="aizawa-copper-notebook",
            name="Aizawa Monolith",
            collection="notebooks",
            equation_type="aizawa",
            description="Electrifying copper and orange strange attractor monolith.",
            params_json='{"a": {"value": 0.95}, "b": {"value": 0.7}, "c": {"value": 0.6}, "d": {"value": 3.5}, "e": {"value": 0.25}, "f": {"value": 0.1}, "color_start": {"value": "#d97706"}, "color_end": {"value": "#ea580c"}, "background_color": {"value": "#000000"}}',
            price_usd=24.99,
            image_url="https://mathrelaxing.store/api/render/preview?product=aizawa-copper-notebook",
            active=True
        )
        
        db.add(fibo)
        db.add(poincare)
        db.add(aizawa)
        
        db.commit()
        print("Exclusive notebooks created!")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_exclusive_notebooks()
