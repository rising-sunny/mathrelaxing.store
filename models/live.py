from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text

from .product import Base


class LiveEvent(Base):
    __tablename__ = "live_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(40), nullable=False, index=True)
    path = Column(String(500), nullable=True)
    referrer_domain = Column(String(200), nullable=True)
    country = Column(String(2), nullable=True)
    country_name = Column(String(80), nullable=True)
    city = Column(String(120), nullable=True)
    ua_class = Column(String(20), nullable=True)
    product_slug = Column(String(120), nullable=True)
    value_usd = Column(Float, nullable=True)
    ip_hash = Column(String(16), nullable=True)
    source = Column(String(60), nullable=True, index=True)
    medium = Column(String(40), nullable=True)
    campaign = Column(String(120), nullable=True, index=True)
    payload = Column(Text, nullable=True)


Index("ix_live_events_session_ts", LiveEvent.session_id, LiveEvent.ts)
