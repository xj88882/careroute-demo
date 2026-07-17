"""Customer-facing API router. Frontend miniprogram calls these endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Customer, Package, Order, OrderItem, Review, Provider
from schemas import (
    CustomerCreate, CustomerOut, PackageOut, OrderCreate, OrderOut,
    ReviewCreate, ReviewOut, PreauthRequest, PreauthResponse, AddonConfirm, AddonCancel,
    OrderDetailOut,
)
from middleware.auth import get_current_admin  # placeholder - use customer JWT in prod
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/v2/public", tags=["Public"])


# ---- Packages ----
@router.get("/packages", response_model=list[PackageOut])
async def list_packages(
    type: str = None, tier: str = None, db: AsyncSession = Depends(get_db)
):
    q = select(Package).where(Package.status == "active")
    if type: q = q.where(Package.type == type)
    if tier: q = q.where(Package.tier == tier)
    q = q.order_by(Package.sort_order)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/packages/{package_id}", response_model=PackageOut)
async def get_package(package_id: str, db: AsyncSession = Depends(get_db)):
    pkg = await db.get(Package, package_id)
    if not pkg: raise HTTPException(404, "Package not found")
    return pkg


# ---- Orders ----
@router.post("/orders", response_model=OrderOut)
async def create_order(
    payload: OrderCreate, db: AsyncSession = Depends(get_db)
):
    # In production, extract customer from JWT; here use a demo customer
    customer = (await db.execute(select(Customer).limit(1))).scalar()
    if not customer:
        raise HTTPException(400, "No customer found. Create a customer first.")

    order = Order(
        id=str(uuid.uuid4()),
        order_no=f"CR-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:3].upper()}",
        customer_id=customer.id,
        package_id=payload.package_id,
        provider_id=payload.provider_id,
        channel=payload.channel,
        channel_ref=payload.channel_ref,
        service_date=payload.service_date,
        status="confirmed",
    )
    db.add(order)
    await db.flush()
    return order


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    o = await db.get(Order, order_id)
    if not o: raise HTTPException(404, "Order not found")
    return o


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(db: AsyncSession = Depends(get_db)):
    # In production: filter by customer from JWT
    result = await db.execute(select(Order).order_by(Order.created_at.desc()).limit(20))
    return result.scalars().all()


# ---- Pre-auth ----
@router.post("/orders/{order_id}/preauth", response_model=PreauthResponse)
async def initiate_preauth(
    order_id: str, payload: PreauthRequest, db: AsyncSession = Depends(get_db)
):
    o = await db.get(Order, order_id)
    if not o: raise HTTPException(404, "Order not found")

    preauth_amount = o.consumer_total_price * 1.2  # 120%
    preauth_id = f"PA-{str(uuid.uuid4())[:12].upper()}"
    o.preauth_amount = preauth_amount
    o.preauth_id = preauth_id
    o.preauth_card_last4 = "0000"  # from token in prod

    # Record payment event
    from models import PaymentRecord
    pr = PaymentRecord(
        id=str(uuid.uuid4()), order_id=order_id,
        type="preauth_freeze", amount=preauth_amount,
        unionpay_ref=preauth_id, status="success",
        triggered_by="customer",
    )
    db.add(pr)
    await db.flush()

    return PreauthResponse(
        preauth_id=preauth_id, amount=preauth_amount,
        card_last4="0000", status="success"
    )


# ---- Addons ----
@router.post("/orders/{order_id}/addons/confirm")
async def confirm_addon(
    order_id: str, payload: AddonConfirm, db: AsyncSession = Depends(get_db)
):
    item = await db.get(OrderItem, payload.addon_item_id)
    if not item or str(item.order_id) != order_id:
        raise HTTPException(404, "Addon item not found")
    item.addon_status = "confirmed"
    item.addon_confirmed_at = datetime.utcnow()
    await db.flush()
    return {"status": "confirmed"}


@router.post("/orders/{order_id}/addons/{addon_id}/cancel")
async def cancel_addon(
    order_id: str, addon_id: str, db: AsyncSession = Depends(get_db)
):
    item = await db.get(OrderItem, addon_id)
    if not item or str(item.order_id) != order_id:
        raise HTTPException(404, "Addon item not found")
    if item.addon_status == "performed":
        raise HTTPException(400, "Cannot cancel a performed addon")
    item.addon_status = "cancelled"
    await db.flush()
    return {"status": "cancelled"}


# ---- Reviews ----
@router.post("/reviews", response_model=ReviewOut)
async def create_review(payload: ReviewCreate, db: AsyncSession = Depends(get_db)):
    customer = (await db.execute(select(Customer).limit(1))).scalar()
    review = Review(
        id=str(uuid.uuid4()),
        order_id=payload.order_id,
        customer_id=customer.id,
        package_id=payload.package_id,
        rating_overall=payload.rating_overall,
        rating_staff=payload.rating_staff,
        rating_english=payload.rating_english,
        rating_wait_time=payload.rating_wait_time,
        rating_report=payload.rating_report,
        comment=payload.comment,
    )
    db.add(review)
    await db.flush()
    await db.refresh(review)
    return review


@router.get("/packages/{package_id}/reviews", response_model=list[ReviewOut])
async def get_reviews(package_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Review).where(Review.package_id == package_id, Review.is_public == True)
        .order_by(Review.created_at.desc())
    )
    return result.scalars().all()


# ---- CITS Inventory (read-only for customers) ----
@router.get("/flights/search")
async def search_flights(
    departure: str, arrival: str, date: str, db: AsyncSession = Depends(get_db)
):
    from models import CitsFlight
    result = await db.execute(
        select(CitsFlight).where(
            CitsFlight.departure_city == departure,
            CitsFlight.arrival_city == arrival,
            CitsFlight.departure_date == date,
            CitsFlight.available_seats > 0,
        )
    )
    flights = result.scalars().all()
    return [{"flight_no": f.flight_no, "airline": f.airline,
             "price": str(f.price), "available_seats": f.available_seats} for f in flights]


@router.get("/hotels/search")
async def search_hotels(city: str, db: AsyncSession = Depends(get_db)):
    from models import CitsHotel
    result = await db.execute(
        select(CitsHotel).where(
            CitsHotel.city == city, CitsHotel.available_rooms > 0
        )
    )
    hotels = result.scalars().all()
    return [{"name": h.name_en, "stars": h.stars, "price_per_night": str(h.price_per_night),
             "is_medical_pool": h.is_medical_pool} for h in hotels]
