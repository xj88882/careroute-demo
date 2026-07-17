"""SQLAlchemy Models — 13 core tables."""
import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Date, DateTime,
    Text, ForeignKey, UniqueConstraint, Index, Numeric, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ===================== CUSTOMERS =====================
class Customer(Base):
    __tablename__ = "customers"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    full_name = Column(String(200), nullable=False)
    nationality = Column(String(3), nullable=False)  # ISO 3166-1 alpha-3
    passport_number = Column(String(200), nullable=False)  # AES-256 encrypted at app layer
    date_of_birth = Column(Date, nullable=True)
    email = Column(String(200), nullable=False)
    phone = Column(String(30), nullable=True)
    preferred_language = Column(String(10), default="en")
    dietary_restrictions = Column(Text, nullable=True)
    cultural_notes = Column(Text, nullable=True)
    medical_history = Column(Text, nullable=True)  # AES-256 encrypted
    allergies = Column(Text, nullable=True)
    channel_source = Column(String(50), nullable=True)
    channel_touch_at = Column(DateTime(timezone=True), nullable=True)
    data_retention_until = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    orders = relationship("Order", back_populates="customer")
    reviews = relationship("Review", back_populates="customer")

    __table_args__ = (
        Index("idx_customer_channel", "channel_source"),
        Index("idx_customer_nationality", "nationality"),
    )


# ===================== PROVIDERS =====================
class Provider(Base):
    __tablename__ = "providers"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(300), nullable=False)
    name_en = Column(String(300), nullable=False)
    type = Column(String(20), nullable=False)  # physical_exam / dental / aesthetic / ophthalmology
    ownership = Column(String(20), nullable=False)  # public / private
    license_no = Column(String(100), unique=True, nullable=False)
    address = Column(Text, nullable=True)
    city = Column(String(50), nullable=False)
    contact_name = Column(String(100), nullable=True)
    contact_phone = Column(String(30), nullable=True)
    contact_email = Column(String(200), nullable=True)
    api_key = Column(String(64), unique=True, nullable=True)
    api_endpoint = Column(String(500), nullable=True)
    integration_mode = Column(String(20), default="api_inbound")  # api_inbound / api_outbound / hybrid
    jci_certified = Column(Boolean, default=False)
    status = Column(String(20), default="active")  # active / suspended / terminated
    contract_signed_at = Column(Date, nullable=True)
    contract_expires_at = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    services = relationship("ProviderService", back_populates="provider")
    orders = relationship("Order", back_populates="provider")

    __table_args__ = (
        Index("idx_provider_type_city", "type", "city"),
    )


# ===================== PROVIDER SERVICES =====================
class ProviderService(Base):
    __tablename__ = "provider_services"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    provider_id = Column(UUID(as_uuid=False), ForeignKey("providers.id"), nullable=False)
    service_code = Column(String(50), nullable=False)
    service_name = Column(String(300), nullable=False)
    service_name_en = Column(String(300), nullable=False)
    category = Column(String(50), nullable=True)
    settlement_price = Column(Numeric(12, 2), nullable=False)  # 底价
    suggested_retail_min = Column(Numeric(12, 2), nullable=True)
    suggested_retail_max = Column(Numeric(12, 2), nullable=True)
    premium_cap_pct = Column(Numeric(5, 2), nullable=True)  # 公立医院 <=30, 私立 NULL
    unit = Column(String(20), default="per_time")
    duration_minutes = Column(Integer, nullable=True)
    is_addon_candidate = Column(Boolean, default=False)
    addon_price_range = Column(String(100), nullable=True)
    requires_consent = Column(Boolean, default=False)
    vat_applicable = Column(Boolean, default=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    provider = relationship("Provider", back_populates="services")

    __table_args__ = (
        UniqueConstraint("provider_id", "service_code", name="uq_provider_service"),
    )


# ===================== PACKAGES =====================
class Package(Base):
    __tablename__ = "packages"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(300), nullable=False)
    name_en = Column(String(300), nullable=False)
    type = Column(String(20), nullable=False)  # physical_exam / dental
    tier = Column(String(5), nullable=False)  # L1 / L2 / L3
    description_en = Column(Text, nullable=True)
    consumer_price_min = Column(Numeric(12, 2), nullable=False)
    consumer_price_max = Column(Numeric(12, 2), nullable=False)
    us_comparison_price = Column(String(100), nullable=True)
    savings_pct = Column(Integer, nullable=True)
    image_url = Column(String(500), nullable=True)
    sort_order = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    warranty_months = Column(Integer, nullable=True)
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items = relationship("PackageItem", back_populates="package")

    __table_args__ = (Index("idx_package_type_tier", "type", "tier"),)


