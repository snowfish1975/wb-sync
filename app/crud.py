from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import ProductCharacteristic, SyncLog, Stock, Order, Price
from datetime import datetime, timedelta
import os
import hashlib
import json


# -------------------------
# Загрузка токенов и имён
# -------------------------
def load_tokens_mapping() -> dict[str, str]:
    """
    Возвращает словарь: cabinet_id → seller_name
    """
    raw = os.getenv("WB_TOKENS_JSON", "{}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    mapping = {}
    for name, token in data.items():
        tid = hashlib.sha256(token.encode()).hexdigest()[:32]
        mapping[tid] = name
    return mapping


# -------------------------
# Функции работы с БД
# -------------------------
def upsert_characteristic(db: Session, cabinet_id: str, nm_id: int, data: dict):
    stmt = pg_insert(ProductCharacteristic).values(
        cabinet_id=cabinet_id,
        nm_id=nm_id,
        characteristics=data,
    ).on_conflict_do_update(
        constraint="uq_cabinet_nm",
        set_={
            "characteristics": data,
            "synced_at": datetime.utcnow(),
        },
    )
    db.execute(stmt)


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


def upsert_order(db: Session, cabinet_id: str, order_data: dict):
    """Сохранение или обновление заказа"""
    
    # Парсинг дат (они приходят в московском времени UTC+3)
    def parse_date(date_str: str) -> datetime | None:
        if not date_str or date_str == "0001-01-01T00:00:00":
            return None
        try:
            # Дата приходит в формате "2024-01-15T10:30:00"
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        except:
            return None
    
    stmt = pg_insert(Order).values(
        cabinet_id=cabinet_id,
        srid=order_data.get("srid"),
        g_number=order_data.get("gNumber"),
        nm_id=order_data.get("nmId"),
        supplier_article=order_data.get("supplierArticle"),
        barcode=order_data.get("barcode"),
        date=parse_date(order_data.get("date")),
        last_change_date=parse_date(order_data.get("lastChangeDate")),
        cancel_date=parse_date(order_data.get("cancelDate")),
        total_price=order_data.get("totalPrice"),
        finished_price=order_data.get("finishedPrice"),
        price_with_disc=order_data.get("priceWithDisc"),
        discount_percent=order_data.get("discountPercent"),
        spp=order_data.get("spp"),
        is_cancel=order_data.get("isCancel", False),
        is_supply=order_data.get("isSupply", False),
        is_realization=order_data.get("isRealization", False),
        warehouse_name=order_data.get("warehouseName"),
        warehouse_type=order_data.get("warehouseType"),
        country_name=order_data.get("countryName"),
        region_name=order_data.get("regionName"),
        category=order_data.get("category"),
        subject=order_data.get("subject"),
        brand=order_data.get("brand"),
        tech_size=order_data.get("techSize"),
        sticker=order_data.get("sticker"),
        income_id=order_data.get("incomeID"),
        synced_at=datetime.utcnow(),
    ).on_conflict_do_update(
        constraint="uq_cabinet_order",
        set_={
            "last_change_date": parse_date(order_data.get("lastChangeDate")),
            "cancel_date": parse_date(order_data.get("cancelDate")),
            "finished_price": order_data.get("finishedPrice"),
            "price_with_disc": order_data.get("priceWithDisc"),
            "is_cancel": order_data.get("isCancel", False),
            "synced_at": datetime.utcnow(),
        },
    )
    db.execute(stmt)


def log_sync(db: Session, cabinet_id: str, status: str, message: str | None = None, records: int = 0):
    entry = SyncLog(
        cabinet_id=cabinet_id,
        status=status,
        message=message,
        records_saved=records,
    )
    db.add(entry)


def get_characteristics(db: Session, cabinet_id: str | None = None, nm_id: int | None = None):
    q = db.query(ProductCharacteristic)
    if cabinet_id:
        q = q.filter(ProductCharacteristic.cabinet_id == cabinet_id)
    if nm_id:
        q = q.filter(ProductCharacteristic.nm_id == nm_id)
    return q.order_by(ProductCharacteristic.synced_at.desc()).limit(500).all()


def get_stocks(db: Session, cabinet_id: str | None = None, nm_id: int | None = None):
    q = db.query(Stock)
    if cabinet_id:
        q = q.filter(Stock.cabinet_id == cabinet_id)
    if nm_id:
        q = q.filter(Stock.nm_id == nm_id)
    return q.order_by(Stock.synced_at.desc()).limit(10000).all()


def get_orders(db: Session, cabinet_id: str | None = None, days_back: int = 40, limit: int = 1000):
    """Получение заказов из БД за последние N дней"""
    q = db.query(Order)
    
    if cabinet_id:
        q = q.filter(Order.cabinet_id == cabinet_id)
    
    # Фильтр по дате заказа (последние N дней)
    threshold_date = datetime.now() - timedelta(days=days_back)
    q = q.filter(Order.date >= threshold_date)
    
    return q.order_by(Order.date.desc()).limit(limit).all()


def get_sync_logs(db: Session, limit: int = 50):
    return db.query(SyncLog).order_by(SyncLog.created_at.desc()).limit(limit).all()


def upsert_price(db: Session, cabinet_id: str, item: dict, size: dict):
    stmt = pg_insert(Price).values(
        cabinet_id=cabinet_id,
        nm_id=item["nmID"],
        chrt_id=size["sizeID"],
        price=size["price"],
        discounted_price=size["discountedPrice"],
        club_discounted_price=size["clubDiscountedPrice"],
        currency=size.get("currencyIsoCode4217", "RUB"),
        discount=size["discount"],
        club_discount=size["clubDiscount"],
        tech_size_name=size["techSizeName"],
    ).on_conflict_do_update(
        constraint="uq_price",
        set_={
            "price": size["price"],
            "discounted_price": size["discountedPrice"],
            "club_discounted_price": size["clubDiscountedPrice"],
            "discount": size["discount"],
            "club_discount": size["clubDiscount"],
            "synced_at": datetime.utcnow(),
        },
    )
    db.execute(stmt)


def get_prices(db: Session, cabinet_id: str = None, nm_id: int = None):
    q = db.query(Price)

    if cabinet_id:
        q = q.filter(Price.cabinet_id == cabinet_id)

    if nm_id:
        q = q.filter(Price.nm_id == nm_id)

    return q.order_by(Price.synced_at.desc()).limit(10000).all()