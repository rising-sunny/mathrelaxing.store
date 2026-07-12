from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from models.product import Base


class TikTokPost(Base):
    __tablename__ = "tiktok_posts"

    id = Column(Integer, primary_key=True, index=True)
    product_slug = Column(String(100), nullable=False)
    video_url = Column(String(500), nullable=False)
    publish_id = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, published, failed
    caption = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text, nullable=True)
