from pydantic import BaseModel, Field

class OtpRequestIn(BaseModel):
    phone: str = Field(..., examples=["+2290197448210"])

class OtpVerifyIn(BaseModel):
    phone: str
    code: str = Field(..., min_length=6, max_length=6)
    full_name: str = "Kossi Ahouansou"
    organization: str | None = "Coopérative Akpakpa"
    role: str = "collecteur"
    zone: str = "Akpakpa"

class QrGenerateIn(BaseModel):
    bin_code: str = "BAC-104"
    zone: str = "Dantokpa"
    household: str = "Coop Dantokpa"

class QrScanIn(BaseModel):
    qr_token: str
    household: str
    weighed_kg: float = Field(..., gt=0)
    lat: float | None = 6.374
    lng: float | None = 2.432

class CheckoutIn(BaseModel):
    lot_sku: str = "LOT-PET-01"
    tons: float = Field(..., gt=0)
    unit_price_xof: int = Field(..., gt=0)
    payer_phone: str = "+2290197448210"
    provider: str = "fedapay"
