from datetime import datetime
from pydantic import BaseModel


class ProductCharacteristicOut(BaseModel):
    id: int
    nm_id: int
    characteristics: dict
    synced_at: datetime
    seller_name: str  # ✅ новое поле

    model_config = {"from_attributes": True}


class SyncLogOut(BaseModel):
    id: int
    status: str
    message: str | None
    records_saved: int
    created_at: datetime
    seller_name: str  # ✅ новое поле

    model_config = {"from_attributes": True}


class TokenRequest(BaseModel):
    token: str


class StockOut(BaseModel):
    id: int
    nm_id: int
    chrt_id: int
    warehouse_id: int
    warehouse_name: str
    region_name: str
    quantity: int
    in_way_to_client: int
    in_way_from_client: int
    synced_at: datetime
    seller_name: str  # ✅ новое поле

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    cabinet_id: str
    seller_name: str | None = None
    srid: str | None = None
    g_number: str | None = None
    nm_id: int | None = None
    supplier_article: str | None = None
    barcode: str | None = None
    date: datetime | None = None
    last_change_date: datetime | None = None
    cancel_date: datetime | None = None
    total_price: float | None = None
    finished_price: float | None = None
    price_with_disc: float | None = None
    discount_percent: int | None = None
    spp: float | None = None
    is_cancel: bool = False
    is_supply: bool = False
    is_realization: bool = False
    warehouse_name: str | None = None
    warehouse_type: str | None = None
    country_name: str | None = None
    region_name: str | None = None
    category: str | None = None
    subject: str | None = None
    brand: str | None = None
    tech_size: str | None = None
    sticker: str | None = None
    income_id: int | None = None
    synced_at: datetime

    model_config = {"from_attributes": True}