class PackageItem(Base):
    __tablename__ = "package_items"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    package_id = Column(UUID(as_uuid=False), ForeignKey("packages.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=False), ForeignKey("providers.id"), nullable=False)
    service_code = Column(String(50), nullable=False)
    is_optional = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)

    package = relationship("Package", back_populates="items")


# ===================== ORDERS =====================
class Order(Base):
    __tablename__ = "orders"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    order_no = Column(String(30), unique=True, nullable=False)
    customer_id = Column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    package_id = Column(UUID(as_uuid=False), ForeignKey("packages.id"), nullable=True)
    provider_id = Column(UUID(as_uuid=False), ForeignKey("providers.id"), nullable=True)
    channel = Column(String(50), nullable=True)  # cits / direct / referral
    channel_ref = Column(String(100), nullable=True)
    status = Column(String(20), default="confirmed")  # confirmed/in_progress/completed/cancelled/disputed
    consumer_total_price = Column(Numeric(12, 2), default=0)
    settlement_total_price = Column(Numeric(12, 2), default=0)
    premium_total = Column(Numeric(12, 2), default=0)
    preauth_amount = Column(Numeric(12, 2), nullable=True)
    preauth_card_last4 = Column(String(4), nullable=True)
    preauth_id = Column(String(100), nullable=True)
    total_charged = Column(Numeric(12, 2), default=0)
    total_released = Column(Numeric(12, 2), default=0)
    service_date = Column(Date, nullable=True)
    medical_report_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    customer = relationship("Customer", back_populates="orders")
    provider = relationship("Provider", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
    stages = relationship("OrderStage", back_populates="order")
    payments = relationship("PaymentRecord", back_populates="order")

    __table_args__ = (
        Index("idx_order_customer", "customer_id"),
        Index("idx_order_status", "status"),
        Index("idx_order_channel", "channel"),
        Index("idx_order_created", "created_at"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    order_id = Column(UUID(as_uuid=False), ForeignKey("orders.id"), nullable=False)
    service_code = Column(String(50), nullable=False)
    service_name_en = Column(String(300), nullable=False)
    settlement_price = Column(Numeric(12, 2), nullable=False)
    consumer_price = Column(Numeric(12, 2), nullable=False)
    is_addon = Column(Boolean, default=False)
    addon_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    addon_performed_at = Column(DateTime(timezone=True), nullable=True)
    addon_status = Column(String(20), nullable=True)  # confirmed / cancelled / performed

    order = relationship("Order", back_populates="items")


class OrderStage(Base):
    __tablename__ = "order_stages"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    order_id = Column(UUID(as_uuid=False), ForeignKey("orders.id"), nullable=False)
    stage_no = Column(Integer, nullable=False)
    stage_name = Column(String(200), nullable=False)
    planned_date = Column(Date, nullable=True)
    actual_date = Column(Date, nullable=True)
    settlement_amount = Column(Numeric(12, 2), default=0)
    consumer_amount = Column(Numeric(12, 2), default=0)
    is_authorized = Column(Boolean, default=False)
    authorized_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="pending")

    order = relationship("Order", back_populates="stages")


# ===================== PAYMENTS =====================
class PaymentRecord(Base):
    __tablename__ = "payment_records"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    order_id = Column(UUID(as_uuid=False), ForeignKey("orders.id"), nullable=False)
    type = Column(String(20), nullable=False)  # preauth_freeze / preauth_capture / preauth_release / refund
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="CNY")
    unionpay_ref = Column(String(100), nullable=True)
    visa_auth_code = Column(String(20), nullable=True)
    status = Column(String(20), default="pending")
    triggered_by = Column(String(50), nullable=True)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="payments")


# ===================== SETTLEMENTS =====================
class Settlement(Base):
    __tablename__ = "settlements"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    provider_id = Column(UUID(as_uuid=False), ForeignKey("providers.id"), nullable=False)
    total_settlement = Column(Numeric(12, 2), default=0)
    total_premium = Column(Numeric(12, 2), default=0)
    total_netsettle = Column(Numeric(12, 2), default=0)
    status = Column(String(20), default="draft")  # draft / confirmed / paid
    invoice_no = Column(String(100), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ===================== REVIEWS =====================
class Review(Base):
    __tablename__ = "reviews"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    order_id = Column(UUID(as_uuid=False), ForeignKey("orders.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    package_id = Column(UUID(as_uuid=False), ForeignKey("packages.id"), nullable=False)
    rating_overall = Column(Integer, nullable=False)
    rating_staff = Column(Integer, nullable=False)
    rating_english = Column(Integer, nullable=False)
    rating_wait_time = Column(Integer, nullable=False)
    rating_report = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer", back_populates="reviews")


# ===================== ADMIN USERS =====================
class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    display_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)  # super_admin / ops / finance / product / analyst
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ===================== CITS INVENTORY (synced) =====================
class CitsFlight(Base):
    __tablename__ = "cits_flights"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    flight_no = Column(String(20), nullable=False)
    airline = Column(String(100), nullable=False)
    departure_city = Column(String(5), nullable=False)
    arrival_city = Column(String(5), nullable=False)
    departure_date = Column(Date, nullable=False)
    cabin_class = Column(String(20), nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    service_fee = Column(Numeric(12, 2), nullable=False)  # for CPS calculation
    available_seats = Column(Integer, default=0)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())


class CitsHotel(Base):
    __tablename__ = "cits_hotels"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(300), nullable=False)
    name_en = Column(String(300), nullable=False)
    city = Column(String(50), nullable=False)
    stars = Column(Integer, default=4)
    room_type = Column(String(100), nullable=False)
    price_per_night = Column(Numeric(12, 2), nullable=False)
    is_medical_pool = Column(Boolean, default=False)
    distance_to_provider = Column(Float, nullable=True)
    available_rooms = Column(Integer, default=0)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
