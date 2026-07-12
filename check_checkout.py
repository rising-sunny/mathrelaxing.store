import sys
sys.path.insert(0, ".")
from database import SessionLocal
from models.live import LiveEvent

def run():
    db = SessionLocal()

    events = db.query(LiveEvent).filter(LiveEvent.event_type == "checkout_start").order_by(LiveEvent.id.desc()).limit(3).all()
    
    if not events:
        print("No checkout_start events found.")
    
    for ev in events:
        print(f"Path: {ev.path}")
        print(f"UA Class: {ev.ua_class}")
        print(f"Medium: {ev.medium}")
        print(f"Source: {ev.source}")
        print(f"Product: {ev.product_slug}")
        print(f"Payload: {ev.payload}")
        print("-" * 40)

    db.close()

if __name__ == "__main__":
    run()
