import os, hmac, hashlib, secrets, time, math
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .schemas import OtpRequestIn, OtpVerifyIn, QrGenerateIn, QrScanIn, CheckoutIn

app = FastAPI(
    title="Salubre Cité API",
    description="Backend FastAPI + PostGIS pour la gestion des déchets multi-rôles, QR HMAC-SHA256 et Bourse de matières recyclées.",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

HMAC_SECRET = os.getenv("SALUBRE_HMAC_SECRET", "SALUBRE_COTONOU_HMAC_2026").encode()
OTP_STORE: dict[str, tuple[str, float]] = {}

DEMO_BINS = [
    {"code": "BAC-101", "name": "Dépôt Akpakpa PK3", "zone": "Akpakpa", "lat": 6.369, "lng": 2.462, "fill": 25, "kg": 0},
    {"code": "BAC-104", "name": "Marché Dantokpa Nord", "zone": "Dantokpa", "lat": 6.374, "lng": 2.432, "fill": 94, "kg": 185},
    {"code": "BAC-108", "name": "Carrefour Ganhi", "zone": "Ganhi", "lat": 6.356, "lng": 2.439, "fill": 86, "kg": 140},
    {"code": "BAC-112", "name": "Haie Vive Résidence", "zone": "Haie Vive", "lat": 6.361, "lng": 2.398, "fill": 78, "kg": 95},
    {"code": "BAC-119", "name": "Fidjrossè Plage", "zone": "Fidjrossè", "lat": 6.352, "lng": 2.361, "fill": 89, "kg": 130},
    {"code": "BAC-123", "name": "Stade de l'Amitié", "zone": "Kouhounou", "lat": 6.386, "lng": 2.378, "fill": 74, "kg": 110},
    {"code": "BAC-131", "name": "Zogbo Carrefour", "zone": "Zogbo", "lat": 6.395, "lng": 2.394, "fill": 83, "kg": 165},
    {"code": "BAC-142", "name": "Cadjèhoun Aéroport", "zone": "Cadjèhoun", "lat": 6.358, "lng": 2.384, "fill": 91, "kg": 150},
    {"code": "BAC-149", "name": "Godomey Échangeur", "zone": "Godomey", "lat": 6.392, "lng": 2.339, "fill": 81, "kg": 145},
]

def haversine_km(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    r = 6371.0
    dlat = math.radians(b_lat - a_lat)
    dlng = math.radians(b_lng - a_lng)
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))

@app.post("/api/v1/auth/otp/request")
async def request_otp(payload: OtpRequestIn):
    code = f"{secrets.randbelow(900000) + 100000}"
    OTP_STORE[payload.phone] = (code, time.time() + 300)
    return {"phone": payload.phone, "ttl_seconds": 300, "demo_otp": code}

@app.post("/api/v1/auth/otp/verify")
async def verify_otp(payload: OtpVerifyIn):
    saved = OTP_STORE.get(payload.phone)
    if not saved or saved[0] != payload.code or time.time() > saved[1]:
        raise HTTPException(status_code=401, detail="Code OTP invalide ou expiré")
    token = hmac.new(HMAC_SECRET, f"{payload.phone}:{payload.role}:{int(time.time())}".encode(), hashlib.sha256).hexdigest()
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "phone": payload.phone,
            "full_name": payload.full_name,
            "organization": payload.organization,
            "role": payload.role,
            "zone": payload.zone,
            "eco_points": 340,
        },
    }

@app.get("/api/v1/routing/optimize")
async def optimize_route(min_fill: int = 70, speed_kmh: float = 26.0):
    depot = DEMO_BINS[0]
    pool = [b for b in DEMO_BINS[1:] if b["fill"] >= min_fill]
    ordered = [depot]
    cur = depot
    total_km = 0.0
    while pool:
        pool.sort(key=lambda b: haversine_km(cur["lat"], cur["lng"], b["lat"], b["lng"]) * 1.28 * (1 - (b["fill"] - 50) / 150))
        nxt = pool.pop(0)
        total_km += haversine_km(cur["lat"], cur["lng"], nxt["lat"], nxt["lng"]) * 1.28
        ordered.append(nxt)
        cur = nxt
    total_km += haversine_km(cur["lat"], cur["lng"], depot["lat"], depot["lng"]) * 1.28
    total_kg = sum(b["kg"] for b in ordered)
    return {
        "engine": "PostGIS ST_DWithin + VRP Nearest-Urgent",
        "stops": ordered,
        "total_km": round(total_km, 1),
        "total_kg": total_kg,
        "estimated_minutes": round((total_km / speed_kmh) * 60 + (len(ordered) - 1) * 6),
        "co2_saved_kg": round(total_kg * 1.65),
    }

@app.post("/api/v1/qr/generate")
async def generate_qr(payload: QrGenerateIn):
    ts = int(time.time())
    body = f"SLB1:{payload.bin_code}:{payload.zone}:{ts}"
    sig = hmac.new(HMAC_SECRET, f"{body}:{payload.household}".encode(), hashlib.sha256).hexdigest()[:16].upper()
    return {"qr_token": f"{body}:{sig}", "signature": sig, "timestamp": ts}

@app.post("/api/v1/qr/scan")
async def scan_qr(payload: QrScanIn):
    parts = payload.qr_token.split(":")
    if len(parts) != 5 or parts[0] != "SLB1":
        raise HTTPException(status_code=400, detail="Format de jeton QR invalide")
    body = ":".join(parts[:4])
    expected = hmac.new(HMAC_SECRET, f"{body}:{payload.household}".encode(), hashlib.sha256).hexdigest()[:16].upper()
    if not hmac.compare_digest(parts[4].upper(), expected):
        raise HTTPException(status_code=403, detail="Signature HMAC-SHA256 invalide")
    pts = int(round(payload.weighed_kg * 5))
    return {"verified": True, "bin_code": parts[1], "zone": parts[2], "weighed_kg": payload.weighed_kg, "awarded_eco_points": pts}

@app.post("/api/v1/payments/checkout")
async def create_checkout(payload: CheckoutIn):
    subtotal = int(round(payload.tons * payload.unit_price_xof))
    fee = int(round(subtotal * 0.04))
    ref = f"PAY-{payload.provider.upper()[:4]}-{secrets.token_hex(4).upper()}"
    return {
        "reference": ref,
        "provider": payload.provider,
        "lot_sku": payload.lot_sku,
        "tons": payload.tons,
        "subtotal_xof": subtotal,
        "platform_fee_xof": fee,
        "seller_net_xof": subtotal - fee,
        "checkout_url": f"https://checkout.{payload.provider}.com/pay/{ref}",
        "status": "pending_webhook",
    }
