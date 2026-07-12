from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from .product import Base


class PinterestPin(Base):
    """Record of pins created automatically by the auto-pinning job.
    Used to avoid re-pinning the same product+variant too frequently and
    to track what's live on Pinterest."""
    __tablename__ = "pinterest_pins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_slug = Column(String(120), nullable=False, index=True)
    product_type = Column(String(20), nullable=True, index=True)  # 'digital' | 'physical'
    variant_idx = Column(Integer, nullable=False, default=0)
    board_id = Column(String(60), nullable=True)
    pin_id = Column(String(60), nullable=True, index=True)  # Pinterest's returned pin id
    image_url = Column(String(500), nullable=True)
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    link_url = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active, failed, deleted
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


Index("ix_pinterest_pins_product_variant", PinterestPin.product_slug, PinterestPin.variant_idx)
