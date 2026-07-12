from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from .product import Base


class PinterestBoard(Base):
    """Maps a product collection slug to its Pinterest board id.
    Boards are auto-created on first use by the auto-pinner."""
    __tablename__ = "pinterest_boards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_slug = Column(String(120), nullable=False, unique=True, index=True)
    board_id = Column(String(60), nullable=False)
    board_name = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
