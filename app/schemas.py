from datetime import datetime
from pydantic import BaseModel


class ProductCharacteristicOut(BaseModel):
    id: int
    cabinet_id: str
    nm_id: int
    characteristics: dict
    synced_at: datetime

    model_config = {"from_attributes": True}


class SyncLogOut(BaseModel):
    id: int
    cabinet_id: str
    status: str
    message: str | None
    records_saved: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenRequest(BaseModel):
    token: str


class StockOut(BaseModel):
    id: int
    cabinet_id: str
    nm_id: int
    chrt_id: int
    warehouse_id: int
    warehouse_name: str
    region_name: str
    quantity: int
    in_way_to_client: int
    in_way_from_client: int
    synced_at: datetime

    model_config = {"from_attributes": True}
