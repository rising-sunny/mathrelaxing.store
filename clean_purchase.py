import asyncio
import sys

sys.path.insert(0, ".")
from database import SessionLocal
from models.product import Purchase

def run():
    db = SessionLocal()

    # Find the purchase by customer email to be safe, or just ID 4
    purchase = db.query(Purchase).filter(Purchase.customer_email == "estebannavarro.rojo@gmail.com", Purchase.status == "paid").order_by(Purchase.id.desc()).first()
    
    if purchase:
        print(f"Found test purchase #{purchase.id}, token: {purchase.download_token}")
        db.delete(purchase)
        db.commit()
        print("Test digital purchase deleted successfully from the database.")
    else:
        print("No test purchase found to delete.")

    db.close()

if __name__ == "__main__":
    run()
