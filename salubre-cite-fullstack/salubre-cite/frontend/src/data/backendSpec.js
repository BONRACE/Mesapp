export const ARCHITECTURE_NOTES = [
  { title: "FastAPI + SQLAlchemy 2.0 Async", detail: "Endpoints REST typés Pydantic v2, JWT Bearer + vérification OTP par téléphone (Redis / mémoire TTL 300 s)." },
  { title: "PostgreSQL 16 + PostGIS 3.4", detail: "Colonnes Geometry(POINT, 4326) et Geometry(LINESTRING, 4326) avec index GIST, requêtes ST_DWithin et ST_DistanceSphere." },
  { title: "QR Codes Signés HMAC-SHA256", detail: "Jeton SLB1:<bin_id>:<zone>:<timestamp>:<hmac> vérifié à chaque scan de collecte pour empêcher la fraude au pesage." },
  { title: "Passerelles Mobile Money & Carte", detail: "Webhooks signés FedaPay / KkiaPay / Stripe avec séquestre automatique et commission plateforme de 4 % sur la bourse." },
];

export const MODELS_CODE = `# backend/app/models.py — SQLAlchemy 2.0 + GeoAlchemy2 (PostGIS)
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
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
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), index=True)
    zone: Mapped[str] = mapped_column(String(80), default="Cotonou")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    eco_points: Mapped[int] = mapped_column(Integer, default=0)
    location = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SmartBin(Base):
    __tablename__ = "smart_bins"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # ex: BAC-104
    label: Mapped[str] = mapped_column(String(120))
    zone: Mapped[str] = mapped_column(String(80), index=True)
    waste_stream: Mapped[str] = mapped_column(String(64))
    fill_level: Mapped[int] = mapped_column(Integer, default=0)             # 0..100 %
    estimated_kg: Mapped[float] = mapped_column(Float, default=0.0)
    qr_secret_salt: Mapped[str] = mapped_column(String(64))
    geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

class CollectionScan(Base):
    __tablename__ = "collection_scans"
    id: Mapped[int] = mapped_column(primary_key=True)
    bin_id: Mapped[int] = mapped_column(ForeignKey("smart_bins.id"), index=True)
    collector_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    qr_token: Mapped[str] = mapped_column(String(180), unique=True)
    verified_hmac: Mapped[bool] = mapped_column(Boolean, default=False)
    weighed_kg: Mapped[float] = mapped_column(Float)
    scan_geom = mapped_column(Geometry(geometry_type="POINT", srid=4326))
    scanned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class RecycledLot(Base):
    __tablename__ = "recycled_lots"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(64), index=True)
    purity_pct: Mapped[float] = mapped_column(Float)
    available_tons: Mapped[float] = mapped_column(Float)
    price_per_ton_xof: Mapped[int] = mapped_column(Numeric(12, 0))
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("recycled_lots.id"))
    payer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(32))  # fedapay | kkiapay | stripe
    amount_xof: Mapped[int] = mapped_column(Numeric(12, 0))
    platform_fee_xof: Mapped[int] = mapped_column(Numeric(12, 0))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)`;

export const ENDPOINTS_CODE = `# backend/app/main.py — FastAPI Endpoints (OTP, PostGIS Routing, QR HMAC, Marketplace & Paiement)
import hmac, hashlib, secrets, time
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import select, func
from geoalchemy2.functions import ST_DWithin, ST_DistanceSphere, ST_SetSRID, ST_MakePoint

app = FastAPI(title="Salubre API", version="1.0.0")
HMAC_SECRET = b"SALUBRE_COTONOU_HMAC_2026"
OTP_STORE: dict[str, tuple[str, float]] = {}

@app.post("/api/v1/auth/otp/request")
async def request_otp(phone: str):
    code = f"{secrets.randbelow(900000) + 100000}"
    OTP_STORE[phone] = (code, time.time() + 300)
    # En production : envoi SMS/WhatsApp via passerelle Twilio / Termii
    return {"phone": phone, "ttl_seconds": 300, "demo_otp": code}

@app.post("/api/v1/auth/otp/verify")
async def verify_otp(phone: str, code: str, role: str = "menage", full_name: str = "Membre Salubre"):
    saved = OTP_STORE.get(phone)
    if not saved or saved[0] != code or time.time() > saved[1]:
        raise HTTPException(status_code=401, detail="Code OTP invalide ou expiré")
    token = hmac.new(HMAC_SECRET, f"{phone}:{role}:{int(time.time())}".encode(), hashlib.sha256).hexdigest()
    return {"access_token": token, "token_type": "bearer", "user": {"phone": phone, "role": role, "full_name": full_name}}

@app.get("/api/v1/routing/optimize")
async def optimize_collection_route(lat: float = 6.369, lng: float = 2.462, min_fill: int = 70, radius_m: int = 12000):
    origin = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
    # Requête PostGIS : sélectionne les bacs dans le rayon triés par proximité et taux de remplissage
    stmt = (
        select(SmartBin, ST_DistanceSphere(SmartBin.geom, origin).label("dist_m"))
        .where(SmartBin.fill_level >= min_fill)
        .where(ST_DWithin(SmartBin.geom, origin, radius_m / 111320.0))
        .order_by("dist_m")
    )
    return {"engine": "PostGIS + VRP Nearest-Urgent", "min_fill_pct": min_fill, "sql_preview": str(stmt)}

@app.post("/api/v1/qr/generate")
async def generate_bin_qr(bin_code: str, zone: str, household: str):
    ts = int(time.time())
    body = f"SLB1:{bin_code}:{zone}:{ts}"
    sig = hmac.new(HMAC_SECRET, f"{body}:{household}".encode(), hashlib.sha256).hexdigest()[:16].upper()
    return {"qr_token": f"{body}:{sig}", "signature": sig, "expires_in_sec": 86400}

@app.post("/api/v1/qr/scan")
async def verify_and_log_scan(qr_token: str, household: str, weighed_kg: float):
    parts = qr_token.split(":")
    if len(parts) != 5 or parts[0] != "SLB1":
        raise HTTPException(status_code=400, detail="Format QR invalide")
    body = ":".join(parts[:4])
    expected = hmac.new(HMAC_SECRET, f"{body}:{household}".encode(), hashlib.sha256).hexdigest()[:16].upper()
    if not hmac.compare_digest(parts[4].upper(), expected):
        raise HTTPException(status_code=403, detail="Signature QR contrefaite")
    eco_points = int(round(weighed_kg * 5))
    return {"verified": True, "bin_code": parts[1], "weighed_kg": weighed_kg, "awarded_eco_points": eco_points}

@app.post("/api/v1/payments/checkout")
async def create_payment_intent(lot_sku: str, tons: float, unit_price_xof: int, provider: str = "fedapay"):
    subtotal = int(round(tons * unit_price_xof))
    fee = int(round(subtotal * 0.04))  # Commission bourse circulaire 4 %
    ref = f"PAY-{provider.upper()}-{secrets.token_hex(4).upper()}"
    return {
        "reference": ref,
        "provider": provider,
        "subtotal_xof": subtotal,
        "platform_fee_xof": fee,
        "seller_net_xof": subtotal - fee,
        "checkout_url": f"https://checkout.{provider}.com/pay/{ref}",
        "status": "pending_webhook",
    }`;
