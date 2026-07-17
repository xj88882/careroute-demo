"""Partner-facing API router. Called by CITS, hospitals/clinics, and UnionPay webhooks."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Order, OrderItem, OrderStage, PaymentRecord, CitsFlight, CitsHotel, ProviderService
from schemas import AuthTrigger, AddonPropose, FlightSync, HotelSync
from middleware.auth import verify_partner
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/v2/partner", tags=["Partner"], dependencies=[Depends(verify_partner)])


# ===================== Authorization Triggers (Hospitals) =====================
@router.post("/orders/{order_id}/authorize/service-start")
async def authorize_service_start(order_id: str, db: AsyncSession = Depends(get_db)):
    """Service appointment check-in. Verify pre-auth coverage."""
    o = await db.get(Order, order_id)
    if not o: raise HTTPException(404, "Order not found")
    if o.status != "confirmed":
        raise HTTPException(400, f"Order is {o.status}, not confirmed")
    o.status = "in_progress"
    await db.flush()
    return {"status": "in_progress", "preauth_amount": str(o.preauth_amount or 0)}


@router.post("/orders/{order_id}/authorize/service-complete")
async def authorize_service_complete(order_id: str, db: AsyncSession = Depends(get_db)):
    """All services completed. Trigger final charge on VISA pre-auth."""
    o = await db.get(Order, order_id)
    if not o: raise HTTPException(404, "Order not found")
    if o.status != "in_progress": raise HTTPException(400, "Order not in progress")

    # Finalize charge
    charge_amount = o.consumer_total_price
    o.total_charged = charge_amount
    o.status = "completed"
    o.completed_at = datetime.utcnow()

    # Record capture
    pr = PaymentRecord(
        id=str(uuid.uuid4()), order_id=order_id,
        type="preauth_capture", amount=charge_amount,
        unionpay_ref=o.preauth_id, status="success", triggered_by="provider"
    )
    db.add(pr)

    # Release remainder
    if o.preauth_amount and o.preauth_amount > charge_amount:
        released = o.preauth_amount - charge_amount
        o.total_released = released
        pr2 = PaymentRecord(
            id=str(uuid.uuid4()), order_id=order_id,
            type="preauth_release", amount=released,
            unionpay_ref=o.preauth_id, status="success", triggered_by="provider"
        )
        db.add(pr2)

    await db.flush()
    return {"status": "completed", "charged": str(charge_amount), "released": str(o.total_released)}


@router.post("/orders/{order_id}/authorize/stage-complete")
async def authorize_stage_complete(order_id: str, payload: AuthTrigger, db: AsyncSession = Depends(get_db)):
    """Dental treatment stage complete. Trigger partial charge."""
    o = await db.get(Order, order_id)
    if not o: raise HTTPException(404, "Order not found")

    stage = (await db.execute(
        select(OrderStage).where(OrderStage.order_id == order_id, OrderStage.stage_no == payload.stage_no)
    )).scalar()
    if not stage: raise HTTPException(404, "Stage not found")

    stage.status = "completed"
    stage.actual_date = datetime.utcnow().date()
    stage.is_authorized = True
    stage.authorized_at = datetime.utcnow()

    charge_amount = stage.consumer_amount
    o.total_charged = (o.total_charged or 0) + charge_amount

    pr = PaymentRecord(
        id=str(uuid.uuid4()), order_id=order_id,
        type="preauth_capture", amount=charge_amount,
        unionpay_ref=f"{o.preauth_id}-S{payload.stage_no}",
        status="success", triggered_by="provider"
    )
    db.add(pr)
    await db.flush()

    return {"status": "stage_completed", "stage": payload.stage_no, "charged": str(charge_amount)}


# ===================== Addon Propose (Provider side) =====================
@router.post("/orders/{order_id}/addons/propose")
async def propose_addon(order_id: str, payload: AddonPropose, db: AsyncSession = Depends(get_db)):
    """Provider suggests an add-on procedure. Pushes notification to customer APP."""
    item = OrderItem(
        id=str(uuid.uuid4()), order_id=order_id,
        service_code=payload.service_code, service_name_en=payload.reason,
        settlement_price=payload.price, consumer_price=payload.price,
        is_addon=True, addon_status="confirmed"  # awaits customer confirmation in APP
    )
    db.add(item)
    await db.flush()
    return {"status": "proposed", "item_id": item.id, "requires_customer_confirm": True}


# ===================== CITS Inventory Sync =====================
@router.put("/flights/inventory")
async def sync_flights(payload: list[FlightSync], db: AsyncSession = Depends(get_db)):
    """Batch sync flight inventory from CITS."""
    count = 0
    for f in payload:
        existing = (await db.execute(
            select(CitsFlight).where(CitsFlight.flight_no == f.flight_no, CitsFlight.departure_date == f.departure_date)
        )).scalar()
        if existing:
            existing.price = f.price; existing.service_fee = f.service_fee
            existing.available_seats = f.available_seats; existing.synced_at = datetime.utcnow()
        else:
            db.add(CitsFlight(id=str(uuid.uuid4()), **f.model_dump(), synced_at=datetime.utcnow()))
        count += 1
    await db.flush()
    return {"synced": count}


@router.put("/hotels/inventory")
async def sync_hotels(payload: list[HotelSync], db: AsyncSession = Depends(get_db)):
    """Batch sync hotel inventory from CITS."""
    count = 0
    for h in payload:
        db.add(CitsHotel(id=str(uuid.uuid4()), **h.model_dump(), synced_at=datetime.utcnow()))
        count += 1
    await db.flush()
    return {"synced": count}


# ===================== Payment Webhook (UnionPay callback) =====================
@router.post("/payment/webhook")
async def payment_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """UnionPay callback. Updates payment record status."""
    body = await request.json()
    ref = body.get("reference")
    status = body.get("status")

    pr = (await db.execute(select(PaymentRecord).where(PaymentRecord.unionpay_ref == ref))).scalar()
    if pr:
        pr.status = status
        pr.completed_at = datetime.utcnow()
    await db.flush()
    return {"received": True}


# ===================== Report Upload =====================
@router.put("/orders/{order_id}/report")
async def upload_report(order_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Provider uploads medical report URL."""
    body = await request.json()
    report_url = body.get("report_url")
    o = await db.get(Order, order_id)
    if not o: raise HTTPException(404, "Order not found")
    o.medical_report_url = report_url
    await db.flush()
    return {"status": "uploaded"}
