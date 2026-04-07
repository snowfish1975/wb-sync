from sqlalchemy.orm import Session 
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import ProductCharacteristic, SyncLog, Stock
from datetime import datetime


def upsert_characteristic(db: Session, cabinet_id: str, nm_id: int, data: dict):
    stmt = pg_insert(ProductCharacteristic).values(
        cabinet_id=cabinet_id,
        nm_id=nm_id,
        characteristics=data,
    ).on_conflict_do_update(
        constraint="uq_cabinet_nm",
        set_={"characteristics": data, "synced_at": datetime.utcnow()},
    )
    db.execute(stmt)


def log_sync(db: Session, cabinet_id: str, status: str, message: str = None, records: int = 0):
    entry = SyncLog(
        cabinet_id=cabinet_id,
        status=status,
        message=message,
        records_saved=records,
    )
    db.add(entry)  # ❗ commit убран


def get_characteristics(db: Session, cabinet_id: str = None, nm_id: int = None):
    q = db.query(ProductCharacteristic)
    if cabinet_id:
        q = q.filter(ProductCharacteristic.cabinet_id == cabinet_id)
    if nm_id:
        q = q.filter(ProductCharacteristic.nm_id == nm_id)
    return q.order_by(ProductCharacteristic.synced_at.desc()).limit(500).all()


def get_sync_logs(db: Session, limit: int = 50):
    return db.query(SyncLog).order_by(SyncLog.created_at.desc()).limit(limit).all()


def upsert_stock(db: Session, cabinet_id: str, item: dict):
    stmt = pg_insert(Stock).values(
        cabinet_id=cabinet_id,
        nm_id=item["nmId"],
        chrt_id=item["chrtId"],
        warehouse_id=item["warehouseId"],
        warehouse_name=item["warehouseName"],
        region_name=item["regionName"],
        quantity=item["quantity"],
        in_way_to_client=item["inWayToClient"],
        in_way_from_client=item["inWayFromClient"],
    ).on_conflict_do_update(
        constraint="uq_stock",
        set_={
            "quantity": item["quantity"],
            "in_way_to_client": item["inWayToClient"],
            "in_way_from_client": item["inWayFromClient"],
            "synced_at": datetime.utcnow(),
        },
    )
    db.execute(stmt)


def get_stocks(db: Session, cabinet_id: str = None, nm_id: int = None):
    q = db.query(Stock)
    if cabinet_id:
        q = q.filter(Stock.cabinet_id == cabinet_id)
    if nm_id:
        q = q.filter(Stock.nm_id == nm_id)
    return q.order_by(Stock.synced_at.desc()).limit(10000).all()
