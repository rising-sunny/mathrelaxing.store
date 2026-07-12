"""
Test script — simulates a completed purchase without PayPal or Gelato.
Run: python3 test_notification.py
Cleans up the test order/certificate from DB after running.
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal
from models.product import Certificate, Order, Product
from services import telegram, email


async def run():
    db = SessionLocal()

    product = db.query(Product).filter(Product.active == True).first()
    if not product:
        print("ERROR: no active product found in DB")
        return

    params = json.loads(product.params_json or "{}")

    order = Order(
        product_id=product.id,
        product_slug=product.slug,
        params_json=product.params_json,
        format_id="canvas",
        customer_name="Esteban Navarro",
        customer_email="estebannavarro.rojo@gmail.com",
        shipping_address=json.dumps({
            "first_name": "Esteban",
            "last_name":  "Navarro",
            "address1":   "Calle Falsa 123",
            "city":       "Santiago",
            "zip":        "8320000",
            "country":    "CL",
        }),
        status="paid",
        paypal_order_id="TEST-PAYPAL-ORDER-001",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    edition = db.query(Certificate).count() + 1
    cert = Certificate(
        order_id=order.id,
        edition_number=edition,
        params_json=order.params_json,
        qr_url=f"https://mathrelaxing.store/certificate/{order.id}",
    )
    db.add(cert)
    db.commit()

    print(f"Test order created: #{order.id}, edition #{edition}")
    print(f"Sending Telegram notification...")
    await telegram.notify_new_order(order, params, edition)
    print("Telegram: sent")

    print(f"Sending confirmation email to {order.customer_email}...")
    await email.send_order_confirmation(order, edition)
    print("Email: sent (check inbox / Resend dashboard)")

    # Cleanup
    db.delete(cert)
    db.delete(order)
    db.commit()
    db.close()
    print("Test order cleaned up from DB.")


asyncio.run(run())
