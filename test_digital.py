import asyncio
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal
from models.product import Purchase, DigitalProduct
from services import email

async def run():
    db = SessionLocal()

    # Find the fractal flora ipad coloring digital product
    product = db.query(DigitalProduct).filter(DigitalProduct.slug == "fractal-flora-ipad-coloring").first()
    if not product:
        product = db.query(DigitalProduct).filter(DigitalProduct.active == True).first()
        
    if not product:
        print("ERROR: no active digital product found in DB")
        return

    # Create a persistent test purchase so the user can test the download
    test_uuid = str(uuid.uuid4())
    purchase = Purchase(
        lemon_order_id=f"TEST-LEMON-{test_uuid[:8]}",
        product_id=product.id,
        customer_email="estebannavarro.rojo@gmail.com",
        customer_name="Esteban Navarro",
        download_token=test_uuid,
        max_downloads=3,
        status="paid"
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    print(f"Test digital purchase created: #{purchase.id} for {product.name}")
    print(f"Sending confirmation email to {purchase.customer_email}...")
    
    await email.send_digital_purchase_email(purchase, product)
    print("Email: sent (check inbox / Resend dashboard)")
    
    # Intentionally NOT deleting the purchase from the DB so the download link works
    print(f"Test purchase remains in DB so the download link works. Token: {purchase.download_token}")
    db.close()

if __name__ == "__main__":
    asyncio.run(run())
