import os
import hashlib
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from app.database import engine, Base, get_db
from app.schemas import ProductCharacteristicOut, SyncLogOut, TokenRequest
from app.crud import get_characteristics, get_sync_logs
from app.scheduler import run_sync_all

load_dotenv()
logging.basicConfig(level=logging.INFO)

Base.metadata.create_all(bind=engine)

scheduler = BackgroundScheduler()

def token_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:32]

@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_hour = int(os.getenv("SYNC_HOUR", "3"))
    scheduler.add_job(run_sync_all, "cron", hour=sync_hour, minute=0, id="wb_sync")
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(
    title="WB Sync API",
    description="Синхронизация данных Wildberries",
    lifespan=lifespan,
)

@app.get("/")
def root():
    return {"status": "ok", "message": "WB Sync работает"}

@app.post("/api/products", response_model=list[ProductCharacteristicOut])
def list_products(
    body: TokenRequest,
    nm_id: int | None = Query(None, description="Артикул WB"),
    db: Session = Depends(get_db),
):
    """Получить характеристики товаров. Токен передаётся в теле запроса."""
    cid = token_id(body.token)
    return get_characteristics(db, cabinet_id=cid, nm_id=nm_id)

@app.get("/api/logs", response_model=list[SyncLogOut])
def list_logs(db: Session = Depends(get_db)):
    return get_sync_logs(db)

@app.post("/api/sync/trigger")
def trigger_sync():
    import threading
    threading.Thread(target=run_sync_all, daemon=True).start()
    return {"status": "started"}

@app.get("/api/health")
def health():
    return {"status": "ok"}