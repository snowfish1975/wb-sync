from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import ProductCharacteristic, SyncLog, Stock, Order, Price, SalesReport
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
        warehouse_name=item.get("warehouseName", ""),
        region_name=item.get("regionName", ""),
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
        nm_id=item.get("nmID"),
        chrt_id=size.get("sizeID"),
        price=size.get("price", 0),
        discounted_price=size.get("discountedPrice", 0),
        club_discounted_price=size.get("clubDiscountedPrice", 0),
        currency=size.get("currencyIsoCode4217", "RUB"),
        discount=size.get("discount", 0),                # ✅ фикс
        club_discount=size.get("clubDiscount", 0),       # ✅ фикс
        tech_size_name=size.get("techSizeName", ""),
        synced_at=datetime.utcnow(),
    ).on_conflict_do_update(
        constraint="uq_price",
        set_={
            "price": size.get("price", 0),
            "discounted_price": size.get("discountedPrice", 0),
            "club_discounted_price": size.get("clubDiscountedPrice", 0),
            "discount": size.get("discount", 0),           # ✅ фикс
            "club_discount": size.get("clubDiscount", 0),  # ✅ фикс
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


def upsert_sales_report_row(db: Session, cabinet_id: str, row: dict):
    def parse_dt(val: str | None) -> datetime | None:
        if not val:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(val[:19], fmt[:len(val[:19])])
            except Exception:
                continue
        return None

    stmt = pg_insert(SalesReport).values(
        cabinet_id=cabinet_id,
        rrd_id=row.get("rrd_id"),
        realizationreport_id=row.get("realizationreport_id"),
        gi_id=row.get("gi_id"),
        nm_id=row.get("nm_id"),
        shk_id=row.get("shk_id"),
        assembly_id=row.get("assembly_id"),
        srid=row.get("srid"),
        order_uid=row.get("order_uid"),
        date_from=parse_dt(row.get("date_from")),
        date_to=parse_dt(row.get("date_to")),
        create_dt=parse_dt(row.get("create_dt")),
        rr_dt=parse_dt(row.get("rr_dt")),
        order_dt=parse_dt(row.get("order_dt")),
        sale_dt=parse_dt(row.get("sale_dt")),
        fix_tariff_date_from=parse_dt(row.get("fix_tariff_date_from")),
        fix_tariff_date_to=parse_dt(row.get("fix_tariff_date_to")),
        subject_name=row.get("subject_name"),
        brand_name=row.get("brand_name"),
        sa_name=row.get("sa_name"),
        ts_name=row.get("ts_name"),
        barcode=row.get("barcode"),
        doc_type_name=row.get("doc_type_name"),
        supplier_oper_name=row.get("supplier_oper_name"),
        office_name=row.get("office_name"),
        quantity=row.get("quantity"),
        currency_name=row.get("currency_name"),
        retail_price=row.get("retail_price"),
        retail_amount=row.get("retail_amount"),
        retail_price_withdisc_rub=row.get("retail_price_withdisc_rub"),
        sale_percent=row.get("sale_percent"),
        commission_percent=row.get("commission_percent"),
        product_discount_for_report=row.get("product_discount_for_report"),
        supplier_promo=row.get("supplier_promo"),
        ppvz_spp_prc=row.get("ppvz_spp_prc"),
        ppvz_kvw_prc_base=row.get("ppvz_kvw_prc_base"),
        ppvz_kvw_prc=row.get("ppvz_kvw_prc"),
        ppvz_sales_commission=row.get("ppvz_sales_commission"),
        ppvz_for_pay=row.get("ppvz_for_pay"),
        ppvz_reward=row.get("ppvz_reward"),
        ppvz_vw=row.get("ppvz_vw"),
        ppvz_vw_nds=row.get("ppvz_vw_nds"),
        sup_rating_prc_up=row.get("sup_rating_prc_up"),
        is_kgvp_v2=row.get("is_kgvp_v2"),
        acquiring_fee=row.get("acquiring_fee"),
        acquiring_percent=row.get("acquiring_percent"),
        acquiring_bank=row.get("acquiring_bank"),
        payment_processing=row.get("payment_processing"),
        delivery_amount=row.get("delivery_amount"),
        return_amount=row.get("return_amount"),
        delivery_rub=row.get("delivery_rub"),
        gi_box_type_name=row.get("gi_box_type_name"),
        rebill_logistic_cost=row.get("rebill_logistic_cost"),
        rebill_logistic_org=row.get("rebill_logistic_org"),
        dlv_prc=row.get("dlv_prc"),
        penalty=row.get("penalty"),
        additional_payment=row.get("additional_payment"),
        storage_fee=row.get("storage_fee"),
        deduction=row.get("deduction"),
        acceptance=row.get("acceptance"),
        site_country=row.get("site_country"),
        ppvz_office_name=row.get("ppvz_office_name"),
        ppvz_office_id=row.get("ppvz_office_id"),
        ppvz_supplier_id=row.get("ppvz_supplier_id"),
        ppvz_supplier_name=row.get("ppvz_supplier_name"),
        ppvz_inn=row.get("ppvz_inn"),
        sticker_id=row.get("sticker_id"),
        declaration_number=row.get("declaration_number"),
        bonus_type_name=row.get("bonus_type_name"),
        kiz=row.get("kiz"),
        srv_dbs=row.get("srv_dbs"),
        is_legal_entity=row.get("is_legal_entity"),
        report_type=row.get("report_type"),
        synced_at=datetime.utcnow(),
    ).on_conflict_do_update(
        constraint="uq_sales_report_row",
        set_={
            "ppvz_for_pay": row.get("ppvz_for_pay"),
            "penalty": row.get("penalty"),
            "additional_payment": row.get("additional_payment"),
            "storage_fee": row.get("storage_fee"),
            "deduction": row.get("deduction"),
            "synced_at": datetime.utcnow(),
        },
    )
    db.execute(stmt)


def get_sales_report(
    db: Session,
    cabinet_id: str | None = None,
    nm_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 1000,
):
    q = db.query(SalesReport)
    if cabinet_id:
        q = q.filter(SalesReport.cabinet_id == cabinet_id)
    if nm_id:
        q = q.filter(SalesReport.nm_id == nm_id)
    if date_from:
        q = q.filter(SalesReport.rr_dt >= date_from)
    if date_to:
        q = q.filter(SalesReport.rr_dt <= date_to)
    return q.order_by(SalesReport.rr_dt.desc()).limit(limit).all()
