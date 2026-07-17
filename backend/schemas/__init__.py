"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


# ---- Customer ----
class CustomerCreate(BaseModel):
    full_name: str
    nationality: str
    passport_number: str
    date_of_birth: Optional[date] = None
    email: str
    phone: Optional[str] = None
    preferred_language: str = "en"

class CustomerOut(BaseModel):
    id: str
    full_name: str
    nationality: str
    email: str
    preferred_language: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ---- Order ----
class OrderCreate(BaseModel):
    package_id: str
    provider_id: Optional[str] = None
    channel: str = "direct"
    channel_ref: Optional[str] = None
    service_date: Optional[date] = None
    flight_ids: Optional[List[str]] = None
    hotel_ids: Optional[List[str]] = None

class OrderOut(BaseModel):
    id: str
    order_no: str
    customer_id: str
    package_id: Optional[str]
    provider_id: Optional[str]
    channel: Optional[str]
    status: str
    consumer_total_price: Decimal
    premium_total: Decimal
    preauth_amount: Optional[Decimal]
    created_at: datetime
    model_config = {"from_attributes": True}

class OrderDetailOut(OrderOut):
    preauth_card_last4: Optional[str]
    total_charged: Decimal
    total_released: Decimal
    service_date: Optional[date]
    completed_at: Optional[datetime]


# ---- Payment ----
class PreauthRequest(BaseModel):
    order_id: str
    card_token: str  # tokenized card for UnionPay

class PreauthResponse(BaseModel):
    preauth_id: str
    amount: Decimal
    card_last4: str
    status: str


# ---- Authorization (Provider triggers) ----
class AuthTrigger(BaseModel):
    order_id: str
    auth_type: str  # service_start / service_complete / stage_complete
    stage_no: Optional[int] = None
    actual_charge_amount: Optional[Decimal] = None


# ---- Addons ----
class AddonPropose(BaseModel):
    order_id: str
    service_code: str
    reason: str
    price: Decimal

class AddonConfirm(BaseModel):
    addon_item_id: str

class AddonCancel(BaseModel):
    addon_item_id: str


# ---- Provider ----
class ProviderOut(BaseModel):
    id: str
    name: str
    name_en: str
    type: str
    ownership: str
    city: str
    status: str
    contract_expires_at: Optional[date]
    model_config = {"from_attributes": True}


# ---- Package ----
class PackageOut(BaseModel):
    id: str
    name_en: str
    type: str
    tier: str
    description_en: Optional[str]
    consumer_price_min: Decimal
    consumer_price_max: Decimal
    us_comparison_price: Optional[str]
    savings_pct: Optional[int]
    image_url: Optional[str]
    model_config = {"from_attributes": True}


# ---- Review ----
class ReviewCreate(BaseModel):
    order_id: str
    package_id: str
    rating_overall: int = Field(ge=1, le=5)
    rating_staff: int = Field(ge=1, le=5)
    rating_english: int = Field(ge=1, le=5)
    rating_wait_time: int = Field(ge=1, le=5)
    rating_report: int = Field(ge=1, le=5)
    comment: Optional[str] = None

class ReviewOut(BaseModel):
    id: str
    customer_id: str
    package_id: str
    rating_overall: int
    rating_staff: int
    rating_english: int
    rating_wait_time: int
    rating_report: int
    comment: Optional[str]
    is_public: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ---- Settlement ----
class SettlementOut(BaseModel):
    id: str
    period_start: date
    period_end: date
    provider_id: str
    total_settlement: Decimal
    total_premium: Decimal
    total_netsettle: Decimal
    status: str
    invoice_no: Optional[str]
    model_config = {"from_attributes": True}


# ---- CITS ----
class FlightSync(BaseModel):
    flight_no: str
    airline: str
    departure_city: str
    arrival_city: str
    departure_date: date
    cabin_class: str
    price: Decimal
    service_fee: Decimal
    available_seats: int

class HotelSync(BaseModel):
    name: str
    name_en: str
    city: str
    stars: int
    room_type: str
    price_per_night: Decimal
    is_medical_pool: bool
    distance_to_provider: Optional[float] = None
    available_rooms: int


# ---- Admin Auth ----
class AdminLogin(BaseModel):
    username: str
    password: str

class AdminLoginResponse(BaseModel):
    access_token: str
    display_name: str
    role: str


# ---- Dashboard ----
class DashboardKPIs(BaseModel):
    total_revenue_mtd: Decimal
    total_orders: int
    completed_orders: int
    in_progress_orders: int
    avg_rating: float
