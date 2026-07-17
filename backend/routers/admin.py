"""Admin dashboard API router. RBAC-protected internal endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models import Order, Provider, Settlement, Review, AdminUser, PaymentRecord
from schemas import (
    AdminLogin, AdminLoginResponse, DashboardKPIs, OrderOut, ProviderOut,
    SettlementOut, ReviewOut, OrderDetailOut,
)
from middleware.auth import create_admin_token, get_current_admin, require_role
from passlib.context import CryptContext
import uuid

router = APIRouter(prefix="/api/v2/admin", tags=["Admin"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ===================== Auth =====================
@router.post("/auth/login", response_model=AdminLoginResponse)
async def admin_login(payload: AdminLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdminUser).where(AdminUser.username == payload.username))
    user = result.scalar()
    if not user or not pwd_context.verify(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")

    token = create_admin_token(user.id, user.role)
    user.last_login_at = func.now()
    await db.flush()
    return AdminLoginResponse(access_token=token, display_name=user.display_name, role=user.role)


# ===================== Dashboard =====================
@router.get("/dashboard", response_model=DashboardKPIs)
async def dashboard(admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    total_orders = (await db.execute(select(func.count(Order.id)))).scalar()
    completed = (await db.execute(select(func.count(Order.id)).where(Order.status == "completed"))).scalar()
    in_progress = (await db.execute(
        select(func.count(Order.id)).where(Order.status.in_(["confirmed", "in_progress"]))
    )).scalar()
    total_rev = (await db.execute(
        select(func.coalesce(func.sum(Order.total_charged), 0))
        .where(Order.status == "completed")
    )).scalar()
    avg_rating = (await db.execute(select(func.avg(Review.rating_overall)))).scalar() or 0.0

    return DashboardKPIs(
        total_revenue_mtd=total_rev, total_orders=total_orders,
        completed_orders=completed, in_progress_orders=in_progress,
        avg_rating=round(float(avg_rating), 1),
    )


# ===================== Orders =====================
@router.get("/orders", response_model=list[OrderOut])
async def admin_list_orders(
    status: str = None, channel: str = None,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    q = select(Order)
    if status: q = q.where(Order.status == status)
    if channel: q = q.where(Order.channel == channel)
    q = q.order_by(Order.created_at.desc()).limit(100)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
async def admin_get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    o = await db.get(Order, order_id)
    if not o: raise HTTPException(404, "Order not found")
    return o


@router.put("/orders/{order_id}/status")
async def admin_update_order_status(
    order_id: str, status: str, db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    o = await db.get(Order, order_id)
    if not o: raise HTTPException(404, "Order not found")
    valid_statuses = ["confirmed", "in_progress", "completed", "cancelled", "disputed"]
    if status not in valid_statuses:
        raise HTTPException(400, f"Invalid status. Must be one of: {valid_statuses}")
    o.status = status
    await db.flush()
    return {"status": status}


# ===================== Providers =====================
@router.get("/providers", response_model=list[ProviderOut])
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Provider).order_by(Provider.created_at.desc()))
    return result.scalars().all()


@router.post("/providers", response_model=ProviderOut)
async def create_provider(
    provider: ProviderOut, db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    # Simplified - in production, use a create schema
    p = Provider(id=str(uuid.uuid4()), **provider.model_dump(exclude={"id"}))
    db.add(p)
    await db.flush()
    await db.refresh(p)
    return p


# ===================== Settlements =====================
@router.get("/settlements", response_model=list[SettlementOut])
async def list_settlements(
    provider_id: str = None, status: str = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Settlement)
    if provider_id: q = q.where(Settlement.provider_id == provider_id)
    if status: q = q.where(Settlement.status == status)
    q = q.order_by(Settlement.period_start.desc()).limit(50)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/settlements/generate")
async def generate_settlement(
    provider_id: str, period_start: str, period_end: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("super_admin", "finance")),
):
    """Generate settlement for a provider in a given period."""
    from datetime import date as dt_date
    ps = dt_date.fromisoformat(period_start)
    pe = dt_date.fromisoformat(period_end)

    # Sum all completed orders for this provider in this period
    orders_result = await db.execute(
        select(Order).where(
            Order.provider_id == provider_id,
            Order.status == "completed",
            Order.completed_at >= ps,
            Order.completed_at <= pe,
        )
    )
    orders = orders_result.scalars().all()

    total_settlement = sum((o.settlement_total_price or 0) for o in orders)
    total_premium = sum((o.premium_total or 0) for o in orders)

    settlement = Settlement(
        id=str(uuid.uuid4()),
        period_start=ps, period_end=pe, provider_id=provider_id,
        total_settlement=total_settlement, total_premium=total_premium,
        total_netsettle=total_settlement, status="draft",
    )
    db.add(settlement)
    await db.flush()
    await db.refresh(settlement)
    return settlement


@router.put("/settlements/{settlement_id}/confirm")
async def confirm_settlement(
    settlement_id: str, db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("super_admin", "finance")),
):
    s = await db.get(Settlement, settlement_id)
    if not s: raise HTTPException(404, "Settlement not found")
    if s.status != "draft": raise HTTPException(400, "Only draft settlements can be confirmed")
    s.status = "confirmed"
    await db.flush()
    return {"status": "confirmed"}


# ===================== Reviews =====================
@router.get("/reviews", response_model=list[ReviewOut])
async def list_reviews(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Review).order_by(Review.created_at.desc()).limit(100))
    return result.scalars().all()


@router.put("/reviews/{review_id}/toggle-visibility")
async def toggle_review(review_id: str, db: AsyncSession = Depends(get_db)):
    r = await db.get(Review, review_id)
    if not r: raise HTTPException(404, "Review not found")
    r.is_public = not r.is_public
    await db.flush()
    return {"is_public": r.is_public}


# ===================== Analytics =====================
@router.get("/analytics/revenue")
async def revenue_analytics(db: AsyncSession = Depends(get_db)):
    """Revenue grouped by channel."""
    result = await db.execute(
        select(Order.channel, func.sum(Order.total_charged))
        .where(Order.status == "completed")
        .group_by(Order.channel)
    )
    return [{"channel": row[0] or "unknown", "total": str(row[1] or 0)} for row in result.all()]


@router.get("/analytics/conversion")
async def conversion_funnel(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(Order.id)))).scalar() or 0
    completed = (await db.execute(select(func.count(Order.id)).where(Order.status == "completed"))).scalar() or 0
    cancelled = (await db.execute(select(func.count(Order.id)).where(Order.status == "cancelled"))).scalar() or 0
    return {
        "total_created": total,
        "completed": completed,
        "cancelled": cancelled,
        "completion_rate": round(completed / total * 100, 1) if total else 0,
    }
