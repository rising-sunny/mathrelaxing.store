import sys, asyncio
sys.path.append('/var/www/mathrelaxing.store')
from services import paypal as paypal_svc

async def test():
    try:
        url, paypal_id = await paypal_svc.create_digital_order(
            purchase_id=99999,
            product_name="TEST - STEM Focus Planner",
            amount_usd=2.99,
        )
        print(f"SUCCESS: PayPal checkout URL = {url}")
        print(f"paypal_order_id = {paypal_id}")
    except Exception as e:
        print(f"ERROR: {e}")

asyncio.run(test())
