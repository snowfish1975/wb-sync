import os
import asyncio
import hashlib
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import json

from app.database import engine, Base, get_db
from app.schemas import ProductCharacteristicOut, SyncLogOut, TokenRequest, StockOut, OrderOut, PriceOut, SalesReportRowOut, SaleOut
from app.crud import get_characteristics, get_sync_logs, get_stocks, get_orders, load_tokens_mapping, get_prices, get_sales_report, get_sales
from app.scheduler import run_sync_all, run_sales_report_sync

from fastapi.responses import JSONResponse

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def token_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:32]


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(1, 11):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Подключение к БД успешно, таблицы созданы")
            break
        except Exception as e:
            logger.warning(f"БД не готова, попытка {attempt}/10: {e}")
            if attempt == 10:
                raise RuntimeError("Не удалось подключиться к БД после 10 попыток")
            await asyncio.sleep(5)

    sync_hour = int(os.getenv("SYNC_HOUR", "3"))
    scheduler.add_job(run_sync_all, "cron", hour=sync_hour, minute=0, id="wb_sync")

    # Отчёт реализации — в 10:30 МСК = 07:30 UTC
    scheduler.add_job(
        run_sales_report_sync,
        "cron",
        hour=7,
        minute=30,
        id="wb_sales_report_sync",
        timezone="UTC",
    )

    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="WB Sync API", description="Синхронизация данных Wildberries", lifespan=lifespan)


@app.get("/")
def root():
    return {"status": "ok", "message": "WB Sync работает"}


@app.post("/api/products", response_model=list[ProductCharacteristicOut])
def list_products(body: TokenRequest, nm_id: int | None = Query(None), db: Session = Depends(get_db)):
    cid = token_id(body.token)
    mapping = load_tokens_mapping()
    data = get_characteristics(db, cabinet_id=cid, nm_id=nm_id)
    return [
        {
            **{k: v for k, v in item.__dict__.items() if not k.startswith("_")},
            "seller_name": mapping.get(item.cabinet_id, item.cabinet_id[:8]),
        }
        for item in data
    ]


@app.post("/api/stocks", response_model=list[StockOut])
def list_stocks(body: TokenRequest, nm_id: int | None = Query(None), db: Session = Depends(get_db)):
    cid = token_id(body.token)
    mapping = load_tokens_mapping()
    data = get_stocks(db, cabinet_id=cid, nm_id=nm_id)
    return [
        {
            **{k: v for k, v in item.__dict__.items() if not k.startswith("_")},
            "seller_name": mapping.get(item.cabinet_id, item.cabinet_id[:8]),
        }
        for item in data
    ]


@app.post("/api/orders", response_model=list[OrderOut])
def list_orders(
    body: TokenRequest,
    fields: str | None = Query(None, description="Поля через запятую: nm_id,date,total_price"),
    days_back: int = Query(40, description="За сколько дней вернуть заказы (макс 90)", ge=1, le=90),
    limit: int = Query(1000, description="Максимальное количество записей", le=500000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    cid = token_id(body.token)
    mapping = load_tokens_mapping()
    data = get_orders(db, cabinet_id=cid, days_back=days_back, limit=limit, offset=offset)

    requested_fields = [f.strip() for f in fields.split(",")] if fields else None

    result = []
    for item in data:
        row = {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
        row["seller_name"] = mapping.get(item.cabinet_id, item.cabinet_id[:8])
        # datetime не сериализуется в JSON напрямую — конвертируем в строку
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
        if requested_fields:
            row = {k: v for k, v in row.items() if k in requested_fields}
        result.append(row)

    return JSONResponse(content=result)

@app.post("/api/sales", response_model=list[SaleOut])
def list_sales(
    body: TokenRequest,
    fields: str | None = Query(None, description="Поля через запятую: nm_id,date,total_price"),
    days_back: int = Query(40, description="За сколько дней (макс 90)", ge=1, le=90),
    limit: int = Query(1000, description="Максимальное количество записей", le=500000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Продажи и возвраты за последние N дней."""
    cid = token_id(body.token)
    mapping = load_tokens_mapping()
    data = get_sales(db, cabinet_id=cid, nm_id=nm_id, days_back=days_back, limit=limit, offset=offset)

    requested_fields = [f.strip() for f in fields.split(",")] if fields else None

    result = []
    for item in data:
        row = {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
        row["seller_name"] = mapping.get(item.cabinet_id, item.cabinet_id[:8])
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
        if requested_fields:
            row = {k: v for k, v in row.items() if k in requested_fields}
        result.append(row)

    return JSONResponse(content=result)

@app.post("/api/prices", response_model=list[PriceOut])
def list_prices(
    body: TokenRequest,
    nm_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    cid = token_id(body.token)
    mapping = load_tokens_mapping()
    data = get_prices(db, cabinet_id=cid, nm_id=nm_id)
    return [
        {
            **{k: v for k, v in item.__dict__.items() if not k.startswith("_")},
            "seller_name": mapping.get(item.cabinet_id, item.cabinet_id[:8]),
        }
        for item in data
    ]


@app.post("/api/sales-report", response_model=list[SalesReportRowOut])
def list_sales_report(
    body: TokenRequest,
    nm_id: int | None = Query(None, description="Фильтр по артикулу WB"),
    date_from: str | None = Query(None, description="Дата начала YYYY-MM-DD"),
    date_to: str | None = Query(None, description="Дата конца YYYY-MM-DD"),
    limit: int = Query(1000, description="Максимальное количество строк", le=500000),
    db: Session = Depends(get_db),
):
    """Отчёт о продажах по реализации."""
    from datetime import datetime
    cid = token_id(body.token)
    mapping = load_tokens_mapping()
    dt_from = datetime.strptime(date_from, "%Y-%m-%d") if date_from else None
    dt_to = datetime.strptime(date_to, "%Y-%m-%d") if date_to else None
    data = get_sales_report(db, cabinet_id=cid, nm_id=nm_id, date_from=dt_from, date_to=dt_to, limit=limit)
    return [
        {
            **{k: v for k, v in item.__dict__.items() if not k.startswith("_")},
            "seller_name": mapping.get(item.cabinet_id, item.cabinet_id[:8]),
        }
        for item in data
    ]


@app.get("/api/logs", response_model=list[SyncLogOut])
def list_logs(db: Session = Depends(get_db)):
    mapping = load_tokens_mapping()
    data = get_sync_logs(db)
    return [
        {
            **{k: v for k, v in item.__dict__.items() if not k.startswith("_")},
            "seller_name": mapping.get(item.cabinet_id, item.cabinet_id[:8]),
        }
        for item in data
    ]


@app.post("/api/sync/trigger")
def trigger_sync():
    import threading
    threading.Thread(target=run_sync_all, daemon=True).start()
    return {"status": "started"}


@app.post("/api/sync/trigger-sales-report")
def trigger_sales_report_sync():
    """Принудительный запуск синхронизации отчёта реализации за вчера."""
    import threading
    threading.Thread(target=run_sales_report_sync, daemon=True).start()
    return {"status": "started"}


@app.get("/api/health")
def health():
    return {"status": "ok"}
