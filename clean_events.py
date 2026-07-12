import asyncio
import sys

sys.path.insert(0, ".")
from database import SessionLocal
from models.live import LiveEvent

def run():
    db = SessionLocal()

    # Find the live events for the test purchases
    events = db.query(LiveEvent).filter(LiveEvent.event_type == "purchase").order_by(LiveEvent.id.desc()).limit(5).all()
    
    deleted_count = 0
    for ev in events:
        if ev.path == "/srv/paypal_legacy" or "TEST" in (ev.session_id or ""):
            print(f"Deleting test event: {ev.event_type} {ev.path} ({ev.session_id})")
            db.delete(ev)
            deleted_count += 1
            
    if deleted_count > 0:
        db.commit()
        print(f"Deleted {deleted_count} test events from LiveEvent table.")
    else:
        print("No test live events found to delete.")

    db.close()

if __name__ == "__main__":
    run()
