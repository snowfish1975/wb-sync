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
from app.schemas import ProductCharacteristicOut, SyncLogOut, TokenRequest, StockOut, OrderOut, PriceOut
from app.crud import get_characteristics, get_sync_logs, get_stocks, get_orders, load_tokens_mapping, get_prices
from app.scheduler import run_sync_all

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

# -------------------------
# Утилиты
# -------------------------
def token_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:32]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ждём базу — до 10 попыток с интервалом 5 секунд
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
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="WB Sync API", description="Синхронизация данных Wildberries", lifespan=lifespan)

# -------------------------
# Эндпоинты
# -------------------------
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
    nm_id: int | None = Query(None, description="Фильтр по артикулу WB"),
    days_back: int = Query(40, description="За сколько дней вернуть заказы (макс 90)", ge=1, le=90),
    limit: int = Query(1000, description="Максимальное количество записей", le=10000),
    db: Session = Depends(get_db)
):
    """
    Получение заказов по токену кабинета.
    Возвращает заказы за последние N дней (по умолчанию 40).
    """
    cid = token_id(body.token)
    mapping = load_tokens_mapping()
    data = get_orders(db, cabinet_id=cid, days_back=days_back, limit=limit)
    
    # Фильтрация по nm_id если указан
    if nm_id:
        data = [item for item in data if item.nm_id == nm_id]
    
    return [
        {
            **{k: v for k, v in item.__dict__.items() if not k.startswith("_")},
            "seller_name": mapping.get(item.cabinet_id, item.cabinet_id[:8]),
        }
        for item in data
    ]


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


@app.get("/api/health")
def health():
    return {"status": "ok"}
