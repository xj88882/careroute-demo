"""Seed database with demo data for development."""
import asyncio
from datetime import date, datetime
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from models import (
    Base, Customer, Provider, ProviderService, Package, PackageItem,
    AdminUser, Order, OrderItem, Review, CitsFlight, CitsHotel,
)
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DATABASE_URL = "postgresql+asyncpg://careroute:careroute@localhost:5432/careroute"
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Admin
        db.add(AdminUser(id=str(uuid.uuid4()), username="admin",
            password_hash=pwd_context.hash("admin123"),
            display_name="管理员", role="super_admin"))
        db.add(AdminUser(id=str(uuid.uuid4()), username="finance",
            password_hash=pwd_context.hash("finance123"),
            display_name="财务", role="finance"))

        # Customer
        c = Customer(id=str(uuid.uuid4()), full_name="John Smith", nationality="USA",
            passport_number="encrypted_AB123456", email="john@example.com",
            preferred_language="en", data_retention_until=date(2031, 7, 18))
        db.add(c)

        # Providers
        p1 = Provider(id=str(uuid.uuid4()), name="北京协和医院", name_en="PUMCH",
            type="physical_exam", ownership="public", license_no="PE-PUMCH-001",
            city="北京", api_key="crt_pumch_key", integration_mode="hybrid",
            contract_signed_at=date(2026, 7, 1), contract_expires_at=date(2027, 6, 30))
        p2 = Provider(id=str(uuid.uuid4()), name="上海第九人民医院", name_en="Shanghai 9th",
            type="dental", ownership="public", license_no="DN-SH9TH-001",
            city="上海", api_key="crt_sh9th_key", integration_mode="hybrid",
            contract_signed_at=date(2026, 7, 1), contract_expires_at=date(2027, 4, 1))
        db.add_all([p1, p2])

        # Provider services
        db.add(ProviderService(id=str(uuid.uuid4()), provider_id=p1.id,
            service_code="PE-L2-001", service_name="低剂量肺部CT",
            service_name_en="Low-Dose Lung CT", settlement_price=800,
            premium_cap_pct=30, duration_minutes=20))
        db.add(ProviderService(id=str(uuid.uuid4()), provider_id=p2.id,
            service_code="DN-IMP-001", service_name="种植牙(植体+牙冠)",
            service_name_en="Dental Implant (Implant+Crown)",
            settlement_price=8000, duration_minutes=90, is_addon_candidate=True,
            requires_consent=True, vat_applicable=True))

        # Packages
        pkg = Package(id=str(uuid.uuid4()), name="优享体检套餐", name_en="Health Checkup L2 Premium",
            type="physical_exam", tier="L2",
            description_en="Comprehensive screening for 40+ or family history.",
            consumer_price_min=15000, consumer_price_max=30000,
            us_comparison_price="$5,500-11,000", savings_pct=75, is_featured=True)
        db.add(pkg)

        # CITS inventory
        db.add(CitsFlight(id=str(uuid.uuid4()), flight_no="CA982", airline="Air China",
            departure_city="JFK", arrival_city="PEK", departure_date=date(2026, 8, 15),
            cabin_class="Economy", price=6800, service_fee=200, available_seats=20))
        db.add(CitsHotel(id=str(uuid.uuid4()), name="北京香格里拉", name_en="Shangri-La Beijing",
            city="北京", stars=5, room_type="Deluxe King", price_per_night=1800,
            is_medical_pool=True, distance_to_provider=2.5, available_rooms=10))

        await db.commit()
        print("Seed data inserted successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
