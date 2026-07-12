import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


# ── Legacy (kept for migration compat, no longer used in active flow) ──────

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    collection = Column(String, nullable=False, index=True)
    equation_type = Column(String, nullable=False)
    description = Column(Text)
    params_json = Column(Text, nullable=False)
    price_usd = Column(Float, nullable=False)
    image_url = Column(String)
    background_color = Column(String, default="#080808")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    lemon_order_id = Column(String, unique=True, index=True)
    paypal_order_id = Column(String, unique=True, index=True)
    product_id = Column(Integer, nullable=False)
    product_slug = Column(String, nullable=False)
    params_json = Column(Text, nullable=False)
    format_id = Column(String, default="digital")
    customer_email = Column(String)
    customer_name = Column(String)
    shipping_address = Column(Text)
    status = Column(String, default="pending")  # pending, paid, delivered
    printful_order_id = Column(String)
    created_at = Column(DateTime, server_default=func.now())


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, nullable=False, index=True)
    edition_number = Column(Integer, nullable=False)
    params_json = Column(Text, nullable=False)
    generated_at = Column(DateTime, server_default=func.now())
    qr_url = Column(String)


# ── Digital Product Models ─────────────────────────────────────────────────

class DigitalProduct(Base):
    __tablename__ = "digital_products"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    product_type = Column(String, nullable=False)  # image_pack | animation_pack | creator_assets | thematic_bundle
    collection = Column(String, nullable=False, index=True)
    equation_type = Column(String, nullable=False)
    description = Column(Text)
    price_usd = Column(Float, nullable=False)
    contents_json = Column(Text, nullable=False)  # JSON: [{title, item_type, description, resolution, duration_secs}]
    cover_image = Column(String)  # URL or path to cover image
    thumbnail_url = Column(String)  # URL for card thumbnails
    file_url = Column(String)  # S3/local path to downloadable ZIP/MP4
    file_size = Column(String)  # e.g. "245 MB"
    license_type = Column(String, default="personal")  # personal | commercial
    lemon_variant_id = Column(String)  # LemonSqueezy variant ID
    whop_product_id  = Column(String, nullable=True, index=True)
    whop_plan_id     = Column(String, nullable=True, index=True)
    whop_checkout_url = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    lemon_order_id = Column(String, unique=True, index=True)
    product_id = Column(Integer, ForeignKey("digital_products.id"), nullable=False)
    customer_email = Column(String, nullable=False)
    customer_name = Column(String)
    download_token = Column(String, unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    download_count = Column(Integer, default=0)
    max_downloads = Column(Integer, default=3)
    status = Column(String, default="pending")  # pending | paid | delivered | expired
    ref_source = Column(String)  # gpt | direct | social
    item_index = Column(Integer, nullable=True)  # null = full bundle, int = single image
    paypal_order_id = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Coupon(Base):
    __tablename__ = "coupons"
    id           = Column(Integer, primary_key=True, index=True)
    code         = Column(String, unique=True, index=True, nullable=False)
    discount_pct = Column(Float, default=0.0)    # e.g. 20 = 20% off
    discount_fixed = Column(Float, default=0.0)  # e.g. 5 = $5 off
    max_uses     = Column(Integer, nullable=True) # None = unlimited
    used_count   = Column(Integer, default=0)
    active       = Column(Boolean, default=True)
    expires_at   = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)


class LowPolyJob(Base):
    __tablename__ = "lowpoly_jobs"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    lemon_order_id = Column(String, unique=True, index=True, nullable=True)
    customer_email = Column(String, nullable=False)
    customer_name = Column(String, default="")
    params_json = Column(Text, nullable=False)
    coloring_url = Column(String, nullable=False)
    colored_url = Column(String, nullable=False)
    extra_files_json = Column(Text, nullable=True)
    pack_size = Column(Integer, default=1)
    status = Column(String, default="pending")  # pending | paid | expired
    created_at = Column(DateTime, server_default=func.now())


class LowPolyCredit(Base):
    """One-time use credit purchased via Whop. Token is emailed; user redeems on /lowpoly/credit/{token}."""
    __tablename__ = "lowpoly_credits"

    id           = Column(Integer, primary_key=True, index=True)
    token        = Column(String, unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    whop_id      = Column(String, nullable=True, index=True)   # whop payment/membership id
    customer_email = Column(String, nullable=False)
    customer_name  = Column(String, default="")
    pack_size    = Column(Integer, default=1)                   # credits purchased (1 or 5)
    used_count   = Column(Integer, default=0)                   # how many have been redeemed
    status       = Column(String, default="unused")             # unused | partial | exhausted
    created_at   = Column(DateTime, server_default=func.now())
    used_at      = Column(DateTime, nullable=True)
