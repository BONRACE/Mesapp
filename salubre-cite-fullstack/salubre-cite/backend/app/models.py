from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from geoalchemy2 import Geometry

class Base(DeclarativeBase):
    pass

class UserRole(str, PyEnum):
    MENAGE = "menage"
    COLLECTEUR = "collecteur"
    CENTRE = "centre"
    ACHETEUR = "acheteur"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    organization: Mapped[str | None] = mapped_column(String(140))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), index=True)
    zone: Mapped[str] = mapped_column(String(80), default="Cotonou")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    eco_points: Mapped[int] = mapped_column(Integer, default=0)
    location = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SmartBin(Base):
    __tablename__ = "smart_bins"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120))
    zone: Mapped[str] = mapped_column(String(80), index=True)
    waste_stream: Mapped[str] = mapped_column(String(64))
    fill_level: Mapped[int] = mapped_column(Integer, default=0)
    estimated_kg: Mapped[float] = mapped_column(Float, default=0.0)
    household_label: Mapped[str] = mapped_column(String(120))
    geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

class CollectionScan(Base):
    __tablename__ = "collection_scans"
    id: Mapped[int] = mapped_column(primary_key=True)
    bin_code: Mapped[str] = mapped_column(String(32), index=True)
    collector_phone: Mapped[str] = mapped_column(String(24), index=True)
    qr_token: Mapped[str] = mapped_column(String(180), unique=True)
    verified_hmac: Mapped[bool] = mapped_column(Boolean, default=False)
    weighed_kg: Mapped[float] = mapped_column(Float)
    awarded_points: Mapped[int] = mapped_column(Integer, default=0)
    scan_geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class RecycledLot(Base):
    __tablename__ = "recycled_lots"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(64), index=True)
    center_name: Mapped[str] = mapped_column(String(120))
    purity_pct: Mapped[float] = mapped_column(Float)
    available_tons: Mapped[float] = mapped_column(Float)
    min_order_tons: Mapped[float] = mapped_column(Float, default=1.0)
    price_per_ton_xof: Mapped[int] = mapped_column(Numeric(12, 0))

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    lot_sku: Mapped[str] = mapped_column(String(32), index=True)
    payer_phone: Mapped[str] = mapped_column(String(24))
    provider: Mapped[str] = mapped_column(String(32))  # fedapay | kkiapay | stripe
    tons: Mapped[float] = mapped_column(Float)
    subtotal_xof: Mapped[int] = mapped_column(Numeric(12, 0))
    platform_fee_xof: Mapped[int] = mapped_column(Numeric(12, 0))
    seller_net_xof: Mapped[int] = mapped_column(Numeric(12, 0))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
