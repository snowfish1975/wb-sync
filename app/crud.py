from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import ProductCharacteristic, SyncLog

def upsert_characteristic(db: Session, cabinet_hint: str, nm_id: int, data: dict):
    """Вставляет или обновляет запись по кабинету + артикулу."""
    stmt = pg_insert(ProductCharacteristic).values(
        cabinet_token_hint=cabinet_hint,
        nm_id=nm_id,
        characteristics=data,
    ).on_conflict_do_update(
        constraint="uq_cabinet_nm",
        set_={"characteristics": data, "synced_at": __import__("datetime").datetime.utcnow()},
    )
    db.execute(stmt)
    db.commit()

def log_sync(db: Session, cabinet_hint: str, status: str, message: str = None, records: int = 0):
    entry = SyncLog(
        cabinet_token_hint=cabinet_hint,
        status=status,
        message=message,
        records_saved=records,
    )
    db.add(entry)
    db.commit()

def get_characteristics(db: Session, cabinet_hint: str = None, nm_id: int = None):
    q = db.query(ProductCharacteristic)
    if cabinet_hint:
        q = q.filter(ProductCharacteristic.cabinet_token_hint == cabinet_hint)
    if nm_id:
        q = q.filter(ProductCharacteristic.nm_id == nm_id)
    return q.order_by(ProductCharacteristic.synced_at.desc()).limit(500).all()

def get_sync_logs(db: Session, limit: int = 50):
    return db.query(SyncLog).order_by(SyncLog.created_at.desc()).limit(limit).all()